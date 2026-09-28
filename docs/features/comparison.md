# Multi-fund comparison

FundLens compares two to four schemes selected from the browser-local watchlist. The comparison API runs the normal source-backed analysis for each canonical AMFI scheme and returns the analyses in the requested order.

## Evidence shown

- AMFI category, exact plan and option, Riskometer, age and dated NAV
- AUM, expense ratio, beta, standard deviation, Sharpe and alpha
- upside and downside capture
- one-, three- and five-year point-to-point returns
- three-year rolling average, minimum and non-negative-window percentage
- top-ten holding concentration and largest sector
- the user's threshold results and verified-source coverage

Each value retains its selected source. A dash means the adapters returned no verified observation; it never means zero.

## Interpretation rules

- FundLens does not calculate an overall score or winner.
- A response warning identifies cross-category comparisons because their mandates, benchmark behaviour and expected risk may differ.
- Direct and Regular plans or Growth and IDCW options remain distinct schemes. The API warns if variants are mixed.
- Point-to-point and rolling returns remain separate measures.
- Provider conflicts remain visible in each fund's full analysis and are not averaged for the comparison table.
- The comparison reflects research observations and user thresholds; it does not establish investor suitability.

## Limits

- Selections are limited to four funds to keep provider requests bounded and the evidence table readable.
- The comparison selection lasts for the current page session. The underlying watchlist remains in browser localStorage.
- Provider availability and observation dates can differ between columns.
