"""Dependency-free local HTTP API and demo server."""

from __future__ import annotations

import argparse
import json
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
                    "methodology": "rugbuster_stellar_classic_v0.1",
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
        status, report = scan_request(payload)
        self._json(status, report)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
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
