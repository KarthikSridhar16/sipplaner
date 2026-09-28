"use client";

import { useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, BarChart3, CircleHelp, Layers3, Loader2, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { api, dateLabel, fmt } from "@/lib/api";
import { StatisticalSIPAnalysis } from "@/components/statistical-sip-analysis";
import type { Fund, PortfolioAllocationSlice, SIPPortfolioAnalysis, SIPPortfolioEntry } from "@/lib/types";

type Props = {
  watchlistIds: string[];
  entries: SIPPortfolioEntry[];
  onSave: (entries: SIPPortfolioEntry[]) => void;
  onOpen: (id: string) => void;
  onDiscover: () => void;
};

export function PortfolioWorkspace({ watchlistIds, entries, onSave, onOpen, onDiscover }: Props) {
  const [submitted, setSubmitted] = useState<{ entries: SIPPortfolioEntry[]; token: number } | null>(null);
  const fundQueries = useQueries({ queries: watchlistIds.map(id => ({
    queryKey: ["portfolio-fund", id], queryFn: () => api<Fund>(`funds/${encodeURIComponent(id)}`), staleTime: 60_000,
  })) });
  const funds = new Map<string, Fund>();
  watchlistIds.forEach((id, index) => { const fund = fundQueries[index]?.data; if (fund) funds.set(id, fund); });
  const analysis = useQuery({
    queryKey: ["sip-portfolio-analysis", submitted?.token],
    queryFn: ({ signal }) => api<SIPPortfolioAnalysis>("portfolio/analyse", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries: submitted?.entries, rolling_years: 3 }), signal,
    }),
    enabled: submitted !== null,
  });
  const canAnalyse = entries.length > 0 && entries.every(entry => Number.isFinite(entry.monthly_sip) && entry.monthly_sip > 0);
  const total = entries.reduce((sum, entry) => sum + (Number.isFinite(entry.monthly_sip) ? entry.monthly_sip : 0), 0);

  function add(id: string) {
    if (entries.some(entry => entry.canonical_id === id) || entries.length >= 12) return;
    onSave([...entries, { canonical_id: id, monthly_sip: 5000 }]);
    setSubmitted(null);
  }
  function update(id: string, amount: number) {
    onSave(entries.map(entry => entry.canonical_id === id ? { ...entry, monthly_sip: amount } : entry));
    setSubmitted(null);
  }
  function remove(id: string) {
    onSave(entries.filter(entry => entry.canonical_id !== id));
    setSubmitted(null);
  }

  return <>
    <div className="simple-heading"><div className="eyebrow">SEE THE WHOLE SIP</div><h1>SIP portfolio</h1><p>Allocate your monthly SIP, then inspect category, risk, sector and disclosed-holdings concentration.</p></div>
    <section className="portfolio-builder">
      <div className="section-heading"><div><h2>Monthly SIP plan</h2><span className="subtle">Fund selections and amounts stay in this browser</span></div><span className="portfolio-total">₹{fmt(total, 0)} <small>per month</small></span></div>
      {entries.length === 0 ? <div className="portfolio-empty"><Layers3 size={28} /><div><strong>Your SIP plan is empty.</strong><p>Add a saved fund below, or discover and save funds first.</p></div></div> : <div className="portfolio-entry-list">{entries.map(entry => {
        const fund = funds.get(entry.canonical_id);
        return <div className="portfolio-entry" key={entry.canonical_id}><div className="fund-icon">{fund ? fund.amc.split(" ").slice(0, 2).map(word => word[0]).join("") : "MF"}</div><div className="portfolio-entry-name"><strong>{fund?.scheme || entry.canonical_id}</strong><small>{fund ? `${categoryLabel(fund.category)} · ${fund.plan} ${fund.option}` : "Loading fund identity…"}</small></div><label>Monthly SIP<span>₹<input aria-label={`Monthly SIP for ${fund?.scheme || entry.canonical_id}`} type="number" min="1" max="100000000" step="500" value={Number.isFinite(entry.monthly_sip) ? entry.monthly_sip : ""} onChange={event => update(entry.canonical_id, Number(event.target.value))} /></span></label><button className="icon-button" aria-label={`Remove ${fund?.scheme || entry.canonical_id} from SIP portfolio`} onClick={() => remove(entry.canonical_id)}><Trash2 size={17} /></button></div>;
      })}</div>}
      <div className="portfolio-builder-actions"><button className="primary-button" disabled={!canAnalyse || analysis.isFetching} onClick={() => setSubmitted({ entries: entries.map(entry => ({ ...entry })), token: Date.now() })}>{analysis.isFetching ? <Loader2 className="spin" size={16} /> : <BarChart3 size={16} />}{analysis.isFetching ? "Analysing live data…" : "Analyse SIP portfolio"}</button><span>{entries.length}/12 funds</span></div>
    </section>

    <section className="portfolio-watchlist"><div className="section-heading"><div><h2>Add from your watchlist</h2><span className="subtle">Only saved funds are offered here</span></div><button className="text-button" onClick={onDiscover}>Discover funds <ArrowRight size={14} /></button></div>
      {watchlistIds.length === 0 ? <div className="empty-state"><ShieldCheck size={27} /><h3>Save a fund to begin</h3><p>Use Discover funds or the screener, then return here.</p><button className="primary-button" onClick={onDiscover}>Discover funds <ArrowRight size={15} /></button></div> : <div className="portfolio-watchlist-grid">{watchlistIds.map((id, index) => {
        const fund = fundQueries[index]?.data; const added = entries.some(entry => entry.canonical_id === id);
        return <article key={id}><div><strong>{fund?.scheme || id}</strong><small>{fund ? categoryLabel(fund.category) : "Loading…"}</small></div><button className="secondary-button" disabled={added || entries.length >= 12 || !fund} onClick={() => add(id)}>{added ? "Added" : <><Plus size={14} /> Add</>}</button></article>;
      })}</div>}
    </section>

    {analysis.isError && <div className="error-box" role="alert"><h3>We couldn’t analyse this portfolio.</h3><p>{analysis.error.message}</p><button className="secondary-button" onClick={() => analysis.refetch()}>Try again <ArrowRight size={15} /></button></div>}
    {analysis.data && <PortfolioResults data={analysis.data} onOpen={onOpen} />}
    <StatisticalSIPAnalysis entries={entries} funds={[...funds.values()]} />
  </>;
}

function PortfolioResults({ data, onOpen }: { data: SIPPortfolioAnalysis; onOpen: (id: string) => void }) {
  const largestSector = data.sector_exposure[0];
  return <section className="portfolio-results">
    <div className="section-heading"><div><span className="eyebrow">PORTFOLIO VIEW</span><h2>How the monthly SIP is distributed</h2></div><span className="subtle">Fetched {dateLabel(data.fetched_at)}</span></div>
    <div className="portfolio-summary"><div><span>Monthly SIP</span><strong>₹{fmt(data.total_monthly_sip, 0)}</strong></div><div><span>Funds</span><strong>{data.funds.length}</strong></div><div><span>Holdings coverage</span><strong>{fmt(data.holdings_coverage_percent, 0)}%</strong></div><div><span>Largest sector</span><strong>{largestSector ? `${largestSector.name} ${fmt(largestSector.exposure_percent, 1)}%` : "Unavailable"}</strong></div></div>
    <div className="portfolio-fund-allocation">{data.funds.map(item => <article key={item.fund.canonical_id}><div><span>{fmt(item.allocation_percent, 1)}%</span><strong>{item.fund.scheme}</strong><small>₹{fmt(item.monthly_sip, 0)}/month · {item.risk || "Risk unavailable"} · {item.holdings_count} disclosed holdings</small></div><button className="text-button" onClick={() => onOpen(item.fund.canonical_id)}>Open fund <ArrowUpRight size={13} /></button><i><em style={{ width: `${Math.min(item.allocation_percent, 100)}%` }} /></i></article>)}</div>
    <div className="portfolio-grid"><AllocationCard title="Category allocation" items={data.category_allocation} /><AllocationCard title="Asset grouping" items={data.asset_allocation} note="Grouped from the AMFI scheme category." /><AllocationCard title="Riskometer allocation" items={data.risk_allocation} /><ExposureCard title="Weighted sector exposure" items={data.sector_exposure.slice(0, 8)} /></div>
    <div className="portfolio-grid overlap-grid"><article className="portfolio-card"><div className="card-heading"><h3>Pairwise fund overlap</h3><span>DISCLOSED HOLDINGS</span></div>{data.pairwise_overlap.length === 0 ? <p className="subtle portfolio-card-empty">Add a second fund to calculate pairwise overlap.</p> : <div className="overlap-list">{data.pairwise_overlap.map(item => <div key={`${item.fund_a_id}-${item.fund_b_id}`}><p><strong>{item.fund_a_name}</strong><span>and</span><strong>{item.fund_b_name}</strong></p><b>{item.overlap_percent == null ? "Unavailable" : `${fmt(item.overlap_percent)}%`}</b><small>{item.status === "available" ? `${item.common_holdings} common holdings` : item.note}</small></div>)}</div>}</article><article className="portfolio-card"><div className="card-heading"><h3>Shared holdings</h3><span>TOP 10</span></div>{data.common_holdings.length === 0 ? <p className="subtle portfolio-card-empty">No verified common holdings were found, or holdings data is unavailable.</p> : <div className="shared-holdings">{data.common_holdings.slice(0, 10).map(item => <div key={item.name}><span><strong>{item.name}</strong><small>Held by {item.fund_count} funds</small></span><b>{fmt(item.exposure_percent)}%</b></div>)}</div>}</article></div>
    <div className="portfolio-limit"><CircleHelp size={20} /><div><strong>Market-cap exposure is unavailable</strong><p>{data.market_cap_note}</p></div></div>
    <div className="portfolio-notes">{data.warnings.map((warning, index) => <p key={index}><CircleHelp size={15} />{warning}</p>)}</div>
  </section>;
}

function AllocationCard({ title, items, note }: { title: string; items: PortfolioAllocationSlice[]; note?: string }) {
  return <article className="portfolio-card"><h3>{title}</h3>{note && <p className="subtle">{note}</p>}<div className="allocation-bars">{items.map(item => <div key={item.label}><span>{item.label}<b>{fmt(item.allocation_percent, 1)}%</b></span><i><em style={{ width: `${Math.min(item.allocation_percent, 100)}%` }} /></i><small>₹{fmt(item.monthly_sip, 0)}/month · {item.fund_count} fund{item.fund_count === 1 ? "" : "s"}</small></div>)}</div></article>;
}

function ExposureCard({ title, items }: { title: string; items: SIPPortfolioAnalysis["sector_exposure"] }) {
  return <article className="portfolio-card"><h3>{title}</h3><p className="subtle">SIP-weighted disclosed fund portfolios.</p>{items.length === 0 ? <p className="subtle portfolio-card-empty">Verified sector data is unavailable.</p> : <div className="allocation-bars">{items.map(item => <div key={item.name}><span>{item.name}<b>{fmt(item.exposure_percent, 1)}%</b></span><i><em style={{ width: `${Math.min(item.exposure_percent, 100)}%` }} /></i><small>Across {item.fund_count} fund{item.fund_count === 1 ? "" : "s"}</small></div>)}</div>}</article>;
}

function categoryLabel(category: string) {
  return category.replace(/^(Equity|Debt|Hybrid|Other) Schemes?\s*-\s*/, "");
}
