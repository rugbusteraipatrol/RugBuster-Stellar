"""Deterministic and explainable scoring for Stellar Classic assets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RiskSignal:
    code: str
    severity: str
    risk_points: int
    summary: str
    evidence: dict[str, Any]


def _signal(
    code: str,
    severity: str,
    points: int,
    summary: str,
    **evidence: Any,
) -> RiskSignal:
    return RiskSignal(code, severity, points, summary, evidence)


def score_asset(facts: dict[str, Any]) -> dict[str, Any]:
    """Return a risk score without treating centralized controls as proof of fraud."""

    signals: list[RiskSignal] = []
    flags = facts.get("flags", {})

    if flags.get("auth_clawback_enabled"):
        signals.append(
            _signal(
                "issuer_clawback_enabled",
                "high",
                25,
                "Issuer can claw back asset balances. This is a custody/control risk, not proof of fraud.",
                auth_clawback_enabled=True,
            )
        )
    if flags.get("auth_revocable"):
        signals.append(
            _signal(
                "issuer_freeze_enabled",
                "medium",
                18,
                "Issuer can revoke authorization and freeze a holder's balance.",
                auth_revocable=True,
            )
        )
    if flags.get("auth_required"):
        signals.append(
            _signal(
                "issuer_authorization_required",
                "info",
                5,
                "Holders require issuer authorization before using the asset.",
                auth_required=True,
            )
        )
    if flags.get("auth_immutable"):
        signals.append(
            _signal(
                "issuer_flags_immutable",
                "positive",
                -8,
                "Issuer authorization flags are immutable.",
                auth_immutable=True,
            )
        )

    if not facts.get("home_domain"):
        signals.append(
            _signal(
                "issuer_home_domain_missing",
                "medium",
                8,
                "Issuer account does not publish a home domain.",
            )
        )
    if not facts.get("toml_url"):
        signals.append(
            _signal(
                "stellar_toml_not_discovered",
                "medium",
                8,
                "Horizon did not expose a stellar.toml link for this asset.",
            )
        )

    signer = facts.get("signer_analysis", {})
    if signer.get("master_key_active"):
        signals.append(
            _signal(
                "issuer_master_key_active",
                "medium",
                8,
                "The issuer master key still has signing weight.",
                active_signers=signer.get("active_signers"),
                thresholds=signer.get("thresholds"),
            )
        )

    age_days = facts.get("issuer_age_days")
    if isinstance(age_days, int) and age_days < 30:
        signals.append(
            _signal(
                "issuer_account_very_new",
                "high",
                15,
                "Issuer account is less than 30 days old.",
                issuer_age_days=age_days,
            )
        )
    elif isinstance(age_days, int) and age_days < 90:
        signals.append(
            _signal(
                "issuer_account_new",
                "medium",
                8,
                "Issuer account is less than 90 days old.",
                issuer_age_days=age_days,
            )
        )

    holder_count = facts.get("holder_count")
    if isinstance(holder_count, int) and holder_count <= 5:
        signals.append(
            _signal(
                "very_few_trustlines",
                "high",
                15,
                "Asset has five or fewer trustline accounts.",
                holder_count=holder_count,
            )
        )
    elif isinstance(holder_count, int) and holder_count < 25:
        signals.append(
            _signal(
                "few_trustlines",
                "medium",
                8,
                "Asset has fewer than 25 trustline accounts.",
                holder_count=holder_count,
            )
        )

    if facts.get("num_liquidity_pools") == 0:
        signals.append(
            _signal(
                "no_classic_liquidity_pool",
                "medium",
                10,
                "Horizon reports no Classic liquidity pool holding this asset.",
            )
        )

    concentration = facts.get("concentration", {})
    if concentration.get("complete"):
        top1 = concentration.get("top1_share")
        top5 = concentration.get("top5_share")
        if isinstance(top1, float) and top1 >= 0.80:
            signals.append(
                _signal(
                    "extreme_holder_concentration",
                    "high",
                    20,
                    "One sampled trustline holds at least 80% of sampled trustline balances.",
                    top1_share=round(top1, 6),
                )
            )
        elif isinstance(top1, float) and top1 >= 0.50:
            signals.append(
                _signal(
                    "high_holder_concentration",
                    "medium",
                    12,
                    "One sampled trustline holds at least 50% of sampled trustline balances.",
                    top1_share=round(top1, 6),
                )
            )
        if isinstance(top5, float) and top5 >= 0.95 and (top1 or 0) < 0.80:
            signals.append(
                _signal(
                    "top5_holder_concentration",
                    "medium",
                    10,
                    "Five sampled trustlines hold at least 95% of sampled trustline balances.",
                    top5_share=round(top5, 6),
                )
            )

    recent = facts.get("recent_privileged_activity", {})
    if recent.get("set_options_30d", 0) > 0:
        signals.append(
            _signal(
                "recent_issuer_configuration_change",
                "medium",
                12,
                "Issuer used set_options during the last 30 days.",
                count=recent["set_options_30d"],
            )
        )
    if recent.get("clawback_30d", 0) > 0:
        signals.append(
            _signal(
                "recent_clawback_activity",
                "high",
                12,
                "Issuer performed a clawback operation during the last 30 days.",
                count=recent["clawback_30d"],
            )
        )

    risk_score = max(0, min(100, sum(item.risk_points for item in signals)))
    if risk_score >= 60:
        verdict = "HIGH_RISK"
    elif risk_score >= 25:
        verdict = "CAUTION"
    else:
        verdict = "LOW_OBSERVED_RISK"

    # A low score built from an incomplete holder sample is not evidence of low
    # risk -- it may simply mean concentration was never evaluated (see
    # `concentration_not_evaluated` in scanner.py). Concrete positive signals
    # (mint/freeze/clawback, a very new issuer, few trustlines, recent
    # privileged activity) still stand on their own and are not downgraded:
    # only the "nothing bad found" case is blocked from reading as reassuring.
    concentration_complete = concentration.get("complete")
    if verdict == "LOW_OBSERVED_RISK" and concentration_complete is not True:
        verdict = "PARTIAL_ASSESSMENT"

    return {
        "verdict": verdict,
        "risk_score": risk_score,
        "signals": [asdict(item) for item in signals],
    }

