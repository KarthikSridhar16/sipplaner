# IPO research, portfolio and statistical analysis plan

FundLens can support Indian IPO research, but the model must differ from the SIP model. An unlisted company has no market-price history to bootstrap. Pre-listing results will therefore use verified offer-document fundamentals, issue terms, live exchange demand and a historical cohort of comparable IPOs. After listing, exchange price history can support ordinary return and drawdown analysis.

## Product areas

### IPO explorer

- Search open, upcoming, recently closed and listed issues.
- Keep main-board and SME issues separate.
- Show the price band, lot size, issue dates, issue size, fresh issue and offer-for-sale split, proposed listing exchange and document status.
- Link the exact SEBI DRHP, RHP, prospectus and addenda used by the analysis.
- Show live NSE/BSE subscription by investor category with its observation time.
- Extract financial history, use of proceeds, peer valuation, promoter dilution, material litigation and named risk factors from the offer document with page references.

### IPO portfolio

The browser-local portfolio will track research and actual allotments without connecting to a broker or placing bids.

- Watch, applied, allotted, listed, sold and skipped states.
- Lots requested, application amount, amount blocked, allotted shares and final acquisition cost.
- Listing price, current exchange price, unrealized/realized return and return relative to a suitable benchmark.
- Exposure by issuer, sector, main-board/SME, issue stage and listing vintage.
- Concentration, capital-at-risk, listing-day gap and post-listing drawdown warnings.
- Manual transaction entry with local browser storage in the first release.

### Statistical IPO analysis

Pre-listing and post-listing decisions are separate.

Pre-listing labels:

- `consider applying`
- `wait for final evidence / post-listing`
- `avoid at the offered valuation`
- `insufficient verified evidence`

Post-listing labels:

- `consider buying`
- `phase in / wait for stabilization`
- `avoid at the current valuation`
- `insufficient trading history`

The word **avoid** describes the evidence at the stated price and date. The application will not claim that an issuer should never be owned.

## Pre-listing evidence

Only information observable at the requested analysis timestamp may enter the model.

- Revenue, EBITDA, PAT and operating-cash-flow history.
- Revenue and profit growth, margins, return on equity/capital, leverage and cash conversion.
- Upper-band P/E, P/B and EV/EBITDA relative to disclosed listed peers.
- Fresh-issue versus offer-for-sale share, dilution and stated use of proceeds.
- Promoter and management background, related-party exposure, material litigation and risk-factor flags.
- QIB, NII and retail subscription separately; final demand is never backfilled into an earlier analysis.
- Issue size, firm age, sector, main-board/SME status, lead managers and listing delay.
- Nifty 50, sector-index and Nifty IPO market regime at the time of issue.

Grey-market premium will not be a decision input in the evidence-first release because it is unofficial, difficult to timestamp consistently and vulnerable to manipulation. It can be shown later only as clearly labelled unverified sentiment, separate from the model.

## Statistical method

The engine will maintain a historical IPO cohort with features frozen as of each issue's decision date. Main-board and SME models are trained and reported separately.

Outcomes include:

- listing-open and listing-close return from the final issue price;
- probability of closing below issue price on listing day;
- 30, 90, 180 and 365-day return and benchmark-relative return;
- maximum drawdown during the first year;
- probability of remaining below the issue price after 90 and 365 days.

The initial validated model suite will compare:

1. Historical base rates and matched cohorts as the mandatory baseline.
2. Regularized logistic regression for calibrated outcome probabilities.
3. Quantile gradient boosting for downside, median and upside return ranges.
4. Conformal intervals on rolling-origin holdout periods to show empirically checked uncertainty.

Model selection is based on out-of-time performance, calibration error and interval coverage rather than in-sample accuracy. Every result will show cohort size, observation period, missing fields, feature timestamp, model version and the strongest positive and negative contributors. Subscription data, market conditions and later prices must never leak backward into an earlier prediction.

## Validation gates

The statistical decision labels remain disabled until all of these gates pass:

- Canonical issue identity is reconciled across SEBI and the exchange.
- Historical issues include delisted, failed and poorly performing outcomes where obtainable; the dataset is not a winners-only sample.
- Rolling-origin validation spans hot, cold, crisis and sideways IPO markets.
- Probability calibration and quantile coverage are published by time period, main-board/SME and outcome horizon.
- The trained model beats the historical base-rate baseline on unseen periods.
- Threshold changes are versioned and recorded.

Until then, the application can show a sourced IPO research report and descriptive historical cohort without an apply/buy label.

## Primary sources

- [SEBI public-issue filings](https://www.sebi.gov.in/filings/public-issues.html): DRHP, RHP, prospectus and addenda.
- [NSE upcoming and recent IPO issues](https://www.nseindia.com/market-data/all-upcoming-issues-ipo): issue dates, status and subscription totals.
- [NSE issue information](https://www.nseindia.com/market-data/issue-information): bid and category-demand evidence.
- [Nifty IPO index](https://niftyindices.com/indices/equity/thematic-indices/nifty-ipo): post-listing IPO-market benchmark.
- BSE public-issue and market data will be used as a second exchange source where automated access and terms permit it.

Offer documents are authoritative for issuer disclosures, but their forward-looking statements are not treated as verified outcomes. Exchange observations retain both `as_of` and `fetched_at` timestamps.

## Research basis

- Sehgal and Singh, *Determinants of Initial and Long-Run Performance of IPOs in Indian Stock Market* (2008), reports firm age, listing delay and subscription as relevant determinants in its historical Indian sample: https://doi.org/10.1177/097324700800400403
- Ranganathan and Saraogi, *What explains voluntary premarket underpricing and aftermarket mispricing in Indian IPOs?* (2021), separates premarket pricing from aftermarket mispricing and studies institutional/retail demand and market momentum: https://doi.org/10.1016/j.jbef.2021.100565
- Gompers and Lerner, *The Really Long-Run Performance of Initial Public Offerings* (NBER Working Paper 8505), shows that long-run conclusions vary by abnormal-return methodology. FundLens will therefore publish both absolute and benchmark-relative outcomes: https://doi.org/10.3386/w8505

These studies motivate candidate variables and validation design; their historical coefficients will not be copied into the production model. FundLens will estimate and validate its model on its own timestamped Indian cohort.

## Delivery sequence

1. Canonical IPO catalogue, source adapters and exact document links.
2. IPO detail page with issue terms, financials, valuation, promoters, management and risk evidence.
3. Browser-local IPO watchlist and application/allotment portfolio.
4. Historical outcome dataset and reproducible feature pipeline.
5. Rolling-origin calibration report and statistical decision labels.
6. Post-listing price, drawdown and benchmark-relative monitoring.
7. IPO MCP resources and read-only research tools.
