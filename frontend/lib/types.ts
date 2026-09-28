export type Metric = {
  key: string; label: string; value: number | null; unit: string; source: string;
  source_url: string; fetched_at: string; as_of: string | null; definition: string;
  period: string | null; benchmark: string | null; status: string; note: string | null;
};
export type Fund = {
  canonical_id: string; amfi_code: string; name: string; scheme: string; amc: string;
  category: string; plan: string; option: string; option_label: string; isins: string[]; nav: Metric;
};
export type Rules = { beta_max: number; expense_ratio_max: number; upside_capture_min: number; downside_capture_max: number };
export type Analysis = {
  fund: Fund; metrics: Metric[];
  sources: { source: string; status: string; name?: string; url?: string; method?: string; note?: string }[];
  rules: { metric: string; status: string; explanation: string }[];
  applied_rules: Rules; warnings: string[]; fetched_at: string;
  metric_observations: Record<string, Metric[]>;
  returns: { period: string; value: number | null; category_value: number | null; source: string; source_url: string; fetched_at: string; status: string }[];
  holdings: { name: string; sector: string | null; instrument: string | null; weight: number; as_of: string | null; source: string; source_url: string }[];
  sectors: { sector: string; weight: number; as_of: string | null; source: string; source_url: string }[];
  managers: { name: string; tenure_start: string | null; tenure_years: number | null; experience: string | null; other_funds: string[]; source: string; source_url: string }[];
  portfolio: { holdings_count: number; largest_holding: number | null; top_5: number | null; top_10: number | null; top_20: number | null;
    largest_sector: string | null; largest_sector_weight: number | null; top_3_sectors: number | null; top_5_sectors: number | null;
    as_of: string | null; source: string; source_url: string } | null;
  facts: { risk: string | null; inception_date: string | null; age_years: number | null; benchmark: string | null; exit_load: string | null; source: string; source_url: string } | null;
  rolling: { years: number; start_date: string; end_date: string | null; average: number | null; median: number | null;
    minimum: number | null; maximum: number | null; positive_percent: number | null; category_average: number | null;
    source: string; source_url: string; fetched_at: string; status: string; note: string | null } | null;
};
export type Comparison = { analyses: Analysis[]; warnings: string[]; fetched_at: string };
export type ScreenFilters = {
  query: string; amc: string; category: string; plan: "Direct" | "Regular" | ""; option: "Growth" | "IDCW" | "";
  risk_levels: string[]; beta_max: number | null; expense_ratio_max: number | null; manager_tenure_min: number | null;
  upside_capture_min: number | null; downside_capture_max: number | null; aum_min: number | null; aum_max: number | null;
  fund_age_min: number | null; unknown_policy: "exclude" | "include"; rolling_years: 1 | 3 | 5; candidate_limit: number; offset: number;
};
export type ScreenCriterion = { key: string; label: string; operator: string; threshold: number | string; value: number | string | null; unit: string; source: string | null; status: "PASS" | "FAIL" | "UNAVAILABLE" };
export type ScreenResult = Pick<Analysis, "fund" | "metrics" | "rolling" | "facts" | "managers" | "portfolio" | "sources" | "warnings"> & {
  criteria: ScreenCriterion[]; matched: boolean; evidence_complete: boolean;
};
export type ScreenResponse = { total_candidates: number; offset: number; analysed: number; matched: number; results: ScreenResult[]; warnings: string[]; fetched_at: string };
export type SIPPortfolioEntry = { canonical_id: string; monthly_sip: number };
export type PortfolioAllocationSlice = { label: string; monthly_sip: number; allocation_percent: number; fund_count: number };
export type PortfolioExposure = { name: string; exposure_percent: number; fund_count: number; funds: string[] };
export type SIPPortfolioAnalysis = {
  total_monthly_sip: number;
  funds: { fund: Fund; monthly_sip: number; allocation_percent: number; risk: string | null; holdings_count: number; holdings_as_of: string | null }[];
  category_allocation: PortfolioAllocationSlice[];
  asset_allocation: PortfolioAllocationSlice[];
  risk_allocation: PortfolioAllocationSlice[];
  sector_exposure: PortfolioExposure[];
  common_holdings: PortfolioExposure[];
  pairwise_overlap: { fund_a_id: string; fund_a_name: string; fund_b_id: string; fund_b_name: string; common_holdings: number; overlap_percent: number | null; status: "available" | "unavailable"; note: string | null }[];
  holdings_coverage_percent: number;
  market_cap_status: "unavailable";
  market_cap_note: string;
  warnings: string[];
  fetched_at: string;
};
export type MarketRegime = {
  benchmark: string; status: "available" | "unavailable"; source: string; source_url: string; as_of: string | null;
  close: number | null; drawdown_1y_percent: number | null; return_6m_percent: number | null; versus_200d_average_percent: number | null;
  pe: number | null; pe_percentile: number | null; pb: number | null; pb_percentile: number | null; dividend_yield: number | null;
  valuation_state: "below historical range" | "within historical range" | "elevated" | "extreme" | "unavailable";
  history_start: string | null; valuation_observations: number; note: string | null;
};
export type StatisticalSignal = {
  label: string; value: string; status: "positive" | "neutral" | "warning" | "negative" | "unavailable"; explanation: string;
};
export type ManagerTenurePerformance = {
  name: string; tenure_start: string | null; tenure_years: number | null; experience: string | null;
  other_funds: string[]; source: string; source_url: string; nav_coverage_start: string | null;
  monthly_observations: number; annualized_return_percent: number | null;
  annualized_volatility_percent: number | null; max_drawdown_percent: number | null;
  positive_months_percent: number | null; status: "established" | "developing" | "recent" | "tenure unavailable";
  note: string;
};
export type FundManagerAnalysis = {
  status: "established" | "mixed" | "recent transition" | "unavailable"; summary: string;
  managers: ManagerTenurePerformance[]; shortest_tenure_years: number | null;
  source: string | null; source_url: string | null; warnings: string[];
};
export type StatisticalSIPResponse = {
  fund: Fund;
  action: "invest now" | "phase in / wait for better entry" | "avoid this fund" | "insufficient data";
  confidence: "low" | "medium" | "high"; headline: string;
  history: { monthly_observations: number; start_date: string; end_date: string; annualized_return_percent: number;
    annualized_volatility_percent: number; downside_deviation_percent: number; max_drawdown_percent: number;
    positive_months_percent: number; worst_month_percent: number; best_month_percent: number };
  forecast: { horizon_years: number; monthly_sip: number; total_contributions: number; p10_value: number; p25_value: number;
    median_value: number; p75_value: number; p90_value: number; probability_below_contributions_percent: number;
    probability_above_12pct_return_percent: number; simulations: number };
  backtest: { window_years: number; windows: number; profitable_windows_percent: number | null;
    median_annualized_return_percent: number | null; worst_annualized_return_percent: number | null;
    best_annualized_return_percent: number | null; note: string | null };
  manager_analysis: FundManagerAnalysis;
  market_regime: MarketRegime | null; signals: StatisticalSignal[]; reasons: string[]; risks: string[];
  review_trigger: string; history_source: string; history_source_url: string; methodology_version: string;
  warnings: string[]; fetched_at: string;
};
export type SourceStatus = { id: string; name: string; status: string; enabled: boolean; last_success: string | null; message: string | null; capabilities: string[]; adapter_version: string };
export type IPOIssue = {
  canonical_id: string; company_name: string; symbol: string; exchange: "NSE" | "BSE";
  board: "Mainboard" | "SME"; series: string; status: "open" | "upcoming" | "closed";
  issue_start: string; issue_end: string; price_band_text: string | null; price_min: number | null;
  price_max: number | null; issue_size_shares: number | null; shares_offered: number | null;
  shares_bid: number | null; subscription_times: number | null; source: string; source_url: string;
  fetched_at: string;
};
export type IPOCatalogueResponse = {
  issues: IPOIssue[]; total: number; open_count: number; upcoming_count: number; source: string;
  source_url: string; warnings: string[]; fetched_at: string;
};
export type IPODocument = {
  kind: "DRHP" | "RHP" | "Prospectus" | "Advertisement" | "In-principle XBRL" | "Abridged prospectus XBRL" | "Final-listing XBRL" | "Issuer presentation";
  label: string; url: string; filed_on: string | null; file_size: string | null; status: string | null;
  source: string; source_url: string;
};
export type IPOResearchItem = { label: string; value: string | null; status: "available" | "unavailable"; note: string | null };
export type IPOResearchSection = {
  key: "company" | "offer" | "business" | "promoters" | "directors" | "objects" | "financials" | "valuation" | "litigation";
  title: string; description: string; items: IPOResearchItem[]; source_url: string; available: boolean;
};
export type IPOResearchResponse = {
  issue: IPOIssue; match_status: "exact" | "unavailable"; matched_company: string | null; document_status: string | null;
  documents: IPODocument[]; sections: IPOResearchSection[]; warnings: string[]; source: string; source_url: string;
  fetched_at: string;
};
export type IPOTransaction = {
  id: string; type: "buy" | "sell"; date: string; quantity: number; price: number; fees: number;
};
export type IPOPortfolioEntry = {
  id: string; canonical_id: string; company_name: string; symbol: string; exchange: "NSE" | "BSE";
  board: "Mainboard" | "SME"; status: "planned" | "applied" | "allotted" | "refunded" | "listed" | "closed";
  application_date: string; lots_applied: number; lot_size: number; bid_price: number;
  allotment_date: string; shares_allotted: number; refund_amount: number; refund_date: string;
  listing_date: string; listing_price: number | null; current_price: number | null; price_as_of: string;
  transactions: IPOTransaction[];
};
