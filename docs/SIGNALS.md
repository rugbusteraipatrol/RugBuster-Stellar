# Signal methodology v0.1

## Design principles

1. Ledger evidence comes before narrative.
2. Centralized controls are risks, not automatic accusations of fraud.
3. Partial holder samples do not produce concentration claims.
4. Missing core evidence returns `INSUFFICIENT_DATA` instead of a false `SAFE`.
5. Every scoring change requires a methodology version change and regression
   tests.

## Current scoring

| Signal | Points | Interpretation |
|---|---:|---|
| Clawback enabled | +25 | Issuer can remove balances |
| Revocable authorization | +18 | Issuer can freeze trustlines |
| Authorization required | +5 | Permissioned holding model |
| Flags immutable | -8 | Authorization flags cannot later change |
| Home domain missing | +8 | Reduced issuer discoverability |
| `stellar.toml` not discovered | +8 | Reduced public metadata evidence |
| Active issuer master key | +8 | Issuer root key retains signing power |
| Issuer younger than 30 days | +15 | Very limited history |
| Issuer younger than 90 days | +8 | Limited history |
| Five or fewer trustlines | +15 | Very small holder footprint |
| Fewer than 25 trustlines | +8 | Small holder footprint |
| No Classic liquidity pool | +10 | No Horizon-reported Classic pool |
| Top holder >=80% | +20 | Extreme concentration, complete set only |
| Top holder >=50% | +12 | High concentration, complete set only |
| Top five >=95% | +10 | High group concentration, complete set only |
| `set_options` in last 30 days | +12 | Recent issuer configuration change |
| Clawback in last 30 days | +12 | Recent use of clawback authority |

Verdict boundaries:

- `0-24`: `SAFE`
- `25-59`: `CAUTION`
- `60-100`: `HIGH_RISK`

These weights are an explicit MVP hypothesis. They must be calibrated against a
documented fixture set before any accuracy claim is published.

## Known limitations

- Classic assets are identified by asset code plus issuer. Asset code alone is
  never sufficient.
- Issuer G-addresses are validated by StrKey version byte, payload length, and
  CRC16-XModem checksum.
- Classic liquidity-pool presence is not equivalent to USD liquidity depth.
- Holder balances exclude amounts outside ordinary account trustlines, which are
  reported separately by Horizon.
- No off-chain identity, sanctions, legal status, or website-content verdict is
  produced.
- Soroban contracts and Stellar Asset Contracts are outside v0.1 scope.
