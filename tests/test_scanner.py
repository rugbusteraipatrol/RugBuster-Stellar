from datetime import datetime, timezone

from rugbuster_stellar.client import HorizonResponse
from rugbuster_stellar.scanner import StellarAssetScanner

ISSUER = "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5"


class FakeClient:
    base_url = "https://horizon-testnet.stellar.org"

    def get(self, path, params=None):
        if path == "/assets":
            return HorizonResponse(
                {
                    "_embedded": {
                        "records": [
                            {
                                "asset_type": "credit_alphanum4",
                                "asset_code": "TEST",
                                "asset_issuer": ISSUER,
                                "accounts": {"authorized": 2, "unauthorized": 0},
                                "balances": {"authorized": "100"},
                                "num_claimable_balances": 0,
                                "num_liquidity_pools": 1,
                                "num_contracts": 0,
                                "flags": {
                                    "auth_required": False,
                                    "auth_revocable": False,
                                    "auth_immutable": True,
                                },
                                "_links": {
                                    "toml": {"href": "https://example.org/.well-known/stellar.toml"}
                                },
                            }
                        ]
                    }
                },
                100,
                "asset-url",
            )
        if path == f"/accounts/{ISSUER}":
            return HorizonResponse(
                {
                    "account_id": ISSUER,
                    "home_domain": "example.org",
                    "flags": {
                        "auth_required": False,
                        "auth_revocable": False,
                        "auth_immutable": True,
                        "auth_clawback_enabled": False,
                    },
                    "thresholds": {
                        "low_threshold": 1,
                        "med_threshold": 1,
                        "high_threshold": 1,
                    },
                    "signers": [{"key": ISSUER, "weight": 0}],
                },
                100,
                "account-url",
            )
        if path == "/accounts":
            records = []
            for index, balance in enumerate(("60", "40")):
                records.append(
                    {
                        "paging_token": str(index + 1),
                        "balances": [
                            {
                                "asset_code": "TEST",
                                "asset_issuer": ISSUER,
                                "balance": balance,
                            }
                        ],
                    }
                )
            return HorizonResponse({"_embedded": {"records": records}}, 100, "holders-url")
        if path.endswith("/operations") and params["order"] == "asc":
            return HorizonResponse(
                {"_embedded": {"records": [{"created_at": "2020-01-01T00:00:00Z"}]}},
                100,
                "first-op-url",
            )
        if path.endswith("/operations"):
            return HorizonResponse({"_embedded": {"records": []}}, 100, "recent-op-url")
        raise AssertionError((path, params))


def test_scanner_builds_evidence_report():
    scanner = StellarAssetScanner(
        FakeClient(), now=datetime(2026, 8, 15, tzinfo=timezone.utc)
    )
    report = scanner.scan("test", ISSUER.lower())
    assert report["network"] == "stellar_testnet"
    assert report["asset"]["code"] == "TEST"
    assert report["holder_analysis"]["complete"] is True
    assert report["holder_analysis"]["top1_share"] == 0.6
    assert report["verdict"] == "CAUTION"
    assert report["evidence_quality"] == "COMPLETE"


def test_invalid_input_fails_closed():
    scanner = StellarAssetScanner(FakeClient())
    report = scanner.scan("not-valid!", "bad")
    assert report["verdict"] == "INSUFFICIENT_DATA"
    assert report["risk_score"] is None
