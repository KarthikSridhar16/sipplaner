import asyncio
import re
import time
from datetime import date, datetime
from urllib.parse import urlparse

import httpx
from cachetools import TTLCache

from app.schemas import (IPODocument, IPOIssue, IPOResearchItem, IPOResearchResponse, IPOResearchSection,
                         SourceStatus, now)
from app.sources.base import SourceError

PAGE = "https://www.nseindia.com/market-data/all-upcoming-issues-ipo"
CURRENT = "https://www.nseindia.com/api/ipo-current-issue"
UPCOMING = "https://www.nseindia.com/api/all-upcoming-issues"
OFFER_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-offer-documents"
OFFER_DOCS = "https://www.nseindia.com/api/corporates/offerdocs"
ABRIDGED = "https://www.nseindia.com/api/offer-documents-abridged-prospectus"

STRUCTURED_TYPES = {
    "GENERAL": "GeneralInfo10Response",
    "OFFER_PUBLIC": "DetailsOfOfferToPublic20Response",
    "ISSUER_COMP": "PromotersOfIssuerCompany130Response",
    "BOAS": "BusinessOverviewAndStrategy140Response",
    "BOD": "BoardOfDirector150Response",
    "OBJ_ISSUE": "ObjectsOfTheIssue170Response",
    "RCA": "RestatedConsolidatedAudited210Response",
    "LITIGATION": "Litigations220Response",
    "MATERIAL": "DetailsOfTopFiveMaterialOutstandingLitigationsAgainstTheCompanyAndAmountInvolved230Response",
    "REGULATORY": "RegulatoryAction240Response",
}


def _date(value: str) -> date:
    return datetime.strptime(value.strip(), "%d-%b-%Y").date()


def _number(value, integer: bool = False):
    if value in (None, "", "-"):
        return None
    try:
        number = float(str(value).replace(",", ""))
        return int(round(number)) if integer else number
    except (TypeError, ValueError):
        return None


def _price_band(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    numbers = [float(item.replace(",", "")) for item in re.findall(r"\d[\d,]*(?:\.\d+)?", value)]
    if not numbers:
        return None, None
    return (numbers[0], numbers[-1])


def _text(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return None if text in ("", "-") else text


def _company_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _file_date(value) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return _date(text)
    except ValueError:
        return None


def _url(value) -> str | None:
    text = _text(value)
    if not text:
        return None
    parsed = urlparse(text if "://" in text else f"https://{text.lstrip('/')}")
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return parsed.geturl()


def _item(label: str, value, note: str | None = None) -> IPOResearchItem:
    text = _text(value)
    return IPOResearchItem(label=label, value=text, status="available" if text else "unavailable", note=note)


def _section(key: str, title: str, description: str, items: list[IPOResearchItem]) -> IPOResearchSection:
    return IPOResearchSection(key=key, title=title, description=description, items=items,
                              available=any(item.status == "available" for item in items))


def _series(row: dict, key: str) -> str | None:
    values = [_text(row.get(f"{key}FY{index}")) for index in (1, 2, 3)]
    if not any(values):
        return None
    return " · ".join(f"FY{index}: {value or 'unavailable'}" for index, value in enumerate(values, 1))


def parse_offer_research(issue: IPOIssue, row: dict | None, structured: dict[str, list[dict]],
                         fetched_at: datetime, request_warnings: list[str] | None = None) -> IPOResearchResponse:
    warnings = list(request_warnings or [])
    if row is None:
        unavailable = [_section(key, title, description, [_item("Evidence", None, "No exact NSE offer-document match.")])
                       for key, title, description in (
                           ("company", "Company", "Issuer identity and incorporation evidence."),
                           ("offer", "Offer structure", "Fresh issue, offer-for-sale and exchange terms."),
                           ("business", "Business", "Business model, products, markets and disclosed strategy."),
                           ("promoters", "Promoters", "Promoter identity and disclosed experience."),
                           ("directors", "Directors", "Board roles, experience and qualifications."),
                           ("objects", "Use of proceeds", "Stated objects and proposed use of issue proceeds."),
                           ("financials", "Financial snapshot", "Restated source-reported financial series."),
                           ("valuation", "Valuation inputs", "Price-band and audited earnings inputs."),
                           ("litigation", "Litigation and regulation", "Material litigation and regulatory disclosures."),
                       )]
        warnings.append("No exact company-name or exchange-symbol match was found in NSE offer documents.")
        return IPOResearchResponse(issue=issue, match_status="unavailable", sections=unavailable,
                                   warnings=warnings, fetched_at=fetched_at)

    documents = []
    for kind, label, url_key, date_key, size_key in (
        ("DRHP", "Draft red herring prospectus", "drhpAttach", "drhpDate", "drhpAttachFileSize"),
        ("RHP", "Red herring prospectus", "rhpAttach", "rhpDate", "rhpAttachFileSize"),
        ("Prospectus", "Final prospectus", "fpAttach", "fpDate", "fpAttachFileSize"),
        ("Advertisement", "Issue advertisement", "advAttach", "advDate", "advAttachFileSize"),
        ("In-principle XBRL", "In-principle filing", "ipo_inprincipal_xbrl_link", None,
         "ipo_inprincipal_xbrl_link_file_size"),
        ("Abridged prospectus XBRL", "Abridged prospectus filing", "ipo_abridged_prospectus_xbrl_link", None,
         "ipo_abridged_prospectus_xbrl_link_file_size"),
        ("Final-listing XBRL", "Final listing filing", "ipo_inlisting_xbrl_link", None,
         "ipo_inlisting_xbrl_link_file_size"),
        ("Issuer presentation", "Issuer audio-visual presentation", "drhpAvLink", "drhpSubDate", None),
    ):
        link = _url(row.get(url_key))
        if link:
            documents.append(IPODocument(kind=kind, label=label, url=link,
                                         filed_on=_file_date(row.get(date_key)) if date_key else None,
                                         file_size=_text(row.get(size_key)) if size_key else None,
                                         status=_text(row.get("drhpStatus")) if kind == "DRHP" else None))

    def rows(key: str) -> list[dict]:
        value = structured.get(key, [])
        return value if isinstance(value, list) else []

    general = (rows("GeneralInfo10Response") or [{}])[0]
    offer = (rows("DetailsOfOfferToPublic20Response") or [{}])[0]
    business = (rows("BusinessOverviewAndStrategy140Response") or [{}])[0]
    finance = (rows("RestatedConsolidatedAudited210Response") or [{}])[0]
    regulatory = (rows("RegulatoryAction240Response") or [{}])[0]
    structured_rhp = _url(general.get("urlofRHP"))
    if structured_rhp and not any(document.kind == "RHP" for document in documents):
        documents.append(IPODocument(kind="RHP", label="Red herring prospectus", url=structured_rhp))

    company_items = [
        _item("Issuer", general.get("nameOfTheIssuerCompany") or row.get("company")),
        _item("CIN", general.get("cinofTheIssuerCompany")),
        _item("Incorporated", general.get("dateOfIncorporation")),
        _item("Registered office", general.get("addressOfRegisteredOffice")),
        _item("Website", general.get("websiteOfTheCompany")),
    ]
    offer_items = [
        _item("Issue type", offer.get("typeOfIssue")),
        _item("Fresh issue shares", offer.get("numberOfSharesInFreshIssue")),
        _item("Fresh issue amount", offer.get("amountOfFreshIssueSize"), "Source-reported amount; unit is not inferred."),
        _item("OFS shares", offer.get("numberOfSharesInOpenForSales")),
        _item("OFS amount", offer.get("amountOfOpenForSaleSize"), "Source-reported amount; unit is not inferred."),
        _item("Total issue shares", offer.get("numberOfSharesInTotalIssue")),
        _item("Total issue amount", offer.get("totalAmountOfIssueSize"), "Source-reported amount; unit is not inferred."),
        _item("Proposed exchanges", offer.get("stockExchangeWhereEquitySharesAreProposedToBeListed")),
    ]
    business_items = [
        _item("Overview", business.get("overviewOfTheCompany")),
        _item("Products and services", business.get("productOrServiceOfferingOfTheCompany")),
        _item("Markets and clients", business.get("detailsOfClientProfileOrIndustriesServed")),
        _item("Geographies", business.get("detailsOfGeographiesServed")),
        _item("Key performance indicators", business.get("detailsOfKeyPerformanceIndicators")),
        _item("Employees", business.get("strengthOfEmployee")),
    ]
    promoter_items = []
    for promoter in rows("PromotersOfIssuerCompany130Response"):
        name = _text(promoter.get("nameOfPromoter"))
        detail = " · ".join(filter(None, [_text(promoter.get("typeOfPromoterIndividualOrCorporate")),
                                          _text(promoter.get("experienceAndEducationalQualification"))]))
        promoter_items.append(_item(name or "Promoter", detail or None))
    director_items = []
    for director in rows("BoardOfDirector150Response"):
        name = _text(director.get("nameOfBoardOfDirector"))
        detail = " · ".join(filter(None, [_text(director.get("designationOfBoardOfDirector")),
                                          _text(director.get("experienceOfBoardOfDirector")),
                                          _text(director.get("educationalQualificationOfBoardOfDirector"))]))
        director_items.append(_item(name or "Director", detail or None))
    object_items = []
    for purpose in rows("ObjectsOfTheIssue170Response"):
        label = _text(purpose.get("objectsOfTheIssue")) or "Disclosed object"
        object_items.append(_item(label, purpose.get("amountToBeFinanced"), "Source-reported amount; unit is not inferred."))
    finance_items = [
        _item("Revenue from operations", _series(finance, "totalIncomeFromOperations"), "FY1–FY3 labels follow the NSE filing response."),
        _item("Profit after tax", _series(finance, "profAfterItemsAndTax"), "FY1–FY3 labels follow the NSE filing response."),
        _item("Net worth", _series(finance, "netWorth"), "FY1–FY3 labels follow the NSE filing response."),
        _item("Basic EPS", _series(finance, "basicLossPerShare"), "FY1–FY3 labels follow the NSE filing response."),
        _item("Return on net worth", _series(finance, "returnOnNetWorth"), "Raw source values; scale is not inferred."),
    ]
    valuation_items = [
        _item("Upper price band", issue.price_max),
        _item("Basic EPS series", _series(finance, "basicLossPerShare"), "A P/E is withheld until the fiscal-period mapping is explicit."),
        _item("Computed P/E", None, "Unavailable: the NSE response does not explicitly map FY1–FY3 to dates."),
    ]
    litigation_items = []
    for index, litigation in enumerate(rows("Litigations220Response"), 1):
        parts = [f"Criminal: {_text(litigation.get('criminalProceedings')) or 'unavailable'}",
                 f"Tax: {_text(litigation.get('taxProceedings')) or 'unavailable'}",
                 f"Regulatory: {_text(litigation.get('statutoryOrRegulatoryProceedings')) or 'unavailable'}",
                 f"Civil: {_text(litigation.get('materialCivilLitigations')) or 'unavailable'}",
                 f"Aggregate amount: {_text(litigation.get('aggregateAmountInvolved')) or 'unavailable'}"]
        litigation_items.append(_item(f"Litigation row {index}", " · ".join(parts), "Amount units follow the source filing."))
    for index, material in enumerate(rows("DetailsOfTopFiveMaterialOutstandingLitigationsAgainstTheCompanyAndAmountInvolved230Response"), 1):
        detail = " · ".join(filter(None, [_text(material.get("detailsOfLitigation")),
                                          _text(material.get("currentStatusOfLitigation")),
                                          _text(material.get("amountInvolvedInLitigation"))]))
        if detail and detail.lower() != "nil · nil · nil":
            litigation_items.append(_item(f"Material case {index}", detail))
    regulatory_detail = " · ".join(filter(None, [_text(regulatory.get("briefDetailsOfCriminalProceedings")),
                                                   _text(regulatory.get("disciplinaryActionTakenBySEBI")),
                                                   _text(regulatory.get("anyOtherImpInfoAsPerBRLM"))]))
    if regulatory_detail:
        litigation_items.append(_item("Regulatory disclosure", regulatory_detail))

    sections = [
        _section("company", "Company", "Issuer identity and incorporation evidence.", company_items),
        _section("offer", "Offer structure", "Fresh issue, offer-for-sale and exchange terms.", offer_items),
        _section("business", "Business", "Business model, products, markets and disclosed KPIs.", business_items),
        _section("promoters", "Promoters", "Promoter identity and disclosed experience.", promoter_items or [_item("Promoters", None)]),
        _section("directors", "Directors", "Board roles, experience and qualifications.", director_items or [_item("Directors", None)]),
        _section("objects", "Use of proceeds", "Stated objects and proposed use of issue proceeds.", object_items or [_item("Objects", None)]),
        _section("financials", "Financial snapshot", "Restated source-reported financial series.", finance_items),
        _section("valuation", "Valuation inputs", "Price-band and audited earnings inputs; unsupported ratios stay unavailable.", valuation_items),
        _section("litigation", "Litigation and regulation", "Material litigation and regulatory disclosures.", litigation_items or [_item("Disclosures", None)]),
    ]
    if not any(section.available for section in sections[1:]):
        warnings.append("NSE has an offer-document record, but structured abridged-prospectus sections are not published yet.")
    warnings.extend([
        "DRHP information can change; use the RHP or final prospectus when available for an investment decision.",
        "Source-reported financial values are displayed without inferred currency units or fiscal-year labels.",
        "Valuation multiples remain unavailable until the financial period and share-count basis can be verified.",
    ])
    return IPOResearchResponse(issue=issue, match_status="exact", matched_company=_text(row.get("company")),
                               document_status=_text(row.get("drhpStatus")), documents=documents, sections=sections,
                               warnings=list(dict.fromkeys(warnings)), fetched_at=fetched_at)


def parse_catalogue(current: list[dict], upcoming: list[dict], fetched_at: datetime,
                    today: date | None = None) -> list[IPOIssue]:
    today = today or fetched_at.date()
    merged: dict[tuple[str, str], dict] = {}
    for item in upcoming:
        if item.get("symbol") and item.get("issueStartDate"):
            merged[(item["symbol"], item["issueStartDate"])] = dict(item)
    for item in current:
        if item.get("symbol") and item.get("issueStartDate"):
            key = (item["symbol"], item["issueStartDate"])
            merged[key] = {**merged.get(key, {}), **item}
    issues = []
    for item in merged.values():
        try:
            start, end = _date(item["issueStartDate"]), _date(item["issueEndDate"])
        except (KeyError, TypeError, ValueError):
            continue
        status = "upcoming" if today < start else "closed" if today > end else "open"
        symbol = str(item["symbol"]).strip().upper()
        series = str(item.get("series") or "EQ").strip().upper()
        exchange = "BSE" if str(item.get("isBse") or "") == "1" else "NSE"
        board = "Mainboard" if series == "EQ" else "SME"
        low, high = _price_band(item.get("issuePrice"))
        issues.append(IPOIssue(
            canonical_id=f"ipo:{exchange.lower()}:{symbol}:{start.isoformat()}",
            company_name=str(item.get("companyName") or symbol).strip(), symbol=symbol,
            exchange=exchange, board=board, series=series, status=status, issue_start=start, issue_end=end,
            price_band_text=item.get("issuePrice"), price_min=low, price_max=high,
            issue_size_shares=_number(item.get("issueSize"), True),
            shares_offered=_number(item.get("noOfSharesOffered"), True),
            shares_bid=_number(item.get("noOfsharesBid"), True),
            subscription_times=_number(item.get("noOfTime")), fetched_at=fetched_at,
        ))
    order = {"open": 0, "upcoming": 1, "closed": 2}
    return sorted(issues, key=lambda item: (order[item.status], item.issue_end, item.company_name.lower()))


class NSEIPOSource:
    id = "nse_ipo"
    name = "NSE IPO"
    capabilities = ["ipo_catalogue", "issue_dates", "price_band", "subscription", "mainboard_and_sme",
                    "offer_documents", "structured_prospectus"]

    def __init__(self, *, enabled: bool, ttl_seconds: int, interval_seconds: float, timeout: float = 20):
        self.enabled = enabled
        self.status = "Not checked" if enabled else "Disabled"
        self.message: str | None = None
        self.last_success: datetime | None = None
        self.cache = TTLCache(maxsize=32, ttl=ttl_seconds)
        self.lock = asyncio.Lock()
        self.interval = interval_seconds
        self.next_request = 0.0
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FundLens/0.1; IPO research)",
            "Accept": "application/json,text/plain,*/*", "Referer": PAGE,
        })

    async def _get(self, url: str, **kwargs):
        await asyncio.sleep(max(0, self.next_request - time.monotonic()))
        try:
            response = await self.client.get(url, **kwargs)
            if response.status_code in (401, 403, 429):
                raise SourceError(f"NSE IPO returned HTTP {response.status_code}; access was not retried.",
                                  "Rate Limited" if response.status_code == 429 else "Unavailable")
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise SourceError("NSE IPO data could not be reached. Try again later.") from exc
        finally:
            self.next_request = time.monotonic() + self.interval

    async def catalogue(self) -> tuple[list[IPOIssue], datetime]:
        if not self.enabled:
            raise SourceError("NSE IPO is disabled.", "Disabled")
        if "catalogue" in self.cache:
            return self.cache["catalogue"]
        async with self.lock:
            if "catalogue" in self.cache:
                return self.cache["catalogue"]
            try:
                await self._get(PAGE)
                current_response = await self._get(CURRENT)
                upcoming_response = await self._get(UPCOMING, params={"category": "ipo"})
                current, upcoming = current_response.json(), upcoming_response.json()
                if not isinstance(current, list) or not isinstance(upcoming, list):
                    raise ValueError("IPO endpoints did not return lists")
                fetched = now()
                issues = parse_catalogue(current, upcoming, fetched)
                if not issues:
                    raise ValueError("No valid IPO issues were returned")
                self.last_success, self.status, self.message = fetched, "Healthy", None
                self.cache["catalogue"] = (issues, fetched)
                return issues, fetched
            except SourceError as exc:
                self.status, self.message = exc.status, str(exc)
                raise
            except (ValueError, TypeError) as exc:
                self.status, self.message = "Parsing Error", "NSE IPO returned an unexpected response."
                raise SourceError(self.message, self.status) from exc

    async def offer_records(self, board: str) -> tuple[list[dict], datetime]:
        if not self.enabled:
            raise SourceError("NSE IPO is disabled.", "Disabled")
        index = "sme" if board == "SME" else "equities"
        key = f"offer_records:{index}"
        if key in self.cache:
            return self.cache[key]
        async with self.lock:
            if key in self.cache:
                return self.cache[key]
            try:
                await self._get(OFFER_PAGE)
                response = await self._get(OFFER_DOCS, params={"index": index})
                records = response.json()
                if not isinstance(records, list):
                    raise ValueError("Offer-document endpoint did not return a list")
                fetched = now()
                self.last_success, self.status, self.message = fetched, "Healthy", None
                self.cache[key] = (records, fetched)
                return records, fetched
            except SourceError as exc:
                self.status, self.message = exc.status, str(exc)
                raise
            except (ValueError, TypeError) as exc:
                self.status, self.message = "Parsing Error", "NSE offer documents returned an unexpected response."
                raise SourceError(self.message, self.status) from exc

    async def research(self, issue: IPOIssue) -> IPOResearchResponse:
        key = f"research:{issue.canonical_id}"
        if key in self.cache:
            return self.cache[key]
        records, fetched = await self.offer_records(issue.board)
        issue_key = _company_key(issue.company_name)
        row = next((candidate for candidate in records
                    if _company_key(candidate.get("company")) == issue_key
                    or (_text(candidate.get("symbol")) not in (None, "-")
                        and _text(candidate.get("symbol")).upper() == issue.symbol.upper())), None)
        structured: dict[str, list[dict]] = {}
        warnings: list[str] = []
        if row and _text(row.get("pan_no")) and _url(row.get("ipo_abridged_prospectus_xbrl_link")):
            for detail_type, response_key in STRUCTURED_TYPES.items():
                try:
                    response = await self._get(ABRIDGED, params={"pan_no": row["pan_no"], "type": detail_type})
                    payload = response.json()
                    values = payload.get(response_key, []) if isinstance(payload, dict) else []
                    if isinstance(values, list):
                        structured[response_key] = values
                except (SourceError, ValueError, TypeError):
                    warnings.append(f"NSE structured section {detail_type} was unavailable during this fetch.")
        result = parse_offer_research(issue, row, structured, fetched, warnings)
        self.cache[key] = result
        return result

    def health(self) -> SourceStatus:
        return SourceStatus(id=self.id, name=self.name, enabled=self.enabled, status=self.status,
                            last_success=self.last_success, message=self.message, capabilities=self.capabilities)

    async def close(self):
        await self.client.aclose()
