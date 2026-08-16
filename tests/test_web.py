from http import HTTPStatus

import pytest

import rugbuster_stellar.web as web_module
from rugbuster_stellar.web import (
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    RugBusterHandler,
    allow_request,
    cached_scan_request,
    scan_request,
)


@pytest.fixture(autouse=True)
def _reset_shared_demo_state():
    """The scan cache and rate-limit buckets are module-level state shared by
    every request the running server handles. Tests must not leak into each
    other through it."""
    web_module._scan_cache.clear()
    web_module._rate_buckets.clear()
    yield
    web_module._scan_cache.clear()
    web_module._rate_buckets.clear()


class FakeScanner:
    def __init__(self, client, *, max_holders):
        self.client = client
        self.max_holders = max_holders
        self.calls = 0

    def scan(self, code, issuer):
        self.calls += 1
        return {
            "verdict": "LOW_OBSERVED_RISK",
            "risk_score": 0,
            "asset": {"code": code, "issuer": issuer},
            "limitations": [],
        }


def test_scan_request_accepts_mainnet_payload():
    status, report = scan_request(
        {
            "network": "mainnet",
            "asset_code": "USDC",
            "issuer": "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
            "max_holders": 50,
        },
        scanner_factory=FakeScanner,
    )
    assert status == HTTPStatus.OK
    assert report["verdict"] == "LOW_OBSERVED_RISK"


def test_scan_request_rejects_unknown_network():
    status, report = scan_request(
        {"network": "futurenet", "asset_code": "TEST", "issuer": "G..."},
        scanner_factory=FakeScanner,
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert report["error"] == "network_must_be_mainnet_or_testnet"


def test_scan_request_bounds_holder_work():
    status, report = scan_request(
        {
            "network": "mainnet",
            "asset_code": "TEST",
            "issuer": "G...",
            "max_holders": 501,
        },
        scanner_factory=FakeScanner,
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert report["error"] == "max_holders_must_be_between_1_and_500"


def test_cached_scan_request_avoids_a_second_scan_within_the_ttl():
    payload = {
        "network": "mainnet",
        "asset_code": "USDC",
        "issuer": "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
        "max_holders": 50,
    }
    scanners = []

    def factory(client, *, max_holders):
        scanner = FakeScanner(client, max_holders=max_holders)
        scanners.append(scanner)
        return scanner

    status1, report1, hit1 = cached_scan_request(payload, factory, now=1_000.0)
    status2, report2, hit2 = cached_scan_request(payload, factory, now=1_010.0)

    assert (status1, status2) == (HTTPStatus.OK, HTTPStatus.OK)
    assert report1 == report2
    assert (hit1, hit2) == (False, True)
    assert len(scanners) == 1
    assert scanners[0].calls == 1


def test_cached_scan_request_expires_after_the_ttl():
    payload = {
        "network": "mainnet",
        "asset_code": "USDC",
        "issuer": "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
        "max_holders": 50,
    }
    call_count = 0

    def factory(client, *, max_holders):
        nonlocal call_count
        call_count += 1
        return FakeScanner(client, max_holders=max_holders)

    cached_scan_request(payload, factory, now=1_000.0)
    cached_scan_request(payload, factory, now=1_000.0 + 121.0)

    assert call_count == 2


def test_cached_scan_request_does_not_cache_errors():
    payload = {"network": "futurenet", "asset_code": "TEST", "issuer": "G..."}

    status, report, hit = cached_scan_request(payload, FakeScanner, now=1_000.0)

    assert status == HTTPStatus.BAD_REQUEST
    assert hit is False
    # A second call at the same instant must not be served from cache either --
    # only successful reports are cached.
    status2, report2, hit2 = cached_scan_request(payload, FakeScanner, now=1_000.0)
    assert hit2 is False


def test_allow_request_permits_up_to_the_limit_then_blocks():
    client_ip = "203.0.113.5"
    for _ in range(RATE_LIMIT_MAX_REQUESTS):
        assert allow_request(client_ip, now=1_000.0) is True
    assert allow_request(client_ip, now=1_000.0) is False


def test_allow_request_resets_after_the_window():
    client_ip = "203.0.113.9"
    for _ in range(RATE_LIMIT_MAX_REQUESTS):
        allow_request(client_ip, now=2_000.0)
    assert allow_request(client_ip, now=2_000.0) is False

    assert allow_request(client_ip, now=2_000.0 + RATE_LIMIT_WINDOW_SECONDS + 1) is True


def test_allow_request_tracks_clients_independently():
    assert allow_request("198.51.100.1", now=3_000.0) is True
    for _ in range(RATE_LIMIT_MAX_REQUESTS):
        allow_request("198.51.100.2", now=3_000.0)
    assert allow_request("198.51.100.2", now=3_000.0) is False
    # A different client is unaffected by another client's rate limit.
    assert allow_request("198.51.100.1", now=3_000.0) is True


def test_html_security_headers_are_restrictive():
    handler = object.__new__(RugBusterHandler)
    headers = []
    handler.send_header = lambda name, value: headers.append((name, value))

    handler._security_headers(html=True)

    rendered = dict(headers)
    assert rendered["X-Content-Type-Options"] == "nosniff"
    assert rendered["X-Frame-Options"] == "DENY"
    assert rendered["Referrer-Policy"] == "no-referrer"
    assert "default-src 'self'" in rendered["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in rendered["Content-Security-Policy"]
