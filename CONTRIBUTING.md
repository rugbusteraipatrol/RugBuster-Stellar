# Contributing

RugBuster Stellar is an experimental security-tooling proof of concept. Small,
evidence-backed contributions are welcome.

## Before opening a change

1. Open an issue describing the signal, data source, bug, or documentation gap.
2. Cite the relevant Stellar protocol or Horizon documentation.
3. Do not include private keys, seed phrases, personal data, or confidential
   incident details.
4. Keep scoring changes separate from unrelated refactors.

## Local checks

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Scoring changes

A scoring change must include:

- a clear threat or risk rationale;
- public, reproducible evidence or a sanitized fixture;
- regression tests;
- an update to `docs/SIGNALS.md`;
- a new methodology version when output semantics change.

Do not describe issuer control features as proof of fraud. Do not weaken the
`INSUFFICIENT_DATA` behavior when core evidence is missing, or the
`PARTIAL_ASSESSMENT` behavior when holder concentration could not be fully
evaluated -- a low score is never sufficient on its own to report
`LOW_OBSERVED_RISK`.

## Pull requests

Keep pull requests focused and explain:

- what changed;
- which public evidence supports it;
- how it was tested;
- any new limitations or false-positive risks.

By contributing, you agree that your contribution is licensed under the MIT
License used by this repository.
