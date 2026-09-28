from datetime import date, datetime, timezone

from app.schemas import IPOIssue
from app.sources.nse_ipo import parse_catalogue, parse_offer_research


FETCHED = datetime(2026, 9, 28, 6, 30, tzinfo=timezone.utc)


def test_nse_ipo_catalogue_merges_live_subscription_with_upcoming_identity():
    upcoming = [{
        "companyName": "Example Industries Limited", "symbol": "EXAMPLE", "series": "EQ",
        "issueStartDate": "28-Sep-2026", "issueEndDate": "30-Sep-2026",
        "issuePrice": "Rs.159 to Rs.167", "issueSize": "3779440", "status": "Active",
    }, {
        "companyName": "Future Limited", "symbol": "FUTURE", "series": "EQ",
        "issueStartDate": "05-Oct-2026", "issueEndDate": "07-Oct-2026",
        "issuePrice": "Rs.200 to Rs.220", "status": "Forthcoming",
    }]
    current = [{
        **upcoming[0], "category": "Total", "noOfSharesOffered": "3779440.0",
        "noOfsharesBid": "803675.0", "noOfTime": "0.21264393666786613",
    }, {
        "companyName": "BSE SME Limited", "symbol": "BSESME", "series": "SME", "isBse": "1",
        "issueStartDate": "25-Sep-2026", "issueEndDate": "29-Sep-2026",
        "noOfSharesOffered": "2761200", "noOfsharesBid": "3103200", "noOfTime": "1.12",
    }]

    issues = parse_catalogue(current, upcoming, FETCHED, date(2026, 9, 28))

    assert len(issues) == 3
    example = next(issue for issue in issues if issue.symbol == "EXAMPLE")
    assert example.canonical_id == "ipo:nse:EXAMPLE:2026-09-28"
    assert example.status == "open"
    assert (example.price_min, example.price_max) == (159, 167)
    assert example.shares_offered == 3_779_440
    assert example.subscription_times == 0.21264393666786613
    future = next(issue for issue in issues if issue.symbol == "FUTURE")
    assert future.status == "upcoming"
    sme = next(issue for issue in issues if issue.symbol == "BSESME")
    assert sme.exchange == "BSE"
    assert sme.board == "SME"


def test_nse_ipo_catalogue_skips_records_without_valid_issue_dates():
    issues = parse_catalogue([{"companyName": "Broken", "symbol": "BROKEN"}], [], FETCHED)
    assert issues == []


def test_offer_research_preserves_documents_and_structured_evidence_without_inferred_valuation():
    issue = IPOIssue(canonical_id="ipo:nse:EXAMPLE:2026-09-28", company_name="Example Industries Limited",
                     symbol="EXAMPLE", exchange="NSE", board="Mainboard", series="EQ", status="open",
                     issue_start=date(2026, 9, 28), issue_end=date(2026, 9, 30), price_max=167, fetched_at=FETCHED)
    row = {
        "company": "Example Industries Limited", "drhpStatus": "Approved",
        "drhpAttach": "https://nsearchives.nseindia.com/corporate/example.pdf", "drhpDate": "01-Mar-2026",
        "drhpAttachFileSize": "10 MB", "ipo_inprincipal_xbrl_link": "-",
    }
    structured = {
        "DetailsOfOfferToPublic20Response": [{"typeOfIssue": "Fresh & OFS", "numberOfSharesInFreshIssue": "1000",
                                               "numberOfSharesInOpenForSales": "500"}],
        "PromotersOfIssuerCompany130Response": [{"nameOfPromoter": "A Promoter",
                                                  "typeOfPromoterIndividualOrCorporate": "Individual"}],
        "RestatedConsolidatedAudited210Response": [{"totalIncomeFromOperationsFY1": "100",
                                                     "totalIncomeFromOperationsFY2": "120",
                                                     "totalIncomeFromOperationsFY3": "150",
                                                     "basicLossPerShareFY3": "8.5"}],
        "Litigations220Response": [{"taxProceedings": "1", "aggregateAmountInvolved": "4.12"}],
    }

    result = parse_offer_research(issue, row, structured, FETCHED)

    assert result.match_status == "exact"
    assert result.document_status == "Approved"
    assert result.documents[0].kind == "DRHP"
    assert result.documents[0].filed_on == date(2026, 3, 1)
    offer = next(section for section in result.sections if section.key == "offer")
    assert next(item.value for item in offer.items if item.label == "Issue type") == "Fresh & OFS"
    financials = next(section for section in result.sections if section.key == "financials")
    assert next(item.value for item in financials.items if item.label == "Revenue from operations") == "FY1: 100 · FY2: 120 · FY3: 150"
    valuation = next(section for section in result.sections if section.key == "valuation")
    computed = next(item for item in valuation.items if item.label == "Computed P/E")
    assert computed.status == "unavailable"
    assert "withheld" in next(item.note for item in valuation.items if item.label == "Basic EPS series")


def test_offer_research_fails_closed_when_no_exact_document_match_exists():
    issue = IPOIssue(canonical_id="ipo:bse:NOPE:2026-09-28", company_name="No Match Limited", symbol="NOPE",
                     exchange="BSE", board="SME", series="SME", status="open", issue_start=date(2026, 9, 28),
                     issue_end=date(2026, 9, 30), fetched_at=FETCHED)

    result = parse_offer_research(issue, None, {}, FETCHED)

    assert result.match_status == "unavailable"
    assert result.documents == []
    assert all(not section.available for section in result.sections)
    assert "No exact" in result.warnings[-1]
