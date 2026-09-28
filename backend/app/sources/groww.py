import json
import math
import re
from datetime import date, datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from app.normalization.identity import option_of, plan_of, scheme_key
from app.schemas import (
    Fund,
    FundFacts,
    FundManager,
    Holding,
    Metric,
    PortfolioSummary,
    ReturnObservation,
    SectorAllocation,
    SourceData,
    SourceMatch,
)
from app.sources.base import MutualFundSource, SourceError

BASE = "https://groww.in/mutual-funds/"
SEARCH = "https://groww.in/v1/api/search/v3/query/global/st_p_query"


def number(value) -> float | None:
    try:
        result = float(str(value).strip().replace(",", "").replace("%", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    clean = value[:10] if "T" in value else value
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            pass
    return None


def slug_for(fund: Fund) -> str:
    text = f"{fund.scheme} {fund.plan} {fund.option}"
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def parse_search(text: str) -> list[dict]:
    try:
        content = json.loads(text)["data"]["content"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SourceError("Groww search response shape changed.", "Parsing Error") from exc
    if not isinstance(content, list):
        raise SourceError("Groww search response is not a list.", "Parsing Error")
    return [item for item in content if isinstance(item, dict) and item.get("entity_type") == "Scheme"
            and isinstance(item.get("search_id"), str) and isinstance(item.get("title"), str)]


def _metric(key: str, label: str, value, unit: str, url: str, fetched: datetime, *, as_of=None,
            benchmark=None, period=None, definition=None) -> Metric:
    numeric = number(value)
    status = "available" if numeric is not None else "unavailable"
    note = None
    if numeric is not None and ((key == "expense_ratio" and not 0 <= numeric <= 5)
                                or (key == "aum" and numeric <= 0)
                                or (key == "standard_deviation" and numeric < 0)):
        status, note = "suspicious", "Outside the parser's validation range. Verify the original source."
    return Metric(key=key, label=label, value=numeric, unit=unit, source="Groww", source_url=url,
                  fetched_at=fetched, as_of=as_of, benchmark=benchmark, period=period, status=status,
                  definition=definition or f"{label} reported by Groww; retain the provider's methodology.", note=note)


def parse_page(html: str, fund: Fund, url: str, fetched: datetime) -> SourceData:
    soup = BeautifulSoup(html, "lxml")
    payload = soup.select_one("#__NEXT_DATA__")
    if not payload or not payload.string:
        raise SourceError("Groww page no longer exposes its server-rendered data payload.", "Parsing Error")
    try:
        data = json.loads(payload.string)["props"]["pageProps"]["mfServerSideData"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SourceError("Groww fund payload shape changed.", "Parsing Error") from exc

    scheme_code = str(data.get("scheme_code") or "")
    isin = str(data.get("isin") or "")
    identity_matches = scheme_code == fund.amfi_code or bool(isin and isin in fund.isins)
    if not identity_matches or data.get("plan_type") != fund.plan or data.get("scheme_type") != fund.option:
        raise SourceError("Groww page did not confirm the selected AMFI scheme, plan and option.", "Parsing Error")
    if scheme_key(data.get("scheme_name", "")) != scheme_key(fund.scheme):
        # AMFI code/ISIN remain authoritative; keep the name discrepancy visible.
        name_warning = "Groww's display name differs after normalization; AMFI code or ISIN confirmed the identity."
    else:
        name_warning = None

    history = data.get("historic_fund_expense") or []
    expense_as_of = parse_date(history[0].get("as_on_date")) if history and isinstance(history[0], dict) else None
    stats = (data.get("return_stats") or [{}])[0]
    benchmark = data.get("benchmark_name") or data.get("benchmark")
    metrics = [
        _metric("aum", "Assets under management", data.get("aum"), "Cr", url, fetched),
        _metric("expense_ratio", "Expense ratio (TER)", data.get("expense_ratio"), "%", url, fetched,
                as_of=expense_as_of, definition="Groww's displayed expense ratio for the selected direct plan."),
        _metric("beta", "Beta", stats.get("beta"), "", url, fetched, benchmark=benchmark),
        _metric("standard_deviation", "Standard deviation", stats.get("standard_deviation"), "%", url, fetched,
                benchmark=benchmark),
        _metric("sharpe", "Sharpe ratio", stats.get("sharpe_ratio"), "", url, fetched, benchmark=benchmark),
        _metric("alpha", "Alpha", stats.get("alpha"), "%", url, fetched, benchmark=benchmark),
    ]
    risk = stats.get("risk") or data.get("nfo_risk")
    returns = []
    for period, key, category_key in (("1Y", "return1y", "cat_return1y"), ("3Y", "return3y", "cat_return3y"),
                                      ("5Y", "return5y", "cat_return5y"), ("10Y", "return10y", "cat_return10y")):
        value = number(stats.get(key))
        category_value = number(stats.get(category_key))
        returns.append(ReturnObservation(period=period, value=value, category_value=category_value,
                                         source="Groww", source_url=url, fetched_at=fetched,
                                         status="available" if value is not None else "unavailable"))

    holdings = []
    warnings = [name_warning] if name_warning else []
    for item in data.get("holdings") or []:
        weight = number(item.get("corpus_per"))
        if weight is None or not 0 <= weight <= 100 or not item.get("company_name"):
            warnings.append("Groww returned a holding with an invalid name or portfolio weight; it was omitted.")
            continue
        holdings.append(Holding(name=item["company_name"], sector=item.get("sector_name"),
                                instrument=item.get("instrument_name"), weight=weight,
                                as_of=parse_date(item.get("portfolio_date")), source="Groww", source_url=url))
    holdings.sort(key=lambda item: item.weight, reverse=True)
    total = sum(item.weight for item in holdings)
    if holdings and not 95 <= total <= 105:
        warnings.append(f"Groww holding weights total {total:.2f}%; treat concentration figures as incomplete.")

    sector_totals: dict[str, float] = {}
    for holding in holdings:
        sector = holding.sector or "Unspecified"
        sector_totals[sector] = sector_totals.get(sector, 0) + holding.weight
    as_of = next((h.as_of for h in holdings if h.as_of), None)
    sectors = [SectorAllocation(sector=name, weight=round(weight, 2), as_of=as_of, source="Groww", source_url=url)
               for name, weight in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)]

    managers = []
    for item in data.get("fund_manager_details") or []:
        started = parse_date(item.get("date_from"))
        tenure = round((date.today() - started).days / 365.2425, 1) if started and started <= date.today() else None
        managers.append(FundManager(name=item.get("person_name") or "Not supplied", tenure_start=started,
                                    tenure_years=tenure, experience=item.get("experience"),
                                    other_funds=[f.get("scheme_name") for f in item.get("funds_managed") or [] if f.get("scheme_name")],
                                    source="Groww", source_url=url))
    inception = parse_date(data.get("launch_date")) or parse_date(data.get("allotment_date"))
    age = round((date.today() - inception).days / 365.2425, 1) if inception and inception <= date.today() else None
    facts = FundFacts(risk=risk, inception_date=inception, age_years=age, benchmark=benchmark,
                      exit_load=data.get("exit_load"), source="Groww", source_url=url)
    portfolio = None
    if holdings:
        weights = [h.weight for h in holdings]
        portfolio = PortfolioSummary(holdings_count=len(holdings), largest_holding=weights[0],
                                     top_5=round(sum(weights[:5]), 2), top_10=round(sum(weights[:10]), 2),
                                     top_20=round(sum(weights[:20]), 2),
                                     largest_sector=sectors[0].sector if sectors else None,
                                     largest_sector_weight=sectors[0].weight if sectors else None,
                                     top_3_sectors=round(sum(s.weight for s in sectors[:3]), 2),
                                     top_5_sectors=round(sum(s.weight for s in sectors[:5]), 2),
                                     as_of=as_of, source="Groww", source_url=url)
    return SourceData(
        match=SourceMatch(source="Groww", status="Matched", name=data.get("scheme_name"), url=url,
                          method="AMFI scheme code or ISIN + explicit plan + option, confirmed in Groww's public page payload"),
        metrics=metrics, returns=returns, holdings=holdings, sectors=sectors, managers=managers,
        portfolio=portfolio, facts=facts, warnings=warnings,
    )


class GrowwSource(MutualFundSource):
    id, name = "groww", "Groww"
    capabilities = ["scheme_matching", "aum", "expense_ratio", "risk", "returns", "portfolio",
                    "sector_allocation", "fund_manager", "fund_age", "exit_load"]

    async def search_funds(self, query: str) -> list[dict]:
        text, _ = await self.request("GET", SEARCH, params={"page": 0, "query": query, "size": 20, "web": "true"})
        try:
            return parse_search(text)
        except SourceError as exc:
            raise self.parsing_error(str(exc)) from exc

    async def get_fund_details(self, fund: Fund, rolling_years: int = 3) -> SourceData:
        if fund.plan == "Unknown" or fund.option == "Unknown":
            return SourceData(match=SourceMatch(source=self.name, status="Unmatched",
                              note="Groww matching requires an explicit plan and option."))
        # Groww's public search returns no result for some renamed schemes when the generic
        # trailing word "Fund" is present (for example HDFC Flexi Cap Fund).
        query = re.sub(r"(?i)\s+fund$", "", fund.scheme).strip()
        candidates = await self.search_funds(query)
        matches = [item for item in candidates if scheme_key(item["title"]) == scheme_key(fund.scheme)
                   and plan_of(item["search_id"]) == fund.plan and option_of(item["search_id"]) == fund.option]
        slug = matches[0]["search_id"] if len(matches) == 1 else slug_for(fund)
        url = BASE + quote(slug, safe="-")
        try:
            html, fetched = await self.request("GET", url)
            return parse_page(html, fund, url, fetched)
        except SourceError as exc:
            if exc.status == "Parsing Error":
                raise self.parsing_error(str(exc)) from exc
            return SourceData(match=SourceMatch(source=self.name, status="Unavailable", url=url, note=str(exc)),
                              warnings=[str(exc)])
