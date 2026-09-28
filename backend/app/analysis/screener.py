from collections.abc import Callable

from app.schemas import Analysis, ScreenCriterion, ScreenFilters


def category_matches(category: str, requested: str) -> bool:
    query = requested.strip().lower()
    if not query:
        return True
    value = category.strip().lower()
    leaf = value.rsplit(" - ", 1)[-1]
    exact_leaves = {
        "large cap": "large cap fund",
        "mid cap": "mid cap fund",
        "small cap": "small cap fund",
        "flexi cap": "flexi cap fund",
        "multi cap": "multi cap fund",
    }
    if query in exact_leaves:
        return leaf == exact_leaves[query]
    if query == "debt":
        return value.startswith("debt scheme")
    if query == "hybrid":
        return value.startswith("hybrid scheme")
    if query == "index":
        return "index fund" in leaf
    if query == "elss":
        return "elss" in leaf or "tax saver" in leaf
    return query in leaf


def _number_criterion(key: str, label: str, operator: str, threshold: float | None, value: float | None,
                      unit: str, source: str | None, compare: Callable[[float, float], bool]):
    if threshold is None:
        return None
    status = "UNAVAILABLE" if value is None else "PASS" if compare(value, threshold) else "FAIL"
    return ScreenCriterion(key=key, label=label, operator=operator, threshold=threshold, value=value,
                           unit=unit, source=source, status=status)


def evaluate_screen(analysis: Analysis, filters: ScreenFilters) -> tuple[list[ScreenCriterion], bool, bool]:
    metrics = {item.key: item for item in analysis.metrics if item.value is not None and item.status == "available"}
    criteria: list[ScreenCriterion] = []

    definitions = [
        ("beta", "Beta", "<", filters.beta_max, metrics.get("beta"), "", lambda a, b: a < b),
        ("expense_ratio", "Expense ratio", "<", filters.expense_ratio_max, metrics.get("expense_ratio"), "%", lambda a, b: a < b),
        ("upside_capture", "Upside capture", ">", filters.upside_capture_min, metrics.get("upside_capture"), "%", lambda a, b: a > b),
        ("downside_capture", "Downside capture", "<", filters.downside_capture_max, metrics.get("downside_capture"), "%", lambda a, b: a < b),
        ("aum_min", "AUM", "≥", filters.aum_min, metrics.get("aum"), "Cr", lambda a, b: a >= b),
        ("aum_max", "AUM", "≤", filters.aum_max, metrics.get("aum"), "Cr", lambda a, b: a <= b),
    ]
    for key, label, operator, threshold, metric, unit, compare in definitions:
        criterion = _number_criterion(key, label, operator, threshold, metric.value if metric else None,
                                      unit, metric.source if metric else None, compare)
        if criterion:
            criteria.append(criterion)

    tenures = [manager.tenure_years for manager in analysis.managers if manager.tenure_years is not None]
    shortest_tenure = min(tenures) if tenures else None
    tenure_source = analysis.managers[0].source if analysis.managers else None
    criterion = _number_criterion("manager_tenure", "Shortest reported manager tenure", "≥",
                                  filters.manager_tenure_min, shortest_tenure, "years", tenure_source,
                                  lambda a, b: a >= b)
    if criterion:
        criteria.append(criterion)

    criterion = _number_criterion("fund_age", "Fund age", "≥", filters.fund_age_min,
                                  analysis.facts.age_years if analysis.facts else None, "years",
                                  analysis.facts.source if analysis.facts else None, lambda a, b: a >= b)
    if criterion:
        criteria.append(criterion)

    if filters.risk_levels:
        risk = analysis.facts.risk if analysis.facts else None
        status = "UNAVAILABLE" if not risk else "PASS" if risk in filters.risk_levels else "FAIL"
        criteria.append(ScreenCriterion(key="risk", label="Riskometer", operator="in",
                                        threshold=", ".join(filters.risk_levels), value=risk,
                                        source=analysis.facts.source if analysis.facts else None, status=status))

    complete = all(item.status != "UNAVAILABLE" for item in criteria)
    has_failure = any(item.status == "FAIL" for item in criteria)
    matched = not has_failure and (complete or filters.unknown_policy == "include")
    return criteria, matched, complete
