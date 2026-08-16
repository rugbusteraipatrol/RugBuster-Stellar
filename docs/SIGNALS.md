# Signal methodology v0.2

## Design principles

1. Ledger evidence comes before narrative.
2. Centralized controls are risks, not automatic accusations of fraud.
3. Partial holder samples do not produce concentration claims.
4. Missing core evidence returns `INSUFFICIENT_DATA` instead of a false
   reassuring verdict. Missing *concentration* evidence specifically -- core
   asset/issuer facts present, but the holder sample incomplete or skipped --
   returns `PARTIAL_ASSESSMENT` rather than `LOW_OBSERVED_RISK`, even when
   every other signal is clean.
5. Every scoring change requires a methodology version change and regression
   tests.

## Changelog

### v0.2 (2026-08-16)

`v0.1` gated concentration scoring on `complete` (every Horizon-reported
trustline account fetched), which is the correct call for what it was built to
prevent -- a tiny, unrepresentative sample producing a misleading
concentration claim. What it did not account for: when the *total* trustline
count exceeds the configured sample bound, `complete` is `False` regardless of
how concentrated the balances actually are among the accounts that hold a
positive balance, and every other signal can legitimately come back clean.
That combination produced a `SAFE` verdict for a live Stellar asset publicly
flagged as a counterfeit `ETH` token, where the fetched sample already showed
62% of balance on the top holder and 99% on the top five -- concentration data
that existed and was simply never scored.

Changes:

- `SAFE` is renamed `LOW_OBSERVED_RISK` everywhere, including in the public
  demo UI. It is not a safety claim, and the new name says so directly.
- A low score computed while concentration is incomplete now returns
  `PARTIAL_ASSESSMENT`, not `LOW_OBSERVED_RISK`. A score that is `CAUTION` or
  `HIGH_RISK` on its own evidence is unaffected -- concrete positive signals
  are never downgraded for a missing concentration sample.
- When the asset's reported trustline count already exceeds `max_holders`,
  holder enumeration is skipped before any request is sent (`fast mode`),
  instead of fetching a partial sample the scorer was always going to discard.
  This also fixes the latency this created: some widely-held assets were
  taking 30-70 seconds per scan against Horizon's public instance.
- The public demo adds a short response cache and a per-client rate limit;
  neither changes scoring.

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

Verdict boundaries, by risk score:

- `0-24`: `LOW_OBSERVED_RISK` -- **only** if holder concentration was fully
  evaluated (`holder_analysis.complete == true`). Otherwise: `PARTIAL_ASSESSMENT`.
- `25-59`: `CAUTION`
- `60-100`: `HIGH_RISK`

`CAUTION` and `HIGH_RISK` are reported as computed regardless of concentration
completeness: a concrete positive signal is evidence on its own and is never
withheld for a missing concentration sample. Only the "risk score under 25"
case depends on concentration having actually been checked, because that is
the only case where "we found nothing" and "we did not look" would otherwise
look identical to the reader.

Separately, `INSUFFICIENT_DATA` is returned before scoring runs at all when
core evidence -- the asset or issuer itself -- cannot be found or Horizon is
unavailable. It is not a risk-score tier.

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
