# Threat model

## System boundary

RugBuster Stellar v0.1 is a read-only analyzer. It does not request secrets,
hold keys, sign operations, submit transactions, or modify issuer state.

## Assets to protect

- integrity of the verdict and evidence;
- availability of the scanner;
- correctness of asset identity (`code + issuer`);
- reproducibility of published reports;
- user understanding of uncertainty and limitations.

## Primary threats

### Wrong-asset substitution

An attacker may reuse a recognized asset code with a different issuer.

Mitigation: the scanner requires and displays the full issuer address and sends
both fields to Horizon.

### False safety during upstream failure

Horizon timeout, rate limiting, malformed responses, or unavailable asset data
could otherwise produce an incomplete low score.

Mitigation: missing asset or issuer evidence returns `INSUFFICIENT_DATA` with no
numeric score. Non-core collection failures are listed as limitations and mark
evidence quality `PARTIAL`.

### Misleading concentration from sampling

A bounded holder sample can make a large asset appear highly concentrated.

Mitigation: concentration affects the score only if every Horizon-reported
trustline account was fetched.

### Legitimate control flags described as fraud

Regulated issuers may intentionally use authorization, freeze, and clawback.

Mitigation: these are described as custody/control risks. The report explicitly
states they are not proof of fraud.

### Stale ledger evidence

Ledger state can change after a report is generated.

Mitigation: reports include scan time, methodology version, network, and the
latest Horizon ledger header when available. Consumers must enforce freshness.

### Resource exhaustion and rate-limit abuse

Large holder sets can cause excessive Horizon requests.

Mitigation: holder enumeration is bounded to 2,000 accounts and defaults to 200.
Production API work will add per-client limits, caching, and request budgets.

### Methodology manipulation

Changing weights after seeing outcomes can create misleading retrospective
results.

Mitigation: publish methodology versions, fixtures, regression tests, and dated
benchmark artifacts before changing production scoring.

## Out of scope for v0.1

- smart-contract execution and XDR simulation;
- private-key compromise at an issuer;
- legal or sanctions screening;
- exploit detection inside arbitrary Soroban Wasm;
- guarantees of future liquidity or solvency.

