"""Evidence collection and report assembly for Stellar Classic assets."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

from .client import HorizonClient, HorizonError
from .scoring import score_asset
from .strkey import is_valid_account_id


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("_embedded", {}).get("records", [])


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class StellarAssetScanner:
    def __init__(
        self,
        client: HorizonClient | None = None,
        *,
        max_holders: int = 200,
        now: datetime | None = None,
    ) -> None:
        self.client = client or HorizonClient()
        self.max_holders = max(1, min(max_holders, 2_000))
        self.now = now or datetime.now(timezone.utc)

    def scan(self, asset_code: str, issuer: str) -> dict[str, Any]:
        code = asset_code.strip().upper()
        issuer = issuer.strip().upper()
        validation_error = self._validate(code, issuer)
        if validation_error:
            return self._insufficient(code, issuer, validation_error)

        try:
            asset_response = self.client.get(
                "/assets",
                {"asset_code": code, "asset_issuer": issuer, "limit": 1},
            )
            asset_records = _records(asset_response.data)
            if not asset_records:
                return self._insufficient(code, issuer, "asset_not_found")
            asset = asset_records[0]

            account_response = self.client.get(f"/accounts/{quote(issuer)}")
            account = account_response.data
        except HorizonError as exc:
            reason = "issuer_not_found" if exc.status == 404 else "horizon_unavailable"
            return self._insufficient(code, issuer, reason, detail=str(exc))

        limitations: list[str] = []
        latest_ledgers = [asset_response.latest_ledger, account_response.latest_ledger]

        holder_data: dict[str, Any]
        expected_holders = self._expected_holder_count(asset)
        if expected_holders > self.max_holders:
            # A large trustline set cannot be fully enumerated within the
            # configured bound, and Horizon's holder-listing query itself gets
            # slow as the trustline count grows into the hundreds of thousands.
            # Skip the request entirely rather than pay that latency for a
            # sample scoring will not trust anyway: an incomplete sample never
            # produces a concentration claim (see scoring.py), so fetching it
            # only when it fits the bound has no scoring cost.
            holder_data = {
                "expected_trustline_accounts": expected_holders,
                "fetched_accounts": 0,
                "positive_balance_accounts": 0,
                "complete": False,
                "top1_share": None,
                "top5_share": None,
                "sample_balance": None,
            }
            limitations.append(
                "concentration_not_evaluated: trustline count "
                f"({expected_holders}) exceeds the configured holder sample "
                f"limit ({self.max_holders}); holder concentration was not "
                "evaluated and does not affect this verdict."
            )
        else:
            try:
                holder_data, holder_ledgers = self._collect_holders(code, issuer, asset)
                latest_ledgers.extend(holder_ledgers)
                if not holder_data["complete"]:
                    limitations.append(
                        "concentration_not_evaluated: the configured holder sample "
                        "was incomplete; holder concentration was not evaluated and "
                        "does not affect this verdict."
                    )
            except HorizonError as exc:
                holder_data = {
                    "fetched_accounts": 0,
                    "positive_balance_accounts": 0,
                    "complete": False,
                    "top1_share": None,
                    "top5_share": None,
                    "sample_balance": None,
                }
                limitations.append(f"Holder collection unavailable: {exc}")

        history, history_ledgers, history_limitations = self._collect_history(issuer)
        latest_ledgers.extend(history_ledgers)
        limitations.extend(history_limitations)

        account_flags = account.get("flags", {})
        asset_flags = asset.get("flags", {})
        flags = {
            "auth_required": bool(account_flags.get("auth_required", asset_flags.get("auth_required"))),
            "auth_revocable": bool(account_flags.get("auth_revocable", asset_flags.get("auth_revocable"))),
            "auth_immutable": bool(account_flags.get("auth_immutable", asset_flags.get("auth_immutable"))),
            "auth_clawback_enabled": bool(account_flags.get("auth_clawback_enabled", False)),
        }
        signer_analysis = self._analyze_signers(account, issuer)
        holder_count = sum(int(v or 0) for v in asset.get("accounts", {}).values())
        toml_url = asset.get("_links", {}).get("toml", {}).get("href")

        facts = {
            "flags": flags,
            "home_domain": account.get("home_domain") or None,
            "toml_url": toml_url,
            "signer_analysis": signer_analysis,
            "issuer_age_days": history.get("issuer_age_days"),
            "holder_count": holder_count,
            "num_liquidity_pools": int(asset.get("num_liquidity_pools", 0) or 0),
            "concentration": holder_data,
            "recent_privileged_activity": history.get("recent_privileged_activity", {}),
        }
        scored = score_asset(facts)
        valid_ledgers = [value for value in latest_ledgers if isinstance(value, int)]

        return {
            "schema_version": "0.1.0",
            "methodology": "rugbuster_stellar_classic_v0.2",
            "network": "stellar_mainnet"
            if "testnet" not in self.client.base_url
            else "stellar_testnet",
            "scanned_at": self.now.isoformat().replace("+00:00", "Z"),
            "latest_ledger": max(valid_ledgers) if valid_ledgers else None,
            "evidence_sources": {
                "asset": asset_response.url,
                "issuer": account_response.url,
                "horizon": self.client.base_url,
            },
            "asset": {
                "code": code,
                "issuer": issuer,
                "type": asset.get("asset_type"),
                "home_domain": account.get("home_domain") or None,
                "stellar_toml": toml_url,
                "trustline_accounts": asset.get("accounts", {}),
                "trustline_balances": asset.get("balances", {}),
                "claimable_balances": int(asset.get("num_claimable_balances", 0) or 0),
                "liquidity_pools": int(asset.get("num_liquidity_pools", 0) or 0),
                "contracts_holding_asset": int(asset.get("num_contracts", 0) or 0),
            },
            "issuer": {
                "flags": flags,
                "age_days": history.get("issuer_age_days"),
                "first_operation_at": history.get("first_operation_at"),
                "signers": signer_analysis,
                "recent_privileged_activity": history.get("recent_privileged_activity", {}),
            },
            "holder_analysis": holder_data,
            "verdict": scored["verdict"],
            "risk_score": scored["risk_score"],
            "signals": scored["signals"],
            "evidence_quality": "PARTIAL" if limitations else "COMPLETE",
            "limitations": limitations,
            "disclaimer": (
                "Deterministic risk indicators are not proof of fraud and are not financial advice. "
                "Issuer control flags may be legitimate compliance features."
            ),
        }

    @staticmethod
    def _validate(code: str, issuer: str) -> str | None:
        if not 1 <= len(code) <= 12 or not code.isalnum():
            return "invalid_asset_code"
        if not is_valid_account_id(issuer):
            return "invalid_issuer_address"
        return None

    @staticmethod
    def _expected_holder_count(asset: dict[str, Any]) -> int:
        return sum(int(v or 0) for v in asset.get("accounts", {}).values())

    def _collect_holders(
        self, code: str, issuer: str, asset: dict[str, Any]
    ) -> tuple[dict[str, Any], list[int | None]]:
        expected = self._expected_holder_count(asset)
        balances: list[Decimal] = []
        fetched = 0
        cursor: str | None = None
        ledgers: list[int | None] = []

        while fetched < self.max_holders:
            page_limit = min(200, self.max_holders - fetched)
            response = self.client.get(
                "/accounts",
                {
                    "asset": f"{code}:{issuer}",
                    "limit": page_limit,
                    "order": "asc",
                    "cursor": cursor,
                },
            )
            ledgers.append(response.latest_ledger)
            records = _records(response.data)
            if not records:
                break
            for account in records:
                fetched += 1
                for balance in account.get("balances", []):
                    if (
                        balance.get("asset_code") == code
                        and balance.get("asset_issuer") == issuer
                    ):
                        try:
                            amount = Decimal(str(balance.get("balance", "0")))
                        except InvalidOperation:
                            amount = Decimal(0)
                        if amount > 0:
                            balances.append(amount)
                        break
            cursor = records[-1].get("paging_token")
            if len(records) < page_limit or not cursor:
                break

        balances.sort(reverse=True)
        total = sum(balances, Decimal(0))
        complete = fetched >= expected
        top1 = float(balances[0] / total) if total > 0 and balances else None
        top5 = float(sum(balances[:5], Decimal(0)) / total) if total > 0 else None
        return (
            {
                "expected_trustline_accounts": expected,
                "fetched_accounts": fetched,
                "positive_balance_accounts": len(balances),
                "complete": complete,
                "top1_share": top1,
                "top5_share": top5,
                "sample_balance": format(total, "f"),
            },
            ledgers,
        )

    def _collect_history(
        self, issuer: str
    ) -> tuple[dict[str, Any], list[int | None], list[str]]:
        ledgers: list[int | None] = []
        limitations: list[str] = []
        first_at: datetime | None = None
        recent_records: list[dict[str, Any]] = []
        try:
            first = self.client.get(
                f"/accounts/{quote(issuer)}/operations", {"order": "asc", "limit": 1}
            )
            ledgers.append(first.latest_ledger)
            first_records = _records(first.data)
            if first_records:
                first_at = _parse_time(first_records[0].get("created_at"))
        except HorizonError as exc:
            limitations.append(f"Issuer age unavailable: {exc}")

        try:
            recent = self.client.get(
                f"/accounts/{quote(issuer)}/operations", {"order": "desc", "limit": 200}
            )
            ledgers.append(recent.latest_ledger)
            recent_records = _records(recent.data)
        except HorizonError as exc:
            limitations.append(f"Recent issuer activity unavailable: {exc}")

        age_days = (self.now - first_at).days if first_at else None
        set_options_30d = 0
        clawback_30d = 0
        for operation in recent_records:
            created_at = _parse_time(operation.get("created_at"))
            if not created_at or (self.now - created_at).days > 30:
                continue
            if operation.get("type") == "set_options":
                set_options_30d += 1
            if operation.get("type") in {"clawback", "clawback_claimable_balance"}:
                clawback_30d += 1

        return (
            {
                "first_operation_at": first_at.isoformat().replace("+00:00", "Z")
                if first_at
                else None,
                "issuer_age_days": age_days,
                "recent_privileged_activity": {
                    "set_options_30d": set_options_30d,
                    "clawback_30d": clawback_30d,
                    "operations_examined": len(recent_records),
                },
            },
            ledgers,
            limitations,
        )

    @staticmethod
    def _analyze_signers(account: dict[str, Any], issuer: str) -> dict[str, Any]:
        active = [signer for signer in account.get("signers", []) if int(signer.get("weight", 0)) > 0]
        master = next((signer for signer in active if signer.get("key") == issuer), None)
        return {
            "master_key_active": master is not None,
            "master_key_weight": int(master.get("weight", 0)) if master else 0,
            "active_signers": len(active),
            "thresholds": account.get("thresholds", {}),
        }

    def _insufficient(
        self,
        code: str,
        issuer: str,
        reason: str,
        *,
        detail: str | None = None,
    ) -> dict[str, Any]:
        limitation = reason if detail is None else f"{reason}: {detail}"
        return {
            "schema_version": "0.1.0",
            "methodology": "rugbuster_stellar_classic_v0.2",
            "network": "stellar_mainnet"
            if "testnet" not in self.client.base_url
            else "stellar_testnet",
            "scanned_at": self.now.isoformat().replace("+00:00", "Z"),
            "asset": {"code": code, "issuer": issuer},
            "verdict": "INSUFFICIENT_DATA",
            "risk_score": None,
            "signals": [],
            "evidence_quality": "INSUFFICIENT",
            "limitations": [limitation],
            "disclaimer": "No safety conclusion was produced because required evidence was unavailable.",
        }
