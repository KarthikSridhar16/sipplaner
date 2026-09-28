# Browser-local IPO portfolio

The IPO portfolio records applications and post-listing transactions in browser localStorage. It does not connect to a broker, bank or demat account and does not place an IPO bid.

## Stored application snapshot

Each application preserves the canonical issue identifier, company, symbol, exchange and Mainboard/SME classification so the record remains readable after the issue leaves the live catalogue. Up to 50 applications and 100 post-listing transactions per application are retained.

The ledger records:

- planned, applied, allotted, refunded, listed and closed stages;
- application date, lots, shares per lot and bid price;
- allotment date and allotted shares;
- refund amount and date;
- listing date and listing price;
- manually observed current price and its date;
- manual post-listing buys, sells and fees.

## Cash-flow definitions

Application amount is `lots applied × shares per lot × bid price`.

Allotment cost is `allotted shares × bid price`.

Expected refund is the positive difference between the application amount and allotment cost. Refund outstanding is the positive difference between expected refund and the manually recorded refund. Refunds are cash releases from the IPO application and are not classified as investment profit.

Listing profit is the allotted-share gain or loss from the bid price to the manually entered listing price. It is an observation and is not added again to current portfolio profit.

## Holdings and return calculations

Allotted shares form the first acquisition lot at the bid price. Manual post-listing buys add acquisition lots with fees included in their cost. Sells consume available lots in first-in, first-out order. Selling fees reduce proceeds.

- Remaining cost basis is the cost of unsold lots.
- Realized profit is sell proceeds after fees minus the FIFO cost consumed.
- Current value is remaining shares multiplied by the manually entered current price.
- Unrealized profit is current value minus remaining cost basis.
- Total tracked profit is realized plus priced unrealized profit.

If the current price is unavailable, current value and unrealized profit remain unavailable. The interface prevents adding a sell larger than the currently tracked holding and warns if imported saved data contains an oversell.

## Persistence and verification

The complete ledger stays in the existing `fundlens.preferences.v1` localStorage object. Loading validates identifiers, dates, numeric bounds, statuses and transactions before accepting saved records. Users should verify every entry against broker and bank records.
