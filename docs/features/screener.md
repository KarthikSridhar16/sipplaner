# Fund screener

The FundLens screener applies manual catalogue and evidence filters without storing a market-wide analytics database. It first narrows the current AMFI catalogue, then performs the normal multi-source analysis for a bounded batch of candidates.

## Catalogue scope

A request must provide at least one of category, AMC or name/keyword. Plan defaults to Direct and option defaults to Growth.

Specific equity categories use AMFI's leaf category. For example, `Mid Cap` matches `Mid Cap Fund` and does not include `Large & Mid Cap Fund`. Debt and Hybrid remain broad groups. The API returns the total catalogue candidates and the offset of the current batch.

## Evidence filters

- beta below a maximum
- expense ratio below a maximum
- shortest reported current-manager tenure at or above a minimum
- upside capture above a minimum
- downside capture below a maximum
- optional minimum and maximum AUM
- optional minimum fund age
- optional SEBI Riskometer level

Every active criterion returns its raw value, source, operator, threshold, and `PASS`, `FAIL`, or `UNAVAILABLE` state. Strict mode excludes a fund when any active criterion is unavailable. The optional provisional mode can include a fund when no criterion fails but one or more values are unavailable; such a result is marked as incomplete evidence.

## Batching

Each request analyses two to eight candidates. A page warning states when more AMFI candidates exist, and the UI provides previous/next batch controls. Batching bounds provider traffic and makes it explicit that one response is not a complete market ranking.

## Local state

The last submitted filters are saved in browser localStorage with the user's other preferences. Results are fetched live and are not stored permanently.

## Interpretation

Results are ordered with matches first and then alphabetically. FundLens does not calculate a winner or silently treat missing data as zero. A filter match reflects only the returned observations and does not establish investor suitability.
