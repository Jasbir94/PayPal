# APP Shield Phase 15 reliability report

## Outcome

Phase 15 hardens evidence handling and payment authorization in the simulated payment backend. Customer statements remain useful context, but they no longer erase earlier concerning answers or create protective risk reductions by themselves. Recipient history can support a payment relationship, while the system clearly states that history does not prove identity. A click on “verified” cannot satisfy a backend verification requirement.

## Changes made

- Added an analyst-only evidence ledger with source type, reference, timestamp, confidence value and kind, verification state, payment ID, and supported interpretation. User statements, external narrative, approved RAG references, backend records, and model inferences are kept distinct.
- Added relationship, identity, and payment-purpose consistency checks. Missing account history is represented as uncertainty, not as evidence of deception.
- Preserved earlier reports of pressure when a later answer denies them, and recorded the contradiction without treating either statement as independently verified.
- Removed protective-score deductions based solely on user-reported absence of pressure or unknown contact. Backend history and other independently derived evidence remain available to the scoring system.
- Bound the assessment to a fingerprint of the payment details. Editing amount, recipient, or other payment details invalidates the old assessment and requires reassessment.
- Made verification UI actions record an unverified claim only. The backend continues to require its policy state before settlement.
- Added request idempotency for chat start/message calls when a request key is supplied. Replays return the same result; reusing a key for a different payload is rejected.
- Kept customer-facing evidence explanations separate from the detailed analyst provenance ledger.

## Verification results

| Check | Result |
|---|---:|
| Phase 15 evidence, fusion, missing-evidence, adversarial, and local RAG tests | 28 passed |
| Windows test wrapper targeted run | 21 passed |
| Frontend tests | 7 passed |
| Frontend production build | Passed (Vite 8.2.1) |
| Python compile check (`backend/app`, `tests`) | Passed |
| `git diff --check` | Passed; Git only emitted line-ending conversion notices |
| Complete backend/API suite | Not verified in this run |

The new adversarial tests exercise the payment simulator and conversation agent directly. Covered outcomes include an unrecorded relationship claim, pressure against a known recipient, conflicting rent/investment narratives, prompt injection, cancelled payments, changed payment details, contradictory answers, and removal of self-reported protective deductions. The RAG tests cover approved-source attribution, low-relevance/source rejection, and injection-resistant retrieved guidance.

Three direct backend scenario replays also completed: ordinary family emergency reached review at risk 39.53; a legitimate family emergency with recorded history remained low risk/allowed at 0.0; and government impersonation remained paused for verification at risk 39.58. These are deterministic synthetic demos, not estimates of real-world fraud performance.

## Conversations, false positives, and false negatives

The Phase 15 adversarial tests are not a fresh run of 20 full HTTP conversations. A prior synthetic conversation audit is stored in `reports/conversation_reliability_audit.json`; it recorded 20 terminal flows, no repeated questions, at most one question in a flow, and no execution before confirmation. Its measurements predate this Phase 15 change and should not be presented as a Phase 15 acceptance run.

No independently verified real-world labels were available for this run. Therefore, false-positive and false-negative rates for the updated behavior are **not measured**. Existing synthetic temporal evaluation has 400 test examples (33 positive) and reports precision 0.889, recall 0.485, false-positive rate 0.00545, false-negative rate 0.515, and Brier score 0.0371. Modality coverage for graph, context, scenario, and psychology was zero in that evaluation. These are historic synthetic results, not validated performance and not a before/after estimate of Phase 15.

Unnecessary-question counts and question repetition were not freshly measured across the complete HTTP conversation suite after the changes. The earlier 20-flow audit found zero repeats and at most one question per flow.

## Payment safety

Regression coverage confirms that a verification click cannot authorize settlement, a cancelled attempt cannot be confirmed, altered payment details invalidate the assessment, and prompt-injection text cannot authorize or fabricate a receipt. The simulator still requires an explicit continuation action after review. These controls were tested in-process; the full API integration suite could not be completed because this machine's Python async event-loop/TestClient startup hangs before application startup, including for a bare FastAPI app.

Chat idempotency is in-memory and bounded. It protects retries within one running process; it does not provide cross-worker or restart-safe deduplication. A production payment system needs durable idempotency storage and a transactional settlement/outbox boundary. This project remains simulated and does not move funds.

## RAG and startup

The local RAG subset passed. It checks source approval and relevance, attribution of retrieved official guidance, and that injected query text cannot modify or authorize the retrieved answer. A live external knowledge provider and real payment-provider behavior were not tested.

The project test wrapper `scripts/run_windows_tests.py` passed its 21-test targeted run using the project virtual environment. Its SQLAlchemy pure-Python fallback is process-local and does not alter installed packages. This verifies the wrapper path for the targeted tests, not every machine's App Control policy or the full documented application startup path. The API-level TestClient hang remains an environment-level integration blocker and requires a separate Windows async/runtime investigation.

## Latency

No fresh latency benchmark was run after Phase 15. The prior synthetic audit JSON reports HTTP response median 63.8 ms / p95 154.4 ms, full payment analysis median 55.27 ms / p95 91.36 ms, local RAG retrieval median 0.045 ms / p95 0.15 ms, and complete flow median 180.18 ms / p95 245.55 ms. These are prior-run measurements, not current performance claims. No optimization was made because there is no new profiling evidence showing a bottleneck.

## Remaining limitations and next research step

- Run all 20 conversation cases through the live API after resolving the local async/TestClient startup hang.
- Move idempotency keys to durable storage before any multi-worker or real-money integration.
- The provenance ledger is analyst-facing and is not a cryptographically signed audit log.
- User reports and supplied narrative remain unverified unless a connected trusted source can confirm them.
- Synthetic test cases do not establish resistance to novel scam behavior or production calibration.
- Rerun temporal, adversarial, and subgroup evaluation with verified labels and nonzero coverage for the graph, scenario, context, and psychology modalities. Use clustered false-positive/false-negative review to guide the next model changes.

APP Shield remains a research/demo system. These changes improve evidence integrity and simulated payment safety; they do not establish production readiness.
