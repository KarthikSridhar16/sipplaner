import hashlib
import math
import random
import statistics
from datetime import timedelta

from app.schemas import (Analysis, FundManagerAnalysis, HistoricalNAVPoint, HistoricalRiskSummary,
                         ManagerTenurePerformance, MarketRegime, SIPForecast, StatisticalSignal,
                         StatisticalSIPResponse, WalkForwardSummary)


def _month_end(points: list[HistoricalNAVPoint]) -> list[HistoricalNAVPoint]:
    months: dict[tuple[int, int], HistoricalNAVPoint] = {}
    for point in sorted(points, key=lambda item: item.date):
        months[(point.date.year, point.date.month)] = point
    return list(months.values())


def _returns(points: list[HistoricalNAVPoint]) -> tuple[list[HistoricalNAVPoint], list[float]]:
    monthly = _month_end(points)
    values = [monthly[index].nav / monthly[index - 1].nav - 1 for index in range(1, len(monthly))]
    return monthly, values


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _corpus(monthly_sip: float, returns: list[float]) -> float:
    balance = 0.0
    for monthly_return in returns:
        balance = (balance + monthly_sip) * (1 + monthly_return)
    return max(balance, 0)


def _constant_rate_corpus(monthly_sip: float, months: int, annual_rate: float) -> float:
    rate = (1 + annual_rate) ** (1 / 12) - 1
    return _corpus(monthly_sip, [rate] * months)


def _annualized_sip_return(monthly_sip: float, terminal: float, months: int) -> float:
    low, high = -0.95, 3.0
    for _ in range(70):
        middle = (low + high) / 2
        if _constant_rate_corpus(monthly_sip, months, middle) < terminal:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def historical_summary(monthly: list[HistoricalNAVPoint], returns: list[float]) -> HistoricalRiskSummary:
    years = max((monthly[-1].date - monthly[0].date).days / 365.2425, 1 / 12)
    annualized = (monthly[-1].nav / monthly[0].nav) ** (1 / years) - 1
    volatility = statistics.stdev(returns) * math.sqrt(12) if len(returns) > 1 else 0
    downside = math.sqrt(sum(min(value, 0) ** 2 for value in returns) / len(returns)) * math.sqrt(12)
    peak, drawdown = monthly[0].nav, 0.0
    for point in monthly:
        peak = max(peak, point.nav)
        drawdown = min(drawdown, point.nav / peak - 1)
    return HistoricalRiskSummary(
        monthly_observations=len(returns), start_date=monthly[0].date, end_date=monthly[-1].date,
        annualized_return_percent=round(annualized * 100, 2), annualized_volatility_percent=round(volatility * 100, 2),
        downside_deviation_percent=round(downside * 100, 2), max_drawdown_percent=round(drawdown * 100, 2),
        positive_months_percent=round(sum(value > 0 for value in returns) / len(returns) * 100, 1),
        worst_month_percent=round(min(returns) * 100, 2), best_month_percent=round(max(returns) * 100, 2),
    )


def block_bootstrap_forecast(canonical_id: str, last_date, monthly_sip: float, horizon_years: int,
                             returns: list[float], simulations: int) -> SIPForecast:
    months = horizon_years * 12
    block_length = 3 if len(returns) >= 36 else 2
    starts = list(range(0, len(returns) - block_length + 1))
    seed_text = f"{canonical_id}:{last_date}:{monthly_sip:.2f}:{horizon_years}:{simulations}"
    rng = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16))
    outcomes = []
    target_12 = _constant_rate_corpus(monthly_sip, months, .12)
    for _ in range(simulations):
        path = []
        while len(path) < months:
            start = rng.choice(starts)
            path.extend(returns[start:start + block_length])
        outcomes.append(_corpus(monthly_sip, path[:months]))
    contributions = monthly_sip * months
    return SIPForecast(
        horizon_years=horizon_years, monthly_sip=monthly_sip, total_contributions=contributions,
        p10_value=round(_percentile(outcomes, .10), 2), p25_value=round(_percentile(outcomes, .25), 2),
        median_value=round(_percentile(outcomes, .50), 2), p75_value=round(_percentile(outcomes, .75), 2),
        p90_value=round(_percentile(outcomes, .90), 2),
        probability_below_contributions_percent=round(sum(value < contributions for value in outcomes) / simulations * 100, 1),
        probability_above_12pct_return_percent=round(sum(value >= target_12 for value in outcomes) / simulations * 100, 1),
        simulations=simulations,
    )


def walk_forward(monthly_sip: float, requested_years: int, returns: list[float]) -> WalkForwardSummary:
    window_years = min(requested_years, 5)
    while window_years >= 3 and len(returns) < window_years * 12 + 6:
        window_years -= 1
    if window_years < 3:
        return WalkForwardSummary(window_years=max(window_years, 1), windows=0,
                                  note="At least three years plus six months of monthly history is needed for a useful walk-forward check.")
    months = window_years * 12
    outcomes = [_corpus(monthly_sip, returns[start:start + months])
                for start in range(0, len(returns) - months + 1)]
    annualized = [_annualized_sip_return(monthly_sip, value, months) * 100 for value in outcomes]
    contributions = monthly_sip * months
    return WalkForwardSummary(
        window_years=window_years, windows=len(outcomes),
        profitable_windows_percent=round(sum(value > contributions for value in outcomes) / len(outcomes) * 100, 1),
        median_annualized_return_percent=round(statistics.median(annualized), 2),
        worst_annualized_return_percent=round(min(annualized), 2), best_annualized_return_percent=round(max(annualized), 2),
        note="Overlapping historical SIP start dates; each window uses only returns that were known after that start date.",
    )


def _metric(analysis: Analysis | None, key: str):
    if analysis is None:
        return None
    return next((item for item in analysis.metrics if item.key == key and item.status == "available"), None)


def analyse_fund_managers(analysis: Analysis | None,
                          monthly: list[HistoricalNAVPoint]) -> FundManagerAnalysis:
    managers = analysis.managers if analysis else []
    if not managers:
        return FundManagerAnalysis(
            status="unavailable",
            summary="The current fund manager and tenure could not be verified from the available fund sources.",
            warnings=["Manager evidence is unavailable, so it cannot increase confidence in this result."],
        )

    results: list[ManagerTenurePerformance] = []
    known_tenures: list[float] = []
    for manager in managers:
        tenure_years = manager.tenure_years
        if tenure_years is None and manager.tenure_start:
            tenure_years = round((monthly[-1].date - manager.tenure_start).days / 365.2425, 1)
        if tenure_years is not None:
            known_tenures.append(max(tenure_years, 0))
        cutoff = manager.tenure_start
        if cutoff is None and tenure_years is not None:
            cutoff = monthly[-1].date - timedelta(days=round(tenure_years * 365.2425))
        covered = [point for point in monthly if cutoff is None or point.date >= cutoff]
        manager_status = ("tenure unavailable" if tenure_years is None else "established" if tenure_years >= 5
                          else "developing" if tenure_years >= 3 else "recent")
        summary = None
        if cutoff is not None and len(covered) >= 7:
            covered_returns = [covered[index].nav / covered[index - 1].nav - 1
                               for index in range(1, len(covered))]
            summary = historical_summary(covered, covered_returns)
        if cutoff is None:
            note = "The source names this manager but does not provide a start date or tenure."
        elif summary is None:
            note = "Fewer than six monthly returns are available during the reported tenure, so performance statistics are withheld."
        elif manager.tenure_start and manager.tenure_start < monthly[0].date:
            note = "The reported tenure predates the available NAV sample; statistics cover only the displayed NAV period."
        else:
            note = "Fund performance during the reported current-manager tenure; this is not a measure of manager alpha."
        results.append(ManagerTenurePerformance(
            name=manager.name, tenure_start=manager.tenure_start, tenure_years=tenure_years,
            experience=manager.experience, other_funds=manager.other_funds, source=manager.source,
            source_url=manager.source_url, nav_coverage_start=covered[0].date if covered and cutoff else None,
            monthly_observations=summary.monthly_observations if summary else 0,
            annualized_return_percent=summary.annualized_return_percent if summary else None,
            annualized_volatility_percent=summary.annualized_volatility_percent if summary else None,
            max_drawdown_percent=summary.max_drawdown_percent if summary else None,
            positive_months_percent=summary.positive_months_percent if summary else None,
            status=manager_status, note=note,
        ))

    if not known_tenures:
        status = "unavailable"
        summary_text = "Current manager names are available, but their tenure dates are not verified."
    elif min(known_tenures) < 3:
        status = "recent transition"
        summary_text = "At least one current manager has less than three years of reported tenure, so the full fund history may not represent the present team."
    elif len(known_tenures) != len(results):
        status = "mixed"
        summary_text = "The established manager evidence is partly usable, but tenure is missing for at least one current manager."
    else:
        status = "established"
        summary_text = "All reported current managers have at least three years of tenure, providing a usable tenure-period record."
    return FundManagerAnalysis(
        status=status, summary=summary_text, managers=results,
        shortest_tenure_years=round(min(known_tenures), 1) if known_tenures else None,
        source=managers[0].source, source_url=managers[0].source_url,
        warnings=[
            "Tenure-period returns are the fund's returns while the manager was reported in role; they do not isolate manager skill or alpha.",
            "A co-manager change can alter the investment process even when another manager has a long tenure.",
        ],
    )


def evaluate_statistical_sip(fund, points: list[HistoricalNAVPoint], monthly_sip: float, horizon_years: int,
                             simulations: int, regime: MarketRegime | None, analysis: Analysis | None = None) -> StatisticalSIPResponse:
    monthly, returns = _returns(points)
    if len(returns) < 24:
        raise ValueError("At least 24 monthly returns are required for statistical analysis.")
    history = historical_summary(monthly, returns)
    forecast = block_bootstrap_forecast(fund.canonical_id, monthly[-1].date, monthly_sip, horizon_years, returns, simulations)
    backtest = walk_forward(monthly_sip, horizon_years, returns)
    manager_analysis = analyse_fund_managers(analysis, monthly)
    signals: list[StatisticalSignal] = []

    loss_status = "positive" if forecast.probability_below_contributions_percent <= 15 else "warning" if forecast.probability_below_contributions_percent <= 30 else "negative"
    signals.append(StatisticalSignal(label="Simulated loss probability", value=f"{forecast.probability_below_contributions_percent:.1f}%",
        status=loss_status, explanation=f"Share of {simulations:,} moving-block bootstrap paths ending below total SIP contributions after {horizon_years} years."))
    backtest_status = "unavailable" if backtest.profitable_windows_percent is None else "positive" if backtest.profitable_windows_percent >= 75 else "warning" if backtest.profitable_windows_percent >= 60 else "negative"
    signals.append(StatisticalSignal(label=f"Profitable historical {backtest.window_years}Y SIP windows",
        value="Unavailable" if backtest.profitable_windows_percent is None else f"{backtest.profitable_windows_percent:.1f}%",
        status=backtest_status, explanation="Walk-forward outcomes across historical monthly start dates; overlapping windows are not independent."))
    drawdown_status = "positive" if history.max_drawdown_percent > -20 else "warning" if history.max_drawdown_percent > -40 else "negative"
    signals.append(StatisticalSignal(label="Maximum historical drawdown", value=f"{history.max_drawdown_percent:.1f}%",
        status=drawdown_status, explanation="Largest peak-to-trough decline in the available month-end NAV history."))

    structural_concerns = 0
    structural_concerns += history.annualized_return_percent <= 0
    structural_concerns += forecast.probability_below_contributions_percent >= 45
    structural_concerns += backtest.profitable_windows_percent is not None and backtest.profitable_windows_percent < 55
    failed_rules = sum(rule.status == "FAIL" for rule in analysis.rules) if analysis else 0
    if failed_rules >= 2:
        structural_concerns += 1
        signals.append(StatisticalSignal(label="Fund research rule failures", value=str(failed_rules), status="negative",
            explanation="Multiple configured cost or risk checks failed in the current live fund analysis."))
    expense = _metric(analysis, "expense_ratio")
    if expense:
        signals.append(StatisticalSignal(label="Expense ratio", value=f"{expense.value:g}%", status="neutral",
            explanation="NAV returns are already net of fund expenses; this value is retained as a structural cost signal."))

    manager_status = ("positive" if manager_analysis.status == "established" else
                      "warning" if manager_analysis.status in {"mixed", "recent transition"} else "unavailable")
    signals.append(StatisticalSignal(
        label="Current manager tenure",
        value=(f"{manager_analysis.shortest_tenure_years:.1f} years shortest" if manager_analysis.shortest_tenure_years is not None
               else "Tenure unavailable"),
        status=manager_status,
        explanation=manager_analysis.summary,
    ))

    market_hot = regime is not None and regime.status == "available" and regime.valuation_state in {"elevated", "extreme"}
    if regime is None:
        signals.append(StatisticalSignal(label="Market entry condition", value="No benchmark mapping", status="unavailable",
            explanation="This category does not have a supported NSE Indices valuation mapping."))
    elif regime.status == "unavailable":
        signals.append(StatisticalSignal(label="Market entry condition", value="Unavailable", status="unavailable",
            explanation=regime.note or "Official NSE Indices evidence was unavailable."))
    else:
        market_status = "negative" if regime.valuation_state == "extreme" else "warning" if regime.valuation_state == "elevated" else "positive"
        ranks = [value for value in (regime.pe_percentile, regime.pb_percentile) if value is not None]
        rank = sum(ranks) / len(ranks) if ranks else None
        signals.append(StatisticalSignal(label="Benchmark valuation regime",
            value=regime.valuation_state.title() + (f" · {rank:.0f}th percentile" if rank is not None else ""),
            status=market_status, explanation="Current P/E and P/B are ranked against available official NSE Indices history; this affects entry pacing, not the fund forecast."))

    confidence = "high" if len(returns) >= 108 and backtest.windows >= 36 else "medium" if len(returns) >= 60 and backtest.windows >= 12 else "low"
    if manager_analysis.status in {"mixed", "recent transition", "unavailable"}:
        confidence = "medium" if confidence == "high" else "low"
    reasons = [
        f"The fund has {len(returns)} monthly returns from {monthly[0].date:%b %Y} to {monthly[-1].date:%b %Y}.",
        f"The median simulated corpus is ₹{forecast.median_value:,.0f} versus ₹{forecast.total_contributions:,.0f} contributed.",
        f"Historical annualized return was {history.annualized_return_percent:.1f}% with {history.annualized_volatility_percent:.1f}% annualized volatility.",
    ]
    risks = [
        f"A weak bootstrap path ends near ₹{forecast.p10_value:,.0f}; the model estimates a {forecast.probability_below_contributions_percent:.1f}% chance of finishing below contributions.",
        f"The observed maximum drawdown was {history.max_drawdown_percent:.1f}% and the worst month was {history.worst_month_percent:.1f}%.",
    ]
    if manager_analysis.status == "established":
        reasons.append(manager_analysis.summary)
    else:
        risks.append(manager_analysis.summary)
    if structural_concerns >= 2:
        action, headline = "avoid this fund", "The fund-specific evidence is too weak to support a new SIP under the current data."
        review = "Re-run only after at least six new monthly NAV observations or after the failed fund-quality signals materially improve."
    elif market_hot:
        action, headline = "phase in / wait for better entry", "The fund evidence is usable, but its benchmark is in an expensive historical valuation range."
        review = "Review when the benchmark valuation falls below the 75th percentile, the index moves near its 200-day average, or after the next monthly valuation update."
    elif confidence == "low" or forecast.probability_below_contributions_percent > 30:
        action, headline = "phase in / wait for better entry", "The evidence is not strong enough for a full-speed start; use a smaller phased SIP and gather more data."
        review = "Review after six additional monthly NAV observations or when the simulated loss probability falls below 30%."
    else:
        action, headline = "invest now", "The historical distribution supports starting the planned SIP at the current valuation regime."
        review = "Re-run monthly, or sooner if the benchmark enters the top 75% of its valuation history or the fund records a new material drawdown."

    return StatisticalSIPResponse(
        fund=fund, action=action, confidence=confidence, headline=headline, history=history, forecast=forecast,
        backtest=backtest, manager_analysis=manager_analysis, market_regime=regime, signals=signals,
        reasons=reasons, risks=risks, review_trigger=review,
        warnings=[
            "This is a probability model based on historical NAV paths, not a promise that the fund will deliver the projected values.",
            "Moving-block bootstrap preserves short return sequences but cannot reproduce a market regime absent from the history.",
            "Valuation percentiles can support pacing over long horizons; they cannot identify an exact market top, bottom or future purchase date.",
            "Past winner rankings are not treated as proof of persistent manager skill.",
        ],
    )
