# NSE Indices market-regime source

FundLens uses the public historical-data calls exposed by the official NSE Indices reports page. The adapter sends bounded requests to the same-origin historical close and P/E, P/B and dividend-yield endpoints used by that page.

## Current benchmark mapping

- Large Cap: Nifty 100
- Mid Cap: Nifty Midcap 150
- Small Cap: Nifty Smallcap 250
- Flexi Cap, Multi Cap and other diversified equity categories: Nifty 500
- Recognized Nifty 50 and Nifty Next 50 scheme names: their named index
- Debt categories: no equity benchmark regime is assigned

The mapping is a first-release default and must be reviewed for every AMFI category before advisory use.

## Calculations

- Close history uses the latest allowed one-year request.
- One-year drawdown compares the latest close with the maximum close in that response.
- Six-month return uses the observation closest to 182 days before the latest date.
- Trend compares the latest close with the average of up to 200 latest daily closes.
- Valuation history uses four bounded yearly requests, deduplicated by date.
- P/E and P/B percentiles are empirical ranks within the available daily history.
- The valuation state is `below historical range` at or below the 25th average percentile, `elevated` from the 75th percentile, and `extreme` from the 90th percentile.

Every response preserves the benchmark, source URL, observation date, history start and number of valuation observations. Missing or changed source data returns an unavailable regime rather than a fabricated value.

India VIX is an official planned source, but NSE may block automated requests. FundLens keeps it unavailable in that case and does not substitute a third-party value.
