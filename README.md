# FundLens

FundLens is a database-free Indian mutual-fund and IPO research application. It supports live AMFI fund identity, exact AdvisorKhoj, Groww and Zerodha Coin reconciliation, official NSE IPO discovery, source cross-checks, risk and return research, portfolio concentration, configurable rule labels, and browser-local watchlists.

The IPO catalogue, watchlist, offer-document research and browser-local IPO portfolio releases are complete. Calibrated statistical IPO analysis remains staged in the product roadmap. Statistical decision labels will be enabled only after out-of-time validation.

## What works

- Search the AMFI catalogue by scheme name, AMC, category, ISIN, or scheme code.
- Keep Direct/Regular and Growth/IDCW variants distinct through AMFI scheme codes and ISINs.
- Match Growth schemes to AdvisorKhoj only when the normalized scheme, explicit plan, and option agree.
- Resolve Groww's public scheme slug through its search response, then require the AMFI code or ISIN plus the exact plan and option before accepting data.
- Open Coin's public ISIN route directly, then require the same ISIN, plan and option inside the page before accepting data.
- Display NAV, beta, standard deviation, Sharpe, alpha, TER, AUM, rolling returns, and capture ratios with source context.
- Show Groww's point-to-point returns beside category returns, current risk, inception, benchmark, exit load, fund-manager tenure, holdings and sector concentration.
- Retain observations from both research providers and show material differences instead of silently replacing them.
- Compare two to four saved funds across identity, costs, risk, returns, rolling evidence, concentration, rule checks and source coverage.
- Screen bounded AMFI category/AMC/name batches with live beta, TER, manager-tenure, capture, AUM, age and Riskometer criteria.
- Build a browser-local monthly SIP plan and analyse fund, category, category-derived asset, Riskometer and disclosed sector allocation.
- Measure SIP-weighted common-holding exposure and pairwise overlap from verified disclosed portfolios, with explicit coverage warnings.
- Analyse a selected SIP with historical outcome probabilities, downside risk, walk-forward evidence, current fund-manager tenure evidence and benchmark valuation.
- Add official NSE Indices benchmark history and multi-year P/E/P/B percentiles for category-appropriate market-regime context.
- Browse open and forthcoming main-board and SME IPOs with official NSE issue dates, price bands and live subscription evidence.
- Save IPOs to a browser-local watchlist while the application/allotment portfolio is developed.
- Open exact-matched NSE offer-document research with official DRHP/RHP/prospectus links and structured company, offer, business, promoter, director, proceeds, financial and litigation evidence when published.
- Track IPO applications, lots, bid prices, allotments, refunds, listing observations and manual post-listing buys and sells in a browser-local portfolio with FIFO realized and unrealized results.
- Preserve `fetched_at` separately from the source's `as_of` date.
- Continue with partial results when a research source is unavailable.
- Save watchlist, filters, and personal thresholds in browser localStorage.

This is research software, not investment advice. Rule labels reflect user preferences and do not establish suitability.

## Run locally

Requirements: Python 3.12+ and Node.js 24+.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal, start the web application:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:3000`. API documentation is at `http://127.0.0.1:8000/docs`.

Docker users can run `docker compose up --build` from the repository root.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend\tests
cd frontend
npm run typecheck
npm run build
```

Parser tests use saved, minimal HTML and AMFI fixtures. Live source calls are kept out of deterministic tests.

## Architecture

The frontend sends only canonical identifiers and rule overrides. `FundService` orchestrates source adapters and owns source priority. AMFI is the canonical catalogue for this milestone. AdvisorKhoj is treated as a secondary research source and cannot change the selected AMFI identity.

```text
Next.js UI -> FastAPI routes -> FundService -> source adapters
                                      |          |- AMFI
                                      |          |- MFapi.in (historical NAV)
                                      |          |- NSE Indices
                                      |          |- AdvisorKhoj
                                      |          |- Groww
                                      |          `- Coin
                                      `-> rule evaluation
```

Source responses use short-lived in-memory caches and disappear when the backend restarts. User state remains in the current browser only. No database or user account is present.

## API

- `GET /health`
- `GET /api/search?q=HDFC%20mid&plan=Direct&option=Growth`
- `GET /api/funds/{canonical_id}`
- `GET /api/funds/{canonical_id}/analysis?rolling_years=3`
- `POST /api/analyse` with a canonical ID and optional rules
- `POST /api/compare` with two to four unique canonical IDs and optional rules
- `POST /api/screen` with catalogue scope, live evidence filters, missing-data policy and batch controls
- `POST /api/portfolio/analyse` with one to twelve unique canonical IDs and positive monthly SIP amounts
- `POST /api/sip/statistical-analysis` with one canonical scheme, monthly SIP, horizon and bounded simulation count
- `GET /api/ipos` with optional company/symbol, board and status filters
- `GET /api/ipos/{canonical_id}/research` for exact-matched NSE offer documents and structured prospectus evidence
- `GET /api/source-status`
- `GET /api/rules`

## Current limits

AdvisorKhoj's public pages do not state the lookback or as-of date for several risk metrics. FundLens displays that limitation beside the value. Rolling-return summaries are provider-calculated and use a bounded ten-year start range. Groww data comes from its public server-rendered fund payload and public search response. Coin uses its public server-rendered ISIN page. Neither adapter uses an account or investment APIs. Portfolio asset grouping comes from the AMFI scheme category; verified security-level asset and market-cap look-through are not currently available. Statistical SIP ranges use MFapi.in history only after the latest value is cross-checked against AMFI. The model is an explainable historical probability baseline and still needs formal out-of-sample calibration before production advisory use. India VIX is shown as unavailable when NSE blocks automated access; FundLens does not substitute an unofficial feed. MCP is the next product milestone.

See [Groww source notes](docs/sources/groww.md) for identity, validation, caching, and known limitations.

See [Coin source notes](docs/sources/coin.md) for its ISIN matching, public fields and limitations.

See [comparison notes](docs/features/comparison.md) for selection limits, row definitions and interpretation rules.

See [screener notes](docs/features/screener.md) for filter semantics, batching and missing-data handling.

See [SIP portfolio notes](docs/features/sip-portfolio.md) for allocation, overlap formulas, storage and data-coverage limits.

See [statistical SIP analysis notes](docs/features/statistical-sip-decision-support.md) for the NAV pipeline, bootstrap forecast, walk-forward checks, manager-tenure analysis, market-regime calculation and limitations.

See [NSE Indices source notes](docs/sources/nifty-indices.md) for benchmark mapping, valuation percentiles and endpoint limits.

See [NSE offer-document source notes](docs/sources/nse-offer-documents.md) for exact matching, document precedence, structured sections and missing-data behavior.

See [IPO portfolio notes](docs/features/ipo-portfolio.md) for the local data model, cash-flow definitions and FIFO calculation rules.

See [MFapi.in source notes](docs/sources/mfapi.md) for historical NAV identity checks, AMFI reconciliation and limitations.

See the [product roadmap](docs/product-roadmap.md) for completed milestones and the next statistical validation work.

See the [IPO research plan](docs/features/ipo-research-plan.md) for the planned IPO explorer, portfolio, historical cohort model and validation gates.
