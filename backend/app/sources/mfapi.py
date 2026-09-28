import json
import math
from datetime import date, datetime, timedelta

from app.schemas import Fund, HistoricalNAVPoint, SourceData, SourceMatch
from app.sources.base import MutualFundSource, SourceError

BASE = "https://api.mfapi.in/mf"
SITE = "https://www.mfapi.in/"


def parse_history(text: str, fund: Fund, fetched_at: datetime, max_years: int = 10) -> list[HistoricalNAVPoint]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourceError("MFapi.in returned invalid historical NAV data.", "Parsing Error") from exc
    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if str(meta.get("scheme_code", "")) != fund.amfi_code or not isinstance(rows, list):
        raise SourceError("Historical NAV identity did not match the selected AMFI scheme.", "Parsing Error")
    cutoff = fetched_at.date() - timedelta(days=366 * max_years)
    points: dict[date, HistoricalNAVPoint] = {}
    for row in rows:
        try:
            day = datetime.strptime(str(row["date"]), "%d-%m-%Y").date()
            nav = float(row["nav"])
        except (KeyError, TypeError, ValueError):
            continue
        if day >= cutoff and math.isfinite(nav) and nav > 0:
            points[day] = HistoricalNAVPoint(date=day, nav=nav)
    result = sorted(points.values(), key=lambda item: item.date)
    if len(result) < 24:
        raise SourceError("Fewer than 24 valid historical NAV observations were returned.", "Parsing Error")
    return result


def verify_against_amfi(points: list[HistoricalNAVPoint], fund: Fund) -> None:
    official_day = fund.nav.as_of
    official_nav = fund.nav.value
    if official_day is None or official_nav is None:
        raise SourceError("The latest official AMFI NAV is unavailable for identity verification.")
    matched = next((point for point in points if point.date == official_day), None)
    if matched is None:
        raise SourceError("Historical NAV does not yet contain the latest dated AMFI observation.")
    difference = abs(matched.nav / official_nav - 1)
    if difference > 0.001:
        raise SourceError("Historical NAV failed the latest-value cross-check against AMFI.", "Parsing Error")


class MFAPIHistorySource(MutualFundSource):
    id, name = "mfapi", "MFapi.in"
    capabilities = ["historical_nav", "monthly_returns", "sip_simulation"]

    async def search_funds(self, query: str) -> list:
        return []

    async def get_fund_details(self, fund: Fund, rolling_years: int = 3) -> SourceData:
        return SourceData(match=SourceMatch(source=self.name, status="Not applicable"))

    async def history(self, fund: Fund, max_years: int = 10) -> tuple[list[HistoricalNAVPoint], datetime]:
        text, fetched_at = await self.request("GET", f"{BASE}/{fund.amfi_code}")
        try:
            points = parse_history(text, fund, fetched_at, max_years)
            verify_against_amfi(points, fund)
            return points, fetched_at
        except SourceError as exc:
            raise self.parsing_error(str(exc)) from exc
