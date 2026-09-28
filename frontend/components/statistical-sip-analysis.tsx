"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, BarChart3, CircleHelp, ExternalLink, Loader2, ShieldCheck, TrendingUp, UserRound } from "lucide-react";
import { api, dateLabel, fmt } from "@/lib/api";
import type { Fund, SIPPortfolioEntry, StatisticalSIPResponse } from "@/lib/types";

type Props = { entries: SIPPortfolioEntry[]; funds: Fund[] };

export function StatisticalSIPAnalysis({ entries, funds }: Props) {
  const [fundId, setFundId] = useState(entries[0]?.canonical_id || "");
  const selectedEntry = entries.find(item => item.canonical_id === fundId);
  const [monthlySip, setMonthlySip] = useState(selectedEntry?.monthly_sip || 5000);
  const [horizonYears, setHorizonYears] = useState<3 | 5 | 10>(5);
  const [submitted, setSubmitted] = useState<{ fundId: string; monthlySip: number; horizonYears: 3 | 5 | 10; token: number } | null>(null);
  useEffect(() => {
    if (!entries.some(item => item.canonical_id === fundId)) setFundId(entries[0]?.canonical_id || "");
  }, [entries, fundId]);
  useEffect(() => {
    const entry = entries.find(item => item.canonical_id === fundId);
    if (entry) setMonthlySip(entry.monthly_sip);
  }, [fundId, entries]);
  const result = useQuery({
    queryKey: ["statistical-sip", submitted?.token],
    queryFn: ({ signal }) => api<StatisticalSIPResponse>("sip/statistical-analysis", {
      method: "POST", headers: { "Content-Type": "application/json" }, signal,
      body: JSON.stringify({ canonical_id: submitted?.fundId, monthly_sip: submitted?.monthlySip,
        horizon_years: submitted?.horizonYears, simulations: 4000 }),
    }),
    enabled: submitted !== null,
  });
  const valid = Boolean(fundId) && Number.isFinite(monthlySip) && monthlySip > 0;

  return <section className="decision-workspace statistical-workspace">
    <div className="decision-heading"><div><span className="eyebrow">STATISTICAL SIP ANALYSIS</span><h2>Should I start this SIP now?</h2><p>Select one fund. The model tests its NAV history, downside risk, SIP outcomes, current manager tenure and benchmark valuation.</p></div><Activity size={42} /></div>
    <form className="statistical-form" onSubmit={event => { event.preventDefault(); setSubmitted({ fundId, monthlySip, horizonYears, token: Date.now() }); }}>
      <label>Fund to analyse<select value={fundId} onChange={event => { setFundId(event.target.value); setSubmitted(null); }}><option value="">Select a fund</option>{entries.map(entry => { const fund = funds.find(item => item.canonical_id === entry.canonical_id); return <option key={entry.canonical_id} value={entry.canonical_id}>{fund?.scheme || entry.canonical_id}</option>; })}</select></label>
      <label>Monthly SIP<span className="money-input">₹<input type="number" min="100" max="100000000" step="100" value={monthlySip} onChange={event => { setMonthlySip(Number(event.target.value)); setSubmitted(null); }} /></span></label>
      <label>Analysis horizon<select value={horizonYears} onChange={event => { setHorizonYears(Number(event.target.value) as 3 | 5 | 10); setSubmitted(null); }}><option value={3}>3 years</option><option value={5}>5 years</option><option value={10}>10 years</option></select></label>
      <button className="primary-button" type="submit" disabled={!valid || result.isFetching}>{result.isFetching ? <Loader2 className="spin" size={16} /> : <BarChart3 size={16} />}{result.isFetching ? "Running 4,000 scenarios…" : "Run statistical analysis"}</button>
    </form>
    {entries.length === 0 && <div className="decision-inline-warning"><CircleHelp size={17} />Add a fund to the SIP plan above before running this analysis.</div>}
    <div className="model-note"><ShieldCheck size={18} /><p><strong>No personal-finance questionnaire.</strong> This result analyses the selected fund and its market conditions. It does not manage your income, expenses or debt.</p></div>
    {result.isError && <div className="error-box" role="alert"><h3>The statistical analysis could not be completed.</h3><p>{result.error.message}</p><button className="secondary-button" onClick={() => result.refetch()}>Try again <ArrowRight size={15} /></button></div>}
    {result.data && <StatisticalResults result={result.data} />}
  </section>;
}

function StatisticalResults({ result }: { result: StatisticalSIPResponse }) {
  const f = result.forecast;
  const actionClass = result.action === "invest now" ? "supportive" : result.action === "avoid this fund" ? "concern" : "watch";
  return <div className="decision-results statistical-results">
    <article className={`decision-verdict decision-${actionClass}`}><div><span>MODEL RESULT · {result.confidence.toUpperCase()} EVIDENCE CONFIDENCE</span><h2>{result.action}</h2><p>{result.headline}</p></div><TrendingUp size={38} /></article>
    <div className="forecast-summary">
      <div><span>Total contributions</span><strong>₹{fmt(f.total_contributions, 0)}</strong></div>
      <div><span>Weak path · 10th percentile</span><strong>₹{fmt(f.p10_value, 0)}</strong></div>
      <div className="forecast-primary"><span>Median projected value</span><strong>₹{fmt(f.median_value, 0)}</strong></div>
      <div><span>Strong path · 90th percentile</span><strong>₹{fmt(f.p90_value, 0)}</strong></div>
    </div>
    <div className="forecast-range"><span>10%</span><i><em style={{ left: `${Math.max(2, Math.min(96, f.p10_value / f.p90_value * 100))}%` }} /><b style={{ left: `${Math.max(2, Math.min(96, f.median_value / f.p90_value * 100))}%` }} /></i><span>90%</span><small>Distribution from {f.simulations.toLocaleString("en-IN")} block-bootstrap SIP paths. The centre marker is the median.</small></div>
    <div className="stat-grid">
      <article><span>Chance below contributions</span><strong>{fmt(f.probability_below_contributions_percent, 1)}%</strong><small>After {f.horizon_years} years</small></article>
      <article><span>Historical return</span><strong>{fmt(result.history.annualized_return_percent, 1)}%</strong><small>Annualized</small></article>
      <article><span>Historical volatility</span><strong>{fmt(result.history.annualized_volatility_percent, 1)}%</strong><small>Annualized monthly volatility</small></article>
      <article><span>Maximum drawdown</span><strong>{fmt(result.history.max_drawdown_percent, 1)}%</strong><small>Peak to trough</small></article>
    </div>
    <section className="signal-panel"><div className="section-heading"><div><span className="eyebrow">WHY THE MODEL CHOSE THIS</span><h2>Decision signals</h2></div><span className="subtle">{result.history.monthly_observations} monthly observations</span></div><div className="signal-list">{result.signals.map(signal => <article key={signal.label}><i className={`signal-dot signal-${signal.status}`} /><div><strong>{signal.label}</strong><p>{signal.explanation}</p></div><b>{signal.value}</b></article>)}</div></section>
    <div className="statistical-detail-grid">
      <article className="decision-section"><h3>Walk-forward check</h3><p className="subtle">How the SIP actually behaved across historical start dates.</p><div className="detail-values"><div><span>Windows tested</span><strong>{result.backtest.windows}</strong></div><div><span>Profitable windows</span><strong>{result.backtest.profitable_windows_percent == null ? "Unavailable" : `${fmt(result.backtest.profitable_windows_percent, 1)}%`}</strong></div><div><span>Median annualized SIP return</span><strong>{result.backtest.median_annualized_return_percent == null ? "Unavailable" : `${fmt(result.backtest.median_annualized_return_percent, 1)}%`}</strong></div><div><span>Worst annualized SIP return</span><strong>{result.backtest.worst_annualized_return_percent == null ? "Unavailable" : `${fmt(result.backtest.worst_annualized_return_percent, 1)}%`}</strong></div></div></article>
      <article className="decision-section"><h3>Current market condition</h3>{!result.market_regime ? <p className="subtle">No supported benchmark mapping for this category.</p> : result.market_regime.status === "unavailable" ? <p className="subtle">{result.market_regime.note}</p> : <><span className={`decision-state state-${result.market_regime.valuation_state === "extreme" ? "concern" : result.market_regime.valuation_state === "elevated" ? "watch" : "supportive"}`}>{result.market_regime.valuation_state}</span><div className="detail-values"><div><span>Benchmark</span><strong>{result.market_regime.benchmark}</strong></div><div><span>P/E percentile</span><strong>{fmt(result.market_regime.pe_percentile, 0)}th</strong></div><div><span>P/B percentile</span><strong>{fmt(result.market_regime.pb_percentile, 0)}th</strong></div><div><span>Vs 200-day average</span><strong>{fmt(result.market_regime.versus_200d_average_percent, 1)}%</strong></div></div><a className="text-button" href={result.market_regime.source_url} target="_blank" rel="noreferrer">Open NSE Indices source <ExternalLink size={12} /></a></>}</article>
    </div>
    <ManagerAnalysis result={result} />
    <div className="decision-balance"><article><h3>Evidence supporting the result</h3>{result.reasons.map(item => <p key={item}>{item}</p>)}</article><article><h3>Risk evidence</h3>{result.risks.map(item => <p key={item}>{item}</p>)}</article></div>
    <div className="decision-review"><TrendingUp size={20} /><div><strong>When to run it again</strong><p>{result.review_trigger}</p></div></div>
    <div className="methodology-note"><strong>Method: moving-block bootstrap + walk-forward SIP tests + manager-tenure evidence + NSE valuation regime.</strong><p>Historical NAV: <a href={result.history_source_url} target="_blank" rel="noreferrer">{result.history_source}</a>. Data range {dateLabel(result.history.start_date)} to {dateLabel(result.history.end_date)}. Version {result.methodology_version}.</p></div>
    <div className="portfolio-notes">{result.warnings.map((warning, index) => <p key={index}><CircleHelp size={15} />{warning}</p>)}</div>
  </div>;
}

function ManagerAnalysis({ result }: { result: StatisticalSIPResponse }) {
  const analysis = result.manager_analysis;
  const state = analysis.status === "established" ? "supportive" : analysis.status === "unavailable" ? "neutral" : "watch";
  return <section className="manager-analysis-panel">
    <div className="manager-analysis-heading"><div><span className="eyebrow">FUND MANAGER ANALYSIS</span><h2>Current team and tenure-period evidence</h2></div><span className={`decision-state state-${state}`}>{analysis.status}</span></div>
    <p className="manager-summary">{analysis.summary}</p>
    {analysis.managers.length === 0 ? <div className="manager-empty"><UserRound size={20} /><span>No verified manager record is available for this scheme.</span></div> :
      <div className="manager-analysis-grid">{analysis.managers.map(manager => <article key={`${manager.name}-${manager.source}`}>
        <div className="manager-card-head"><span className="manager-avatar"><UserRound size={18} /></span><div><h3>{manager.name}</h3><a href={manager.source_url} target="_blank" rel="noreferrer">{manager.source} source <ExternalLink size={11} /></a></div><span className={`manager-status manager-status-${manager.status.replaceAll(" ", "-")}`}>{manager.status}</span></div>
        <div className="manager-tenure"><div><span>Reported tenure</span><strong>{manager.tenure_years == null ? "Unavailable" : `${fmt(manager.tenure_years, 1)} years`}</strong><small>{manager.tenure_start ? `Since ${dateLabel(manager.tenure_start)}` : "Start date not supplied"}</small></div><div><span>NAV months tested</span><strong>{manager.monthly_observations || "—"}</strong><small>{manager.nav_coverage_start ? `From ${dateLabel(manager.nav_coverage_start)}` : "Insufficient tenure data"}</small></div></div>
        <div className="manager-metrics"><div><span>Fund return</span><strong>{manager.annualized_return_percent == null ? "—" : `${fmt(manager.annualized_return_percent, 1)}%`}</strong></div><div><span>Volatility</span><strong>{manager.annualized_volatility_percent == null ? "—" : `${fmt(manager.annualized_volatility_percent, 1)}%`}</strong></div><div><span>Max drawdown</span><strong>{manager.max_drawdown_percent == null ? "—" : `${fmt(manager.max_drawdown_percent, 1)}%`}</strong></div><div><span>Positive months</span><strong>{manager.positive_months_percent == null ? "—" : `${fmt(manager.positive_months_percent, 1)}%`}</strong></div></div>
        {manager.experience && <p className="manager-experience"><strong>Provider profile:</strong> {manager.experience}</p>}
        {manager.other_funds.length > 0 && <p className="manager-other-funds"><strong>Other reported funds:</strong> {manager.other_funds.slice(0, 3).join(", ")}{manager.other_funds.length > 3 ? ` +${manager.other_funds.length - 3} more` : ""}</p>}
        <p className="manager-note">{manager.note}</p>
      </article>)}</div>}
    <div className="manager-warnings">{analysis.warnings.map(item => <p key={item}><CircleHelp size={14} />{item}</p>)}</div>
  </section>;
}
