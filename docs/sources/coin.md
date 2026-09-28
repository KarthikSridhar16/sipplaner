# Zerodha Coin source adapter

The Coin adapter reads only the public, server-rendered mutual-fund summary. It does not log in, read a user's holdings, place orders, or call account/investment endpoints.

## Discovery and identity

1. Take the ISIN attached to the canonical AMFI scheme.
2. Request Coin's public `/mf/fund/{ISIN}` route; no name search or guessed scheme identifier is required.
3. Read the server-rendered `#ssr-content` section.
4. Accept observations only when the page repeats the exact ISIN and its explicit plan and dividend type match the selected AMFI plan and option.

This matching remains strict even if Coin's display name differs from AMFI after a scheme rename.

## Data used

- NAV and its displayed date, as a cross-check against AMFI
- AUM and expense ratio
- one- through five-year provider returns when present
- launch date, fund manager and displayed exit-load value

FundLens preserves Coin's values as separate observations. AMFI keeps priority for NAV, while Groww currently keeps priority for AUM and expense ratio. Material differences appear in the source-verification warnings.

## Limitations

- Coin's public summary does not supply observation dates for AUM or expense ratio.
- The summary's exit-load field can be terse, so FundLens keeps the provider text without interpreting it as a percentage or holding-period rule.
- Coin documents holdings, sectors and the Riskometer in its interactive product, but these are not present in the server-rendered public summary used by this adapter. FundLens does not use authenticated endpoints to obtain them.
- A changed page structure produces a `Parsing Error` for Coin while the rest of the analysis continues.
- No protected API, anti-bot bypass, account data, order flow or transaction capability is used.
