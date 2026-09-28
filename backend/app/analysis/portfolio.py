import re
from collections import defaultdict
from itertools import combinations

from app.schemas import (Analysis, PortfolioAllocationSlice, PortfolioExposure, PortfolioFundAllocation,
                         PortfolioOverlap, SIPPortfolioAnalysis, SIPPortfolioEntry)


def _round(value: float) -> float:
    return round(value, 2)


def _category_label(category: str) -> str:
    return re.sub(r"^(Equity|Debt|Hybrid|Other) Schemes?\s*-\s*", "", category).strip() or "Unclassified"


def _asset_group(category: str) -> str:
    value = category.lower()
    if value.startswith("equity scheme") or "index fund" in value:
        return "Equity"
    if value.startswith("debt scheme"):
        return "Debt"
    if value.startswith("hybrid scheme"):
        return "Hybrid"
    return "Other / solution-oriented"


def _holding_key(name: str) -> str:
    value = name.lower().replace("&", " and ")
    value = re.sub(r"\b(limited|ltd|ltd\.|corporation|corp|company|co)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _slices(values: dict[str, dict], total: float) -> list[PortfolioAllocationSlice]:
    return sorted((PortfolioAllocationSlice(label=label, monthly_sip=_round(data["amount"]),
                                             allocation_percent=_round(data["amount"] / total * 100),
                                             fund_count=len(data["funds"]))
                   for label, data in values.items()), key=lambda item: (-item.monthly_sip, item.label))


def analyse_sip_portfolio(analyses: list[Analysis], entries: list[SIPPortfolioEntry]) -> SIPPortfolioAnalysis:
    by_id = {analysis.fund.canonical_id: analysis for analysis in analyses}
    total = sum(entry.monthly_sip for entry in entries)
    categories: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "funds": set()})
    assets: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "funds": set()})
    risks: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "funds": set()})
    sector_values: dict[str, dict] = defaultdict(lambda: {"exposure": 0.0, "funds": set()})
    holding_values: dict[str, dict] = defaultdict(lambda: {"exposure": 0.0, "funds": set(), "name": ""})
    funds: list[PortfolioFundAllocation] = []
    holding_maps: dict[str, dict[str, tuple[str, float]]] = {}

    for entry in entries:
        analysis = by_id[entry.canonical_id]
        allocation = entry.monthly_sip / total
        fund_id = analysis.fund.canonical_id
        category = _category_label(analysis.fund.category)
        asset = _asset_group(analysis.fund.category)
        risk = analysis.facts.risk if analysis.facts and analysis.facts.risk else "Unavailable"
        for target, label in ((categories, category), (assets, asset), (risks, risk)):
            target[label]["amount"] += entry.monthly_sip
            target[label]["funds"].add(fund_id)

        for sector in analysis.sectors:
            sector_values[sector.sector]["exposure"] += allocation * sector.weight
            sector_values[sector.sector]["funds"].add(fund_id)

        fund_holdings: dict[str, tuple[str, float]] = {}
        for holding in analysis.holdings:
            key = _holding_key(holding.name)
            if not key:
                continue
            previous = fund_holdings.get(key)
            if previous is None or holding.weight > previous[1]:
                fund_holdings[key] = (holding.name, holding.weight)
        holding_maps[fund_id] = fund_holdings
        for key, (name, weight) in fund_holdings.items():
            holding_values[key]["name"] = holding_values[key]["name"] or name
            holding_values[key]["exposure"] += allocation * weight
            holding_values[key]["funds"].add(fund_id)

        funds.append(PortfolioFundAllocation(
            fund=analysis.fund, monthly_sip=_round(entry.monthly_sip), allocation_percent=_round(allocation * 100),
            risk=None if risk == "Unavailable" else risk, holdings_count=len(fund_holdings),
            holdings_as_of=analysis.portfolio.as_of if analysis.portfolio else None,
        ))

    sectors = sorted((PortfolioExposure(name=name, exposure_percent=_round(data["exposure"]),
                                         fund_count=len(data["funds"]), funds=sorted(data["funds"]))
                      for name, data in sector_values.items()), key=lambda item: (-item.exposure_percent, item.name))
    common = sorted((PortfolioExposure(name=data["name"], exposure_percent=_round(data["exposure"]),
                                        fund_count=len(data["funds"]), funds=sorted(data["funds"]))
                     for data in holding_values.values() if len(data["funds"]) > 1),
                    key=lambda item: (-item.fund_count, -item.exposure_percent, item.name))

    overlaps: list[PortfolioOverlap] = []
    for left, right in combinations(analyses, 2):
        left_map, right_map = holding_maps[left.fund.canonical_id], holding_maps[right.fund.canonical_id]
        if not left_map or not right_map:
            overlaps.append(PortfolioOverlap(
                fund_a_id=left.fund.canonical_id, fund_a_name=left.fund.scheme,
                fund_b_id=right.fund.canonical_id, fund_b_name=right.fund.scheme,
                common_holdings=0, status="unavailable",
                note="One or both funds have no verified disclosed holdings.",
            ))
            continue
        shared = left_map.keys() & right_map.keys()
        overlap = sum(min(left_map[key][1], right_map[key][1]) for key in shared)
        overlaps.append(PortfolioOverlap(
            fund_a_id=left.fund.canonical_id, fund_a_name=left.fund.scheme,
            fund_b_id=right.fund.canonical_id, fund_b_name=right.fund.scheme,
            common_holdings=len(shared), overlap_percent=_round(overlap), status="available",
            note="Sum of the lower disclosed portfolio weight for each common holding.",
        ))
    overlaps.sort(key=lambda item: (item.status != "available", -(item.overlap_percent or 0)))

    covered_amount = sum(entry.monthly_sip for entry in entries if holding_maps[entry.canonical_id])
    coverage = _round(covered_amount / total * 100)
    warnings = [
        "Asset allocation is grouped from the AMFI scheme category; it is not a security-level asset look-through.",
        "Sector and holding exposures use the latest verified disclosed portfolio and are weighted by monthly SIP allocation.",
        "Verified market-cap look-through data is unavailable from the current sources.",
    ]
    if coverage < 100:
        warnings.append(f"Disclosed holdings cover {coverage:g}% of the monthly SIP; overlap and sector results exclude uncovered funds.")
    largest = max(funds, key=lambda item: item.allocation_percent)
    if largest.allocation_percent > 50:
        warnings.append(f"{largest.fund.scheme} receives {largest.allocation_percent:g}% of the monthly SIP, creating fund-level concentration.")
    if sectors and sectors[0].exposure_percent > 30:
        warnings.append(f"{sectors[0].name} is the largest disclosed sector exposure at {sectors[0].exposure_percent:g}% of the portfolio SIP.")
    high_overlap = next((item for item in overlaps if item.overlap_percent is not None and item.overlap_percent >= 50), None)
    if high_overlap:
        warnings.append(f"{high_overlap.fund_a_name} and {high_overlap.fund_b_name} have {high_overlap.overlap_percent:g}% disclosed-holdings overlap.")

    return SIPPortfolioAnalysis(
        total_monthly_sip=_round(total), funds=funds, category_allocation=_slices(categories, total),
        asset_allocation=_slices(assets, total), risk_allocation=_slices(risks, total),
        sector_exposure=sectors, common_holdings=common, pairwise_overlap=overlaps,
        holdings_coverage_percent=coverage, warnings=warnings,
    )
