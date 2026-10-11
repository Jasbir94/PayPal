# Unified chat banking acceptance report

Run date: 2026-10-09. Environment: local Windows synthetic demo, Python 3.12.10, Node.js 24.19.0. No real payment rail was connected.

## Verification

- Backend: 336 tests passed; one existing Starlette/httpx deprecation warning.
- Focused chat and ledger suite: 58 passed.
- Frontend: 7 tests passed; Vite production build passed.
- Windows startup: scripts/start_app.ps1 -NoBrowser passed preflight, validated the bundled synthetic data/models, and served readiness successfully.
- Live conversation audit: 20/20 terminal outcomes; zero settlements before confirmation; zero unresolved questions; zero repeated questions; maximum one question in a flow (one question total across this run).
- RAG tests verify approved RBI/cybercrime sources, attribution/hash, irrelevant-query rejection, unapproved-source rejection, and that injected query text cannot alter returned documents. A simulated retrieval outage leaves the payment unexecuted and returns an empty evidence list.

## Live scenario outcomes

These are synthetic scripted cases and observations, not measurements against verified real-world labels.

| Scenario | Observed decision | Risk band / score | Terminal state |
| --- | --- | ---: | --- |
| Known recipient | ALLOW | LOW / 0.00 | SIMULATED_COMPLETED |
| New legitimate recipient | ALLOW | LOW / 0.42 | CANCELLED |
| Urgent family emergency | ALLOW | LOW / 0.00 | CANCELLED |
| Government impersonation | STEP_UP_VERIFICATION | LOW / 25.20 | CANCELLED |
| Fake bank verification | STEP_UP_VERIFICATION | LOW / 20.80 | CANCELLED |
| Fake job registration fee | WARN_AND_REVIEW | LOW / 17.26 | CANCELLED |
| Investment scam | WARN_AND_REVIEW | LOW / 10.52 | CANCELLED |
| Suspicious recipient network | WARN_AND_REVIEW | LOW / 22.91 | CANCELLED |
| Missing information | ALLOW | LOW / 0.00 | CANCELLED |
| User changes their mind | ALLOW_WITH_WARNING | LOW / 0.00 | CANCELLED |
| Small known payment | ALLOW_WITH_WARNING | LOW / 0.00 | SIMULATED_COMPLETED |
| Established merchant | ALLOW | LOW / 11.22 | SIMULATED_COMPLETED |
| Legitimate large purchase | ALLOW_WITH_WARNING | LOW / 25.34 | CANCELLED |
| Legitimate family emergency | ALLOW | LOW / 0.00 | SIMULATED_COMPLETED |
| Secret authority request | STEP_UP_VERIFICATION | LOW / 24.46 | CANCELLED |
| Uncertain contact | ALLOW | LOW / 0.00 | CANCELLED |
| Hinglish bank impersonation | STEP_UP_VERIFICATION | MEDIUM / 47.88 | CANCELLED |
| Remote support pressure | STEP_UP_VERIFICATION | LOW / 22.67 | CANCELLED |
| Refund pressure | WARN_AND_REVIEW | LOW / 9.28 | CANCELLED |
| Ordinary merchant | ALLOW | LOW / 11.34 | SIMULATED_COMPLETED |

## Issues found and fixed

The live audit revealed that useful opening-message context could be dropped when it did not match the structured claim extractor. Initial payer context now reaches the backend assessment, while a bare amount/recipient request still triggers a targeted question. A regression test covers this path. The post-settlement balance refresh is also guarded so a display read error cannot hide a committed receipt or encourage a duplicate retry. Test wallet balances are isolated to make the suite independent of test order. The audit runner now supports direct Windows invocation and follows up to four questions so it can detect unresolved or repeated prompts.

## Safety and interpretation limits

No false-positive or false-negative rate is reported: these scripted scenario names are not independently verified ground-truth labels. Scam-themed scenarios produced policy interventions, but several remained in the LOW risk band. In particular, government/bank impersonation triggered step-up verification while staying LOW. The app therefore should present the intervention and evidence clearly, and the risk band must not be interpreted as a confidence score or proof that the payment is safe.

The demo profile token is account-scoped but is not real identity authentication. Chat transcripts are in-memory and expire; wallets and ledger entries persist locally in SQLite. Internal simulated transfers atomically debit and credit both demo accounts; external demo recipients create no fictitious recipient wallet. No real funds move.

The normal application is back on its default data/processed/demo_banking.sqlite3 database. The live audit used a separate synthetic ledger; its detailed cases and timings are in reports/unified_chat_live_audit.json.

## Observed latency

Single local warm run; milliseconds. These timings include this machine, its current load, and synthetic models only.

| Measurement | Median | P95 | Maximum |
| --- | ---: | ---: | ---: |
| Chat HTTP response | 56.58 | 94.28 | 111.36 |
| Complete conversation flow | 107.24 | 165.02 | 178.78 |
| Passive analysis | 12.68 | 20.10 | 30.39 |
| Full analysis | 35.72 | 61.73 | 62.00 |
| End-to-end analysis | 48.35 | 81.83 | 92.39 |
| Local RAG retrieval (50 samples) | 0.106 | 0.19 | 0.257 |

No performance optimization was justified by these local synthetic measurements. They do not establish production latency or detection quality.

## Remaining limitations

Broader multilingual understanding, real authentication, recipient identity verification, durable chat transcripts, independently labeled evaluation data, and an external payment rail are out of scope. The service is a synthetic local demo and has not been validated for production banking.
