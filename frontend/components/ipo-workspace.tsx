"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Bookmark, Building2, CircleHelp, ExternalLink, FileSearch, Loader2, RefreshCw, Search, ShieldCheck, X } from "lucide-react";
import { api, dateLabel, fmt } from "@/lib/api";
import type { IPOCatalogueResponse, IPOIssue, IPOResearchResponse } from "@/lib/types";

type Props = { watchlist: string[]; onSave: (ids: string[]) => void };

export function IPOWorkspace({ watchlist, onSave }: Props) {
  const [query, setQuery] = useState("");
  const [board, setBoard] = useState<"" | "Mainboard" | "SME">("");
  const [status, setStatus] = useState<"" | "open" | "upcoming">("");
  const [selected, setSelected] = useState<string | null>(null);
  const catalogue = useQuery({ queryKey: ["ipo-catalogue"], queryFn: () => api<IPOCatalogueResponse>("ipos"), staleTime: 240_000 });
  const research = useQuery({ queryKey: ["ipo-research", selected], queryFn: () => api<IPOResearchResponse>(`ipos/${encodeURIComponent(selected!)}/research`), enabled: Boolean(selected), staleTime: 240_000 });
  useEffect(() => {
    if (!selected) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setSelected(null); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selected]);
  const issues = useMemo(() => (catalogue.data?.issues || []).filter(issue => {
    const term = query.trim().toLowerCase();
    return (!term || issue.company_name.toLowerCase().includes(term) || issue.symbol.toLowerCase().includes(term))
      && (!board || issue.board === board) && (!status || issue.status === status);
  }), [catalogue.data, query, board, status]);
  function toggle(id: string) {
    onSave(watchlist.includes(id) ? watchlist.filter(item => item !== id) : [...watchlist, id].slice(0, 50));
  }

  return <>
    <div className="simple-heading ipo-heading"><div className="eyebrow">RESEARCH THE ISSUE, NOT THE HYPE</div><h1>IPO research</h1><p>Explore live Indian public issues with exchange-sourced terms, dates and subscription evidence.</p></div>
    <section className="ipo-summary">
      <div><span>Open issues</span><strong>{catalogue.data?.open_count ?? "—"}</strong></div>
      <div><span>Forthcoming</span><strong>{catalogue.data?.upcoming_count ?? "—"}</strong></div>
      <div><span>In your IPO watchlist</span><strong>{watchlist.length}</strong></div>
      <div className="ipo-source"><ShieldCheck size={18} /><span>Primary source</span><strong>NSE India</strong></div>
    </section>
    <section className="ipo-controls">
      <label className="ipo-search"><Search size={18} /><input aria-label="Search IPOs" placeholder="Company or symbol" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <select aria-label="IPO status" value={status} onChange={event => setStatus(event.target.value as typeof status)}><option value="">Open + upcoming</option><option value="open">Open now</option><option value="upcoming">Upcoming</option></select>
      <select aria-label="IPO board" value={board} onChange={event => setBoard(event.target.value as typeof board)}><option value="">All boards</option><option value="Mainboard">Mainboard</option><option value="SME">SME</option></select>
      <button className="secondary-button" onClick={() => catalogue.refetch()} disabled={catalogue.isFetching}><RefreshCw className={catalogue.isFetching ? "spin" : ""} size={15} />Refresh</button>
    </section>
    {catalogue.isPending && <div className="loading" role="status"><Loader2 className="spin" size={24} /><p>Loading official IPO issues…</p></div>}
    {catalogue.isError && <div className="error-box" role="alert"><h3>IPO catalogue unavailable</h3><p>{catalogue.error.message}</p><button className="secondary-button" onClick={() => catalogue.refetch()}>Try again</button></div>}
    {catalogue.data && <>
      <div className="section-heading ipo-result-heading"><div><h2>Current issue board</h2><span className="subtle">{issues.length} matching issues · fetched {new Date(catalogue.data.fetched_at).toLocaleString("en-IN")}</span></div><a className="text-button" href={catalogue.data.source_url} target="_blank" rel="noreferrer">Open official source <ExternalLink size={12} /></a></div>
      {issues.length === 0 ? <div className="empty-state"><Search size={27} /><h3>No matching IPOs</h3><p>Clear a filter or refresh the live exchange catalogue.</p></div> : <div className="ipo-grid">{issues.map(issue => <IPOCard key={issue.canonical_id} issue={issue} saved={watchlist.includes(issue.canonical_id)} onToggle={() => toggle(issue.canonical_id)} onResearch={() => setSelected(issue.canonical_id)} />)}</div>}
      {selected && <div className="ipo-research-modal" role="dialog" aria-modal="true" aria-label="IPO offer document research" onMouseDown={event => { if (event.target === event.currentTarget) setSelected(null); }}><div className="ipo-research-modal-body"><IPOResearchPanel data={research.data} pending={research.isPending} error={research.isError ? research.error : null} onRetry={() => research.refetch()} onClose={() => setSelected(null)} /></div></div>}
      <section className="ipo-watch-panel"><div><Bookmark size={22} /><div><span className="eyebrow">BROWSER-LOCAL IPO WATCHLIST</span><h2>{watchlist.length ? `${watchlist.length} issue${watchlist.length === 1 ? "" : "s"} being watched` : "No IPOs saved yet"}</h2><p>Save issues from the live board. Application, allotment and post-listing transaction tracking arrives in the IPO portfolio milestone.</p></div></div><span>{watchlist.length}/50</span></section>
      <section className="ipo-statistical-preview"><BarChart3 size={28} /><div><span className="eyebrow">STATISTICAL IPO ANALYSIS · VALIDATION REQUIRED</span><h2>Historical-cohort model is the next analytical layer</h2><p>FundLens will compare issue fundamentals, valuation, demand and market conditions with timestamped historical IPO outcomes. Apply/buy labels stay disabled until rolling-origin calibration and survivorship checks pass.</p></div></section>
      <div className="portfolio-notes">{catalogue.data.warnings.map(item => <p key={item}><CircleHelp size={15} />{item}</p>)}</div>
    </>}
  </>;
}

function IPOCard({ issue, saved, onToggle, onResearch }: { issue: IPOIssue; saved: boolean; onToggle: () => void; onResearch: () => void }) {
  const demand = issue.subscription_times == null ? "Unavailable" : `${fmt(issue.subscription_times, 2)}×`;
  return <article className="ipo-card">
    <div className="ipo-card-head"><span className="ipo-building"><Building2 size={19} /></span><div><h3>{issue.company_name}</h3><p>{issue.symbol} · {issue.exchange}</p></div><button className={`bookmark-button ${saved ? "saved" : ""}`} aria-label={`${saved ? "Remove" : "Save"} ${issue.company_name}`} aria-pressed={saved} onClick={onToggle}><Bookmark size={18} fill={saved ? "currentColor" : "none"} /></button></div>
    <div className="ipo-tags"><span className={`ipo-status ipo-status-${issue.status}`}>{issue.status}</span><span>{issue.board}</span></div>
    <div className="ipo-price"><span>PRICE BAND</span><strong>{issue.price_min == null ? "Unavailable" : issue.price_min === issue.price_max ? `₹${fmt(issue.price_max, 0)}` : `₹${fmt(issue.price_min, 0)} – ₹${fmt(issue.price_max, 0)}`}</strong></div>
    <div className="ipo-card-values"><div><span>Issue window</span><strong>{dateLabel(issue.issue_start)} – {dateLabel(issue.issue_end)}</strong></div><div><span>Live subscription</span><strong>{demand}</strong></div><div><span>Shares offered</span><strong>{issue.shares_offered == null ? "Unavailable" : fmt(issue.shares_offered, 0)}</strong></div><div><span>Shares bid</span><strong>{issue.shares_bid == null ? "Unavailable" : fmt(issue.shares_bid, 0)}</strong></div></div>
    <div className="ipo-card-foot"><span>Fetched {new Date(issue.fetched_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</span><a href={issue.source_url} target="_blank" rel="noreferrer">NSE source <ExternalLink size={11} /></a></div>
    <button className="ipo-research-button" onClick={onResearch}><FileSearch size={14} />Research offer document</button>
  </article>;
}

function IPOResearchPanel({ data, pending, error, onRetry, onClose }: { data?: IPOResearchResponse; pending: boolean; error: Error | null; onRetry: () => void; onClose: () => void }) {
  return <section className="ipo-research-panel">
    <div className="ipo-research-head"><div><span className="eyebrow">OFFICIAL OFFER-DOCUMENT EVIDENCE</span><h2>{data?.issue.company_name || "Loading issue research…"}</h2><p>{data ? `Exact-match status: ${data.match_status} · fetched ${new Date(data.fetched_at).toLocaleString("en-IN")}` : "Matching the issue to NSE offer documents."}</p></div><button className="icon-button" aria-label="Close IPO research" onClick={onClose}><X size={18} /></button></div>
    {pending && <div className="loading" role="status"><Loader2 className="spin" size={24} /><p>Loading official offer-document evidence…</p></div>}
    {error && <div className="error-box" role="alert"><h3>Issue research unavailable</h3><p>{error.message}</p><button className="secondary-button" onClick={onRetry}>Try again</button></div>}
    {data && <>
      <div className="ipo-document-strip"><div><strong>{data.documents.length}</strong><span>verified document links</span></div><div><strong>{data.sections.filter(section => section.available).length}/{data.sections.length}</strong><span>research sections available</span></div><div><strong>{data.document_status || "Not stated"}</strong><span>draft status</span></div></div>
      <div className="ipo-documents"><div className="section-heading"><div><h3>Official documents</h3><span className="subtle">Use the RHP or final prospectus when published.</span></div><a className="text-button" href={data.source_url} target="_blank" rel="noreferrer">NSE filings <ExternalLink size={11} /></a></div>{data.documents.length ? <div className="ipo-document-grid">{data.documents.map(document => <a key={`${document.kind}-${document.url}`} href={document.url} target="_blank" rel="noreferrer"><FileSearch size={17} /><span><strong>{document.label}</strong><small>{[document.filed_on ? dateLabel(document.filed_on) : null, document.file_size, document.status].filter(Boolean).join(" · ") || "Official filing"}</small></span><ExternalLink size={12} /></a>)}</div> : <p className="ipo-unavailable">No document URL was available in the exact NSE record.</p>}</div>
      <div className="ipo-research-sections">{data.sections.map(section => <article key={section.key} className={`ipo-research-section ${section.available ? "" : "unavailable"}`}><div><h3>{section.title}</h3><span className={`status ${section.available ? "status-available" : "status-unavailable"}`}>{section.available ? "Available" : "Unavailable"}</span></div><p>{section.description}</p><dl>{section.items.map((item, index) => <div key={`${item.label}-${index}`}><dt>{item.label}</dt><dd>{item.value || "Unavailable"}{item.note && <small>{item.note}</small>}</dd></div>)}</dl></article>)}</div>
      <div className="portfolio-notes">{data.warnings.map(item => <p key={item}><CircleHelp size={15} />{item}</p>)}</div>
    </>}
  </section>;
}
