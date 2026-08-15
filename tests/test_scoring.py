from rugbuster_stellar.scoring import score_asset


def base_facts():
    return {
        "flags": {
            "auth_required": False,
            "auth_revocable": False,
            "auth_immutable": True,
            "auth_clawback_enabled": False,
        },
        "home_domain": "example.org",
        "toml_url": "https://example.org/.well-known/stellar.toml",
        "signer_analysis": {"master_key_active": False},
        "issuer_age_days": 900,
        "holder_count": 1_000,
        "num_liquidity_pools": 2,
        "concentration": {"complete": True, "top1_share": 0.10, "top5_share": 0.30},
        "recent_privileged_activity": {"set_options_30d": 0, "clawback_30d": 0},
    }


def test_low_risk_asset_is_safe():
    result = score_asset(base_facts())
    assert result["verdict"] == "SAFE"
    assert result["risk_score"] == 0


def test_centralized_controls_are_caution_not_automatic_fraud():
    facts = base_facts()
    facts["flags"] = {
        "auth_required": True,
        "auth_revocable": True,
        "auth_immutable": False,
        "auth_clawback_enabled": True,
    }
    result = score_asset(facts)
    assert result["verdict"] == "CAUTION"
    assert result["risk_score"] == 48


def test_new_concentrated_asset_is_high_risk():
    facts = base_facts()
    facts.update(
        {
            "issuer_age_days": 4,
            "holder_count": 4,
            "num_liquidity_pools": 0,
            "home_domain": None,
            "toml_url": None,
            "concentration": {"complete": True, "top1_share": 0.91, "top5_share": 1.0},
        }
    )
    result = score_asset(facts)
    assert result["verdict"] == "HIGH_RISK"
    assert result["risk_score"] >= 60


def test_incomplete_holder_sample_does_not_score_concentration():
    facts = base_facts()
    facts["concentration"] = {"complete": False, "top1_share": 0.99, "top5_share": 1.0}
    result = score_asset(facts)
    assert "extreme_holder_concentration" not in {s["code"] for s in result["signals"]}

