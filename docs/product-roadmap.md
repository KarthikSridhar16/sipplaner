# FundLens product roadmap

This document records product decisions and planned work that should survive beyond a single development session.

## Build order

1. AMFI catalogue and canonical scheme identity — complete
2. AdvisorKhoj research metrics — complete
3. Analysis dashboard and browser-local settings/watchlist — complete
4. Groww verification, facts, returns and portfolio — complete
5. Zerodha Coin verification — complete
6. Multi-fund comparison — complete
7. Fund screener — complete
8. SIP portfolio allocation and overlap analysis — complete
9. Fund-level statistical SIP analysis — first release complete
10. Category/benchmark-relative statistical validation and calibration report
11. IPO catalogue, exchange evidence and browser-local watchlist — first release complete
12. IPO offer-document, financial, valuation and promoter research — first release complete
13. IPO application, allotment and holdings portfolio — first release complete
14. Statistical IPO cohort, calibration report and decision support
15. MCP tools and resources for mutual funds, SIPs and IPOs
16. Deployment hardening

## Statistical SIP analysis product decision

The application analyses a selected SIP/fund. It does not manage the user's personal finances and does not ask for income, expenses, debt, emergency reserves or goals.

Inputs are limited to:

- selected canonical AMFI scheme
- monthly SIP amount
- 3, 5 or 10-year analysis horizon

The first release returns one of four research actions:

- `invest now`
- `phase in / wait for better entry`
- `avoid this fund`
- `insufficient data`

The action must be supported by the fund's historical NAV distribution, observed downside, walk-forward SIP outcomes, live fund-quality checks and current official benchmark valuation. It must show weak, median and strong outcome ranges rather than a promised point forecast.

`Phase in / wait` must include a measurable review condition. `Avoid` requires multiple fund-specific concerns; expensive market conditions alone do not make a fund permanently unsuitable.

See [the statistical SIP analysis design](features/statistical-sip-decision-support.md) for the implemented data pipeline, model and limitations.

## IPO product decision

IPO research is a separate evidence pipeline because an unlisted issuer has no NAV or traded-price history. The pre-listing model will use SEBI offer documents, exchange issue/subscription observations, comparable-company valuation, current market conditions and an out-of-time validated historical IPO cohort. Post-listing analysis will use exchange prices and benchmark-relative outcomes.

The IPO portfolio will remain browser-local and will record applications, allotments and holdings; it will not place bids or connect to a broker in its first release. Statistical apply/buy labels remain disabled until the historical dataset passes the documented calibration gates.

See [the IPO research plan](features/ipo-research-plan.md) for sources, model outcomes, validation gates and delivery order.

## Next statistical milestone

- Add category-index total-return history so fund paths can be assessed relative to a benchmark, not only in isolation.
- Run rolling-origin calibration: test whether forecast percentile bands contain later realized SIP values at the expected frequency.
- Add survivorship and scheme-merger audits without synthetically splicing unrelated scheme codes.
- Publish a validation dataset and threshold-change log.
- Add regime sensitivity tests for crises, sideways markets, rising-rate periods and unusually strong bull runs.
- Review the language and operating model against applicable SEBI research and advisory requirements before any production recommendation service.

## Guardrails

- No promise of returns or exact market timing.
- Preserve source, observation date, fetch time and methodology version.
- Keep historical simulation separate from current market-entry evidence.
- Treat missing evidence as unavailable, never as zero.
- Do not infer persistent manager skill from a recent winner ranking.
- Retain an `insufficient data` outcome when the identity or NAV-history checks fail.
