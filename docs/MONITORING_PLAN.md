# Monitoring plan

## Service indicators

The future public service will monitor:

- Horizon request success rate and latency;
- scans by verdict and evidence-quality state;
- percentage of `INSUFFICIENT_DATA` and `PARTIAL_ASSESSMENT` results by reason;
- rate-limit and upstream timeout frequency;
- holder-enumeration request count, skip rate (fast mode), and truncation rate;
- cache hit rate on `/api/scan`;
- age of the latest Horizon ledger observed;
- methodology version used for every report.

## Initial targets

- >=99% successful responses for valid, existing assets when Horizon is healthy;
- no `LOW_OBSERVED_RISK` response when the asset or issuer lookup failed, and
  no `LOW_OBSERVED_RISK` response when holder concentration was not fully
  evaluated (`PARTIAL_ASSESSMENT` is correct there instead);
- p95 scan latency under 10 seconds with the default 200-holder bound (the
  `v0.2` fast-mode holder skip exists specifically to hold this target for
  widely-held assets, which previously took 30-70 seconds each);
- alert if latest observed ledger stops advancing for 10 minutes;
- alert if `INSUFFICIENT_DATA` exceeds 10% of valid requests over 15 minutes;
- preserve raw fixture responses for every published benchmark example.

## Change control

1. Add or update regression fixtures.
2. Run unit and fixture tests.
3. Create a dated methodology changelog entry.
4. Run the frozen benchmark before release.
5. Publish score changes and known limitations.

No scoring weight will be silently changed in production.

## Incident response

For an incorrect or stale public report:

1. mark the affected methodology or data source as degraded;
2. return `INSUFFICIENT_DATA` where evidence integrity is uncertain;
3. preserve the problematic response and request identifiers;
4. publish a short incident note with scope and remediation;
5. add a regression fixture before restoring normal verdicts.

## Privacy

All v0.1 inputs and evidence are public ledger identifiers. The scanner should
not collect private keys, seed phrases, personal identity documents, or wallet
browser data.

