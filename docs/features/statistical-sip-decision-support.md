# Statistical SIP analysis

This feature answers one focused research question for a selected mutual fund:

> Based on the fund's historical return distribution, downside behavior and current benchmark valuation, should a new SIP be started now, phased in or avoided under the current evidence?

It does not collect income, expenses, debt, goals or other personal-finance inputs. The only user inputs are the fund, monthly SIP amount and analysis horizon.

## Result labels

- **Invest now**: the fund has enough history, the loss distribution is acceptable under the initial thresholds, the walk-forward evidence is usable and the mapped benchmark is not in an elevated valuation regime.
- **Phase in / wait for better entry**: the fund evidence may be usable, but current valuation, loss probability or evidence depth supports a smaller phased start. The result includes a measurable review trigger rather than predicting a perfect date.
- **Avoid this fund**: at least two fund-specific structural concerns are present, such as non-positive long-run return, high simulated loss probability, weak walk-forward outcomes or multiple live research-rule failures. A high market valuation alone cannot produce this result.
- **Insufficient data**: reserved for cases where the minimum validated history cannot be obtained.

These labels are outputs from a research model. They are not guaranteed forecasts.

## Data pipeline

1. The AMFI catalogue supplies the canonical scheme code, scheme identity and latest official NAV.
2. MFapi.in supplies the full daily NAV history for that exact AMFI scheme code.
3. The latest historical observation is cross-checked against the official AMFI NAV before the history is accepted.
4. Daily NAVs are reduced to month-end observations. The analysis uses up to ten years of monthly returns.
5. NSE Indices supplies benchmark close history and P/E/P/B observations for entry-regime context.

MFapi.in is a free third-party historical feed. The application identifies it separately from AMFI and retains the official latest-NAV cross-check because AMFI's own history download is limited to 90-day fund-house files.

## Statistical method

### Historical risk

The engine calculates annualized NAV return, annualized monthly volatility, downside deviation, maximum month-end drawdown, positive-month frequency and best/worst months.

### Moving-block bootstrap

The forecast resamples contiguous three-month return blocks instead of independent individual months. This retains short runs of positive and negative returns and is more appropriate for serially dependent time-series observations than an independent bootstrap.

For each request, 4,000 reproducible SIP paths are simulated. Each path applies the monthly contribution before that month's return. The API returns the 10th, 25th, 50th, 75th and 90th percentile terminal values, the probability of finishing below total contributions and the probability of exceeding a constant 12% annualized SIP outcome.

The primary research basis is Künsch, *The Jackknife and the Bootstrap for General Stationary Observations*, Annals of Statistics 17(3), 1989, DOI `10.1214/aos/1176347265`.

### Walk-forward SIP evidence

The same SIP is replayed across every available historical monthly start date for a three-to-five-year window. The result reports the number of overlapping windows, profitable-window percentage and best, median and worst annualized SIP returns. Because windows overlap, they are evidence about observed regimes rather than independent trials.

### Fund-manager analysis

The current manager name, reported start date, tenure, experience profile and other reported funds come from the identity-verified live fund provider. For each current manager, the engine slices the validated month-end NAV series at the reported tenure start and calculates the fund's annualized return, volatility, maximum drawdown and positive-month frequency over that period. If tenure predates the ten-year NAV sample, the interface states the shorter coverage period. Fewer than six monthly tenure returns suppresses the calculated metrics.

Tenure is classified as recent below three years, developing from three to five years, and established at five years or more. Any current manager below three years marks a recent transition. Missing or recent tenure reduces the overall evidence confidence by one level, but manager tenure alone cannot produce an **avoid this fund** result.

These are fund returns observed during a manager's reported tenure. They do not isolate decisions made by that person, separate a co-manager's contribution, adjust for the benchmark, or prove persistent manager skill. Co-manager changes remain visible because the shortest current tenure drives the transition warning.

### Entry regime

The category-appropriate Nifty benchmark is classified with official NSE Indices observations:

- P/E and P/B percentile in the available valuation history
- distance from the 200-day closing-index average
- six-month return
- drawdown from the latest one-year high

An average valuation percentile of at least 75 is **elevated** and at least 90 is **extreme**. Elevated or extreme valuation can change an otherwise usable fund result to **phase in / wait for better entry**. Review is triggered when valuation falls below the 75th percentile, the index returns near its 200-day average or the next monthly valuation update arrives.

Valuation ratios have evidence as long-horizon return predictors but do not reliably identify exact short-term turning points. See Campbell and Shiller, *Valuation Ratios and the Long-Run Stock Market Outlook: An Update*, NBER Working Paper 8221.

## Guardrails

- Projections are conditional historical distributions, not promised future values.
- The model does not use a single recent return or fund ranking as proof of manager skill. Out-of-sample research finds that much mutual-fund winner persistence disappears; see Choi and Zhao, NBER Working Paper 26707.
- Manager tenure evidence changes confidence and highlights team transitions; it is not treated as causal performance attribution.
- An unseen future crisis cannot be created by bootstrapping history.
- Scheme mergers and code changes are not synthetically spliced.
- Every response shows the data dates, source, method version and limitations.

## API

`POST /api/sip/statistical-analysis`

```json
{
  "canonical_id": "amfi:118989",
  "monthly_sip": 5000,
  "horizon_years": 5,
  "simulations": 4000
}
```

Supported horizons are 3, 5 and 10 years. Simulation count is bounded from 1,000 to 10,000.
