# SIP portfolio analysis

FundLens stores a SIP plan as canonical AMFI scheme IDs and monthly amounts in browser localStorage. No portfolio is written to the backend or a database. A live analysis request can contain one to twelve unique funds with positive monthly SIP amounts.

## Calculations

- Fund allocation is each monthly SIP divided by the total monthly SIP.
- Category allocation uses the exact AMFI scheme category.
- Asset grouping maps AMFI categories to Equity, Debt, Hybrid, or Other / solution-oriented. This is a category grouping, not a security-level asset look-through.
- Risk allocation uses the source-reported SEBI Riskometer label when available. Missing risk remains `Unavailable`.
- Sector exposure multiplies every disclosed fund-sector weight by that fund's SIP allocation, then sums by sector.
- A shared holding appears when its normalized disclosed name occurs in two or more selected funds. Its exposure is the sum of each fund holding weight multiplied by that fund's SIP allocation.
- Pairwise overlap is the sum of the lower disclosed weight for every common holding between two funds. The value describes the provider's disclosed portfolio and is not a full economic-exposure model.

Holding-name normalization is intentionally conservative: it removes punctuation and common corporate suffixes such as `Limited` and `Ltd`. It does not use fuzzy company matching, which could combine unrelated securities.

## Coverage and warnings

Holdings coverage is the share of the monthly SIP assigned to funds with verified disclosed holdings. Funds without holdings are excluded from sector and overlap calculations, and the response states the resulting coverage. The API also flags a fund allocation above 50%, a disclosed sector exposure above 30%, and pairwise overlap at or above 50%.

Market-cap exposure is returned as unavailable because the current verified sources do not provide a complete, dated market-cap look-through. FundLens does not infer it from a scheme name or category.

The analysis describes portfolio structure. It does not determine investor suitability, recommend a fund, forecast returns, or time an entry.

## API

`POST /api/portfolio/analyse`

```json
{
  "entries": [
    { "canonical_id": "amfi:118989", "monthly_sip": 6000 },
    { "canonical_id": "amfi:119010", "monthly_sip": 4000 }
  ],
  "rolling_years": 3
}
```
