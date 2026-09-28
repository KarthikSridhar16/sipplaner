import asyncio
import csv
import math
import re
from datetime import datetime, timezone

from cachetools import TTLCache

from app.normalization.identity import option_of, plan_of
from app.schemas import Fund, Metric, SourceData, SourceMatch
from app.sources.base import MutualFundSource, SourceError

NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"


def parse_catalog(text: str, fetched_at: datetime) -> list[Fund]:
    lines = text.lstrip("\ufeff").splitlines()
    header = next((line for line in lines if line.startswith("Scheme Code;")), None)
    if not header:
        raise SourceError("AMFI feed header is missing.", "Parsing Error")
    headers = header.split(";")
    required = {"Scheme Code", "Scheme Name", "Net Asset Value", "Date"}
    if not required.issubset(headers):
        raise SourceError("AMFI feed columns have changed.", "Parsing Error")
    category, amc = "Unknown", "Unknown"
    funds: dict[str, Fund] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line == header:
            continue
        if ";" not in line:
            if "Schemes(" in line:
                category = line.split("(", 1)[1].rstrip(")")
            else:
                amc = line
            continue
        fields = next(csv.reader([line], delimiter=";"))
        if len(fields) != len(headers) or not fields[0].isdigit():
            continue
        row = dict(zip(headers, fields))
        try:
            value = float(row["Net Asset Value"])
            if not math.isfinite(value) or value <= 0:
                continue
            as_of = datetime.strptime(row["Date"], "%d-%b-%Y").date()
        except ValueError:
            continue
        scheme = row["Scheme Name"].strip()
        plan = plan_of(row.get("Plan", scheme))
        option_label = row.get("Option", scheme)
        option = option_of(option_label)
        name = f"{scheme} · {row.get('Plan', '')} · {option_label}" if "Plan" in row else scheme
        nav = Metric(key="nav", label="Latest NAV", value=value, unit="INR", source="AMFI", source_url=NAV_URL,
                     fetched_at=fetched_at, as_of=as_of, definition="Published net asset value per unit.",
                     status="stale" if (datetime.now(timezone.utc).date() - as_of).days > 7 else "available")
        code = row["Scheme Code"]
        funds[code] = Fund(canonical_id=f"amfi:{code}", amfi_code=code, name=name, scheme=scheme, amc=amc,
                           category=category, plan=plan, option=option, option_label=option_label,
                           isins=[v for k, v in row.items() if k.startswith("ISIN") and re.fullmatch(r"IN[A-Z0-9]{10}", v)], nav=nav)
    if not funds:
        raise SourceError("AMFI feed contained no valid schemes.", "Parsing Error")
    return list(funds.values())


class AMFISource(MutualFundSource):
    id, name = "amfi", "AMFI"
    capabilities = ["search", "identity", "nav", "category"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.catalog_cache = TTLCache(maxsize=1, ttl=kwargs["ttl_seconds"])
        self.catalog_lock = asyncio.Lock()

    async def catalog(self) -> list[Fund]:
        async with self.catalog_lock:
            if "all" in self.catalog_cache:
                return self.catalog_cache["all"]
            text, fetched = await self.request("GET", NAV_URL)
            try:
                funds = parse_catalog(text, fetched)
            except SourceError as exc:
                raise self.parsing_error(str(exc)) from exc
            self.catalog_cache["all"] = funds
            return funds

    async def search_funds(self, query: str) -> list[Fund]:
        words = re.findall(r"[a-z0-9]+", query.lower())
        return [f for f in await self.catalog() if all(w in " ".join([f.name, f.amc, f.category, f.amfi_code, *f.isins]).lower() for w in words)]

    async def get_fund_details(self, fund: Fund, rolling_years: int = 3) -> SourceData:
        return SourceData(match=SourceMatch(source=self.name, status="Verified", name=fund.name, url=NAV_URL,
                                           method="AMFI scheme code and published ISIN"), metrics=[fund.nav])
