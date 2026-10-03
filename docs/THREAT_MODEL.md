# Threat model and privacy notes

## Scope and assets

The prototype handles synthetic payment attributes, pseudonymous local account aliases, optional user-provided context/message text, prediction snapshots, labels, and review/audit records. It does not connect to financial accounts or execute transfers. It must not receive PINs, OTPs, CVVs, passwords, or card numbers.

## Threats considered

- Prompted or malicious text attempts to submit payment credentials: request schemas and feedback validators reject common credential/card patterns; raw message text is excluded from persistent snapshots and aggregate monitoring.
- Oversized/repeated API requests: request-size and rate-limit middleware bound request volume and body size.
- Historical information leakage: recipient and graph features use strict-before timestamp queries; test fixtures check future/equal-time activity exclusion.
- Feedback poisoning: actions are separate from labels; only final trusted labels with high confidence and seven-day maturity are eligible for training.
- Audit tampering: append-only events are SHA-256 hash chained and the chain can be verified. This is tamper-evident local storage, not a signed or externally anchored ledger.
- Model artifact path injection: registry artifacts are constrained to project-local existing files.
- Cross-origin misuse: CORS origins are explicit and credentials are disabled.

## Residual risks

No penetration test, external dependency vulnerability scan, production identity/access control, encryption-at-rest review, signed audit anchor, tenant isolation, or real-data privacy assessment has been performed. SQLite content is local research data and should not contain real customer records. The simulator's aliases and data are synthetic. The Docker images were not built in this host session because Docker Desktop's Linux engine was unavailable.
