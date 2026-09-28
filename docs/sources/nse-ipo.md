# NSE IPO source

FundLens uses NSE India's public IPO pages for the first IPO catalogue milestone.

## Accepted fields

- company name and exchange symbol
- main-board or SME series
- issue start and end dates
- current issue status
- published price-band text
- shares offered and shares bid
- total live subscription multiple

The adapter establishes an NSE web session before reading the public issue responses, applies a five-minute cache and makes requests sequentially. Main-board and SME records stay distinct. BSE SME issues appearing in the NSE public-issue response retain `BSE` as their exchange.

The canonical identifier combines exchange, symbol and issue start date, for example `ipo:nse:EXAMPLE:2026-09-28`. The date prevents a reused symbol from silently colliding with a later issue.

## Limitations

- Subscription totals can change until an issue closes and are retained with `fetched_at`.
- Current public responses do not always include price bands for BSE SME issues; missing values remain unavailable.
- Total subscription is not a statistical recommendation.
- The first milestone covers open and forthcoming issues. Historical outcomes, offer-document extraction and category-level demand are later phases.
- The web responses used by the public NSE page are not a contractual API and can change. Parser failures are surfaced rather than replaced with stale fabricated records.

Source page: https://www.nseindia.com/market-data/all-upcoming-issues-ipo
