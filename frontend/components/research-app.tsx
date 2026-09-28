"use client";

import { useEffect, useRef, useState } from "react";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, BarChart3, Bookmark, Check, ChevronRight,
  BriefcaseBusiness, Building2, CircleHelp, Database, ExternalLink, Layers3, LayoutDashboard, Loader2, Search, Settings2, ShieldCheck,
  SlidersHorizontal, Sparkles, TrendingUp, X } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, dateLabel, fmt } from "@/lib/api";
import { dashboardStorage, INITIAL, type Preferences } from "@/lib/storage";
import { PortfolioWorkspace } from "@/components/portfolio-workspace";
import { IPOWorkspace } from "@/components/ipo-workspace";
import { IPOPortfolioWorkspace } from "@/components/ipo-portfolio-workspace";
import type { Analysis, Comparison, Fund, Metric, Rules, ScreenFilters, ScreenResponse, ScreenResult, SourceStatus } from "@/lib/types";

type Tab = "search" | "dashboard" | "compare" | "screener" | "portfolio" | "ipo" | "ipoPortfolio" | "sources" | "settings";
const DEFAULT_RULES: Rules = { beta_max: 1, expense_ratio_max: 1, upside_capture_min: 100, downside_capture_max: 100 };
const RULE_FIELDS: [keyof Rules, string, number, number][] = [
  ["beta_max", "Maximum beta", 0, 5], ["expense_ratio_max", "TER below (%)", 0, 10],
  ["upside_capture_min", "Upside capture above (%)", 0, 1000], ["downside_capture_max", "Downside capture below (%)", -1000, 1000],
];
const SHORT_HINTS: Record<string, string> = {
  beta: "Sensitivity to the benchmark", standard_deviation: "Historical return variability", sharpe: "Return per unit of risk",
  alpha: "Provider-reported excess return", expense_ratio: "Annual total expense ratio", aum: "Published scheme assets",
  upside_capture: "Participation in rising markets", downside_capture: "Participation in falling markets", capture_ratio: "Upside relative to downside",
};

export function ResearchApp() {
  const [tab, setTab] = useState<Tab>("search");
  const [selected, setSelected] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<Preferences>(INITIAL);
  const [ready, setReady] = useState(false);
  const [storageError, setStorageError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("HDFC mid");
  const [debounced, setDebounced] = useState("");
  const [category, setCategory] = useState("");
  const [metric, setMetric] = useState<Metric | null>(null);
  const client = useQueryClient();

  useEffect(() => { try { setPrefs(dashboardStorage.load()); } catch { setStorageError("Browser storage could not be read. Changes will stay in this session unless storage becomes available."); } setReady(true); }, []);
  useEffect(() => { const timer = setTimeout(() => setDebounced(query.trim()), 400); return () => clearTimeout(timer); }, [query]);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(""), 3500); return () => clearTimeout(timer); }, [notice]);
  function save(next: Preferences) {
    setPrefs(next);
    try { dashboardStorage.save(next); setStorageError(""); } catch { setStorageError("Your browser could not save this change. It is available for this session only."); }
  }
  function toggle(id: string) {
    const exists = prefs.funds.includes(id);
    if (!exists && prefs.funds.length >= 30) { setNotice("Your watchlist holds up to 30 funds."); return; }
    save({ ...prefs, funds: exists ? prefs.funds.filter(f => f !== id) : [...prefs.funds, id] });
    setNotice(exists ? "Fund removed from your watchlist" : "Fund added to your watchlist");
  }
  function navigate(next: Tab) { setTab(next); setSelected(null); }
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api<SourceStatus[]>("source-status"), refetchInterval: 30_000 });
  const search = useQuery({
    queryKey: ["search", debounced, prefs.directOnly, prefs.growthOnly, category],
    queryFn: ({ signal }) => api<{ funds: Fund[]; total: number }>(`search?${new URLSearchParams({ q: debounced, plan: prefs.directOnly ? "Direct" : "", option: prefs.growthOnly ? "Growth" : "", category })}`, { signal }),
    enabled: ready && debounced.length >= 2 && tab === "search" && !selected,
  });
  const nav = [{ id: "search" as Tab, text: "Discover funds", icon: Search }, { id: "dashboard" as Tab, text: "My watchlist", icon: LayoutDashboard },
    { id: "compare" as Tab, text: "Compare funds", icon: BarChart3 },
    { id: "screener" as Tab, text: "Fund screener", icon: SlidersHorizontal },
    { id: "portfolio" as Tab, text: "SIP portfolio", icon: Layers3 },
    { id: "ipo" as Tab, text: "IPO research", icon: Building2 },
    { id: "ipoPortfolio" as Tab, text: "IPO portfolio", icon: BriefcaseBusiness },
    { id: "sources" as Tab, text: "Data sources", icon: Database }, { id: "settings" as Tab, text: "My preferences", icon: Settings2 }];

  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => navigate("search")} aria-label="FundLens home"><span className="brand-mark"><Layers3 size={24} /></span>FundLens<span className="brand-dot">.</span></button>
      <div className="workspace-label">YOUR RESEARCH SPACE</div>
      <nav aria-label="Main navigation">{nav.map(({ id, text, icon: Icon }) => <button key={id} onClick={() => navigate(id)} className={`nav-item ${tab === id ? "active" : ""}`} aria-current={tab === id ? "page" : undefined}><Icon size={19} />{text}{id === "dashboard" && <span className="nav-count">{prefs.funds.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="local-note"><ShieldCheck size={22} /><strong>Your research, your space.</strong><p>Your watchlist is saved in this browser. No account needed.</p></div><div className="profile"><div className="avatar">Y</div><div><strong>Personal workspace</strong><span>Local to this browser</span></div></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14} /><strong>{selected ? "Fund analysis" : nav.find(n => n.id === tab)?.text}</strong></div><div className="topbar-right"><span className="market-label">INDIA <span>·</span> INR</span><span className="beta-badge">EARLY ACCESS</span><span className="avatar small">Y</span></div></header>
      <main>
        {storageError && <div className="alert" role="alert">{storageError}</div>}
        {selected ? <FundAnalysis id={selected} rules={prefs.rules} saved={prefs.funds.includes(selected)} onToggle={() => toggle(selected)} onBack={() => setSelected(null)} onMetric={setMetric} /> : <>
          {tab === "search" && <>
            <div className="page-heading"><div><div className="eyebrow"><span />INDEPENDENT THINKING STARTS HERE</div><h1>Your next investment,<br /><span>better understood.</span></h1><p>Explore mutual funds with clear numbers and traceable sources.</p></div><div className="heading-art" aria-hidden="true"><div className="art-grid" /><span className="art-arrow"><TrendingUp size={92} strokeWidth={1.2} /></span><span className="art-label">A LITTLE MORE PERSPECTIVE.</span></div></div>
            <div className="summary-strip"><div><span className="stat-icon"><Search size={18} /></span><p>Research universe<strong>Indian mutual funds</strong></p></div><div><span className="stat-icon"><Bookmark size={18} /></span><p>In your watchlist<strong>{prefs.funds.length.toString().padStart(2, "0")} funds</strong></p></div><div><span className="stat-icon"><Database size={18} /></span><p>Research sources<strong>AMFI + live research feeds</strong></p></div><div className="summary-callout">Evidence over rankings.<br /><strong>Always your decision. <ArrowUpRight size={15} /></strong></div></div>
            <section className="search-panel" aria-label="Find a mutual fund"><div className="section-heading"><h2>Find your next fund</h2><span className="subtle">Start with a name, AMC, ISIN or scheme code</span></div><div className="search-control"><Search size={22} /><input aria-label="Search mutual funds" placeholder="Try HDFC Mid Cap or Parag Parikh…" value={query} onChange={e => setQuery(e.target.value)} />{query && <button className="icon-button" aria-label="Clear search" onClick={() => setQuery("")}><X size={17} /></button>}<span className="search-hint">SEARCH</span></div><div className="filter-row"><SlidersHorizontal size={16} /><label><input type="checkbox" checked={prefs.directOnly} onChange={e => save({ ...prefs, directOnly: e.target.checked })} />Direct plans</label><label><input type="checkbox" checked={prefs.growthOnly} onChange={e => save({ ...prefs, growthOnly: e.target.checked })} />Growth options</label><span className="filter-divider" /><select aria-label="Fund category" value={category} onChange={e => setCategory(e.target.value)}><option value="">All categories</option>{["Mid Cap", "Large Cap", "Small Cap", "Flexi Cap", "Debt", "Hybrid", "Index"].map(c => <option key={c}>{c}</option>)}</select><button className="text-button clear-filters" onClick={() => { setCategory(""); save({ ...prefs, directOnly: true, growthOnly: true }); }}>Reset filters</button></div></section>
            <div className="discovery-layout"><section><div className="section-heading result-heading"><h2>{debounced.length >= 2 ? "Search results" : "Where would you like to start?"} {search.data && debounced.length >= 2 && <span className="count-pill">{search.data.total}</span>}</h2>{search.isFetching && <Loader2 className="spin" size={17} />}</div>
              {debounced.length < 2 ? <div className="empty-state"><Search size={26} /><h3>A fund name is a good beginning.</h3><p>Enter at least two characters to search the AMFI catalogue.</p><div className="suggestions">{["HDFC mid", "Parag Parikh", "Nippon"].map(q => <button key={q} onClick={() => setQuery(q)}>{q}<ArrowUpRight size={14} /></button>)}</div></div> : search.isPending ? <Loading text="Looking up the latest AMFI catalogue…" /> : search.isError ? <ErrorBox error={search.error} retry={() => search.refetch()} /> : search.data?.funds.length === 0 ? <div className="empty-state"><Search size={28} /><h3>No matching funds</h3><p>Try a shorter name or turn off the Direct and Growth filters.</p></div> : <div className="fund-list">{search.data?.funds.map(f => <FundCard key={f.canonical_id} fund={f} saved={prefs.funds.includes(f.canonical_id)} onToggle={() => toggle(f.canonical_id)} onAnalyse={() => setSelected(f.canonical_id)} />)}</div>}
              {search.data && search.data.total > search.data.funds.length && <p className="subtle">Showing {search.data.funds.length} of {search.data.total} matches. Refine your search to see a specific scheme.</p>}
            </section><aside className="research-aside"><div className="guide-card"><span className="guide-icon"><Sparkles size={22} /></span><div className="eyebrow">THE FUNDLENS APPROACH</div><h3>Look beyond<br />the headline return.</h3><p>A clearer picture comes from asking better questions.</p><div className="guide-step"><span>01</span><div><strong>Is performance consistent?</strong><p>Explore returns across rolling periods.</p></div></div><div className="guide-step"><span>02</span><div><strong>How much risk comes with it?</strong><p>Read volatility and capture together.</p></div></div><div className="guide-step"><span>03</span><div><strong>Where did the numbers come from?</strong><p>Check the source behind each value.</p></div></div><div className="guide-foot">No scores. No automatic winners.<br />Just the evidence you need.</div></div><div className="source-note"><ShieldCheck size={21} /><div><strong>A source for every number</strong><p>Identity and latest NAV from AMFI, history from MFapi.in with an AMFI cross-check, and market context from NSE Indices.</p><button className="text-button" onClick={() => navigate("sources")}>Explore our sources <ArrowRight size={14} /></button></div></div></aside></div>
          </>}
          {tab === "dashboard" && <><SimpleHeading eyebrow="A LITTLE MORE INTENTION" title="Your watchlist" description="The funds you’re keeping an eye on, with current research a click away." /><div className="section-heading"><span className="subtle">{prefs.funds.length} saved funds · Stored in this browser</span><button className="secondary-button" onClick={() => client.invalidateQueries({ queryKey: ["saved-fund"] })}>Refresh NAVs</button></div>{prefs.funds.length === 0 ? <div className="empty-state large"><Bookmark size={34} /><h3>Make space for your shortlist.</h3><p>Save a fund while exploring to see it here.</p><button className="primary-button" onClick={() => navigate("search")}>Discover funds <ArrowRight size={17} /></button></div> : <div className="watchlist-grid">{prefs.funds.map(id => <SavedFund key={id} id={id} onToggle={() => toggle(id)} onAnalyse={() => setSelected(id)} />)}</div>}</>}
          {tab === "compare" && <ComparisonWorkspace ids={prefs.funds} rules={prefs.rules} onOpen={setSelected} onDiscover={() => navigate("search")} />}
          {tab === "screener" && <ScreenerWorkspace rules={prefs.rules} initial={prefs.screen} onSave={screen => save({ ...prefs, screen })} savedIds={prefs.funds} onToggle={toggle} onOpen={setSelected} />}
          {tab === "portfolio" && <PortfolioWorkspace watchlistIds={prefs.funds} entries={prefs.portfolio} onSave={portfolio => save({ ...prefs, portfolio })} onOpen={setSelected} onDiscover={() => navigate("search")} />}
          {tab === "ipo" && <IPOWorkspace watchlist={prefs.ipoWatchlist} onSave={ipoWatchlist => save({ ...prefs, ipoWatchlist })} />}
          {tab === "ipoPortfolio" && <IPOPortfolioWorkspace entries={prefs.ipoPortfolio} onSave={ipoPortfolio => save({ ...prefs, ipoPortfolio })} onResearch={() => navigate("ipo")} />}
          {tab === "sources" && <><SimpleHeading eyebrow="FOLLOW THE EVIDENCE" title="Behind the numbers" description="See where your research comes from and how each source is responding." />{sources.isError ? <ErrorBox error={sources.error} retry={() => sources.refetch()} /> : <div className="source-grid">{sources.data?.map(s => <article className="source-card" key={s.id}><div className="section-heading"><span className="source-symbol">{s.name.slice(0, 1)}</span><Status value={s.status} /></div><h2>{s.name}</h2><p>{s.id === "amfi" ? "Official scheme catalogue, identifiers and published latest NAV." : s.id === "nifty" ? "Official benchmark history and valuation observations for market-regime context." : s.id === "mfapi" ? "Full historical scheme NAV used only after a latest-value cross-check against AMFI." : s.id === "nse_ipo" ? "Official open and forthcoming IPO terms, dates and live subscription totals." : "Risk indicators, rolling-return statistics and market capture."}</p><div className="capabilities">{s.capabilities.map(c => <span key={c}>{c.replaceAll("_", " ")}</span>)}</div><div className="source-meta"><span>Last successful fetch</span><strong>{s.last_success ? new Date(s.last_success).toLocaleString("en-IN") : "No request yet"}</strong></div><div className="source-meta"><span>Adapter version</span><strong>{s.adapter_version}</strong></div>{s.message && <p className="warning-text">{s.message}</p>}</article>)}</div>}<div className="info-banner"><CircleHelp size={20} /><p>Status reflects recent requests, not a guarantee of availability. Data is fetched on demand and cached briefly. “Fetched” and “as of” dates are shown separately.</p></div></>}
          {tab === "settings" && <><SimpleHeading eyebrow="MAKE RESEARCH YOUR OWN" title="Your preferences" description="Set the questions you ask of every fund. These preferences stay in this browser." /><Settings rules={prefs.rules} onSave={rules => { save({ ...prefs, rules }); setNotice("Research preferences saved"); }} /><div className="info-banner"><ShieldCheck size={20} /><p>Pass and fail labels describe your chosen thresholds. They do not establish suitability or predict future performance.</p></div></>}
        </>}
        <footer><span>FundLens<span className="brand-dot">.</span> <span className="footer-divider">/</span> Research with perspective.</span><span>Historical performance does not predict future returns.</span></footer>
      </main>
    </div>
    {notice && <div className="toast" role="status"><Check size={17} />{notice}</div>}
    {metric && <MetricDialog metric={metric} onClose={() => setMetric(null)} />}
  </div>;
}

function SimpleHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) { return <div className="simple-heading"><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>; }
function Loading({ text }: { text: string }) { return <div className="loading" role="status"><Loader2 className="spin" size={24} /><p>{text}</p></div>; }
function ErrorBox({ error, retry }: { error: Error; retry: () => void }) { return <div className="error-box" role="alert"><h3>We couldn’t load this research.</h3><p>{error.message}</p><button className="secondary-button" onClick={retry}>Try again <ArrowRight size={15} /></button></div>; }
function Status({ value }: { value: string }) { return <span className={`status status-${value.toLowerCase().replaceAll(" ", "-")}`}>{value === "PASS" || value === "Healthy" || value === "Verified" || value === "Matched" ? <Check size={11} /> : null}{value}</span>; }
function categoryLabel(category: string) { return category.replace(/^(Equity|Debt|Hybrid|Other) Schemes?\s*-\s*/, ""); }

function FundCard({ fund, saved, onToggle, onAnalyse }: { fund: Fund; saved: boolean; onToggle: () => void; onAnalyse: () => void }) {
  return <article className="fund-card"><div className="fund-card-top"><div className="fund-icon">{fund.amc.split(" ").slice(0, 2).map(s => s[0]).join("")}</div><div className="fund-title"><h3>{fund.scheme}</h3><p>{fund.plan} <span>·</span> {fund.option_label}</p></div><button className={`bookmark-button ${saved ? "saved" : ""}`} aria-label={`${saved ? "Remove" : "Save"} ${fund.scheme}`} aria-pressed={saved} onClick={onToggle}><Bookmark size={19} fill={saved ? "currentColor" : "none"} /></button></div><div className="fund-tags"><span>{categoryLabel(fund.category)}</span><span>AMFI {fund.amfi_code}</span></div><div className="fund-card-bottom"><div><span className="label">LATEST NAV <span className="nav-asof">· {dateLabel(fund.nav.as_of)}</span></span><strong className="nav-value">₹{fmt(fund.nav.value)}{fund.nav.status === "stale" && <Status value="STALE" />}</strong></div><button className="analyse-button" onClick={onAnalyse}>Analyse fund <ArrowUpRight size={17} /></button></div><div className="fund-source-line"><ShieldCheck size={13} />AMFI identity <span>·</span> Additional sources checked on analysis</div></article>;
}

function SavedFund({ id, onToggle, onAnalyse }: { id: string; onToggle: () => void; onAnalyse: () => void }) {
  const data = useQuery({ queryKey: ["saved-fund", id], queryFn: () => api<Fund>(`funds/${encodeURIComponent(id)}`) });
  if (data.isError) return <div><ErrorBox error={data.error} retry={() => data.refetch()} /><button className="text-button" onClick={onToggle}>Remove unavailable fund {id}</button></div>;
  if (!data.data) return <Loading text="Refreshing saved fund…" />;
  return <FundCard fund={data.data} saved onToggle={onToggle} onAnalyse={onAnalyse} />;
}

type ComparisonValue = { main: string; detail?: string };
type ComparisonRow = { group: string; label: string; value: (analysis: Analysis) => ComparisonValue };

function ComparisonWorkspace({ ids, rules, onOpen, onDiscover }: { ids: string[]; rules: Rules | null; onOpen: (id: string) => void; onDiscover: () => void }) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const fundQueries = useQueries({ queries: ids.map(id => ({ queryKey: ["saved-fund", id], queryFn: () => api<Fund>(`funds/${encodeURIComponent(id)}`) })) });
  const funds = fundQueries.flatMap(query => query.data ? [query.data] : []);
  useEffect(() => {
    setSelectedIds(current => {
      const available = current.filter(id => ids.includes(id)).slice(0, 4);
      return available.length >= 2 ? available : ids.slice(0, 4);
    });
  }, [ids]);
  const comparison = useQuery({
    queryKey: ["comparison", selectedIds.join(","), rules],
    queryFn: ({ signal }) => api<Comparison>("compare", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ canonical_ids: selectedIds, rules, rolling_years: 3 }), signal }),
    enabled: selectedIds.length >= 2,
  });
  function toggleComparison(id: string) {
    setSelectedIds(current => current.includes(id) ? current.filter(item => item !== id) : current.length < 4 ? [...current, id] : current);
  }
  return <><SimpleHeading eyebrow="SIDE BY SIDE, SOURCE BY SOURCE" title="Compare funds" description="Select two to four saved funds and inspect the same evidence across each column." />
    {ids.length < 2 ? <div className="empty-state large"><BarChart3 size={34} /><h3>Save at least two funds to compare.</h3><p>Your comparison starts from the watchlist, keeping the shortlist local to this browser.</p><button className="primary-button" onClick={onDiscover}>Discover funds <ArrowRight size={17} /></button></div> : <>
      <section className="compare-picker"><div className="section-heading"><div><h2>Choose your columns</h2><p className="subtle">{selectedIds.length} selected · Maximum 4</p></div><button className="secondary-button" onClick={() => comparison.refetch()} disabled={selectedIds.length < 2 || comparison.isFetching}><Activity size={15} />{comparison.isFetching ? "Refreshing…" : "Refresh comparison"}</button></div>
        {fundQueries.some(query => query.isPending) && funds.length === 0 ? <Loading text="Loading your saved funds…" /> : <div className="compare-options">{funds.map(fund => { const checked = selectedIds.includes(fund.canonical_id); return <label className={`compare-option ${checked ? "selected" : ""}`} key={fund.canonical_id}><input type="checkbox" checked={checked} disabled={!checked && selectedIds.length >= 4} onChange={() => toggleComparison(fund.canonical_id)} /><span><strong>{fund.scheme}</strong><small>{categoryLabel(fund.category)} · {fund.plan} {fund.option}</small></span><Check size={16} /></label>; })}</div>}
        {fundQueries.some(query => query.isError) && <p className="warning-text">One or more saved funds could not be loaded from the current AMFI catalogue.</p>}
      </section>
      {selectedIds.length < 2 ? <div className="info-banner"><CircleHelp size={20} /><p>Select at least two funds. A fund stays in your watchlist when removed from this comparison.</p></div> : comparison.isError ? <ErrorBox error={comparison.error} retry={() => comparison.refetch()} /> : !comparison.data ? <Loading text="Collecting the same source-backed evidence for every selected fund…" /> : <ComparisonTable comparison={comparison.data} onOpen={onOpen} />}
    </>}
  </>;
}

function ComparisonTable({ comparison, onOpen }: { comparison: Comparison; onOpen: (id: string) => void }) {
  const metricValue = (analysis: Analysis, key: string): ComparisonValue => {
    const metric = analysis.metrics.find(item => item.key === key);
    if (!metric || metric.value == null) return { main: "—", detail: "Unavailable" };
    const prefix = metric.unit === "Cr" ? "₹" : "";
    return { main: `${prefix}${fmt(metric.value)}${metric.unit}`, detail: metric.source };
  };
  const returnValue = (analysis: Analysis, period: string): ComparisonValue => {
    const item = analysis.returns.find(value => value.period === period);
    return item?.value == null ? { main: "—", detail: "Unavailable" } : { main: `${fmt(item.value)}%`, detail: item.source };
  };
  const rollingValue = (analysis: Analysis, key: "average" | "minimum" | "positive_percent"): ComparisonValue => {
    const value = analysis.rolling?.[key];
    return value == null ? { main: "—", detail: "Unavailable" } : { main: `${fmt(value)}%`, detail: `${analysis.rolling?.years}Y rolling · ${analysis.rolling?.source || "AdvisorKhoj"}` };
  };
  const rows: ComparisonRow[] = [
    { group: "Identity", label: "Category", value: a => ({ main: categoryLabel(a.fund.category), detail: `${a.fund.plan} · ${a.fund.option}` }) },
    { group: "Identity", label: "Riskometer", value: a => ({ main: a.facts?.risk || "—", detail: a.facts?.risk ? a.facts.source : "Unavailable" }) },
    { group: "Identity", label: "Fund age", value: a => ({ main: a.facts?.age_years == null ? "—" : `${fmt(a.facts.age_years, 1)} years`, detail: a.facts?.inception_date ? `Since ${dateLabel(a.facts.inception_date)}` : "Unavailable" }) },
    { group: "Current facts", label: "NAV", value: a => ({ main: a.fund.nav.value == null ? "—" : `₹${fmt(a.fund.nav.value, 4)}`, detail: `AMFI · ${dateLabel(a.fund.nav.as_of)}` }) },
    { group: "Current facts", label: "AUM", value: a => metricValue(a, "aum") },
    { group: "Current facts", label: "Expense ratio", value: a => metricValue(a, "expense_ratio") },
    { group: "Risk & efficiency", label: "Beta", value: a => metricValue(a, "beta") },
    { group: "Risk & efficiency", label: "Standard deviation", value: a => metricValue(a, "standard_deviation") },
    { group: "Risk & efficiency", label: "Sharpe ratio", value: a => metricValue(a, "sharpe") },
    { group: "Risk & efficiency", label: "Alpha", value: a => metricValue(a, "alpha") },
    { group: "Market capture", label: "Upside capture", value: a => metricValue(a, "upside_capture") },
    { group: "Market capture", label: "Downside capture", value: a => metricValue(a, "downside_capture") },
    { group: "Returns", label: "1-year return", value: a => returnValue(a, "1Y") },
    { group: "Returns", label: "3-year return", value: a => returnValue(a, "3Y") },
    { group: "Returns", label: "5-year return", value: a => returnValue(a, "5Y") },
    { group: "Rolling evidence", label: "3Y rolling average", value: a => rollingValue(a, "average") },
    { group: "Rolling evidence", label: "3Y rolling minimum", value: a => rollingValue(a, "minimum") },
    { group: "Rolling evidence", label: "Non-negative windows", value: a => rollingValue(a, "positive_percent") },
    { group: "Portfolio", label: "Top 10 concentration", value: a => ({ main: a.portfolio?.top_10 == null ? "—" : `${fmt(a.portfolio.top_10)}%`, detail: a.portfolio?.source || "Unavailable" }) },
    { group: "Portfolio", label: "Largest sector", value: a => ({ main: a.portfolio?.largest_sector || "—", detail: a.portfolio?.largest_sector_weight == null ? "Unavailable" : `${fmt(a.portfolio.largest_sector_weight)}% · ${a.portfolio.source}` }) },
    { group: "Checks", label: "Your threshold checks", value: a => { const pass = a.rules.filter(item => item.status === "PASS").length; const fail = a.rules.filter(item => item.status === "FAIL").length; return { main: `${pass} pass · ${fail} fail`, detail: `${a.rules.length - pass - fail} unavailable or needs review` }; } },
    { group: "Checks", label: "Verified sources", value: a => { const count = a.sources.filter(source => ["Matched", "Verified"].includes(source.status)).length; return { main: `${count} of ${a.sources.length}`, detail: a.sources.map(source => `${source.source}: ${source.status}`).join(" · ") }; } },
  ];
  return <section className="comparison-results"><div className="section-heading"><div><span className="eyebrow">COMPARABLE EVIDENCE</span><h2>One measure per row</h2></div><span className="subtle">Fetched {new Date(comparison.fetched_at).toLocaleString("en-IN")}</span></div>
    <div className="comparison-scroll"><table className="comparison-table"><thead><tr><th>Measure</th>{comparison.analyses.map(analysis => <th key={analysis.fund.canonical_id}><span>{categoryLabel(analysis.fund.category)}</span><strong>{analysis.fund.scheme}</strong><small>{analysis.fund.plan} · {analysis.fund.option}</small><button className="text-button" onClick={() => onOpen(analysis.fund.canonical_id)}>Open analysis <ArrowUpRight size={13} /></button></th>)}</tr></thead><tbody>{rows.map((row, index) => { const startsGroup = index === 0 || rows[index - 1].group !== row.group; return <tr key={`${row.group}-${row.label}`} className={startsGroup ? "group-start" : ""}><th>{startsGroup && <span>{row.group}</span>}<strong>{row.label}</strong></th>{comparison.analyses.map(analysis => { const value = row.value(analysis); return <td key={analysis.fund.canonical_id}><strong>{value.main}</strong>{value.detail && <small>{value.detail}</small>}</td>; })}</tr>; })}</tbody></table></div>
    <div className="comparison-notes">{comparison.warnings.map((warning, index) => <p key={index}><CircleHelp size={15} />{warning}</p>)}</div>
    <div className="info-banner"><ShieldCheck size={20} /><p>The table preserves provider values and missing data. It does not rank funds or establish which fund is suitable for you.</p></div>
  </section>;
}

type NumericScreenKey = "beta_max" | "expense_ratio_max" | "manager_tenure_min" | "upside_capture_min" |
  "downside_capture_max" | "aum_min" | "aum_max" | "fund_age_min";
const SCREEN_FIELDS: [NumericScreenKey, string, string][] = [
  ["beta_max", "Beta below", "e.g. 1"], ["expense_ratio_max", "TER below (%)", "e.g. 1"],
  ["manager_tenure_min", "Manager tenure at least", "years"], ["fund_age_min", "Fund age at least", "years"],
  ["upside_capture_min", "Upside capture above", "%"], ["downside_capture_max", "Downside capture below", "%"],
  ["aum_min", "Minimum AUM", "₹ Cr"], ["aum_max", "Maximum AUM", "₹ Cr"],
];
function screenDefaults(rules: Rules | null): ScreenFilters {
  return { query: "", amc: "", category: "Mid Cap", plan: "Direct", option: "Growth", risk_levels: [],
    beta_max: rules?.beta_max ?? 1, expense_ratio_max: rules?.expense_ratio_max ?? 1, manager_tenure_min: 3,
    upside_capture_min: rules?.upside_capture_min ?? 100, downside_capture_max: rules?.downside_capture_max ?? 100,
    aum_min: null, aum_max: null, fund_age_min: null, unknown_policy: "exclude", rolling_years: 3,
    candidate_limit: 6, offset: 0 };
}

function ScreenerWorkspace({ rules, initial, onSave, savedIds, onToggle, onOpen }: { rules: Rules | null; initial: ScreenFilters | null; onSave: (filters: ScreenFilters | null) => void; savedIds: string[]; onToggle: (id: string) => void; onOpen: (id: string) => void }) {
  const [form, setForm] = useState<ScreenFilters>(() => initial || screenDefaults(rules));
  const [submitted, setSubmitted] = useState<ScreenFilters | null>(null);
  const [run, setRun] = useState(0);
  const [scopeError, setScopeError] = useState("");
  const screen = useQuery({
    queryKey: ["screen", submitted, run],
    queryFn: ({ signal }) => api<ScreenResponse>("screen", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(submitted), signal }),
    enabled: submitted !== null,
  });
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.query.trim() && !form.amc.trim() && !form.category.trim()) { setScopeError("Choose a category, AMC or keyword to bound the live screen."); return; }
    setScopeError("");
    const next = { ...form, offset: 0 };
    setSubmitted(next);
    onSave(next);
    setRun(value => value + 1);
  }
  function page(offset: number) {
    if (!submitted) return;
    setSubmitted({ ...submitted, offset });
    setRun(value => value + 1);
  }
  const data = screen.data;
  return <><SimpleHeading eyebrow="TURN PREFERENCES INTO QUESTIONS" title="Fund screener" description="Filter a bounded AMFI candidate set with live, source-backed evidence." />
    <form className="screener-panel" onSubmit={submit}>
      <div className="section-heading"><div><h2>Catalogue scope</h2><p className="subtle">Narrow the universe first; live provider checks run only after you submit.</p></div><span className="screen-limit">UP TO 8 FUNDS PER BATCH</span></div>
      <div className="screener-scope-grid"><label>Category<select value={form.category} onChange={event => setForm({ ...form, category: event.target.value })}><option value="">All categories</option>{["Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "Multi Cap", "Balanced Advantage", "Multi Asset", "Arbitrage", "Index", "ELSS", "Debt", "Hybrid"].map(value => <option key={value}>{value}</option>)}</select></label><label>Fund or keyword<input value={form.query} maxLength={120} placeholder="Optional fund name" onChange={event => setForm({ ...form, query: event.target.value })} /></label><label>AMC<input value={form.amc} maxLength={120} placeholder="Optional AMC" onChange={event => setForm({ ...form, amc: event.target.value })} /></label><label>Plan<select value={form.plan} onChange={event => setForm({ ...form, plan: event.target.value as ScreenFilters["plan"] })}><option value="Direct">Direct</option><option value="Regular">Regular</option><option value="">Any plan</option></select></label><label>Option<select value={form.option} onChange={event => setForm({ ...form, option: event.target.value as ScreenFilters["option"] })}><option value="Growth">Growth</option><option value="IDCW">IDCW</option><option value="">Any option</option></select></label><label>Riskometer<select value={form.risk_levels[0] || ""} onChange={event => setForm({ ...form, risk_levels: event.target.value ? [event.target.value] : [] })}><option value="">Any risk level</option>{["Low", "Low to Moderate", "Moderate", "Moderately High", "High", "Very High"].map(value => <option key={value}>{value}</option>)}</select></label></div>
      <div className="screener-divider"><span>Evidence filters</span></div>
      <div className="screener-filter-grid">{SCREEN_FIELDS.map(([key, label, placeholder]) => <label key={key}>{label}<span><input type="number" step="0.01" min="0" value={form[key] ?? ""} placeholder={placeholder} onChange={event => setForm({ ...form, [key]: event.target.value === "" ? null : Number(event.target.value) })} /><button type="button" aria-label={`Clear ${label}`} onClick={() => setForm({ ...form, [key]: null })}><X size={13} /></button></span></label>)}</div>
      <div className="screener-options"><label><input type="checkbox" checked={form.unknown_policy === "include"} onChange={event => setForm({ ...form, unknown_policy: event.target.checked ? "include" : "exclude" })} />Include provisional matches when an active metric is unavailable</label><label>Batch size<select value={form.candidate_limit} onChange={event => setForm({ ...form, candidate_limit: Number(event.target.value) })}>{[4, 6, 8].map(value => <option key={value}>{value}</option>)}</select></label></div>
      {scopeError && <p className="warning-text">{scopeError}</p>}
      <div className="settings-actions"><button className="primary-button" type="submit" disabled={screen.isFetching}><SlidersHorizontal size={16} />{screen.isFetching ? "Screening live sources…" : "Run live screen"}</button><button className="secondary-button" type="button" onClick={() => { setForm(screenDefaults(rules)); setSubmitted(null); setScopeError(""); onSave(null); }}>Reset filters</button></div>
    </form>
    {screen.isError ? <ErrorBox error={screen.error} retry={() => { setRun(value => value + 1); screen.refetch(); }} /> : screen.isFetching && !data ? <Loading text="Reconciling each candidate across AMFI, AdvisorKhoj, Groww and Coin…" /> : data && <section className="screen-results"><div className="screen-summary"><div><span>Catalogue candidates</span><strong>{data.total_candidates}</strong></div><div><span>Analysed in this batch</span><strong>{data.analysed}</strong></div><div><span>Matching all active filters</span><strong>{data.matched}</strong></div><div><span>Batch</span><strong>{Math.floor(data.offset / (submitted?.candidate_limit || 1)) + 1}</strong></div></div><div className="section-heading"><div><span className="eyebrow">RAW VALUES, EXPLICIT GAPS</span><h2>Screening evidence</h2></div><span className="subtle">Fetched {new Date(data.fetched_at).toLocaleString("en-IN")}</span></div>{data.results.length === 0 ? <div className="empty-state"><Search size={28} /><h3>No catalogue candidates in this batch</h3><p>Change the category, AMC or keyword and try again.</p></div> : <div className="screen-result-list">{data.results.map(result => <ScreenResultCard key={result.fund.canonical_id} result={result} saved={savedIds.includes(result.fund.canonical_id)} onToggle={() => onToggle(result.fund.canonical_id)} onOpen={() => onOpen(result.fund.canonical_id)} />)}</div>}<div className="screen-pagination"><button className="secondary-button" disabled={!submitted || data.offset === 0 || screen.isFetching} onClick={() => page(Math.max(0, data.offset - (submitted?.candidate_limit || 6)))}><ArrowLeft size={15} />Previous batch</button><span>{data.offset + 1}–{Math.min(data.offset + data.analysed, data.total_candidates)} of {data.total_candidates}</span><button className="secondary-button" disabled={!submitted || data.offset + (submitted?.candidate_limit || 6) >= data.total_candidates || screen.isFetching} onClick={() => page(data.offset + (submitted?.candidate_limit || 6))}>Next batch <ArrowRight size={15} /></button></div><div className="comparison-notes">{data.warnings.map((warning, index) => <p key={index}><CircleHelp size={15} />{warning}</p>)}</div><div className="info-banner"><ShieldCheck size={20} /><p>A match means the returned observations satisfy your active filters. It does not establish suitability or predict future performance.</p></div></section>}
  </>;
}

function ScreenResultCard({ result, saved, onToggle, onOpen }: { result: ScreenResult; saved: boolean; onToggle: () => void; onOpen: () => void }) {
  const metric = (key: string) => result.metrics.find(item => item.key === key);
  const aum = metric("aum");
  const expense = metric("expense_ratio");
  return <article className={`screen-result-card ${result.matched ? "matched" : "excluded"}`}><div className="screen-result-heading"><div><div className="screen-result-state"><span>{result.matched ? result.evidence_complete ? "MATCHES" : "PROVISIONAL" : "EXCLUDED"}</span><small>{result.sources.filter(source => ["Matched", "Verified"].includes(source.status)).length}/{result.sources.length} sources verified</small></div><h3>{result.fund.scheme}</h3><p>{categoryLabel(result.fund.category)} · {result.fund.plan} {result.fund.option}</p></div><div className="screen-result-actions"><button className={`bookmark-button ${saved ? "saved" : ""}`} onClick={onToggle} aria-label={`${saved ? "Remove" : "Save"} ${result.fund.scheme}`}><Bookmark size={18} fill={saved ? "currentColor" : "none"} /></button><button className="secondary-button" onClick={onOpen}>Full analysis <ArrowUpRight size={14} /></button></div></div><div className="screen-facts"><div><span>NAV</span><strong>₹{fmt(result.fund.nav.value, 4)}</strong><small>{dateLabel(result.fund.nav.as_of)}</small></div><div><span>Riskometer</span><strong>{result.facts?.risk || "—"}</strong><small>{result.facts?.source || "Unavailable"}</small></div><div><span>AUM</span><strong>{aum?.value == null ? "—" : `₹${fmt(aum.value)} Cr`}</strong><small>{aum?.source || "Unavailable"}</small></div><div><span>TER</span><strong>{expense?.value == null ? "—" : `${fmt(expense.value)}%`}</strong><small>{expense?.source || "Unavailable"}</small></div></div><div className="screen-criteria">{result.criteria.map(item => <div key={item.key}><span><strong>{item.label}</strong><small>Your filter: {item.operator} {typeof item.threshold === "number" ? fmt(item.threshold) : item.threshold}{item.unit ? ` ${item.unit}` : ""}</small></span><b>{item.value == null ? "—" : typeof item.value === "number" ? fmt(item.value) : item.value}{item.value == null || !item.unit ? "" : ` ${item.unit}`}</b><Status value={item.status} /></div>)}</div></article>;
}

function FundAnalysis({ id, rules, saved, onToggle, onBack, onMetric }: { id: string; rules: Rules | null; saved: boolean; onToggle: () => void; onBack: () => void; onMetric: (m: Metric) => void }) {
  const [years, setYears] = useState(3);
  const query = useQuery({ queryKey: ["analysis", id, rules, years], queryFn: ({ signal }) => api<Analysis>("analyse", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ canonical_id: id, rules, rolling_years: years }), signal }) });
  const a = query.data;
  const values = a?.metrics.filter(m => m.key !== "nav") || [];
  return <><button className="text-button back-button" onClick={onBack}><ArrowLeft size={16} />Back to funds</button>{query.isError ? <ErrorBox error={query.error} retry={() => query.refetch()} /> : !a ? <Loading text="Matching the exact scheme and collecting source-backed research…" /> : <>
    <div className="analysis-heading"><div><div className="eyebrow">{categoryLabel(a.fund.category)} <span className="eyebrow-separator">/</span> {a.fund.plan} · {a.fund.option}</div><h1>{a.fund.scheme}</h1><p>{a.fund.amc} <span>·</span> AMFI {a.fund.amfi_code}</p></div><button className={saved ? "secondary-button" : "primary-button"} onClick={onToggle}><Bookmark size={17} fill={saved ? "currentColor" : "none"} />{saved ? "Saved to watchlist" : "Add to watchlist"}</button></div>
    <div className="analysis-overview"><div><span className="label">LATEST NAV</span><strong>₹{fmt(a.fund.nav.value, 4)}</strong><span>As of {dateLabel(a.fund.nav.as_of)} · AMFI</span></div><div className="analysis-source-badges">{a.sources.map(s => <div key={s.source}><span>{s.source}</span><Status value={s.status} /></div>)}</div><button className="text-button" onClick={() => onMetric(a.fund.nav)}>View NAV source <ExternalLink size={14} /></button></div>
    <div className="section-heading analysis-section"><div><h2>The risk & cost picture</h2><p className="subtle">Raw values first. Labels reflect your research preferences.</p></div><button className="secondary-button" onClick={() => query.refetch()} disabled={query.isFetching}><Activity size={15} />{query.isFetching ? "Refreshing…" : "Refresh research"}</button></div>
    <div className="metric-grid">{values.map(m => { const rule = a.rules.find(r => r.metric === m.key); return <button className="metric-card" key={m.key} onClick={() => onMetric(m)}><div className="metric-top"><span>{m.label}</span><ArrowUpRight size={15} /></div><div className="metric-value">{m.unit === "Cr" && m.value !== null ? "₹" : ""}{fmt(m.value)}<span>{m.value !== null ? m.unit : ""}</span></div><p>{SHORT_HINTS[m.key]}</p><div className="metric-foot"><span>{m.source}</span>{rule ? <Status value={rule.status} /> : m.status !== "available" ? <Status value={m.status.toUpperCase()} /> : <span className="neutral-label">OBSERVATION</span>}</div></button>; })}</div>
    <SourceVerification analysis={a} onMetric={onMetric} />
    <div className="analysis-two-col"><section className="rolling-panel"><div className="section-heading"><div><span className="eyebrow">CONSISTENCY</span><h2>Returns across time</h2></div><div className="segmented" aria-label="Rolling return period">{[1, 3, 5].map(y => <button key={y} aria-pressed={years === y} className={years === y ? "selected" : ""} onClick={() => setYears(y)}>{y}Y</button>)}</div></div>{a.rolling?.status === "available" ? <><p className="subtle">{years}-year rolling annualised returns · Start date {dateLabel(a.rolling.start_date)}</p><div className="chart-container"><ResponsiveContainer width="100%" height="100%"><BarChart data={[{ name: "Minimum", value: a.rolling.minimum }, { name: "Average", value: a.rolling.average }, { name: "Median", value: a.rolling.median }, { name: "Maximum", value: a.rolling.maximum }]} margin={{ top: 20, left: -20, right: 10, bottom: 0 }}><CartesianGrid vertical={false} stroke="#ecebe7" /><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#777872", fontSize: 12 }} /><YAxis axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} tick={{ fill: "#777872", fontSize: 11 }} /><Tooltip formatter={v => `${fmt(Number(v))}%`} cursor={{ fill: "#f8f7f4" }} /><ReferenceLine y={0} stroke="#aaa" /><Bar dataKey="value" radius={[5, 5, 0, 0]} maxBarSize={46} isAnimationActive={false}>{["#e5c6b8", "#db6a3b", "#e39a73", "#384f46"].map(c => <Cell key={c} fill={c} />)}</Bar></BarChart></ResponsiveContainer></div><div className="rolling-stats"><div><span>Fund average</span><strong>{fmt(a.rolling.average)}%</strong></div><div><span>Category average</span><strong>{fmt(a.rolling.category_average)}{a.rolling.category_average == null ? "" : "%"}</strong></div><div><span>Non-negative windows</span><strong>{fmt(a.rolling.positive_percent, 1)}{a.rolling.positive_percent == null ? "" : "%"}</strong></div></div><div className="rolling-table">{[["Minimum", a.rolling.minimum], ["Median", a.rolling.median], ["Maximum", a.rolling.maximum]].map(([name, value]) => <span key={String(name)}>{name} <strong>{fmt(value as number)}%</strong></span>)}</div><p className="chart-note">{a.rolling.note} Fetched {dateLabel(a.rolling.fetched_at)}. <a href={a.rolling.source_url} target="_blank" rel="noreferrer">View AdvisorKhoj <ExternalLink size={11} /></a></p></> : <div className="empty-state"><BarChart3 size={28} /><h3>Rolling history unavailable</h3><p>{a.rolling?.note || "This source did not return verified rolling-return statistics for the selected scheme."}</p></div>}</section>
    <section className="reading-panel"><div className="eyebrow">READ THE WHOLE PICTURE</div><h2>What these numbers tell you</h2><div className="reading-item"><TrendingUp size={20} /><div><h3>Beta is sensitivity</h3><p>Below 1 means historically lower sensitivity to the stated benchmark. It does not establish low overall risk.</p></div></div><div className="reading-item"><ArrowDown size={20} /><div><h3>Capture works in both directions</h3><p>Read upside and downside together, using the same benchmark and period. Capture values here use a 3-year period.</p></div></div><div className="reading-item"><BarChart3 size={20} /><div><h3>Compare like with like</h3><p>Sharpe and standard deviation need matching periods, definitions and similar fund categories.</p></div></div><div className="reading-footer">No overall rating is assigned to this fund.</div></section></div>
    <GrowwResearch analysis={a} />
    <section className="provenance-panel"><div className="section-heading"><h2>Evidence & source notes</h2><span className="subtle">Every number has a trail</span></div>{a.sources.map(s => <div className="provenance-row" key={s.source}><strong>{s.source}</strong><Status value={s.status} /><p>{s.method || s.note}</p>{s.url && <a href={s.url} target="_blank" rel="noreferrer" aria-label={`Open ${s.source} source`}><ExternalLink size={17} /></a>}</div>)}<div className="source-identifiers">ISIN {a.fund.isins.join(" / ") || "not supplied"}</div>{a.warnings.map((w, i) => <p className="source-warning" key={i}><CircleHelp size={15} />{w}</p>)}<details><summary>View rule explanations</summary>{a.rules.map(r => <p key={r.metric}><strong>{r.status}</strong> · {r.explanation}</p>)}</details></section>
  </>}</>;
}

function SourceVerification({ analysis, onMetric }: { analysis: Analysis; onMetric: (m: Metric) => void }) {
  const groups = Object.values(analysis.metric_observations || {}).filter(items => items.filter(m => m.value !== null).length > 1);
  if (!groups.length) return null;
  return <section className="verification-panel"><div><span className="eyebrow">SOURCE VERIFICATION</span><h2>Same fund, checked twice</h2><p>Provider values stay separate. The highlighted value follows the configured source priority.</p></div><div className="verification-grid">{groups.map(items => <div className="verification-row" key={items[0].key}><strong>{items[0].label}</strong><div>{items.filter(m => m.value !== null).map(m => <button key={m.source} onClick={() => onMetric(m)}><span>{m.source}</span><b>{m.unit === "Cr" ? "₹" : ""}{fmt(m.value)}{m.unit}</b></button>)}</div></div>)}</div></section>;
}

function GrowwResearch({ analysis }: { analysis: Analysis }) {
  const { facts, portfolio, returns, holdings, sectors, managers } = analysis;
  if (!facts && !portfolio && !returns.length) return null;
  return <section className="deep-research"><div className="section-heading"><div><span className="eyebrow">PORTFOLIO & FUND CONTEXT</span><h2>What sits behind the returns</h2></div><span className="subtle">Groww public fund data · raw values retained</span></div><div className="deep-grid">
    <article className="fund-facts-card"><h3>Fund facts</h3><dl><div><dt>Risk</dt><dd>{facts?.risk || "Not supplied"}</dd></div><div><dt>Inception</dt><dd>{facts?.inception_date ? dateLabel(facts.inception_date) : "Not supplied"}{facts?.age_years != null && <small>{facts.age_years} years</small>}</dd></div><div><dt>Benchmark</dt><dd>{facts?.benchmark || "Not supplied"}</dd></div><div><dt>Exit load</dt><dd>{facts?.exit_load || "Not supplied"}</dd></div></dl>{managers.length > 0 && <div className="manager-list"><span>Fund managers</span>{managers.map(manager => <div key={`${manager.name}-${manager.tenure_start}`}><strong>{manager.name}</strong><small>{manager.tenure_years != null ? `${manager.tenure_years} years on this fund` : "Tenure not supplied"}</small></div>)}</div>}</article>
    <article className="returns-card"><h3>Point-to-point returns</h3><p className="subtle">Compare only with the same category and period.</p><div className="return-table"><span>Period</span><span>Fund</span><span>Category</span>{returns.map(item => <div className="return-row" key={item.period}><b>{item.period}</b><strong>{fmt(item.value)}{item.value == null ? "" : "%"}</strong><span>{fmt(item.category_value)}{item.category_value == null ? "" : "%"}</span></div>)}</div></article>
    {portfolio && <article className="concentration-card"><h3>Portfolio concentration</h3><p className="subtle">As of {dateLabel(portfolio.as_of)} · {portfolio.holdings_count} disclosed positions</p><div className="concentration-stats"><div><span>Largest holding</span><strong>{fmt(portfolio.largest_holding)}%</strong></div><div><span>Top 5</span><strong>{fmt(portfolio.top_5)}%</strong></div><div><span>Top 10</span><strong>{fmt(portfolio.top_10)}%</strong></div><div><span>Top 20</span><strong>{fmt(portfolio.top_20)}%</strong></div></div><h4>Largest sectors</h4><div className="sector-bars">{sectors.slice(0, 6).map(sector => <div key={sector.sector}><span>{sector.sector}<b>{fmt(sector.weight)}%</b></span><i><em style={{ width: `${Math.min(sector.weight, 100)}%` }} /></i></div>)}</div></article>}
    {holdings.length > 0 && <article className="holdings-card"><div className="card-heading"><h3>Largest holdings</h3><span>Top 10</span></div><div className="holding-table">{holdings.slice(0, 10).map((holding, index) => <div key={`${holding.name}-${index}`}><span className="holding-rank">{String(index + 1).padStart(2, "0")}</span><p><strong>{holding.name}</strong><small>{holding.sector || "Unspecified"} · {holding.instrument || "Instrument not supplied"}</small></p><b>{fmt(holding.weight)}%</b></div>)}</div></article>}
  </div></section>;
}

function Settings({ rules, onSave }: { rules: Rules | null; onSave: (rules: Rules | null) => void }) {
  const [values, setValues] = useState<Rules>(rules || DEFAULT_RULES);
  return <form className="settings-panel" onSubmit={e => { e.preventDefault(); onSave(values); }}><div className="section-heading"><h2>Research thresholds</h2><Status value={rules ? "Custom rules" : "Category defaults"} /></div><p className="subtle">Category defaults use a beta limit of 1.1 for small-cap funds and a TER limit of 0.3% for index funds. Custom rules override these defaults.</p><div className="settings-grid">{RULE_FIELDS.map(([key, label, min, max]) => <label key={key}>{label}<input required type="number" step="0.01" min={min} max={max} value={values[key]} onChange={e => setValues({ ...values, [key]: Number(e.target.value) })} /></label>)}</div><div className="settings-actions"><button className="primary-button" type="submit">Save my preferences <Check size={16} /></button><button className="secondary-button" type="button" onClick={() => { setValues(DEFAULT_RULES); onSave(null); }}>Use category defaults</button></div></form>;
}

function MetricDialog({ metric: m, onClose }: { metric: Metric; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="metric-dialog" onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }} aria-labelledby="metric-title"><div className="section-heading"><div className="eyebrow">FOLLOW THE NUMBER</div><button className="icon-button" aria-label="Close source details" onClick={onClose}><X size={20} /></button></div><h2 id="metric-title">{m.label}</h2><div className="dialog-value">{m.unit === "INR" || m.unit === "Cr" ? "₹" : ""}{fmt(m.value)} <span>{m.unit === "INR" ? "" : m.unit}</span></div><Status value={m.status.toUpperCase()} /><p>{m.definition}</p><dl>{[["Source", m.source], ["As of", dateLabel(m.as_of)], ["Fetched", new Date(m.fetched_at).toLocaleString("en-IN")], ["Lookback", m.period || "Not supplied"], ["Benchmark", m.benchmark || "Not supplied"]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{m.note && <div className="metric-note">{m.note}</div>}<a className="primary-button" href={m.source_url} target="_blank" rel="noreferrer">Open original source <ExternalLink size={16} /></a></dialog>;
}
