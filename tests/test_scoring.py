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


def test_low_risk_asset_with_complete_data_is_low_observed_risk():
    result = score_asset(base_facts())
    assert result["verdict"] == "LOW_OBSERVED_RISK"
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


def test_incomplete_holder_sample_with_low_score_is_partial_not_low_risk():
    """The bug this guards: an asset can carry 60%+ concentration among the
    few holders that were actually found, but if the trustline count exceeds
    the sample bound the concentration signal never fires and every other
    check comes back clean. That combination must not read as low risk --
    the correct answer is "we could not fully assess this", not "safe".
    """
    facts = base_facts()
    facts["concentration"] = {"complete": False, "top1_share": 0.99, "top5_share": 1.0}
    result = score_asset(facts)
    assert result["verdict"] == "PARTIAL_ASSESSMENT"


def test_incomplete_holder_sample_does_not_hide_high_risk():
    """An incomplete holder sample must not soften a verdict that other,
    fully-evaluated signals already justify."""
    facts = base_facts()
    facts.update(
        {
            "flags": {
                "auth_required": False,
                "auth_revocable": True,
                "auth_immutable": False,
                "auth_clawback_enabled": True,
            },
            "issuer_age_days": 2,
            "holder_count": 3,
            "num_liquidity_pools": 0,
            "home_domain": None,
            "toml_url": None,
            "concentration": {"complete": False, "top1_share": None, "top5_share": None},
        }
    )
    result = score_asset(facts)
    assert result["verdict"] == "HIGH_RISK"
    assert result["risk_score"] >= 60

