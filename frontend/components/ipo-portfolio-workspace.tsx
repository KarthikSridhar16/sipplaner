"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, BriefcaseBusiness, CircleHelp, Loader2, Plus, ReceiptIndianRupee, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { analyseIPOPosition } from "@/lib/ipo-portfolio";
import type { IPOCatalogueResponse, IPOIssue, IPOPortfolioEntry, IPOTransaction } from "@/lib/types";

type Props = { entries: IPOPortfolioEntry[]; onSave: (entries: IPOPortfolioEntry[]) => void; onResearch: () => void };
type Draft = { canonicalId: string; applicationDate: string; lots: number; lotSize: number; bidPrice: number };

function localToday() {
  const value = new Date();
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 10);
}

function id() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function money(value: number | null) {
  return value == null ? "Unavailable" : value.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
}

export function IPOPortfolioWorkspace({ entries, onSave, onResearch }: Props) {
  const catalogue = useQuery({ queryKey: ["ipo-catalogue"], queryFn: () => api<IPOCatalogueResponse>("ipos"), staleTime: 240_000 });
  const [draft, setDraft] = useState<Draft>({ canonicalId: "", applicationDate: localToday(), lots: 1, lotSize: 1, bidPrice: 0 });
  const [error, setError] = useState("");
  const analyses = useMemo(() => entries.map(entry => ({ entry, result: analyseIPOPosition(entry) })), [entries]);
  const totalApplied = analyses.reduce((sum, item) => sum + item.result.applicationAmount, 0);
  const totalAllotted = analyses.reduce((sum, item) => sum + item.result.allotmentCost, 0);
  const totalRefunded = entries.reduce((sum, entry) => sum + entry.refund_amount, 0);
  const pricedPositions = analyses.filter(item => item.result.currentValue != null);
  const currentValue = pricedPositions.reduce((sum, item) => sum + (item.result.currentValue || 0), 0);
  const realized = analyses.reduce((sum, item) => sum + item.result.realizedProfit, 0);
  const unrealized = pricedPositions.reduce((sum, item) => sum + (item.result.unrealizedProfit || 0), 0);
  const selectedIssue = catalogue.data?.issues.find(issue => issue.canonical_id === draft.canonicalId);

  function selectIssue(canonicalId: string) {
    const issue = catalogue.data?.issues.find(item => item.canonical_id === canonicalId);
    setDraft(current => ({ ...current, canonicalId, bidPrice: issue?.price_max ?? 0 }));
    setError("");
  }

  function addApplication() {
    if (!selectedIssue) { setError("Select an IPO from the current issue board."); return; }
    if (entries.length >= 50) { setError("The IPO portfolio holds up to 50 applications."); return; }
    if (!draft.applicationDate || draft.lots < 1 || draft.lotSize < 1 || draft.bidPrice <= 0) {
      setError("Application date, lots, lot size and bid price must be valid positive values."); return;
    }
    const entry: IPOPortfolioEntry = {
      id: id(), canonical_id: selectedIssue.canonical_id, company_name: selectedIssue.company_name,
      symbol: selectedIssue.symbol, exchange: selectedIssue.exchange, board: selectedIssue.board, status: "applied",
      application_date: draft.applicationDate, lots_applied: Math.trunc(draft.lots), lot_size: Math.trunc(draft.lotSize),
      bid_price: draft.bidPrice, allotment_date: "", shares_allotted: 0, refund_amount: 0, refund_date: "",
      listing_date: "", listing_price: null, current_price: null, price_as_of: "", transactions: [],
    };
    onSave([...entries, entry]);
    setDraft({ canonicalId: "", applicationDate: localToday(), lots: 1, lotSize: 1, bidPrice: 0 });
    setError("");
  }

  function update(next: IPOPortfolioEntry) { onSave(entries.map(entry => entry.id === next.id ? next : entry)); }

  return <>
    <div className="simple-heading"><div className="eyebrow">APPLICATION TO EXIT, IN ONE LEDGER</div><h1>IPO portfolio</h1><p>Track applications, allotments, refunds and post-listing transactions in this browser.</p></div>
    <section className="ipo-portfolio-summary">
      <div><span>Application amount</span><strong>{money(totalApplied)}</strong></div>
      <div><span>Allotment cost</span><strong>{money(totalAllotted)}</strong></div>
      <div><span>Refunds recorded</span><strong>{money(totalRefunded)}</strong></div>
      <div><span>Priced current value</span><strong>{money(currentValue)}</strong><small>{pricedPositions.length}/{analyses.filter(item => item.result.holdings > 0).length} positions priced</small></div>
      <div><span>Total tracked P/L</span><strong className={realized + unrealized < 0 ? "negative" : ""}>{money(realized + unrealized)}</strong><small>realized + priced unrealized</small></div>
    </section>

    <section className="ipo-application-form">
      <div className="section-heading"><div><h2>Add IPO application</h2><span className="subtle">Issue identity is saved locally even after it leaves the live board</span></div><span>{entries.length}/50</span></div>
      {catalogue.isPending ? <div className="loading"><Loader2 className="spin" size={22} /><p>Loading current IPOs…</p></div> : <div className="ipo-application-grid">
        <label className="ipo-application-wide">IPO<select aria-label="IPO for application" value={draft.canonicalId} onChange={event => selectIssue(event.target.value)}><option value="">Select current IPO</option>{catalogue.data?.issues.map(issue => <option key={issue.canonical_id} value={issue.canonical_id}>{issue.company_name} · {issue.board}</option>)}</select></label>
        <label>Application date<input type="date" value={draft.applicationDate} onChange={event => setDraft({ ...draft, applicationDate: event.target.value })} /></label>
        <label>Lots applied<input type="number" min="1" step="1" value={draft.lots} onChange={event => setDraft({ ...draft, lots: Number(event.target.value) })} /></label>
        <label>Shares per lot<input type="number" min="1" step="1" value={draft.lotSize} onChange={event => setDraft({ ...draft, lotSize: Number(event.target.value) })} /></label>
        <label>Bid price ₹<input type="number" min="0.01" step="0.01" value={draft.bidPrice || ""} onChange={event => setDraft({ ...draft, bidPrice: Number(event.target.value) })} /></label>
        <button className="primary-button" onClick={addApplication}><Plus size={16} />Add application</button>
      </div>}
      {catalogue.isError && <div className="error-box"><h3>Current IPOs unavailable</h3><p>{catalogue.error.message}</p><button className="secondary-button" onClick={() => catalogue.refetch()}>Try again</button></div>}
      {error && <p className="ipo-form-error" role="alert">{error}</p>}
      <div className="portfolio-notes"><p><CircleHelp size={15} />Enter the exchange lot size shown by your broker or offer document; the live catalogue does not supply a verified lot size.</p></div>
    </section>

    <div className="section-heading ipo-portfolio-heading"><div><h2>Applications and holdings</h2><span className="subtle">FIFO cost basis is used for manual sell transactions</span></div></div>
    {entries.length === 0 ? <div className="empty-state large"><BriefcaseBusiness size={34} /><h3>No IPO applications recorded</h3><p>Add an issue above after applying, or review the live IPO evidence first.</p><button className="secondary-button" onClick={onResearch}>Open IPO research</button></div>
      : <div className="ipo-position-list">{entries.map(entry => <IPOPositionCard key={entry.id} entry={entry} onUpdate={update} onRemove={() => onSave(entries.filter(item => item.id !== entry.id))} />)}</div>}
    <div className="portfolio-limit"><ReceiptIndianRupee size={22} /><div><strong>Local tracking only</strong><p>This ledger does not place bids, read a demat account or fetch a broker statement. Verify every application, allotment, refund and trade against your broker and bank records.</p></div></div>
  </>;
}

function IPOPositionCard({ entry, onUpdate, onRemove }: { entry: IPOPortfolioEntry; onUpdate: (entry: IPOPortfolioEntry) => void; onRemove: () => void }) {
  const [open, setOpen] = useState(true);
  const [transaction, setTransaction] = useState<Omit<IPOTransaction, "id">>({ type: "buy", date: localToday(), quantity: 1, price: 0, fees: 0 });
  const [transactionError, setTransactionError] = useState("");
  const result = analyseIPOPosition(entry);
  const update = (patch: Partial<IPOPortfolioEntry>) => onUpdate({ ...entry, ...patch });
  const optionalNumber = (value: string) => value === "" ? null : Number(value);

  function addTransaction() {
    if (!transaction.date || transaction.quantity < 1 || !Number.isInteger(transaction.quantity) || transaction.price <= 0 || transaction.fees < 0) {
      setTransactionError("Date, whole-share quantity and price are required; fees cannot be negative."); return;
    }
    if (transaction.type === "sell" && transaction.quantity > result.holdings) {
      setTransactionError(`Only ${result.holdings} shares are currently available to sell.`); return;
    }
    const next: IPOTransaction = { ...transaction, id: id() };
    update({ transactions: [...entry.transactions, next], status: "listed" });
    setTransaction({ type: "buy", date: localToday(), quantity: 1, price: 0, fees: 0 });
    setTransactionError("");
  }

  return <article className="ipo-position-card">
    <div className="ipo-position-head"><span className="ipo-position-symbol">{entry.symbol.slice(0, 2)}</span><div><h3>{entry.company_name}</h3><p>{entry.symbol} · {entry.exchange} · {entry.board}</p></div><span className={`ipo-position-state state-${entry.status}`}>{entry.status}</span><button className="secondary-button" onClick={() => setOpen(!open)}>{open ? "Collapse" : "Manage"}</button><button className="icon-button" aria-label={`Remove ${entry.company_name} application`} onClick={onRemove}><Trash2 size={16} /></button></div>
    <div className="ipo-position-metrics">
      <div><span>Applied</span><strong>{money(result.applicationAmount)}</strong></div>
      <div><span>Allotted</span><strong>{result.holdings} shares</strong></div>
      <div><span>Current value</span><strong>{money(result.currentValue)}</strong></div>
      <div><span>Realized P/L</span><strong className={result.realizedProfit < 0 ? "negative" : ""}>{money(result.realizedProfit)}</strong></div>
      <div><span>Unrealized P/L</span><strong className={(result.unrealizedProfit || 0) < 0 ? "negative" : ""}>{money(result.unrealizedProfit)}</strong></div>
    </div>
    {open && <div className="ipo-position-body">
      <section><h4>Application and allotment</h4><div className="ipo-ledger-grid">
        <label>Status<select value={entry.status} onChange={event => update({ status: event.target.value as IPOPortfolioEntry["status"] })}>{["planned", "applied", "allotted", "refunded", "listed", "closed"].map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Application date<input type="date" value={entry.application_date} onChange={event => update({ application_date: event.target.value })} /></label>
        <label>Lots applied<input type="number" min="1" step="1" value={entry.lots_applied} onChange={event => update({ lots_applied: Math.max(1, Math.trunc(Number(event.target.value))) })} /></label>
        <label>Shares per lot<input type="number" min="1" step="1" value={entry.lot_size} onChange={event => update({ lot_size: Math.max(1, Math.trunc(Number(event.target.value))) })} /></label>
        <label>Bid price ₹<input type="number" min="0.01" step="0.01" value={entry.bid_price} onChange={event => update({ bid_price: Math.max(0.01, Number(event.target.value)) })} /></label>
        <label>Allotment date<input type="date" value={entry.allotment_date} onChange={event => update({ allotment_date: event.target.value })} /></label>
        <label>Shares allotted<input type="number" min="0" step="1" value={entry.shares_allotted} onChange={event => update({ shares_allotted: Math.max(0, Math.trunc(Number(event.target.value))) })} /></label>
        <label>Refund received ₹<input type="number" min="0" step="0.01" value={entry.refund_amount} onChange={event => update({ refund_amount: Math.max(0, Number(event.target.value)) })} /></label>
        <label>Refund date<input type="date" value={entry.refund_date} onChange={event => update({ refund_date: event.target.value })} /></label>
      </div><div className="ipo-cash-flow"><span>Allotment cost<strong>{money(result.allotmentCost)}</strong></span><span>Expected refund<strong>{money(result.expectedRefund)}</strong></span><span>Refund outstanding<strong>{money(result.refundOutstanding)}</strong></span></div></section>

      <section><h4>Listing and mark-to-market</h4><div className="ipo-ledger-grid">
        <label>Listing date<input type="date" value={entry.listing_date} onChange={event => update({ listing_date: event.target.value })} /></label>
        <label>Listing price ₹<input type="number" min="0.01" step="0.01" value={entry.listing_price ?? ""} onChange={event => update({ listing_price: optionalNumber(event.target.value) })} /></label>
        <label>Current price ₹<input type="number" min="0.01" step="0.01" value={entry.current_price ?? ""} onChange={event => update({ current_price: optionalNumber(event.target.value) })} /></label>
        <label>Price as of<input type="date" value={entry.price_as_of} onChange={event => update({ price_as_of: event.target.value })} /></label>
      </div><div className="ipo-cash-flow"><span>Listing P/L<strong>{money(result.listingProfit)}</strong></span><span>FIFO average cost<strong>{money(result.averageCost)}</strong></span><span>Remaining cost basis<strong>{money(result.remainingCost)}</strong></span></div></section>

      <section className="ipo-transactions"><h4>Post-listing transactions</h4><div className="ipo-transaction-form">
        <label>Type<select value={transaction.type} onChange={event => setTransaction({ ...transaction, type: event.target.value as "buy" | "sell" })}><option value="buy">Buy</option><option value="sell">Sell</option></select></label>
        <label>Date<input type="date" value={transaction.date} onChange={event => setTransaction({ ...transaction, date: event.target.value })} /></label>
        <label>Shares<input type="number" min="1" step="1" value={transaction.quantity} onChange={event => setTransaction({ ...transaction, quantity: Number(event.target.value) })} /></label>
        <label>Price ₹<input type="number" min="0.01" step="0.01" value={transaction.price || ""} onChange={event => setTransaction({ ...transaction, price: Number(event.target.value) })} /></label>
        <label>Fees ₹<input type="number" min="0" step="0.01" value={transaction.fees} onChange={event => setTransaction({ ...transaction, fees: Number(event.target.value) })} /></label>
        <button className="secondary-button" onClick={addTransaction}><Plus size={14} />Add trade</button>
      </div>{transactionError && <p className="ipo-form-error">{transactionError}</p>}
      {entry.transactions.length === 0 ? <p className="ipo-no-transactions">No post-listing buys or sells recorded.</p> : <div className="ipo-transaction-list">{entry.transactions.map(item => <div key={item.id}><span className={item.type}>{item.type === "buy" ? <ArrowDownRight size={14} /> : <ArrowUpRight size={14} />}{item.type}</span><strong>{item.quantity} shares × {money(item.price)}</strong><small>{item.date} · fees {money(item.fees)}</small><button className="icon-button" aria-label={`Remove ${item.type} transaction`} onClick={() => update({ transactions: entry.transactions.filter(value => value.id !== item.id) })}><Trash2 size={14} /></button></div>)}</div>}
      </section>
      {result.warnings.length > 0 && <div className="portfolio-notes">{result.warnings.map(warning => <p key={warning}><CircleHelp size={15} />{warning}</p>)}</div>}
    </div>}
  </article>;
}
