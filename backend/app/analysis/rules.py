from app.schemas import Metric, Rules, RuleResult


def evaluate(metrics: list[Metric], rules: Rules) -> list[RuleResult]:
    by_key = {m.key: m for m in metrics}
    checks = [("beta", rules.beta_max, "≤", lambda a, b: a <= b),
              ("expense_ratio", rules.expense_ratio_max, "<", lambda a, b: a < b),
              ("upside_capture", rules.upside_capture_min, ">", lambda a, b: a > b),
              ("downside_capture", rules.downside_capture_max, "<", lambda a, b: a < b)]
    results = []
    for key, threshold, symbol, compare in checks:
        m = by_key.get(key)
        if not m or m.value is None or m.status == "unavailable":
            status, explanation = "UNAVAILABLE", "No source value; this rule cannot be evaluated."
        elif m.status == "stale":
            status, explanation = "STALE", "Published value is too old for a current rule result."
        elif m.status == "suspicious":
            status, explanation = "WARNING", "Value needs source verification before evaluation."
        else:
            status = "PASS" if compare(m.value, threshold) else "FAIL"
            explanation = f"Your rule: {m.label} {symbol} {threshold:g}{m.unit}. This is a preference check, not a fund recommendation."
        results.append(RuleResult(metric=key, status=status, explanation=explanation))
    return results
