import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime

import httpx
from cachetools import TTLCache

from app.schemas import Fund, SourceData, SourceStatus, now


class SourceError(Exception):
    def __init__(self, message: str, status: str = "Unavailable"):
        super().__init__(message)
        self.status = status


class MutualFundSource(ABC):
    id: str
    name: str
    capabilities: list[str]

    def __init__(self, *, enabled: bool, ttl_seconds: int, interval_seconds: float, timeout: float = 20):
        self.enabled = enabled
        self.status = "Not checked" if enabled else "Disabled"
        self.message: str | None = None
        self.last_success: datetime | None = None
        self.cache = TTLCache(maxsize=128, ttl=ttl_seconds)
        self.lock = asyncio.Lock()
        self.next_request = 0.0
        self.cooldown_until = 0.0
        self.interval = interval_seconds
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                       headers={"User-Agent": "FundLens/0.1 (mutual-fund research)"})

    async def request(self, method: str, url: str, **kwargs) -> tuple[str, datetime]:
        if not self.enabled:
            raise SourceError(f"{self.name} is disabled.", "Disabled")
        data = kwargs.get("data", {})
        data_key = str(sorted(data.items())) if isinstance(data, dict) else str(data)
        key = (method, url, data_key, str(sorted(kwargs.get("params", {}).items())),
               repr(kwargs.get("json")), str(kwargs.get("content", "")))
        async with self.lock:
            if key in self.cache:
                return self.cache[key]
            if time.monotonic() < self.cooldown_until:
                raise SourceError(f"{self.name} is cooling down after an upstream failure.", self.status)
            for attempt in range(2):
                await asyncio.sleep(max(0, self.next_request - time.monotonic()))
                started = time.monotonic()
                try:
                    response = await self.client.request(method, url, **kwargs)
                    if response.status_code in (401, 403, 429):
                        self.cooldown_until = time.monotonic() + 60
                        raise SourceError(f"{self.name} returned HTTP {response.status_code}; access was not retried.",
                                          "Rate Limited" if response.status_code == 429 else "Unavailable")
                    response.raise_for_status()
                    if len(response.content) > 12_000_000:
                        raise SourceError("Source response exceeded the size limit.", "Parsing Error")
                    self.last_success = now()
                    self.status = "Slow" if time.monotonic() - started > 5 else "Healthy"
                    self.message = None
                    result = (response.text, self.last_success)
                    self.cache[key] = result
                    return result
                except SourceError as exc:
                    self.status, self.message = exc.status, str(exc)
                    raise
                except httpx.HTTPError as exc:
                    retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code >= 500
                    if attempt == 0 and retryable:
                        await asyncio.sleep(1)
                        continue
                    self.status, self.message = "Unavailable", f"{self.name} could not be reached. Try again later."
                    self.cooldown_until = time.monotonic() + 30
                    raise SourceError(self.message) from exc
                finally:
                    self.next_request = time.monotonic() + self.interval
        raise SourceError("No source response.")

    def parsing_error(self, message: str) -> SourceError:
        self.status, self.message = "Parsing Error", message
        self.cache.clear()
        return SourceError(message, "Parsing Error")

    def health(self) -> SourceStatus:
        return SourceStatus(id=self.id, name=self.name, enabled=self.enabled, status=self.status,
                            last_success=self.last_success, message=self.message, capabilities=self.capabilities)

    async def close(self):
        await self.client.aclose()

    @abstractmethod
    async def search_funds(self, query: str) -> list:
        """Return provider candidates; unsupported searches return an empty list."""

    @abstractmethod
    async def get_fund_details(self, fund: Fund, rolling_years: int = 3) -> SourceData:
        """Return a validated provider snapshot, with unsupported metrics unavailable."""
