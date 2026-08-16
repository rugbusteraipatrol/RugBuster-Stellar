from http import HTTPStatus

from rugbuster_stellar.web import RugBusterHandler, scan_request


class FakeScanner:
    def __init__(self, client, *, max_holders):
        self.client = client
        self.max_holders = max_holders

    def scan(self, code, issuer):
        return {
            "verdict": "SAFE",
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
    assert report["verdict"] == "SAFE"


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
