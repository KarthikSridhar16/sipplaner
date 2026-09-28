# Groww source adapter

The Groww adapter uses only publicly accessible mutual-fund research pages. It does not log in, call investment endpoints, or require a Groww account.

## Discovery and identity

1. Query Groww's public global-search response for the AMFI scheme name.
2. Keep only results whose entity type is `Scheme` and whose normalized scheme name, plan and option match.
3. Fetch the public `/mutual-funds/{search_id}` page.
4. Read the server-rendered `__NEXT_DATA__` payload.
5. Accept the page only when its AMFI scheme code or ISIN matches the selected AMFI fund and its plan and option agree exactly.

The final AMFI code/ISIN check prevents a similar-name search result from being merged into the selected fund.

## Data used

- AUM and expense ratio, including the latest expense-history date when supplied
- provider risk label and point-to-point fund/category returns
- beta, standard deviation, Sharpe and alpha for cross-verification
- inception date, benchmark and exit load
- fund managers, fund-specific tenure start, experience text and other managed funds
- disclosed holdings, portfolio date, sectors and weights

FundLens calculates top 1, 5, 10 and 20 holding concentration and sector totals from the disclosed weights. It flags incomplete portfolios when weights fall outside a 95–105% validation band.

## Source priority and conflicts

Groww currently has priority for AUM and expense ratio. AdvisorKhoj retains priority for risk metrics and capture/rolling-return statistics. All returned observations remain in the API response. Material differences are shown as source warnings and in the source-verification panel.

## Limitations

- Groww can change its public page or search payload without notice. Parser-shape failures mark the source as `Parsing Error` and do not fail the full analysis.
- Provider risk and risk-adjusted metrics do not always include a stated measurement period in the page payload. They remain provider observations and are not treated as interchangeable definitions.
- Manager tenure is calculated from Groww's `date_from` field for the specific scheme. Experience text is displayed separately and is not converted into industry-experience years.
- Holdings are the provider's disclosed snapshot and may include cash, repo, debt or other non-equity instruments.
- No protected API, anti-bot bypass, account data, order flow or transaction capability is used.
