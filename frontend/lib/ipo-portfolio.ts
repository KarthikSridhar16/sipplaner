import type { IPOPortfolioEntry, IPOTransaction } from "./types";

export type IPOPositionAnalysis = {
  applicationAmount: number;
  allotmentCost: number;
  expectedRefund: number;
  refundOutstanding: number;
  holdings: number;
  remainingCost: number;
  averageCost: number | null;
  currentValue: number | null;
  realizedProfit: number;
  unrealizedProfit: number | null;
  totalProfit: number | null;
  listingProfit: number | null;
  warnings: string[];
};

type Lot = { quantity: number; unitCost: number };

function ordered(transactions: IPOTransaction[]) {
  return transactions.map((transaction, index) => ({ transaction, index }))
    .sort((a, b) => a.transaction.date.localeCompare(b.transaction.date) || a.index - b.index)
    .map(item => item.transaction);
}

export function analyseIPOPosition(entry: IPOPortfolioEntry): IPOPositionAnalysis {
  const applicationAmount = entry.lots_applied * entry.lot_size * entry.bid_price;
  const allotmentCost = entry.shares_allotted * entry.bid_price;
  const expectedRefund = Math.max(0, applicationAmount - allotmentCost);
  const refundOutstanding = Math.max(0, expectedRefund - entry.refund_amount);
  const lots: Lot[] = entry.shares_allotted > 0 ? [{ quantity: entry.shares_allotted, unitCost: entry.bid_price }] : [];
  let realizedProfit = 0;
  const warnings: string[] = [];

  for (const transaction of ordered(entry.transactions)) {
    if (transaction.type === "buy") {
      lots.push({ quantity: transaction.quantity, unitCost: transaction.price + transaction.fees / transaction.quantity });
      continue;
    }
    const available = lots.reduce((sum, lot) => sum + lot.quantity, 0);
    const sold = Math.min(transaction.quantity, available);
    if (sold < transaction.quantity) warnings.push(`Sell on ${transaction.date} exceeds available shares by ${transaction.quantity - sold}; excess shares were excluded.`);
    let remaining = sold;
    let consumedCost = 0;
    while (remaining > 0 && lots.length) {
      const lot = lots[0];
      const quantity = Math.min(remaining, lot.quantity);
      consumedCost += quantity * lot.unitCost;
      lot.quantity -= quantity;
      remaining -= quantity;
      if (lot.quantity === 0) lots.shift();
    }
    const allocatedFees = transaction.quantity ? transaction.fees * (sold / transaction.quantity) : 0;
    realizedProfit += sold * transaction.price - allocatedFees - consumedCost;
  }

  const holdings = lots.reduce((sum, lot) => sum + lot.quantity, 0);
  const remainingCost = lots.reduce((sum, lot) => sum + lot.quantity * lot.unitCost, 0);
  const averageCost = holdings ? remainingCost / holdings : null;
  const currentValue = entry.current_price == null ? null : holdings * entry.current_price;
  const unrealizedProfit = currentValue == null ? null : currentValue - remainingCost;
  const totalProfit = unrealizedProfit == null ? null : realizedProfit + unrealizedProfit;
  const listingProfit = entry.listing_price == null || !entry.shares_allotted ? null
    : (entry.listing_price - entry.bid_price) * entry.shares_allotted;
  if (holdings > 0 && entry.current_price == null) warnings.push("Current price is unavailable; current value and unrealized return are not calculated.");
  if (entry.refund_amount > expectedRefund) warnings.push("Recorded refund exceeds the calculated application amount less allotment cost; verify the inputs.");
  return { applicationAmount, allotmentCost, expectedRefund, refundOutstanding, holdings, remainingCost, averageCost,
    currentValue, realizedProfit, unrealizedProfit, totalProfit, listingProfit, warnings };
}
