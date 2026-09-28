import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.analysis.rules import evaluate
from app.analysis.screener import category_matches, evaluate_screen
from app.analysis.portfolio import analyse_sip_portfolio
from app.analysis.statistical import evaluate_statistical_sip
from app.normalization.identity import same_growth_fund
from app.schemas import (Analysis, ComparisonRequest, Fund, FundFacts, FundManager, HistoricalNAVPoint, Holding,
                         MarketRegime, Metric, PortfolioAllocationSlice, PortfolioExposure, PortfolioFundAllocation,
                         PortfolioOverlap, PortfolioSummary, Rules, ScreenFilters, SectorAllocation,
                         SIPPortfolioAnalysis, SIPPortfolioEntry, SIPPortfolioRequest)
from app.sources.advisorkhoj import parse_capture, parse_details, parse_rolling
from app.sources.amfi import parse_catalog
from app.sources.coin import parse_page as parse_coin_page
from app.sources.groww import parse_page, parse_search
from app.sources.nifty import benchmark_for, calculate_regime
from app.sources.mfapi import parse_history, verify_against_amfi

FIXTURES = Path(__file__).parent / "fixtures"
FETCHED = datetime(2026, 9, 20, tzinfo=timezone.utc)


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["amfi_current.txt", "amfi_legacy.txt"])
def test_amfi_parser_handles_current_and_legacy_feeds(name):
    funds = parse_catalog(fixture(name), FETCHED)
    direct = next(f for f in funds if f.amfi_code == "118989")
    assert direct.plan == "Direct"
    assert direct.option == "Growth"
    assert direct.isins == ["INF179K01XQ0"]
    assert direct.nav.value == 231.413
    assert direct.category == "Equity Scheme - Mid Cap Fund"


def test_amfi_keeps_plan_and_option_as_separate_schemes():
    funds = parse_catalog(fixture("amfi_current.txt"), FETCHED)
    assert {(f.plan, f.option) for f in funds} == {("Direct", "Growth"), ("Regular", "Growth"), ("Direct", "IDCW")}
    assert len({f.canonical_id for f in funds}) == 3


def sample_fund():
    return Fund(canonical_id="amfi:118989", amfi_code="118989", name="HDFC Mid Cap Fund · Direct Plan · Growth Option",
                scheme="HDFC Mid Cap Fund", amc="HDFC Mutual Fund", category="Equity Scheme - Mid Cap Fund",
                plan="Direct", option="Growth", option_label="Growth Option", isins=["INF179K01XQ0"],
                nav=Metric(key="nav", label="NAV", value=231.413, unit="INR", source="AMFI", source_url="https://example.test",
                           fetched_at=FETCHED, as_of=date(2026, 9, 18), definition="NAV"))


def test_advisor_match_requires_exact_scheme_plan_and_growth():
    assert same_growth_fund("HDFC Mid Cap Fund", "Direct", "HDFC Mid Cap Fund - Growth Option - Direct Plan")
    assert not same_growth_fund("HDFC Mid Cap Fund", "Direct", "HDFC Mid Cap Fund - Growth Plan")
    assert not same_growth_fund("HDFC Mid Cap Fund", "Direct", "HDFC Large & Mid Cap Fund - Direct Plan - Growth Option")


def test_advisor_detail_parser_attaches_context_and_as_of_dates():
    metrics, category, inception = parse_details(fixture("advisorkhoj_detail.html"), sample_fund(),
        "HDFC Mid Cap Fund - Growth Option - Direct Plan", "https://example.test/fund", FETCHED)
    by_key = {m.key: m for m in metrics}
    assert category == "Equity: Mid Cap"
    assert inception == date(2013, 1, 1)
    assert by_key["beta"].value == .82
    assert by_key["beta"].benchmark == "Nifty Midcap 150 TRI"
    assert by_key["expense_ratio"].as_of == date(2026, 8, 30)
    assert by_key["aum"].value == 108324.55


def test_rolling_and_capture_parsers_do_not_infer_missing_provenance():
    payload = json.dumps([
        {"scheme_name": "HDFC Mid Cap Fund - Growth Option - Direct Plan", "category_flag": 0,
         "average": 19.4, "median": 20.1, "minimum": -8.5, "maximum": 40.3, "less_than_0": 5,
         "scheme_amfi_short_name": "HDFC Mid Cap Fund Gr Dir"},
        {"scheme_name": "Equity: Mid Cap", "category_flag": 1, "average": 16.3},
    ])
    summary, short = parse_rolling(payload, "HDFC Mid Cap Fund - Growth Option - Direct Plan", "Equity: Mid Cap", 3,
                                   date(2016, 1, 1), "https://example.test/rolling", FETCHED)
    assert summary.status == "available"
    assert summary.positive_percent == 95
    assert summary.category_average == 16.3
    assert summary.end_date is None
    assert short == "HDFC Mid Cap Fund Gr Dir"
    capture = parse_capture(fixture("capture.html"), short, "https://example.test/capture", FETCHED, 3)
    assert [(m.key, m.value) for m in capture] == [("upside_capture", 91), ("downside_capture", 78), ("capture_ratio", 1.16)]


def test_rules_preserve_raw_values_and_mark_missing_metrics():
    metrics = [Metric(key="beta", label="Beta", value=.82, source="AdvisorKhoj", source_url="https://example.test",
                      definition="Beta"), Metric(key="expense_ratio", label="TER", value=None, unit="%", source="AdvisorKhoj",
                      source_url="https://example.test", definition="TER", status="unavailable")]
    result = {r.metric: r.status for r in evaluate(metrics, Rules())}
    assert result == {"beta": "PASS", "expense_ratio": "UNAVAILABLE", "upside_capture": "UNAVAILABLE", "downside_capture": "UNAVAILABLE"}


def test_groww_payload_is_identity_checked_and_normalized():
    result = parse_page(fixture("groww_hdfc.html"), sample_fund(), "https://groww.in/example", FETCHED)
    metrics = {metric.key: metric for metric in result.metrics}
    assert result.match.status == "Matched"
    assert metrics["aum"].value == pytest.approx(108324.5467)
    assert metrics["expense_ratio"].value == .76
    assert metrics["expense_ratio"].as_of == date(2026, 9, 24)
    assert metrics["beta"].value == .84
    assert result.facts.risk == "Very High"
    assert result.facts.inception_date == date(2013, 1, 1)
    assert result.portfolio.holdings_count == 81
    assert result.portfolio.top_10 == pytest.approx(sum(h.weight for h in result.holdings[:10]))
    assert result.sectors[0].sector == "Financial"
    assert result.managers[0].name == "Chirag Setalvad"
    assert next(item for item in result.returns if item.period == "3Y").category_value == 15.89


def test_groww_payload_rejects_a_different_amfi_identity():
    fund = sample_fund().model_copy(update={"amfi_code": "999999", "isins": ["OTHER"]})
    with pytest.raises(Exception, match="did not confirm"):
        parse_page(fixture("groww_hdfc.html"), fund, "https://groww.in/example", FETCHED)


def test_groww_search_keeps_only_public_scheme_results():
    payload = json.dumps({"data": {"content": [
        {"entity_type": "Scheme", "search_id": "hdfc-mid-cap-fund-direct-growth", "title": "HDFC Mid Cap Fund"},
        {"entity_type": "ETF", "search_id": "hdfc-nifty-midcap-etf", "title": "HDFC NIFTY Midcap 150 ETF"},
    ]}})
    assert parse_search(payload) == [{"entity_type": "Scheme", "search_id": "hdfc-mid-cap-fund-direct-growth", "title": "HDFC Mid Cap Fund"}]


def test_coin_public_summary_is_identity_checked_and_normalized():
    result = parse_coin_page(fixture("coin_hdfc.html"), sample_fund(),
                             "https://coin.zerodha.com/mf/fund/INF179K01XQ0", FETCHED)
    metrics = {metric.key: metric for metric in result.metrics}
    assert result.match.status == "Matched"
    assert "ISIN" in result.match.method
    assert metrics["nav"].value == 226.38
    assert metrics["nav"].as_of == date(2026, 9, 25)
    assert metrics["aum"].value == 108325
    assert metrics["expense_ratio"].value == .6
    assert [(item.period, item.value) for item in result.returns] == [
        ("1Y", 6.12), ("2Y", 2.99), ("3Y", 16.77), ("4Y", 20.61), ("5Y", 18.34)
    ]
    assert result.managers[0].name == "Chirag Setalvad"
    assert result.facts.inception_date == date(2013, 1, 1)


def test_coin_public_summary_rejects_a_different_isin():
    fund = sample_fund().model_copy(update={"isins": ["OTHER"]})
    with pytest.raises(Exception, match="did not confirm"):
        parse_coin_page(fixture("coin_hdfc.html"), fund,
                        "https://coin.zerodha.com/mf/fund/OTHER", FETCHED)


def test_comparison_request_accepts_two_to_four_unique_amfi_ids():
    request = ComparisonRequest(canonical_ids=["amfi:118989", "amfi:119010"])
    assert request.canonical_ids == ["amfi:118989", "amfi:119010"]
    with pytest.raises(ValidationError, match="at least 2 items"):
        ComparisonRequest(canonical_ids=["amfi:118989"])
    with pytest.raises(ValidationError, match="must be unique"):
        ComparisonRequest(canonical_ids=["amfi:118989", "amfi:118989"])
    with pytest.raises(ValidationError, match="canonical AMFI ID"):
        ComparisonRequest(canonical_ids=["amfi:118989", "groww:hdfc-mid-cap"])


def sample_analysis():
    metrics = [
        Metric(key="beta", label="Beta", value=.82, source="AdvisorKhoj", source_url="https://example.test", definition="Beta"),
        Metric(key="expense_ratio", label="TER", value=.76, unit="%", source="Groww", source_url="https://example.test", definition="TER"),
        Metric(key="upside_capture", label="Upside", value=110, unit="%", source="AdvisorKhoj", source_url="https://example.test", definition="Upside"),
        Metric(key="downside_capture", label="Downside", value=78, unit="%", source="AdvisorKhoj", source_url="https://example.test", definition="Downside"),
    ]
    return Analysis(fund=sample_fund(), metrics=metrics, sources=[], rules=[], applied_rules=Rules(), warnings=[],
                    facts=FundFacts(risk="Very High", inception_date=date(2013, 1, 1), age_years=13.7,
                                    source="Groww", source_url="https://example.test"),
                    managers=[FundManager(name="Manager", tenure_years=5.2, source="Groww", source_url="https://example.test")])


def test_screener_preserves_raw_values_and_requires_all_active_evidence():
    criteria, matched, complete = evaluate_screen(sample_analysis(), ScreenFilters(category="Mid Cap"))
    assert matched and complete
    assert {item.key: (item.value, item.status) for item in criteria}["beta"] == (.82, "PASS")
    missing = sample_analysis().model_copy(update={"managers": []})
    criteria, matched, complete = evaluate_screen(missing, ScreenFilters(category="Mid Cap"))
    assert not matched and not complete
    assert next(item for item in criteria if item.key == "manager_tenure").status == "UNAVAILABLE"
    _, matched, complete = evaluate_screen(missing, ScreenFilters(category="Mid Cap", unknown_policy="include"))
    assert matched and not complete


def test_screener_validates_scope_and_aum_range():
    with pytest.raises(ValidationError, match="bound the live screen"):
        ScreenFilters(category="", query="", amc="")
    with pytest.raises(ValidationError, match="Minimum AUM"):
        ScreenFilters(category="Mid Cap", aum_min=5000, aum_max=1000)


def test_screener_specific_category_does_not_mix_large_and_mid_cap():
    assert category_matches("Equity Scheme - Mid Cap Fund", "Mid Cap")
    assert not category_matches("Equity Schemes - Large & Mid Cap Fund", "Mid Cap")
    assert category_matches("Debt Scheme - Liquid Fund", "Debt")


def test_sip_portfolio_aggregates_allocations_and_disclosed_overlap():
    first = sample_analysis().model_copy(update={
        "holdings": [
            Holding(name="Alpha Limited", sector="Financial", weight=12, source="Groww", source_url="https://example.test"),
            Holding(name="Beta Ltd.", sector="Technology", weight=8, source="Groww", source_url="https://example.test"),
        ],
        "sectors": [
            SectorAllocation(sector="Financial", weight=60, source="Groww", source_url="https://example.test"),
            SectorAllocation(sector="Technology", weight=40, source="Groww", source_url="https://example.test"),
        ],
        "portfolio": PortfolioSummary(holdings_count=2, as_of=date(2026, 8, 31), source="Groww", source_url="https://example.test"),
    })
    second_fund = sample_fund().model_copy(update={
        "canonical_id": "amfi:119010", "amfi_code": "119010", "scheme": "Example Flexi Cap Fund",
        "name": "Example Flexi Cap Fund · Direct Plan · Growth Option", "category": "Equity Scheme - Flexi Cap Fund",
    })
    second = sample_analysis().model_copy(update={
        "fund": second_fund,
        "facts": FundFacts(risk="High", source="Groww", source_url="https://example.test"),
        "holdings": [
            Holding(name="Alpha Ltd", sector="Financial", weight=10, source="Groww", source_url="https://example.test"),
            Holding(name="Gamma Limited", sector="Energy", weight=7, source="Groww", source_url="https://example.test"),
        ],
        "sectors": [
            SectorAllocation(sector="Financial", weight=50, source="Groww", source_url="https://example.test"),
            SectorAllocation(sector="Energy", weight=50, source="Groww", source_url="https://example.test"),
        ],
        "portfolio": PortfolioSummary(holdings_count=2, as_of=date(2026, 8, 31), source="Groww", source_url="https://example.test"),
    })
    result = analyse_sip_portfolio([first, second], [
        SIPPortfolioEntry(canonical_id="amfi:118989", monthly_sip=6000),
        SIPPortfolioEntry(canonical_id="amfi:119010", monthly_sip=4000),
    ])
    assert result.total_monthly_sip == 10000
    assert [(item.label, item.allocation_percent) for item in result.category_allocation] == [
        ("Mid Cap Fund", 60), ("Flexi Cap Fund", 40)
    ]
    assert [(item.label, item.allocation_percent) for item in result.asset_allocation] == [("Equity", 100)]
    assert result.sector_exposure[0].name == "Financial"
    assert result.sector_exposure[0].exposure_percent == 56
    assert result.common_holdings[0].name == "Alpha Limited"
    assert result.common_holdings[0].exposure_percent == 11.2
    assert result.pairwise_overlap[0].common_holdings == 1
    assert result.pairwise_overlap[0].overlap_percent == 10
    assert result.holdings_coverage_percent == 100


def test_sip_portfolio_validates_unique_funds_and_reports_missing_holdings():
    with pytest.raises(ValidationError, match="must be unique"):
        SIPPortfolioRequest(entries=[
            SIPPortfolioEntry(canonical_id="amfi:118989", monthly_sip=5000),
            SIPPortfolioEntry(canonical_id="amfi:118989", monthly_sip=2000),
        ])
    first = sample_analysis()
    result = analyse_sip_portfolio([first], [SIPPortfolioEntry(canonical_id="amfi:118989", monthly_sip=5000)])
    assert result.holdings_coverage_percent == 0
    assert any("cover 0%" in warning for warning in result.warnings)
    assert result.market_cap_status == "unavailable"


def test_nifty_regime_calculates_dated_market_evidence():
    start = date(2026, 1, 1)
    history = [{"HistoricalDate": (start + timedelta(days=index)).strftime("%d %b %Y"),
                "CLOSE": str(100 + index)} for index in range(210)]
    valuations = [
        {"DATE": (start + timedelta(days=index)).strftime("%d %b %Y"), "pe": str(pe), "pb": str(pb), "divYield": "1.2"}
        for index, (pe, pb) in enumerate([(10, 1), (15, 2), (20, 3), (30, 4)])
    ]
    regime = calculate_regime("Nifty 50", history, valuations)
    assert regime.status == "available"
    assert regime.pe == 30
    assert regime.pe_percentile == 100
    assert regime.valuation_state == "extreme"
    assert regime.drawdown_1y_percent == 0
    assert benchmark_for(sample_fund()) == "Nifty Midcap 150"


def synthetic_history(months=121, monthly_return=.01):
    points = []
    year, month, nav = 2016, 1, 100.0
    for _ in range(months):
        points.append(HistoricalNAVPoint(date=date(year, month, 28), nav=nav))
        nav *= 1 + monthly_return
        month += 1
        if month == 13:
            month, year = 1, year + 1
    return points


def test_statistical_sip_phases_entry_when_market_valuation_is_extreme():
    regime = MarketRegime(benchmark="Nifty Midcap 150", status="available", as_of=date(2026, 9, 25),
                          pe=35, pe_percentile=96, pb=5, pb_percentile=94, valuation_state="extreme",
                          drawdown_1y_percent=-1, versus_200d_average_percent=18, valuation_observations=700)
    result = evaluate_statistical_sip(sample_fund(), synthetic_history(), 5000, 5, 1000, regime, sample_analysis())
    assert result.action == "phase in / wait for better entry"
    assert result.forecast.median_value > result.forecast.total_contributions
    assert result.history.monthly_observations == 120
    assert result.backtest.windows > 0


def test_statistical_sip_uses_distribution_for_invest_now_result():
    regime = MarketRegime(benchmark="Nifty Midcap 150", status="available",
                          valuation_state="within historical range", pe_percentile=50, pb_percentile=50)
    result = evaluate_statistical_sip(sample_fund(), synthetic_history(), 5000, 5, 1000, regime, sample_analysis())
    assert result.action == "invest now"
    assert result.forecast.probability_below_contributions_percent == 0
    assert result.manager_analysis.status == "established"
    assert result.manager_analysis.managers[0].monthly_observations >= 60
    assert result.manager_analysis.managers[0].annualized_return_percent == pytest.approx(12.68, abs=.01)
    assert next(signal for signal in result.signals if signal.label == "Current manager tenure").status == "positive"


def test_statistical_sip_marks_recent_manager_transition_and_reduces_confidence():
    regime = MarketRegime(benchmark="Nifty Midcap 150", status="available",
                          valuation_state="within historical range", pe_percentile=50, pb_percentile=50)
    analysis = sample_analysis().model_copy(update={
        "managers": [FundManager(name="New manager", tenure_start=date(2025, 1, 1), tenure_years=1.7,
                                 source="Groww", source_url="https://example.test")]
    })
    result = evaluate_statistical_sip(sample_fund(), synthetic_history(), 5000, 5, 1000, regime, analysis)
    assert result.manager_analysis.status == "recent transition"
    assert result.manager_analysis.managers[0].status == "recent"
    assert result.confidence == "medium"
    assert result.action == "invest now"
    assert any("less than three years" in risk for risk in result.risks)


def test_statistical_sip_reports_unavailable_manager_evidence():
    regime = MarketRegime(benchmark="Nifty Midcap 150", status="available",
                          valuation_state="within historical range", pe_percentile=50, pb_percentile=50)
    analysis = sample_analysis().model_copy(update={"managers": []})
    result = evaluate_statistical_sip(sample_fund(), synthetic_history(), 5000, 5, 1000, regime, analysis)
    assert result.manager_analysis.status == "unavailable"
    assert result.manager_analysis.managers == []
    assert result.confidence == "medium"


def test_mfapi_history_parser_requires_scheme_identity_and_amfi_cross_check():
    fund = sample_fund().model_copy(update={"nav": sample_fund().nav.model_copy(update={"as_of": date(2026, 9, 20), "value": 120})})
    payload = {"meta": {"scheme_code": fund.amfi_code}, "data": [
        {"date": (date(2026, 9, 20) - timedelta(days=index)).strftime("%d-%m-%Y"), "nav": str(120 - index * .01)}
        for index in range(30)
    ]}
    points = parse_history(json.dumps(payload), fund, FETCHED, 10)
    verify_against_amfi(points, fund)
    assert len(points) == 30
