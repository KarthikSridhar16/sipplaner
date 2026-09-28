import asyncio
import json
import math
from datetime import date, datetime, timedelta

from app.schemas import Fund, MarketRegime, SourceData, SourceMatch
from app.sources.base import MutualFundSource, SourceError

BASE = "https://www.niftyindices.com"
REPORTS = f"{BASE}/reports"
HISTORY = f"{BASE}/BackPage/getHistoricaldatatabletoString"
VALUATION = f"{BASE}/BackPage/getpepbHistoricaldataDBtoString"


def benchmark_for(fund: Fund) -> str | None:
    category = fund.category.lower()
    scheme = fund.scheme.lower()
    if category.startswith("debt scheme"):
        return None
    if "nifty 50" in scheme and "next 50" not in scheme:
        return "Nifty 50"
    if "next 50" in scheme:
        return "Nifty Next 50"
    if "midcap 150" in scheme or "mid cap" in category:
        return "Nifty Midcap 150"
    if "smallcap 250" in scheme or "small cap" in category:
        return "Nifty Smallcap 250"
    if "large cap" in category and "large & mid" not in category:
        return "Nifty 100"
    if category.startswith("equity scheme") or category.startswith("hybrid scheme"):
        return "Nifty 500"
    return None


def _number(value) -> float | None:
    try:
        number = float(str(value).replace(",", ""))
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _day(value: str) -> date | None:
    for fmt in ("%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            pass
    return None


def _percentile(values: list[float], current: float) -> float:
    return round(sum(value <= current for value in values) / len(values) * 100, 1)


def calculate_regime(benchmark: str, history_rows: list[dict], valuation_rows: list[dict]) -> MarketRegime:
    history = []
    for row in history_rows:
        day, close = _day(row.get("HistoricalDate", "")), _number(row.get("CLOSE"))
        if day is not None and close is not None:
            history.append((day, close))
    history.sort(key=lambda item: item[0])
    valuations = []
    for row in valuation_rows:
        day = _day(row.get("DATE", ""))
        pe, pb, dividend = _number(row.get("pe")), _number(row.get("pb")), _number(row.get("divYield"))
        if day is not None and (pe is not None or pb is not None):
            valuations.append((day, pe, pb, dividend))
    valuations.sort(key=lambda item: item[0])
    if not history:
        return MarketRegime(benchmark=benchmark, status="unavailable", note="NSE Indices returned no verified close history.")
    as_of, close = history[-1]
    closes = [item[1] for item in history]
    high = max(closes)
    drawdown = round((close / high - 1) * 100, 2)
    target = as_of - timedelta(days=182)
    six_month = min(history, key=lambda item: abs((item[0] - target).days))[1]
    return_6m = round((close / six_month - 1) * 100, 2) if six_month else None
    average_200 = sum(closes[-200:]) / len(closes[-200:])
    versus_average = round((close / average_200 - 1) * 100, 2) if average_200 else None
    pe = pb = dividend = pe_percentile = pb_percentile = None
    state = "unavailable"
    history_start = None
    if valuations:
        history_start = valuations[0][0]
        _, pe, pb, dividend = valuations[-1]
        pe_values = [item[1] for item in valuations if item[1] is not None]
        pb_values = [item[2] for item in valuations if item[2] is not None]
        pe_percentile = _percentile(pe_values, pe) if pe is not None and pe_values else None
        pb_percentile = _percentile(pb_values, pb) if pb is not None and pb_values else None
        ranks = [value for value in (pe_percentile, pb_percentile) if value is not None]
        rank = sum(ranks) / len(ranks) if ranks else None
        if rank is not None:
            state = "extreme" if rank >= 90 else "elevated" if rank >= 75 else "below historical range" if rank <= 25 else "within historical range"
    return MarketRegime(
        benchmark=benchmark, status="available", as_of=as_of, close=round(close, 2),
        drawdown_1y_percent=drawdown, return_6m_percent=return_6m,
        versus_200d_average_percent=versus_average, pe=pe, pe_percentile=pe_percentile,
        pb=pb, pb_percentile=pb_percentile, dividend_yield=dividend, valuation_state=state,
        history_start=history_start, valuation_observations=len(valuations),
        note="Valuation percentiles use available daily NSE Indices observations; close history is limited to the latest year per public request.",
    )


class NiftyIndicesSource(MutualFundSource):
    id, name = "nifty", "NSE Indices"
    capabilities = ["benchmark_history", "tri_reference", "valuation", "market_regime"]

    async def search_funds(self, query: str) -> list:
        return []

    async def get_fund_details(self, fund: Fund, rolling_years: int = 3) -> SourceData:
        return SourceData(match=SourceMatch(source=self.name, status="Not applicable"))

    async def _rows(self, url: str, benchmark: str, start: date, end: date) -> list[dict]:
        cinfo = {"name": benchmark.upper(), "startDate": start.strftime("%m/%d/%Y"),
                 "endDate": end.strftime("%m/%d/%Y"), "indexName": benchmark}
        text, _ = await self.request("POST", url, json={"cinfo": str(cinfo).replace('"', "'")},
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            value = json.loads(text)
            if isinstance(value, dict) and "d" in value:
                value = json.loads(value["d"]) if isinstance(value["d"], str) else value["d"]
            if not isinstance(value, list):
                raise ValueError("response was not a list")
            return value
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise self.parsing_error("NSE Indices returned an unexpected market-data response.") from exc

    async def regime(self, benchmark: str) -> MarketRegime:
        today = datetime.now().date()
        history_start = today - timedelta(days=364)
        ranges = []
        end = today
        for _ in range(4):
            start = end - timedelta(days=364)
            ranges.append((start, end))
            end = start - timedelta(days=1)
        try:
            tasks = [self._rows(HISTORY, benchmark, history_start, today)]
            tasks.extend(self._rows(VALUATION, benchmark, start, end) for start, end in ranges)
            results = await asyncio.gather(*tasks)
            valuation_by_date = {}
            for rows in results[1:]:
                for row in rows:
                    valuation_by_date[row.get("DATE")] = row
            return calculate_regime(benchmark, results[0], list(valuation_by_date.values()))
        except SourceError as exc:
            return MarketRegime(benchmark=benchmark, status="unavailable", note=str(exc))
