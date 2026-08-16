# RugBuster Stellar

Experimental, evidence-first risk scanner for Stellar Classic assets and
issuer accounts.

> **Status: public proof of concept (`v0.1`)**<br>
> The methodology has not yet been calibrated against a representative labeled
> benchmark. Do not use its verdict as a guarantee, audit, or substitute for
> independent due diligence.

This is an early public MVP. It accepts an asset code and issuer address, reads
public ledger evidence through Horizon, and returns one of:

- `SAFE`
- `CAUTION`
- `HIGH_RISK`
- `INSUFFICIENT_DATA`

The scanner is deterministic. It does not ask an AI model to invent a verdict.
Every signal includes a machine-readable reason and the evidence used to produce
it. `SAFE` means only that the checks implemented in this version did not find
enough risk points to cross a threshold. It does **not** mean that the asset or
issuer has been proven safe. Always read `evidence_quality` and `limitations`
with the verdict.

## Why this exists

Asset codes are not unique identities on Stellar: the same code can be issued
by different accounts with very different controls and histories. This PoC
turns public Horizon evidence about the exact `asset code + issuer` pair into a
small, reproducible report. It is designed to support technical discussion and
methodology review before any production or accuracy claim.

## Web scanner

The repository includes a local browser scanner and JSON API in the RugBuster
Shield design language. It does not connect to a wallet, request a seed phrase,
sign an operation, or submit a transaction.

```powershell
rugbuster-stellar-web
```

Then open `http://127.0.0.1:8787`.

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

## Architecture

```text
CLI / local web form
        │
        ▼
bounded input validation
        │
        ▼
read-only Horizon client ──► Stellar public Horizon endpoints
        │
        ▼
normalized issuer, asset, holder and history facts
        │
        ▼
versioned deterministic scoring ──► JSON evidence report
```

The local web API accepts only the built-in Stellar mainnet and testnet Horizon
endpoints. The CLI supports an explicit `--horizon-url` for development.

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

## Validation status

- 11 unit and API-boundary tests are included.
- Two dated Circle USDC smoke reports are frozen under [`evidence/`](evidence/).
- Those reports prove integration behavior, not predictive accuracy.
- No representative labeled Stellar benchmark has been completed yet.
- Scoring weights are an explicit hypothesis documented in
  [`docs/SIGNALS.md`](docs/SIGNALS.md).

## Roadmap (funding or partner-supported)

1. Build and freeze a documented labeled Classic-asset fixture set.
2. Calibrate weights and publish false-positive/false-negative analysis.
3. Add Stellar Asset Contract and Soroban administrator/code-upgrade checks.
4. Publish a TypeScript SDK and reference wallet-warning component.
5. Add transaction-intent preflight for agent and wallet integrations.

The HTTP API and browser scanner are already present in this PoC. Items above
are not represented as completed or funded work.

See [Signal methodology](docs/SIGNALS.md),
[Threat model](docs/THREAT_MODEL.md), and
[Monitoring plan](docs/MONITORING_PLAN.md).

## Contributing and security

Technical review is welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a change. Please do not place vulnerability details in a public issue;
follow [SECURITY.md](SECURITY.md) instead.

## Official data sources

- [Horizon API reference](https://developers.stellar.org/docs/data/apis/horizon/api-reference)
- [Asset object](https://developers.stellar.org/docs/data/apis/horizon/api-reference/resources/assets/object)
- [Account object](https://developers.stellar.org/docs/data/apis/horizon/api-reference/resources/accounts/object)
- [Classic assets](https://developers.stellar.org/docs/learn/fundamentals/stellar-data-structures/assets)

## License

MIT
