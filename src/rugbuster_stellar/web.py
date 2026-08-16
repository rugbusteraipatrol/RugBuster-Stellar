"""Dependency-free local HTTP API and demo server."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any, Callable
from urllib.parse import urlparse

from .client import HorizonClient
from .scanner import StellarAssetScanner

NETWORKS = {
    "mainnet": "https://horizon.stellar.org",
    "testnet": "https://horizon-testnet.stellar.org",
}
MAX_BODY_BYTES = 16_384

# Public-demo protections. Neither is meant to withstand a determined
# attacker; the job is to keep one careless script or crawler from exhausting
# the shared Horizon request budget for every other visitor, and to make
# repeated clicks on a popular asset feel instant instead of re-scanning it.
CACHE_TTL_SECONDS = 120.0
CACHE_MAX_ENTRIES = 500
RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX_REQUESTS = 6
RATE_LIMIT_MAX_TRACKED_CLIENTS = 2_000

_cache_lock = threading.Lock()
_scan_cache: dict[tuple[str, str, str, int], tuple[float, int, dict[str, Any]]] = {}

_rate_lock = threading.Lock()
_rate_buckets: dict[str, list[float]] = {}


def scan_request(
    payload: dict[str, Any],
    scanner_factory: Callable[..., StellarAssetScanner] = StellarAssetScanner,
) -> tuple[int, dict[str, Any]]:
    code = str(payload.get("asset_code", "")).strip()
    issuer = str(payload.get("issuer", "")).strip()
    network = str(payload.get("network", "mainnet")).strip().lower()
    try:
        max_holders = int(payload.get("max_holders", 200))
    except (TypeError, ValueError):
        return HTTPStatus.BAD_REQUEST, {"error": "max_holders_must_be_an_integer"}

    if network not in NETWORKS:
        return HTTPStatus.BAD_REQUEST, {"error": "network_must_be_mainnet_or_testnet"}
    if not 1 <= max_holders <= 500:
        return HTTPStatus.BAD_REQUEST, {"error": "max_holders_must_be_between_1_and_500"}

    scanner = scanner_factory(HorizonClient(NETWORKS[network]), max_holders=max_holders)
    report = scanner.scan(code, issuer)
    invalid = any(
        item.startswith("invalid_asset_code") or item.startswith("invalid_issuer_address")
        for item in report.get("limitations", [])
    )
    return (HTTPStatus.BAD_REQUEST if invalid else HTTPStatus.OK), report


def _cache_key(payload: dict[str, Any]) -> tuple[str, str, str, int]:
    try:
        max_holders = int(payload.get("max_holders", 200))
    except (TypeError, ValueError):
        max_holders = 200
    return (
        str(payload.get("network", "mainnet")).strip().lower(),
        str(payload.get("asset_code", "")).strip().upper(),
        str(payload.get("issuer", "")).strip().upper(),
        max_holders,
    )


def cached_scan_request(
    payload: dict[str, Any],
    scanner_factory: Callable[..., StellarAssetScanner] = StellarAssetScanner,
    *,
    now: float | None = None,
) -> tuple[int, dict[str, Any], bool]:
    """`scan_request` behind a short TTL cache, keyed on the scan inputs.

    Only successful (200) reports are cached, so a bad request never sticks.
    `scan_request` itself stays uncached and is what the test suite exercises
    directly -- this wrapper only matters for the running public demo.
    """
    moment = time.monotonic() if now is None else now
    key = _cache_key(payload)
    with _cache_lock:
        cached = _scan_cache.get(key)
        if cached and moment - cached[0] < CACHE_TTL_SECONDS:
            return cached[1], cached[2], True

    status, report = scan_request(payload, scanner_factory)
    if status == HTTPStatus.OK:
        with _cache_lock:
            if len(_scan_cache) >= CACHE_MAX_ENTRIES:
                oldest_key = min(_scan_cache, key=lambda k: _scan_cache[k][0])
                _scan_cache.pop(oldest_key, None)
            _scan_cache[key] = (moment, status, report)
    return status, report, False


def allow_request(client_ip: str, *, now: float | None = None) -> bool:
    """A simple fixed-window per-IP limiter for the public demo.

    Not distributed and not meant to withstand a determined attacker; its job
    is to keep one careless script from exhausting the shared Horizon budget
    for every other visitor.
    """
    moment = time.monotonic() if now is None else now
    with _rate_lock:
        if client_ip not in _rate_buckets and len(_rate_buckets) >= RATE_LIMIT_MAX_TRACKED_CLIENTS:
            oldest_ip = min(_rate_buckets, key=lambda ip: _rate_buckets[ip][0] if _rate_buckets[ip] else 0.0)
            _rate_buckets.pop(oldest_ip, None)
        bucket = _rate_buckets.setdefault(client_ip, [])
        cutoff = moment - RATE_LIMIT_WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        bucket.append(moment)
        return True


class RugBusterHandler(BaseHTTPRequestHandler):
    server_version = "RugBusterStellar/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlparse(self.path).path
        if path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "rugbuster-stellar",
                    "methodology": "rugbuster_stellar_classic_v0.2",
                },
            )
            return
        static = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
        }
        if path not in static:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        filename, content_type = static[path]
        content = files("rugbuster_stellar").joinpath("static", filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers(html=filename == "index.html")
        self.end_headers()
        self._write_body(content)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if urlparse(self.path).path != "/api/scan":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        client_ip = self.client_address[0] if self.client_address else "unknown"
        if not allow_request(client_ip):
            self._json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "error": "rate_limited",
                    "detail": f"Max {RATE_LIMIT_MAX_REQUESTS} scans per "
                    f"{int(RATE_LIMIT_WINDOW_SECONDS)}s per client on this public demo.",
                },
                extra_headers={"Retry-After": str(int(RATE_LIMIT_WINDOW_SECONDS))},
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_body_size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "json_object_required"})
            return
        status, report, cache_hit = cached_scan_request(payload)
        self._json(status, report, extra_headers={"X-Cache": "HIT" if cache_hit else "MISS"})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self._security_headers()
        self.end_headers()
        self._write_body(body)

    def _security_headers(self, *, html: bool = False) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        if html:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            )
        else:
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")

    def _write_body(self, body: bytes) -> None:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # A browser tab may close while a bounded Horizon scan is finishing.
            return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local RugBuster Stellar demo")
    # Defaults favor local, single-user use (127.0.0.1). The public deploy
    # sets HOST=0.0.0.0 explicitly via environment rather than relying on an
    # implicit default here, so a plain local run never accidentally listens
    # beyond localhost.
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", default=int(os.getenv("PORT", "8787")), type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), RugBusterHandler)
    print(f"RugBuster Stellar demo: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
