import type { IPOPortfolioEntry, IPOTransaction, Rules, ScreenFilters, SIPPortfolioEntry } from "./types";

export type Preferences = { version: 1; funds: string[]; directOnly: boolean; growthOnly: boolean; rules: Rules | null; screen: ScreenFilters | null; portfolio: SIPPortfolioEntry[]; ipoWatchlist: string[]; ipoPortfolio: IPOPortfolioEntry[] };
export const INITIAL: Preferences = { version: 1, funds: [], directOnly: true, growthOnly: true, rules: null, screen: null, portfolio: [], ipoWatchlist: [], ipoPortfolio: [] };
export interface DashboardStorage { load(): Preferences; save(value: Preferences): void }
export const dashboardStorage: DashboardStorage = {
  load() {
    const raw = localStorage.getItem("fundlens.preferences.v1");
    if (!raw) return { ...INITIAL };
    const v = JSON.parse(raw);
    if (v.version !== 1 || !Array.isArray(v.funds)) throw new Error("Saved preferences are not in a supported format.");
    let rules: Rules | null = null;
    if (v.rules && ["beta_max", "expense_ratio_max", "upside_capture_min", "downside_capture_max"].every(k => typeof v.rules[k] === "number" && Number.isFinite(v.rules[k]))) rules = v.rules;
    const numericScreenKeys = ["beta_max", "expense_ratio_max", "manager_tenure_min", "upside_capture_min", "downside_capture_max", "aum_min", "aum_max", "fund_age_min"];
    const validScreen = v.screen && typeof v.screen === "object" && typeof v.screen.query === "string" && typeof v.screen.amc === "string"
      && typeof v.screen.category === "string" && ["Direct", "Regular", ""].includes(v.screen.plan)
      && ["Growth", "IDCW", ""].includes(v.screen.option) && Array.isArray(v.screen.risk_levels)
      && numericScreenKeys.every(key => v.screen[key] === null || (typeof v.screen[key] === "number" && Number.isFinite(v.screen[key])))
      && ["exclude", "include"].includes(v.screen.unknown_policy) && [1, 3, 5].includes(v.screen.rolling_years)
      && [4, 6, 8].includes(v.screen.candidate_limit);
    const screen = validScreen ? { ...v.screen, offset: 0 } as ScreenFilters : null;
    const seen = new Set<string>();
    const portfolio = Array.isArray(v.portfolio) ? v.portfolio.filter((entry: unknown): entry is SIPPortfolioEntry => {
      if (!entry || typeof entry !== "object") return false;
      const item = entry as Record<string, unknown>;
      if (typeof item.canonical_id !== "string" || !/^amfi:\d{5,8}$/.test(item.canonical_id) || seen.has(item.canonical_id)) return false;
      if (typeof item.monthly_sip !== "number" || !Number.isFinite(item.monthly_sip) || item.monthly_sip <= 0 || item.monthly_sip > 100_000_000) return false;
      seen.add(item.canonical_id);
      return true;
    }).slice(0, 12) : [];
    const ipoWatchlist = Array.isArray(v.ipoWatchlist)
      ? [...new Set<string>(v.ipoWatchlist.filter((id: unknown) => typeof id === "string" && /^ipo:(nse|bse):[A-Z0-9&-]+:\d{4}-\d{2}-\d{2}$/.test(id)))].slice(0, 50)
      : [];
    const validNumber = (value: unknown, allowZero = true) => typeof value === "number" && Number.isFinite(value) && (allowZero ? value >= 0 : value > 0) && value <= 1_000_000_000;
    const validDate = (value: unknown) => typeof value === "string" && (value === "" || /^\d{4}-\d{2}-\d{2}$/.test(value));
    const entryIds = new Set<string>();
    const ipoPortfolio = Array.isArray(v.ipoPortfolio) ? v.ipoPortfolio.filter((entry: unknown): entry is IPOPortfolioEntry => {
      if (!entry || typeof entry !== "object") return false;
      const item = entry as Record<string, unknown>;
      if (typeof item.id !== "string" || !item.id || entryIds.has(item.id)) return false;
      if (typeof item.canonical_id !== "string" || !/^ipo:(nse|bse):[A-Z0-9&-]+:\d{4}-\d{2}-\d{2}$/.test(item.canonical_id)) return false;
      if (typeof item.company_name !== "string" || typeof item.symbol !== "string" || !["NSE", "BSE"].includes(String(item.exchange)) || !["Mainboard", "SME"].includes(String(item.board))) return false;
      if (!["planned", "applied", "allotted", "refunded", "listed", "closed"].includes(String(item.status))) return false;
      if (![item.application_date, item.allotment_date, item.refund_date, item.listing_date, item.price_as_of].every(validDate)) return false;
      if (!validNumber(item.lots_applied, false) || !Number.isInteger(item.lots_applied) || !validNumber(item.lot_size, false)
          || !Number.isInteger(item.lot_size) || !validNumber(item.bid_price, false) || !validNumber(item.shares_allotted)
          || !Number.isInteger(item.shares_allotted) || !validNumber(item.refund_amount)) return false;
      if (!(item.listing_price === null || validNumber(item.listing_price, false)) || !(item.current_price === null || validNumber(item.current_price, false))) return false;
      const transactions = Array.isArray(item.transactions) ? item.transactions.filter((value: unknown): value is IPOTransaction => {
        if (!value || typeof value !== "object") return false;
        const transaction = value as Record<string, unknown>;
        return typeof transaction.id === "string" && ["buy", "sell"].includes(String(transaction.type))
          && validDate(transaction.date) && transaction.date !== "" && validNumber(transaction.quantity, false) && Number.isInteger(transaction.quantity)
          && validNumber(transaction.price, false) && validNumber(transaction.fees);
      }).slice(0, 100) : [];
      item.transactions = transactions;
      entryIds.add(item.id);
      return true;
    }).slice(0, 50) : [];
    return { version: 1, funds: [...new Set<string>(v.funds.filter((id: unknown) => typeof id === "string" && /^amfi:\d{5,8}$/.test(id)))].slice(0, 30),
      directOnly: typeof v.directOnly === "boolean" ? v.directOnly : true,
      growthOnly: typeof v.growthOnly === "boolean" ? v.growthOnly : true, rules, screen, portfolio, ipoWatchlist, ipoPortfolio };
  },
  save(value) { localStorage.setItem("fundlens.preferences.v1", JSON.stringify(value)); },
};
