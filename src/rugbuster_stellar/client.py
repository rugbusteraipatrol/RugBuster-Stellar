"""Small, dependency-free Horizon client with bounded retries."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HorizonError(RuntimeError):
    """Raised when Horizon cannot provide a usable response."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class HorizonResponse:
    data: dict[str, Any]
    latest_ledger: int | None
    url: str


class HorizonClient:
    def __init__(
        self,
        base_url: str = "https://horizon.stellar.org",
        *,
        timeout: float = 15.0,
        retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def get(self, path: str, params: dict[str, Any] | None = None) -> HorizonResponse:
        query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "RugBuster-Stellar/0.1",
                    },
                )
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    ledger_header = response.headers.get("Latest-Ledger")
                    return HorizonResponse(
                        data=payload,
                        latest_ledger=int(ledger_header) if ledger_header else None,
                        url=url,
                    )
            except HTTPError as exc:
                if exc.code < 500 and exc.code != 429:
                    raise HorizonError(
                        f"Horizon returned HTTP {exc.code} for {url}", status=exc.code
                    ) from exc
                last_error = exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc

            if attempt < self.retries:
                time.sleep(0.4 * (2**attempt))

        raise HorizonError(f"Horizon request failed for {url}: {last_error}")

