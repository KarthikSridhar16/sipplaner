import json
import math
import re
from datetime import date, datetime
from urllib.parse import quote, urlencode

from bs4 import BeautifulSoup

from app.normalization.identity import advisor_slug, same_growth_fund
from app.schemas import Fund, Metric, RollingSummary, SourceData, SourceMatch
from app.sources.base import MutualFundSource, SourceError

BASE = "https://www.advisorkhoj.com/mutual-funds-research/"
LABELS = {"beta": ("Beta", ""), "standard_deviation": ("Standard deviation", "%"),
          "sharpe": ("Sharpe ratio", ""), "alpha": ("Alpha", "%"),
          "expense_ratio": ("Expense ratio (TER)", "%"), "aum": ("Assets under management", "Cr"),
          "upside_capture": ("Upside capture", "%"), "downside_capture": ("Downside capture", "%"),
          "capture_ratio": ("Capture ratio", "")}


def number(value) -> float | None:
    try:
        result = float(str(value).strip().replace(",", "").replace("%", ""))
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def parse_date(value: str) -> date | None:
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def metric(key, value, url, fetched, *, as_of=None, benchmark=None, period=None, note=None):
    label, unit = LABELS[key]
    status = "available" if value is not None else "unavailable"
    if value is not None and ((key == "expense_ratio" and not 0 <= value <= 5)
                              or (key == "aum" and value <= 0) or (key == "standard_deviation" and value < 0)):
        status, note = "suspicious", "Outside the parser's validation range. Verify the original source."
    if status == "available" and as_of and (date.today() - as_of).days > 45:
        status, note = "stale", "Published value is more than 45 days old."
    return Metric(key=key, label=label, value=value, unit=unit, source="AdvisorKhoj", source_url=url,
                  fetched_at=fetched, as_of=as_of, benchmark=benchmark, period=period, status=status,
                  definition=f"{label} reported by AdvisorKhoj; retain the provider's methodology.", note=note)


def parse_details(html: str, fund: Fund, candidate: str, url: str, fetched: datetime):
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("h1")
    if not title or not same_growth_fund(fund.scheme, fund.plan, title.get_text(" ", strip=True)):
        raise SourceError("AdvisorKhoj page did not confirm the selected scheme and plan.", "Parsing Error")
    rows = [row.find_all("td", recursive=False) for row in soup.select("tr")]
    values = {}
    info = {}
    for cells in rows:
        if len(cells) == 1:
            text = cells[0].get_text(" ", strip=True)
            if ":" in text:
                key, value = text.split(":", 1)
                info.setdefault(key.strip(), value.strip())
        if len(cells) == 2:
            values.setdefault(cells[0].get_text(" ", strip=True).lower(), cells[1].get_text(" ", strip=True))
    benchmark = info.get("Benchmark")
    metrics = []
    for key, label in [("beta", "beta"), ("standard_deviation", "standard deviation"), ("sharpe", "sharpe ratio"), ("alpha", "alpha")]:
        metrics.append(metric(key, number(values.get(label)), url, fetched, benchmark=benchmark,
                              note="The page does not specify this metric's as-of date, lookback or sampling frequency."))
    for key, field in [("expense_ratio", "TER"), ("aum", "Total Assets")]:
        text = info.get(field, "")
        value_match = re.match(r"([\d,.]+)", text)
        date_match = re.search(r"(\d{2}-\d{2}-\d{4})", text)
        metrics.append(metric(key, number(value_match[1]) if value_match else None, url, fetched,
                              as_of=parse_date(date_match[1]) if date_match else None))
    category = info.get("Category")
    if not any(m.value is not None for m in metrics):
        raise SourceError("AdvisorKhoj detail page no longer contains recognised metrics.", "Parsing Error")
    return metrics, category, parse_date(info.get("Launch Date", ""))


def parse_rolling(text: str, candidate: str, category: str, years: int, start: date, url: str, fetched: datetime):
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise SourceError("Rolling-return response is not valid JSON.", "Parsing Error") from exc
    if not isinstance(data, list):
        raise SourceError("Rolling-return response shape changed.", "Parsing Error")
    row = next((r for r in data if isinstance(r, dict) and r.get("scheme_name") == candidate and r.get("category_flag") == 0), None)
    summary = RollingSummary(years=years, start_date=start, source_url=url, fetched_at=fetched)
    if not row:
        summary.note = "The provider returned no rolling history for this exact scheme."
        return summary, None
    for key in ("average", "median", "minimum", "maximum"):
        setattr(summary, key, number(row.get(key)))
    if summary.minimum is not None and summary.maximum is not None and summary.minimum > summary.maximum:
        raise SourceError("Rolling-return range is invalid.", "Parsing Error")
    negative = number(row.get("less_than_0"))
    if negative is not None and 0 <= negative <= 100:
        summary.positive_percent = 100 - negative
    category_row = next((r for r in data if isinstance(r, dict) and r.get("scheme_name") == category and r.get("category_flag") == 1), {})
    summary.category_average = number(category_row.get("average"))
    summary.status = "available" if all(getattr(summary, k) is not None for k in ("average", "median", "minimum", "maximum")) else "unavailable"
    summary.note = "Provider-calculated rolling annualised returns. Latest window date and category-beating frequency are not supplied."
    return summary, row.get("scheme_amfi_short_name")


def parse_capture(html: str, short_name: str, url: str, fetched: datetime, years: int) -> list[Metric]:
    soup = BeautifulSoup(html, "lxml")
    for table in soup.select("table"):
        headings = " ".join(th.get_text(" ", strip=True) for th in table.select("th")).lower()
        if "up market capture" not in headings or "down market capture" not in headings:
            continue
        for row in table.select("tbody tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all("td", recursive=False)]
            if len(cells) >= 7 and cells[0] == short_name:
                return [metric(key, number(value), url, fetched, benchmark=cells[2], period=f"{years} years",
                               note="Provider calculation. As-of date and sampling frequency are not stated.")
                        for key, value in zip(("upside_capture", "downside_capture", "capture_ratio"), cells[-3:])]
    return []


class AdvisorKhojSource(MutualFundSource):
    id, name = "advisorkhoj", "AdvisorKhoj"
    capabilities = ["scheme_matching", "beta", "standard_deviation", "sharpe", "alpha", "expense_ratio", "aum", "rolling_returns", "capture_ratios"]

    async def search_funds(self, query: str) -> list[str]:
        text, _ = await self.request("POST", BASE + "autoSuggestAllMfSchemesInSchemeDetailsPage", data={"query": query})
        try:
            result = json.loads(text)
            if not isinstance(result, list) or any(not isinstance(r, str) for r in result):
                raise ValueError()
            return result
        except ValueError as exc:
            raise self.parsing_error("AdvisorKhoj search response format changed.") from exc

    async def get_fund_details(self, fund: Fund, rolling_years: int = 3) -> SourceData:
        if fund.option != "Growth":
            return SourceData(match=SourceMatch(source=self.name, status="Unavailable", note="IDCW sub-option reconciliation is not yet supported; AMFI identity remains available."))
        candidates = await self.search_funds(fund.scheme)
        matches = [c for c in candidates if same_growth_fund(fund.scheme, fund.plan, c)]
        if len(matches) != 1:
            return SourceData(match=SourceMatch(source=self.name, status="Unmatched", note="No unique exact scheme-and-plan match. Similar names were not merged."))
        candidate = matches[0]
        url = BASE + quote(advisor_slug(candidate), safe="-")
        html, fetched = await self.request("GET", url)
        try:
            metrics, category, inception = parse_details(html, fund, candidate, url, fetched)
        except SourceError as exc:
            raise self.parsing_error(str(exc)) from exc
        result = SourceData(match=SourceMatch(source=self.name, status="Matched", name=candidate, url=url,
                            method="Unique normalized scheme name + explicit plan + Growth, confirmed by page heading"), metrics=metrics)
        if not category or not inception:
            result.warnings.append("Rolling and capture analysis require the provider's category and inception date.")
            return result
        # Bound the window to at most ten years of start dates; preserve that choice in provenance.
        start = max(inception, date(date.today().year - 10, 1, 1))
        params = {"schemes": quote(quote(candidate, safe=""), safe=""), "category": category,
                  "start_date": start.strftime("%d-%m-%Y"), "period": f"{rolling_years} Year"}
        try:
            text, rolling_fetched = await self.request("POST", BASE + "getRollingReturnsSch", data=params)
            rolling_url = BASE + "rolling-returns?" + urlencode({"scheme": candidate, "start_date": params["start_date"], "period": params["period"]})
            result.rolling, short_name = parse_rolling(text, candidate, category, rolling_years, start, rolling_url, rolling_fetched)
            if short_name:
                capture_params = {"category": category, "schemes": short_name, "period": "3"}
                capture_url = BASE + "market-capture-ratio?" + urlencode(capture_params)
                capture_html, capture_fetched = await self.request("GET", capture_url)
                result.metrics.extend(parse_capture(capture_html, short_name, capture_url, capture_fetched, 3))
        except SourceError as exc:
            if exc.status == "Parsing Error":
                self.parsing_error(str(exc))
            result.warnings.append(str(exc))
        return result
