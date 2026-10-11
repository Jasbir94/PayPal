# APP Shield final integration and validation report

**Verification date:** 2026-10-11

**Scope:** Local synthetic demo only. No live payment service or real funds are connected.

## Result

APP Shield is runnable locally as a unified chat for simulated payments, balance checks, and transaction details. The React frontend, FastAPI backend, simulated account service, local risk pipeline, and local retrieval guidance are integrated. Current checks pass: **358 backend tests**, **7 frontend tests**, and the Vite production build. The backend health and readiness endpoints and frontend HTTP entry point returned HTTP 200 during this verification.

This is a research/demo prototype, not a production banking release. The available fraud data and scenario audits are synthetic and authored; they do not establish real-world detection performance.

## Product and integration inventory

- The customer experience uses one chat for payment, balance, and transaction requests, with three primary operation choices.
- Backend chat routes handle intent, demo-account context, payment attempts, questions, review, confirmation, cancellation, and handoff to balance/history operations.
- Payment assessment composes the available transaction, recipient, graph, context/scenario, manipulation/psychology, and risk-policy components. Unsupported or unavailable evidence is represented as missing/uncertain; the system does not treat a user’s reassurance as independently verified protective evidence.
- Local RAG retrieves approved, attributed guidance. It does not grant payment authority or determine the payment action; policy remains backend-owned. There is no hosted LLM configured for this run.
- The analyst interface and research routes remain available as separate research views; they are not part of the customer’s three primary chat operations.
- Demo wallets and ledger data are local and synthetic. Internal transfers and simulated external-recipient actions are covered by backend tests. Nothing contacts a payment rail.

The final pass now includes a fresh live HTTP run of all 20 authored conversation cases and a separate isolated live internal-transfer reconciliation. These do not constitute coverage of all 26 requested edge-case scenarios or real-world fraud performance.

## Changes in this stabilization pass

- Fixed a context-availability defect: an empty default `reported_contradictions` list was incorrectly counted as evidence. Empty context now remains unavailable, with an explicit regression test.
- Added a bounded Windows asyncio startup probe to `scripts/start_app.ps1`. It fails with an actionable timeout instead of hanging before Uvicorn starts.
- Kept the SQLAlchemy compiled-extension workaround in the project test runner, process-local and pure Python; no installed packages or machine security settings were changed.
- Added Windows startup troubleshooting guidance in `docs/TROUBLESHOOTING.md`.
- Retained existing protections for payment-version reassessment, confirmation policy, simulated ledger operations, idempotent chat retries, evidence provenance, contradictions, and RAG fallback.

## Verification results

| Check | Result |
|---|---|
| Full backend suite: `.venv\\Scripts\\python.exe scripts\\run_windows_tests.py -q` | **358 passed**, 1 upstream Starlette/httpx deprecation warning, 72.52 s |
| Focused context/API regression suite | **64 passed**, 1 upstream deprecation warning, 6.57 s |
| Focused payment, conversation, adversarial, ledger, evidence, and RAG suite | **79 passed**, 1 upstream deprecation warning, 20.90 s |
| Frontend: `node.exe --test` (from `frontend`) | **7 passed** |
| Production frontend: `node.exe node_modules\\vite\\bin\\vite.js build` | **Passed**, Vite 8.2.1 |
| `git diff --check` | Passed; Git emitted only CRLF conversion notices |
| Live local health | `/health` = `healthy`; `/ready` = `ready` |
| Live frontend entry | `http://127.0.0.1:5173/` returned HTTP 200 |
| Windows startup | `scripts/start_app.ps1 -NoBrowser` started/validated both services in this environment |
| Fresh live HTTP conversation audit | **20/20 terminal outcomes**, 0 pre-confirmation executions, 0 repeated or unresolved questions, maximum 1 question/flow |
| Isolated two-account chat transfer | **Passed**: ₹10,000 → ₹7,000 for A; ₹2,000 → ₹5,000 for B; matching debit/credit history |
| Concurrent live confirmation retry | **Passed**: both requests returned the same receipt and exactly one debit record existed |

The Python runner supplies SQLAlchemy’s bundled pure-Python processor implementation for the test process because the optional compiled extension is blocked in this Windows environment. The full suite passes through this runner without modifying the virtual environment. Normal app startup does not depend on the test fallback.

## Conversation, question, and safety evidence

The fresh live HTTP audit is saved as [`reports/final_live_http_audit.json`](reports/final_live_http_audit.json). It exercises known and new recipients, a family emergency, government and bank impersonation, job fee, investment, suspicious recipient network, missing details, Hinglish, remote support, refund pressure, and change-of-mind. Across 20 conversations it recorded one question total, at most one per flow, no repeated or unresolved prompts, 20 terminal outcomes, and no execution before explicit test confirmation. The audit ran against an isolated temporary SQLite database with sufficiently high synthetic test balances so insufficient funds did not suppress scenario analysis.

The observed intervention outcomes included step-up verification for government/bank impersonation and remote support, review for fake job fee, investment, suspicious network, and refund pressure. Urgency alone did not escalate the legitimate family emergency; it remained LOW risk / ALLOW and the scripted demo completed after confirmation. Several scam-themed cases still displayed LOW risk bands despite review/verification interventions; risk and policy action must remain visibly distinct.

The separate live two-account flow is verified through the chat start, review, explicit confirm, receipt, and authorized account history APIs. It posted one internal transfer ID with A’s debit and B’s credit, and balances reconciled exactly. A concurrent retry of that same chat confirmation returned the same receipt twice and did not create a duplicate debit.

Current backend tests cover confirmation/version binding, cancellation, retry idempotency, prompt-injection attempts, policy enforcement, errors that must not authorize, local RAG approval/relevance/fallback, evidence provenance, contradiction handling, and demo banking. These are automated tests; they do not prove absence of all bypasses. The current test run does not amount to a fresh two-account live reconciliation demonstration or a live replay of all scenarios A–Z.

No independently verified real-world labels are available. Therefore, **false-positive and false-negative rates are not measured** for this final pass. Previously published synthetic model metrics remain synthetic research results, not ground truth or a production claim. Some earlier scenario rows received review/verification interventions while their displayed risk band remained LOW; keep intervention policy, risk, and model confidence distinct in customer explanations.

## RAG and latency

The local RAG tests exercise approved-source attribution, relevance rejection, unapproved-source rejection, injection-resistant handling, and safe empty-evidence behavior on retrieval failure. Retrieval uses a small curated local corpus and lexical matching; source freshness is not automatically verified. A hosted LLM, external retrieval provider, and LLM latency were not tested or configured.

Fresh local synthetic timings from the 20-flow HTTP audit: chat HTTP median 82.61 ms / p95 193.88 ms; complete flow median 238.01 ms / p95 280.93 ms; passive analysis median 41.54 ms / p95 52.52 ms; contextual/fusion analysis median 104.01 ms / p95 125.22 ms; end-to-end analysis median 144.96 ms / p95 168.17 ms; local RAG 50-sample median 0.107 ms / p95 0.47 ms. Timing is environment-dependent and not a service-level guarantee. No optimization was justified by these measurements.

## Release gates

- **Functionality — verified with limits:** unified chat routes and backend tests cover payments, balance, and transaction details; local frontend and API respond. Twenty authored conversation cases and the two-account live reconciliation passed. Remaining adversarial cases have automated coverage where implemented, but the complete A–Z list was not replayed as 26 separate live HTTP scenarios.
- **Fraud intelligence — partially verified:** components are exercised through the assessment workflow and tests; no verified real-world accuracy or full modality-ablation comparison is available.
- **Safety — verified for tested cases:** backend tests exercise explicit confirmation, stale assessment rejection, cancellation, idempotency, account scoping, and fail-closed paths. In-memory chat idempotency is process-local; it is not restart- or multi-worker durable.
- **Reliability — verified locally with limits:** full backend/frontend suites, production build, startup, health checks, live conversation replay, ledger reconciliation, and concurrent confirmation retry pass. One upstream deprecation warning remains. Browser visual inspection was not completed in this pass.
- **Scientific credibility — documented:** scenario and timing results are identified as synthetic/prior-run; real-world false-positive/negative rates are not claimed.

## Remaining limitations and next step

- Repeat all 26 scenarios against an isolated live HTTP test database, including account A/B reconciliation and concurrency, after the final code change.
- Replace process-local chat idempotency with durable storage and a transactional outbox before multi-worker deployment; real-money integration remains out of scope.
- Obtain independently labeled, temporally separated, representative data before making accuracy or calibration claims. Evaluate transaction-only, recipient, graph, and full fusion on the same eligible cases, including subgroup and hard-legitimate analysis.
- Improve language and multilingual coverage using adversarial paraphrases and reviewed labels; authored deterministic scenarios are not a substitute.
- Retire the Starlette/httpx test-client deprecation by updating the supported test dependency combination when dependency policy allows.
- Run the requested independent hackathon demonstration after the final live scenario and reconciliation rehearsal; do not add more feature scope first.

## Reproduction

From the project root on Windows:

```powershell
start.bat
# Open http://127.0.0.1:5173/
# API documentation: http://127.0.0.1:8000/docs

.venv\Scripts\python.exe scripts\run_windows_tests.py -q
cd frontend
node.exe --test
node.exe node_modules\vite\bin\vite.js build
cd ..
stop.bat
```

No API key is required for the local synthetic flow. Do not add a secret key to source control.
