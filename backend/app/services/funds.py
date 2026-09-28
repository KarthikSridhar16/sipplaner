import asyncio
import os
from pathlib import Path

import yaml

from app.analysis.rules import evaluate
from app.analysis.screener import category_matches, evaluate_screen
from app.analysis.portfolio import analyse_sip_portfolio
from app.analysis.statistical import evaluate_statistical_sip
from app.schemas import (Analysis, Comparison, IPOCatalogueResponse, IPOResearchResponse, Metric, Rules, ScreenFilters, ScreenResponse,
                         ScreenResult, SearchResponse, SIPPortfolioRequest, SourceData, SourceMatch,
                         StatisticalSIPRequest)
from app.sources.advisorkhoj import AdvisorKhojSource, BASE, LABELS
from app.sources.amfi import AMFISource
from app.sources.base import SourceError
from app.sources.coin import CoinSource
from app.sources.groww import GrowwSource
from app.sources.nifty import NiftyIndicesSource, benchmark_for
from app.sources.mfapi import MFAPIHistorySource
from app.sources.nse_ipo import NSEIPOSource

CONFIG = Path(__file__).resolve().parents[2] / "config"


class FundService:
    def __init__(self):
        config = yaml.safe_load((CONFIG / "sources.yaml").read_text())["sources"]
        self.defaults = yaml.safe_load((CONFIG / "default_rules.yaml").read_text())
        self.priority = yaml.safe_load((CONFIG / "source_priority.yaml").read_text())
        self.sources = {}
        for cls in (AMFISource, AdvisorKhojSource, GrowwSource, CoinSource):
            settings = dict(config[cls.id])
            settings["enabled"] = os.getenv(f"{cls.id.upper()}_ENABLED", str(settings["enabled"])).lower() == "true"
            self.sources[cls.id] = cls(**settings, timeout=float(os.getenv("HTTP_TIMEOUT", "20")))
        market_settings = dict(config["nifty"])
        market_settings["enabled"] = os.getenv("NIFTY_ENABLED", str(market_settings["enabled"])).lower() == "true"
        self.market_source = NiftyIndicesSource(**market_settings, timeout=float(os.getenv("HTTP_TIMEOUT", "20")))
        history_settings = dict(config["mfapi"])
        history_settings["enabled"] = os.getenv("MFAPI_ENABLED", str(history_settings["enabled"])).lower() == "true"
        self.history_source = MFAPIHistorySource(**history_settings, timeout=float(os.getenv("HTTP_TIMEOUT", "20")))
        ipo_settings = dict(config["nse_ipo"])
        ipo_settings["enabled"] = os.getenv("NSE_IPO_ENABLED", str(ipo_settings["enabled"])).lower() == "true"
        self.ipo_source = NSEIPOSource(**ipo_settings, timeout=float(os.getenv("HTTP_TIMEOUT", "20")))
        self.catalog_source = self.sources["amfi"]
        self.slots = asyncio.Semaphore(8)

    async def close(self):
        await asyncio.gather(*(s.close() for s in self.sources.values()), self.market_source.close(),
                             self.history_source.close(), self.ipo_source.close())

    async def search(self, query: str, plan: str = "Direct", option: str = "Growth", category: str = "", limit: int = 30):
        funds = await self.catalog_source.search_funds(query)
        funds = [f for f in funds if (not plan or f.plan == plan) and (not option or f.option == option)
                 and category.lower() in f.category.lower()]
        funds.sort(key=lambda f: (f.nav.status == "stale", len(f.scheme), f.name))
        return SearchResponse(funds=funds[:limit], total=len(funds), query=query)

    async def fund(self, canonical_id: str):
        return next((f for f in await self.catalog_source.catalog() if f.canonical_id == canonical_id), None)

    def effective_rules(self, fund, overrides):
        if overrides is not None:
            return overrides
        values = {k: v for k, v in self.defaults.items() if k != "category_rules"}
        category = fund.category.lower()
        key = "index" if "index" in fund.scheme.lower() else "small_cap" if "small cap" in category else ""
        values.update(self.defaults.get("category_rules", {}).get(key, {}))
        return Rules(**values)

    async def analyse(self, canonical_id: str, overrides: Rules | None = None, rolling_years: int = 3):
        async with self.slots:
            fund = await self.fund(canonical_id)
            if not fund:
                return None
            async def fetch(source):
                try:
                    return await source.get_fund_details(fund, rolling_years)
                except SourceError as exc:
                    return SourceData(match=SourceMatch(source=source.name, status="Unavailable", note=str(exc)), warnings=[str(exc)])
            snapshots = await asyncio.gather(*(fetch(s) for s in self.sources.values()))
            metrics = [m for s in snapshots for m in s.metrics]
            observations = {}
            for metric in metrics:
                observations.setdefault(metric.key, []).append(metric)
            # Resolve by configured metric priority; retain all source matches. Future conflicts must retain observations.
            def order(m):
                group = m.key if m.key in self.priority else "risk_metrics"
                priority = self.priority.get(group, [])
                return priority.index(m.source.lower()) if m.source.lower() in priority else 100
            selected = {}
            for m in sorted(metrics, key=order):
                selected.setdefault(m.key, m)
            for key, (label, unit) in LABELS.items():
                if key not in selected:
                    selected[key] = Metric(key=key, label=label, unit=unit, source="AdvisorKhoj", source_url=BASE,
                                           definition=f"Source-reported {label}.", status="unavailable", note="No verified value was returned.")
            metrics = list(selected.values())
            rules = self.effective_rules(fund, overrides)
            warnings = [w for s in snapshots for w in s.warnings]
            for key, values in observations.items():
                available = [m for m in values if m.value is not None and m.status == "available"]
                if len(available) > 1:
                    low, high = min(m.value for m in available), max(m.value for m in available)
                    tolerance = 0.01 if key == "expense_ratio" else max(0.01, abs(low) * 0.02)
                    if high - low > tolerance:
                        detail = ", ".join(f"{m.source} {m.value:g}{m.unit}" for m in available)
                        warnings.append(f"Sources differ for {available[0].label}: {detail}. The displayed value follows source priority.")
            if fund.nav.status == "stale":
                warnings.append("AMFI's latest NAV for this scheme is more than seven days old.")
            warnings.append("Risk metrics without a stated period, date or methodology should not be compared across providers.")
            rich = next((s for s in snapshots if s.holdings or s.facts or s.returns), SourceData(match=SourceMatch(source="None", status="Unavailable")))
            return Analysis(fund=fund, metrics=metrics, metric_observations=observations,
                            sources=[s.match for s in snapshots],
                            rolling=next((s.rolling for s in snapshots if s.rolling), None),
                            returns=rich.returns, holdings=rich.holdings, sectors=rich.sectors,
                            managers=rich.managers, portfolio=rich.portfolio, facts=rich.facts,
                            rules=evaluate(metrics, rules), applied_rules=rules, warnings=warnings)

    async def compare(self, canonical_ids: list[str], overrides: Rules | None = None, rolling_years: int = 3):
        results = await asyncio.gather(*(self.analyse(item, overrides, rolling_years) for item in canonical_ids))
        if any(item is None for item in results):
            return None
        analyses = [item for item in results if item is not None]
        warnings = []
        categories = {item.fund.category for item in analyses}
        if len(categories) > 1:
            warnings.append("These funds span multiple AMFI categories. Return and risk values may not be like-for-like.")
        plans = {item.fund.plan for item in analyses}
        options = {item.fund.option for item in analyses}
        if len(plans) > 1 or len(options) > 1:
            warnings.append("The selected schemes do not all use the same plan and option. Costs and returns can differ by variant.")
        warnings.append("A missing value means no verified observation was returned; it is not a zero.")
        return Comparison(analyses=analyses, warnings=warnings)

    async def screen(self, filters: ScreenFilters):
        candidates = await self.catalog_source.search_funds(filters.query.strip())
        category = filters.category.strip().lower()
        amc = filters.amc.strip().lower()
        candidates = [fund for fund in candidates
                      if (not filters.plan or fund.plan == filters.plan)
                      and (not filters.option or fund.option == filters.option)
                      and category_matches(fund.category, category)
                      and (not amc or amc in fund.amc.lower())]
        candidates.sort(key=lambda fund: (fund.scheme.lower(), fund.amfi_code))
        total = len(candidates)
        batch = candidates[filters.offset:filters.offset + filters.candidate_limit]
        analyses = await asyncio.gather(*(self.analyse(fund.canonical_id, None, filters.rolling_years) for fund in batch))
        results = []
        for analysis in analyses:
            if analysis is None:
                continue
            criteria, matched, complete = evaluate_screen(analysis, filters)
            results.append(ScreenResult(fund=analysis.fund, metrics=analysis.metrics, rolling=analysis.rolling,
                                        facts=analysis.facts, managers=analysis.managers, portfolio=analysis.portfolio,
                                        sources=analysis.sources, criteria=criteria, matched=matched,
                                        evidence_complete=complete, warnings=analysis.warnings))
        results.sort(key=lambda item: (not item.matched, item.fund.scheme.lower()))
        warnings = []
        if total > len(batch):
            warnings.append(f"This live request evaluated {len(batch)} of {total} catalogue candidates. Use the next batch to continue.")
        if filters.unknown_policy == "include":
            warnings.append("Funds with unavailable criteria can appear as provisional matches; inspect their evidence before using the result.")
        else:
            warnings.append("Funds missing any active criterion are excluded from matches.")
        return ScreenResponse(total_candidates=total, offset=filters.offset, analysed=len(results),
                              matched=sum(item.matched for item in results), results=results, warnings=warnings)

    async def analyse_portfolio(self, request: SIPPortfolioRequest):
        analyses = await asyncio.gather(*(self.analyse(entry.canonical_id, None, request.rolling_years)
                                          for entry in request.entries))
        if any(item is None for item in analyses):
            return None
        return analyse_sip_portfolio([item for item in analyses if item is not None], request.entries)

    async def statistical_sip(self, request: StatisticalSIPRequest):
        fund = await self.fund(request.canonical_id)
        if fund is None:
            return None
        benchmark = benchmark_for(fund)
        history_task = self.history_source.history(fund, max_years=10)
        analysis_task = self.analyse(fund.canonical_id, None, min(request.horizon_years, 5))
        regime_task = self.market_source.regime(benchmark) if benchmark else asyncio.sleep(0, result=None)
        (points, _), analysis, regime = await asyncio.gather(history_task, analysis_task, regime_task)
        return evaluate_statistical_sip(fund, points, request.monthly_sip, request.horizon_years,
                                        request.simulations, regime, analysis)

    async def ipo_catalogue(self, query: str = "", board: str = "", status: str = ""):
        issues, fetched = await self.ipo_source.catalogue()
        query = query.strip().lower()
        filtered = [issue for issue in issues
                    if (not query or query in issue.company_name.lower() or query in issue.symbol.lower())
                    and (not board or issue.board.lower() == board.lower())
                    and (not status or issue.status == status)]
        return IPOCatalogueResponse(
            issues=filtered, total=len(filtered),
            open_count=sum(issue.status == "open" for issue in filtered),
            upcoming_count=sum(issue.status == "upcoming" for issue in filtered),
            fetched_at=fetched,
            warnings=[
                "Subscription totals are exchange observations and can change until the issue closes.",
                "An unavailable price band or subscription value is shown as unavailable, never as zero.",
                "Statistical apply/buy labels remain disabled until the historical IPO cohort passes out-of-time calibration.",
            ],
        )

    async def ipo_research(self, canonical_id: str) -> IPOResearchResponse | None:
        issues, _ = await self.ipo_source.catalogue()
        issue = next((item for item in issues if item.canonical_id == canonical_id), None)
        return await self.ipo_source.research(issue) if issue else None
