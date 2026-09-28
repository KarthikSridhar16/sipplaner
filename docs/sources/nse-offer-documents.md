# NSE offer-document research source

FundLens uses NSE India's public corporate-filings offer-document page and its public JSON responses for issue research.

Source page: https://www.nseindia.com/companies-listing/corporate-filings-offer-documents

## Identity and matching

The selected issue comes from the live NSE IPO catalogue. FundLens loads the corresponding Mainboard or SME offer-document collection and accepts a record only when the normalized company name is exact or the published exchange symbol is exact. It does not use fuzzy company-name matching. An unmatched issue remains unavailable.

## Documents

The adapter preserves official links for the DRHP, RHP, final prospectus, issue advertisement, in-principle XBRL, abridged-prospectus XBRL, final-listing XBRL and issuer audio-visual presentation when NSE publishes them. Dates, file sizes and the draft-document status are retained when supplied.

The RHP or final prospectus takes precedence over the DRHP for an investment decision because terms and disclosures can change after the draft filing.

## Structured sections

When NSE publishes an abridged-prospectus XBRL record, FundLens reads the public structured sections for:

- issuer identity and incorporation
- fresh issue and offer-for-sale composition
- business overview, markets and disclosed KPIs
- promoters and directors
- objects and proposed use of proceeds
- restated financial series
- litigation and regulatory disclosures

The API can publish an offer-document record before it publishes the structured abridged-prospectus sections. FundLens shows the document links immediately and marks those research sections unavailable.

## Financial and valuation safeguards

Some structured financial responses label observations only as FY1, FY2 and FY3 and do not state the currency unit in the same response. FundLens preserves those labels and raw values. It does not infer fiscal dates, currency scale or a price-to-earnings multiple. A valuation multiple remains unavailable until its period, share-count basis and unit can be verified.

## Caching and failures

Responses use the configured short-lived in-memory IPO cache. Upstream failures return a source error; malformed response shapes fail closed. Missing fields are shown as unavailable and are never converted to zero.
