import re
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now() -> datetime:
    return datetime.now(timezone.utc)


class Metric(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    key: str
    label: str
    value: float | None = None
    unit: str = ""
    source: str
    source_url: str
    fetched_at: datetime = Field(default_factory=now)
    as_of: date | None = None
    definition: str
    period: str | None = None
    benchmark: str | None = None
    status: Literal["available", "unavailable", "stale", "suspicious"] = "available"
    note: str | None = None


class Fund(BaseModel):
    canonical_id: str
    amfi_code: str
    name: str
    scheme: str
    amc: str
    category: str
    plan: Literal["Direct", "Regular", "Unknown"]
    option: Literal["Growth", "IDCW", "Unknown"]
    option_label: str
    isins: list[str] = Field(default_factory=list)
    nav: Metric


class SourceStatus(BaseModel):
    id: str
    name: str
    enabled: bool
    status: str = "Not checked"
    last_success: datetime | None = None
    message: str | None = None
    capabilities: list[str]
    adapter_version: str = "0.1.0"


class SourceMatch(BaseModel):
    source: str
    status: str
    name: str | None = None
    url: str | None = None
    method: str | None = None
    note: str | None = None


class RollingSummary(BaseModel):
    years: int
    start_date: date
    end_date: date | None = None
    source: str = "AdvisorKhoj"
    source_url: str
    fetched_at: datetime = Field(default_factory=now)
    average: float | None = None
    median: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    category_average: float | None = None
    positive_percent: float | None = None
    status: str = "unavailable"
    note: str | None = None


class ReturnObservation(BaseModel):
    period: str
    value: float | None = None
    category_value: float | None = None
    source: str
    source_url: str
    fetched_at: datetime = Field(default_factory=now)
    status: Literal["available", "unavailable", "stale", "suspicious"] = "available"


class Holding(BaseModel):
    name: str
    sector: str | None = None
    instrument: str | None = None
    weight: float
    as_of: date | None = None
    source: str
    source_url: str


class SectorAllocation(BaseModel):
    sector: str
    weight: float
    as_of: date | None = None
    source: str
    source_url: str


class FundManager(BaseModel):
    name: str
    tenure_start: date | None = None
    tenure_years: float | None = None
    experience: str | None = None
    other_funds: list[str] = Field(default_factory=list)
    source: str
    source_url: str


class PortfolioSummary(BaseModel):
    holdings_count: int
    largest_holding: float | None = None
    top_5: float | None = None
    top_10: float | None = None
    top_20: float | None = None
    largest_sector: str | None = None
    largest_sector_weight: float | None = None
    top_3_sectors: float | None = None
    top_5_sectors: float | None = None
    as_of: date | None = None
    source: str
    source_url: str


class FundFacts(BaseModel):
    risk: str | None = None
    inception_date: date | None = None
    age_years: float | None = None
    benchmark: str | None = None
    exit_load: str | None = None
    source: str
    source_url: str


class SourceData(BaseModel):
    match: SourceMatch
    metrics: list[Metric] = Field(default_factory=list)
    rolling: RollingSummary | None = None
    returns: list[ReturnObservation] = Field(default_factory=list)
    holdings: list[Holding] = Field(default_factory=list)
    sectors: list[SectorAllocation] = Field(default_factory=list)
    managers: list[FundManager] = Field(default_factory=list)
    portfolio: PortfolioSummary | None = None
    facts: FundFacts | None = None
    warnings: list[str] = Field(default_factory=list)


class Rules(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    beta_max: float = Field(default=1, ge=0, le=5)
    expense_ratio_max: float = Field(default=1, ge=0, le=10)
    upside_capture_min: float = Field(default=100, ge=0, le=1000)
    downside_capture_max: float = Field(default=100, ge=-1000, le=1000)


class RuleResult(BaseModel):
    metric: str
    status: Literal["PASS", "WARNING", "FAIL", "UNAVAILABLE", "STALE"]
    explanation: str


class Analysis(BaseModel):
    fund: Fund
    metrics: list[Metric]
    sources: list[SourceMatch]
    rules: list[RuleResult]
    applied_rules: Rules
    rolling: RollingSummary | None = None
    metric_observations: dict[str, list[Metric]] = Field(default_factory=dict)
    returns: list[ReturnObservation] = Field(default_factory=list)
    holdings: list[Holding] = Field(default_factory=list)
    sectors: list[SectorAllocation] = Field(default_factory=list)
    managers: list[FundManager] = Field(default_factory=list)
    portfolio: PortfolioSummary | None = None
    facts: FundFacts | None = None
    warnings: list[str]
    fetched_at: datetime = Field(default_factory=now)


class AnalysisRequest(BaseModel):
    canonical_id: str = Field(pattern=r"^amfi:\d{5,8}$")
    rules: Rules | None = None
    rolling_years: Literal[1, 3, 5] = 3


class ComparisonRequest(BaseModel):
    canonical_ids: list[str] = Field(min_length=2, max_length=4)
    rules: Rules | None = None
    rolling_years: Literal[1, 3, 5] = 3

    @model_validator(mode="after")
    def validate_ids(self):
        if len(set(self.canonical_ids)) != len(self.canonical_ids):
            raise ValueError("Comparison funds must be unique.")
        if any(not re.fullmatch(r"amfi:\d{5,8}", item) for item in self.canonical_ids):
            raise ValueError("Each comparison fund must use a canonical AMFI ID.")
        return self


class Comparison(BaseModel):
    analyses: list[Analysis]
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=now)


class ScreenFilters(BaseModel):
    query: str = Field(default="", max_length=120)
    amc: str = Field(default="", max_length=120)
    category: str = Field(default="Mid Cap", max_length=120)
    plan: Literal["Direct", "Regular", ""] = "Direct"
    option: Literal["Growth", "IDCW", ""] = "Growth"
    risk_levels: list[str] = Field(default_factory=list, max_length=6)
    beta_max: float | None = Field(default=1, ge=0, le=5)
    expense_ratio_max: float | None = Field(default=1, ge=0, le=10)
    manager_tenure_min: float | None = Field(default=3, ge=0, le=100)
    upside_capture_min: float | None = Field(default=100, ge=-1000, le=1000)
    downside_capture_max: float | None = Field(default=100, ge=-1000, le=1000)
    aum_min: float | None = Field(default=None, ge=0)
    aum_max: float | None = Field(default=None, ge=0)
    fund_age_min: float | None = Field(default=None, ge=0, le=200)
    unknown_policy: Literal["exclude", "include"] = "exclude"
    rolling_years: Literal[1, 3, 5] = 3
    candidate_limit: int = Field(default=6, ge=2, le=8)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_scope(self):
        if not any((self.query.strip(), self.amc.strip(), self.category.strip())):
            raise ValueError("Provide a query, AMC or category to bound the live screen.")
        if self.aum_min is not None and self.aum_max is not None and self.aum_min > self.aum_max:
            raise ValueError("Minimum AUM cannot exceed maximum AUM.")
        allowed_risks = {"Low", "Low to Moderate", "Moderate", "Moderately High", "High", "Very High"}
        if any(item not in allowed_risks for item in self.risk_levels):
            raise ValueError("Risk levels must use SEBI Riskometer labels.")
        return self


class ScreenCriterion(BaseModel):
    key: str
    label: str
    operator: str
    threshold: float | str
    value: float | str | None = None
    unit: str = ""
    source: str | None = None
    status: Literal["PASS", "FAIL", "UNAVAILABLE"]


class ScreenResult(BaseModel):
    fund: Fund
    metrics: list[Metric] = Field(default_factory=list)
    rolling: RollingSummary | None = None
    facts: FundFacts | None = None
    managers: list[FundManager] = Field(default_factory=list)
    portfolio: PortfolioSummary | None = None
    sources: list[SourceMatch] = Field(default_factory=list)
    criteria: list[ScreenCriterion] = Field(default_factory=list)
    matched: bool
    evidence_complete: bool
    warnings: list[str] = Field(default_factory=list)


class ScreenResponse(BaseModel):
    total_candidates: int
    offset: int
    analysed: int
    matched: int
    results: list[ScreenResult]
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=now)


class SIPPortfolioEntry(BaseModel):
    canonical_id: str = Field(pattern=r"^amfi:\d{5,8}$")
    monthly_sip: float = Field(gt=0, le=100_000_000)


class SIPPortfolioRequest(BaseModel):
    entries: list[SIPPortfolioEntry] = Field(min_length=1, max_length=12)
    rolling_years: Literal[1, 3, 5] = 3

    @model_validator(mode="after")
    def validate_entries(self):
        ids = [entry.canonical_id for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise ValueError("SIP portfolio funds must be unique.")
        return self


class PortfolioFundAllocation(BaseModel):
    fund: Fund
    monthly_sip: float
    allocation_percent: float
    risk: str | None = None
    holdings_count: int = 0
    holdings_as_of: date | None = None


class PortfolioAllocationSlice(BaseModel):
    label: str
    monthly_sip: float
    allocation_percent: float
    fund_count: int


class PortfolioExposure(BaseModel):
    name: str
    exposure_percent: float
    fund_count: int
    funds: list[str] = Field(default_factory=list)


class PortfolioOverlap(BaseModel):
    fund_a_id: str
    fund_a_name: str
    fund_b_id: str
    fund_b_name: str
    common_holdings: int
    overlap_percent: float | None = None
    status: Literal["available", "unavailable"]
    note: str | None = None


class SIPPortfolioAnalysis(BaseModel):
    total_monthly_sip: float
    funds: list[PortfolioFundAllocation]
    category_allocation: list[PortfolioAllocationSlice] = Field(default_factory=list)
    asset_allocation: list[PortfolioAllocationSlice] = Field(default_factory=list)
    risk_allocation: list[PortfolioAllocationSlice] = Field(default_factory=list)
    sector_exposure: list[PortfolioExposure] = Field(default_factory=list)
    common_holdings: list[PortfolioExposure] = Field(default_factory=list)
    pairwise_overlap: list[PortfolioOverlap] = Field(default_factory=list)
    holdings_coverage_percent: float
    market_cap_status: Literal["unavailable"] = "unavailable"
    market_cap_note: str = "Verified market-cap look-through data is not available from the current sources."
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=now)


class MarketRegime(BaseModel):
    benchmark: str
    status: Literal["available", "unavailable"]
    source: str = "NSE Indices"
    source_url: str = "https://www.niftyindices.com/reports"
    as_of: date | None = None
    close: float | None = None
    drawdown_1y_percent: float | None = None
    return_6m_percent: float | None = None
    versus_200d_average_percent: float | None = None
    pe: float | None = None
    pe_percentile: float | None = None
    pb: float | None = None
    pb_percentile: float | None = None
    dividend_yield: float | None = None
    valuation_state: Literal["below historical range", "within historical range", "elevated", "extreme", "unavailable"] = "unavailable"
    history_start: date | None = None
    valuation_observations: int = 0
    note: str | None = None


class HistoricalNAVPoint(BaseModel):
    date: date
    nav: float = Field(gt=0)


class StatisticalSIPRequest(BaseModel):
    canonical_id: str = Field(pattern=r"^amfi:\d{5,8}$")
    monthly_sip: float = Field(gt=0, le=100_000_000)
    horizon_years: Literal[3, 5, 10] = 5
    simulations: int = Field(default=4000, ge=1000, le=10_000)


class HistoricalRiskSummary(BaseModel):
    monthly_observations: int
    start_date: date
    end_date: date
    annualized_return_percent: float
    annualized_volatility_percent: float
    downside_deviation_percent: float
    max_drawdown_percent: float
    positive_months_percent: float
    worst_month_percent: float
    best_month_percent: float


class SIPForecast(BaseModel):
    horizon_years: int
    monthly_sip: float
    total_contributions: float
    p10_value: float
    p25_value: float
    median_value: float
    p75_value: float
    p90_value: float
    probability_below_contributions_percent: float
    probability_above_12pct_return_percent: float
    simulations: int


class WalkForwardSummary(BaseModel):
    window_years: int
    windows: int
    profitable_windows_percent: float | None = None
    median_annualized_return_percent: float | None = None
    worst_annualized_return_percent: float | None = None
    best_annualized_return_percent: float | None = None
    note: str | None = None


class StatisticalSignal(BaseModel):
    label: str
    value: str
    status: Literal["positive", "neutral", "warning", "negative", "unavailable"]
    explanation: str


class ManagerTenurePerformance(BaseModel):
    name: str
    tenure_start: date | None = None
    tenure_years: float | None = None
    experience: str | None = None
    other_funds: list[str] = Field(default_factory=list)
    source: str
    source_url: str
    nav_coverage_start: date | None = None
    monthly_observations: int = 0
    annualized_return_percent: float | None = None
    annualized_volatility_percent: float | None = None
    max_drawdown_percent: float | None = None
    positive_months_percent: float | None = None
    status: Literal["established", "developing", "recent", "tenure unavailable"]
    note: str


class FundManagerAnalysis(BaseModel):
    status: Literal["established", "mixed", "recent transition", "unavailable"]
    summary: str
    managers: list[ManagerTenurePerformance] = Field(default_factory=list)
    shortest_tenure_years: float | None = None
    source: str | None = None
    source_url: str | None = None
    warnings: list[str] = Field(default_factory=list)


class StatisticalSIPResponse(BaseModel):
    fund: Fund
    action: Literal["invest now", "phase in / wait for better entry", "avoid this fund", "insufficient data"]
    confidence: Literal["low", "medium", "high"]
    headline: str
    history: HistoricalRiskSummary
    forecast: SIPForecast
    backtest: WalkForwardSummary
    manager_analysis: FundManagerAnalysis
    market_regime: MarketRegime | None = None
    signals: list[StatisticalSignal] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    review_trigger: str
    history_source: str = "MFapi.in historical NAV, cross-checked against latest AMFI NAV"
    history_source_url: str = "https://www.mfapi.in/"
    methodology_version: str = "sip-statistical-v1.1"
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=now)


class SearchResponse(BaseModel):
    funds: list[Fund]
    total: int
    query: str
    warnings: list[str] = Field(default_factory=list)


class IPOIssue(BaseModel):
    canonical_id: str
    company_name: str
    symbol: str
    exchange: Literal["NSE", "BSE"]
    board: Literal["Mainboard", "SME"]
    series: str
    status: Literal["open", "upcoming", "closed"]
    issue_start: date
    issue_end: date
    price_band_text: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    issue_size_shares: int | None = None
    shares_offered: int | None = None
    shares_bid: int | None = None
    subscription_times: float | None = None
    source: str = "NSE India"
    source_url: str = "https://www.nseindia.com/market-data/all-upcoming-issues-ipo"
    fetched_at: datetime = Field(default_factory=now)


class IPOCatalogueResponse(BaseModel):
    issues: list[IPOIssue]
    total: int
    open_count: int
    upcoming_count: int
    source: str = "NSE India"
    source_url: str = "https://www.nseindia.com/market-data/all-upcoming-issues-ipo"
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=now)


class IPODocument(BaseModel):
    kind: Literal["DRHP", "RHP", "Prospectus", "Advertisement", "In-principle XBRL", "Abridged prospectus XBRL",
                  "Final-listing XBRL", "Issuer presentation"]
    label: str
    url: str
    filed_on: date | None = None
    file_size: str | None = None
    status: str | None = None
    source: str = "NSE India"
    source_url: str = "https://www.nseindia.com/companies-listing/corporate-filings-offer-documents"


class IPOResearchItem(BaseModel):
    label: str
    value: str | None = None
    status: Literal["available", "unavailable"] = "available"
    note: str | None = None


class IPOResearchSection(BaseModel):
    key: Literal["company", "offer", "business", "promoters", "directors", "objects", "financials", "valuation",
                 "litigation"]
    title: str
    description: str
    items: list[IPOResearchItem] = Field(default_factory=list)
    source_url: str = "https://www.nseindia.com/companies-listing/corporate-filings-offer-documents"
    available: bool = False


class IPOResearchResponse(BaseModel):
    issue: IPOIssue
    match_status: Literal["exact", "unavailable"]
    matched_company: str | None = None
    document_status: str | None = None
    documents: list[IPODocument] = Field(default_factory=list)
    sections: list[IPOResearchSection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str = "NSE India"
    source_url: str = "https://www.nseindia.com/companies-listing/corporate-filings-offer-documents"
    fetched_at: datetime = Field(default_factory=now)
