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


class LargeHolderFakeClient(FakeClient):
    """Same fixture as FakeClient, but the asset reports far more trustlines
    than the configured holder-sample bound."""

    def get(self, path, params=None):
        if path == "/assets":
            response = super().get(path, params)
            response.data["_embedded"]["records"][0]["accounts"] = {
                "authorized": 1000,
                "unauthorized": 0,
            }
            return response
        if path == "/accounts":
            raise AssertionError(
                "holder listing must be skipped once the expected trustline "
                "count already exceeds max_holders"
            )
        return super().get(path, params)


def test_large_trustline_count_skips_holder_enumeration():
    scanner = StellarAssetScanner(
        LargeHolderFakeClient(), max_holders=200, now=datetime(2026, 8, 15, tzinfo=timezone.utc)
    )
    report = scanner.scan("test", ISSUER.lower())
    assert report["holder_analysis"]["complete"] is False
    assert report["holder_analysis"]["fetched_accounts"] == 0
    assert any(item.startswith("concentration_not_evaluated") for item in report["limitations"])
    # Nothing else about this fixture is risky, so skipping concentration must
    # not be allowed to read as "safe" -- this is exactly the bug a fake ETH
    # asset with 62% top-holder concentration hit in the wild: 534 trustlines
    # exceeded the 200-holder bound, concentration was silently dropped, and
    # every other check came back clean, producing a false SAFE.
    assert report["verdict"] == "PARTIAL_ASSESSMENT"


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
