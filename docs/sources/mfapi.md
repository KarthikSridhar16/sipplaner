# MFapi.in historical NAV source

## Role

MFapi.in provides a full historical NAV series for an AMFI scheme code in one JSON response. FundLens uses it only for the statistical SIP model.

- Website: <https://www.mfapi.in/>
- Scheme history: `https://api.mfapi.in/mf/{AMFI_SCHEME_CODE}`
- Authentication: none
- Cost: free at the time of implementation
- Classification: third-party historical data feed

## Trust checks

1. The requested code comes from the current official AMFI catalogue.
2. The returned `meta.scheme_code` must equal that code.
3. The history must include the exact date of the latest AMFI observation.
4. The historical value on that date must differ from AMFI by no more than 0.1%.
5. Invalid, duplicate, non-positive and non-finite observations are rejected.

If any identity or latest-value check fails, the statistical result is unavailable. FundLens does not silently fall back to an unmatched history.

## Why it is used

AMFI is the source of record and exposes historical NAV downloads, but its current public interface limits each request to 90 days and returns a full fund-house file. Using that interface for an interactive ten-year, single-scheme analysis would require many large requests. MFapi.in makes the same scheme-level history practical while the AMFI latest-NAV cross-check protects identity and freshness.

## Limits

- MFapi.in is not AMFI and does not replace the official catalogue or current NAV.
- A valid cross-check confirms identity and the latest shared observation; it cannot independently audit every historical row.
- Renamed, merged and discontinued schemes keep their own scheme-code history. FundLens does not splice successor histories.
