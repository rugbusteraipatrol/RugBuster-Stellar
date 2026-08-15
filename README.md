# RugBuster Stellar

Evidence-first risk scanner for Stellar Classic assets and issuer accounts.

This is an early public MVP. It accepts an asset code and issuer address, reads
public ledger evidence through Horizon, and returns one of:

- `SAFE`
- `CAUTION`
- `HIGH_RISK`
- `INSUFFICIENT_DATA`

The scanner is deterministic. It does not ask an AI model to invent a verdict.
Every signal includes a machine-readable reason and the evidence used to produce
it. `SAFE` means that the implemented checks did not find elevated risk; it is
not a guarantee that an asset or issuer is safe.

## Current scope

Version `0.1` analyzes:

- issuer authorization, freeze, clawback, and immutability flags;
- issuer home domain and discoverable `stellar.toml` metadata;
- active issuer master key and signer configuration;
- issuer account age;
- trustline count;
- complete or bounded holder-balance concentration sampling;
- Classic liquidity-pool presence;
- recent issuer `set_options` and clawback operations.

Issuer control features are reported as custody and centralization risks, not as
proof of fraud. A legitimate regulated asset may therefore receive `CAUTION`.

## Quick start

Python 3.11 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

Scan Circle USDC on Stellar mainnet:

```powershell
rugbuster-stellar USDC GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN `
  --max-holders 200 `
  --output outputs/usdc-mainnet.json
```

Use testnet:

```powershell
rugbuster-stellar USDC GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5 `
  --horizon-url https://horizon-testnet.stellar.org
```

Run the local browser demo and HTTP API:

```powershell
rugbuster-stellar-web
```

Open `http://127.0.0.1:8787`. The API endpoint is `POST /api/scan`:

```json
{
  "network": "mainnet",
  "asset_code": "USDC",
  "issuer": "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN",
  "max_holders": 200
}
```

## Evidence behavior

- If the asset or issuer cannot be verified, the scanner returns
  `INSUFFICIENT_DATA` and no numeric score.
- Holder concentration affects the score only when all Horizon trustline
  accounts were fetched. Partial samples remain visible but are not used to
  make a concentration claim.
- Horizon's `Latest-Ledger` header is included in the report when available.
- Every report records its scan time, methodology version, limitations, and
  deterministic signals.

## Report shape

```json
{
  "methodology": "rugbuster_stellar_classic_v0.1",
  "network": "stellar_mainnet",
  "asset": {"code": "USDC", "issuer": "G..."},
  "verdict": "CAUTION",
  "risk_score": 48,
  "signals": [
    {
      "code": "issuer_clawback_enabled",
      "severity": "high",
      "risk_points": 25,
      "summary": "Issuer can claw back asset balances...",
      "evidence": {"auth_clawback_enabled": true}
    }
  ],
  "evidence_quality": "PARTIAL",
  "limitations": []
}
```

## Roadmap

1. Validate the Classic-asset methodology on a documented public fixture set.
2. Add a small HTTP API and browser scanner.
3. Add Stellar Asset Contract and Soroban administrator/code-upgrade checks.
4. Publish a TypeScript SDK and wallet-warning component.
5. Add transaction-intent preflight for agent and wallet integrations.

See [Signal methodology](docs/SIGNALS.md),
[Threat model](docs/THREAT_MODEL.md), and
[Monitoring plan](docs/MONITORING_PLAN.md).

## Official data sources

- [Horizon API reference](https://developers.stellar.org/docs/data/apis/horizon/api-reference)
- [Asset object](https://developers.stellar.org/docs/data/apis/horizon/api-reference/resources/assets/object)
- [Account object](https://developers.stellar.org/docs/data/apis/horizon/api-reference/resources/accounts/object)
- [Classic assets](https://developers.stellar.org/docs/learn/fundamentals/stellar-data-structures/assets)

## License

MIT
