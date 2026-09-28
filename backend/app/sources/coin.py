import math
import re
from datetime import date, datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from app.normalization.identity import scheme_key
from app.schemas import Fund, FundFacts, FundManager, Metric, ReturnObservation, SourceData, SourceMatch
from app.sources.base import MutualFundSource, SourceError

BASE = "https://coin.zerodha.com/mf/fund/"


def number(value) -> float | None:
    try:
        result = float(str(value).strip().replace(",", "").replace("%", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def _metric(key: str, label: str, value, unit: str, url: str, fetched: datetime, *, as_of=None,
            definition=None) -> Metric:
    numeric = number(value)
    status = "available" if numeric is not None else "unavailable"
    note = None
    if numeric is not None and ((key in {"nav", "aum"} and numeric <= 0)
                                or (key == "expense_ratio" and not 0 <= numeric <= 5)):
        status, note = "suspicious", "Outside the parser's validation range. Verify the original source."
    return Metric(key=key, label=label, value=numeric, unit=unit, source="Coin", source_url=url,
                  fetched_at=fetched, as_of=as_of, status=status,
                  definition=definition or f"{label} displayed on Zerodha Coin's public fund page.", note=note)


def _table_after(heading):
    return heading.find_next("table") if heading else None


def parse_page(html: str, fund: Fund, url: str, fetched: datetime) -> SourceData:
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one("#ssr-content")
    if not root:
        raise SourceError("Coin page no longer exposes its server-rendered research summary.", "Parsing Error")

    title = root.find("h1")
    title_text = title.get_text(" ", strip=True) if title else ""
    page_text = root.get_text(" ", strip=True)
    isin_match = re.search(r"\bISIN:\s*([A-Z0-9]{12})\b", page_text)
    plan_match = re.search(r"\bPlan:\s*(Direct|Regular)\b", page_text, re.IGNORECASE)
    isin = isin_match.group(1) if isin_match else ""
    plan = plan_match.group(1).title() if plan_match else "Unknown"

    details_heading = next((h for h in root.find_all("h2") if h.get_text(" ", strip=True) == "Fund Details"), None)
    detail_rows: dict[str, str] = {}
    table = _table_after(details_heading)
    if table:
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                detail_rows[cells[0].get_text(" ", strip=True)] = cells[1].get_text(" ", strip=True)

    dividend_type = detail_rows.get("Dividend Type", "").upper()
    option = "Growth" if dividend_type == "G" else "IDCW" if dividend_type in {"D", "IDCW"} else "Unknown"
    if isin not in fund.isins or plan != fund.plan or option != fund.option:
        raise SourceError("Coin page did not confirm the selected AMFI ISIN, plan and option.", "Parsing Error")

    display_scheme = re.sub(r"\s*-\s*(Direct|Regular)\s+Plan\s*$", "", title_text, flags=re.IGNORECASE)
    warnings = []
    if scheme_key(display_scheme) != scheme_key(fund.scheme):
        warnings.append("Coin's display name differs after normalization; the exact AMFI ISIN confirmed the identity.")

    nav_match = re.search(r"\bNAV:\s*Rs\s*([\d,.]+)", page_text, re.IGNORECASE)
    nav_date_match = re.search(r"\bas of\s+(\d{4}-\d{2}-\d{2})\b", page_text, re.IGNORECASE)
    aum_match = re.search(r"(?:Rs\s*)?([\d,.]+)\s*Cr\b", detail_rows.get("AUM", ""), re.IGNORECASE)
    expense_match = re.search(r"([\d,.]+)\s*%", detail_rows.get("Expense Ratio", ""))
    metrics = [
        _metric("nav", "NAV", nav_match.group(1) if nav_match else None, "INR", url, fetched,
                as_of=parse_date(nav_date_match.group(1)) if nav_date_match else None,
                definition="NAV displayed on Zerodha Coin's public fund page."),
        _metric("aum", "Assets under management", aum_match.group(1) if aum_match else None, "Cr", url, fetched),
        _metric("expense_ratio", "Expense ratio (TER)", expense_match.group(1) if expense_match else None, "%", url, fetched,
                definition="Expense ratio displayed for the selected plan on Zerodha Coin."),
    ]

    returns_heading = next((h for h in root.find_all("h2") if h.get_text(" ", strip=True) == "Returns"), None)
    returns = []
    returns_table = _table_after(returns_heading)
    if returns_table:
        for row in returns_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) != 2:
                continue
            period_match = re.fullmatch(r"(\d+)\s+Year", cells[0].get_text(" ", strip=True), re.IGNORECASE)
            value_match = re.search(r"-?[\d,.]+", cells[1].get_text(" ", strip=True))
            if period_match and value_match:
                returns.append(ReturnObservation(period=f"{period_match.group(1)}Y", value=number(value_match.group()),
                                                 source="Coin", source_url=url, fetched_at=fetched))

    manager_text = detail_rows.get("Fund Manager", "")
    manager_name = re.sub(r"^(Mr|Mrs|Ms|Dr)\.?\s+", "", manager_text, flags=re.IGNORECASE).strip()
    managers = ([FundManager(name=manager_name, source="Coin", source_url=url)] if manager_name else [])
    inception = parse_date(detail_rows.get("Launch Date"))
    age = round((date.today() - inception).days / 365.2425, 1) if inception and inception <= date.today() else None
    facts = FundFacts(inception_date=inception, age_years=age, exit_load=detail_rows.get("Exit Load"),
                      source="Coin", source_url=url)
    warnings.append("Coin's public summary does not date its AUM or expense-ratio observations.")
    return SourceData(
        match=SourceMatch(source="Coin", status="Matched", name=title_text, url=url,
                          method="Exact AMFI ISIN in Coin's public URL and page + explicit plan + dividend type"),
        metrics=metrics, returns=returns, managers=managers, facts=facts, warnings=warnings,
    )


class CoinSource(MutualFundSource):
    id, name = "coin", "Coin"
    capabilities = ["scheme_matching", "nav", "aum", "expense_ratio", "returns", "fund_manager",
                    "fund_age", "exit_load"]

    async def search_funds(self, query: str) -> list:
        return []

    async def get_fund_details(self, fund: Fund, rolling_years: int = 3) -> SourceData:
        if not fund.isins or fund.plan == "Unknown" or fund.option == "Unknown":
            return SourceData(match=SourceMatch(source=self.name, status="Unmatched",
                              note="Coin matching requires an AMFI ISIN plus explicit plan and option."))
        url = BASE + quote(fund.isins[0], safe="")
        try:
            html, fetched = await self.request("GET", url)
            return parse_page(html, fund, url, fetched)
        except SourceError as exc:
            if exc.status == "Parsing Error":
                raise self.parsing_error(str(exc)) from exc
            return SourceData(match=SourceMatch(source=self.name, status="Unavailable", url=url, note=str(exc)),
                              warnings=[str(exc)])
