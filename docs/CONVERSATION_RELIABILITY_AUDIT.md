# APP Shield conversational payment reliability audit

**Run date:** 2026-10-09

**Scope:** Local FastAPI and React demo, synthetic recipients and transactions, simulated actions only. No payment provider was contacted and no real money moved.

## Outcome

The complete chat flow was exercised through the running HTTP API for 20 authored scenarios. All 20 reached a terminal outcome. No attempt executed before a separate explicit confirmation, and the session asked at most one context question per flow (6 prompts in total, with no repeated prompt). The backend remained responsible for analysis, allowed actions, payment state, cancellation, and confirmation.

The run surfaced a real policy gap: the learned fusion score could undercut direct scam-context evidence. The risk-to-action policy now applies transparent minimum interventions for reported authority plus pressure, unknown-contact urgency, guaranteed returns, advance job fees, remote-access requests, and recipient prior-report/network evidence. These policy floors trigger review or verification; they do not assert that a report is independently verified or that fraud is certain. Regression tests cover the new floors and that an instruction embedded in chat cannot set the score or add actions.

## Conversation outcomes

“Review” and “step-up” mean the backend presented an intervention; they are not verified fraud classifications. “Cancelled” means the test driver selected its specified simulated action.

| Scenario | Backend outcome | Conversation result |
| --- | --- | --- |
| Known recipient | ALLOW_WITH_WARNING | Simulated confirmation completed |
| New legitimate recipient | ALLOW | Cancelled |
| Urgent family emergency | ALLOW_WITH_WARNING | Cancelled; urgency alone did not produce a scam verdict |
| Government impersonation | STEP_UP_VERIFICATION | Cancelled |
| Fake bank verification | STEP_UP_VERIFICATION | Cancelled |
| Fake job registration fee | WARN_AND_REVIEW | Cancelled |
| Investment with guaranteed returns | WARN_AND_REVIEW | Cancelled |
| Recipient with prior-risk/network evidence | WARN_AND_REVIEW | Cancelled |
| Missing details | ALLOW_WITH_WARNING | Cancelled after completing the details flow |
| User changes their mind | ALLOW_WITH_WARNING | Natural-language cancellation worked |
| Small known payment | ALLOW_WITH_WARNING | Simulated confirmation completed |
| Established merchant | ALLOW | Simulated confirmation completed |
| Legitimate large purchase | ALLOW | Cancelled |
| Legitimate family emergency | ALLOW_WITH_WARNING | Simulated confirmation completed |
| Secret authority request | STEP_UP_VERIFICATION | Cancelled |
| Uncertain contact | ALLOW | Cancelled |
| Hinglish bank impersonation | STEP_UP_VERIFICATION | Cancelled |
| Remote-support pressure | STEP_UP_VERIFICATION | Cancelled |
| Refund-return pressure | WARN_AND_REVIEW | Cancelled |
| Ordinary merchant | ALLOW | Simulated confirmation completed |

The exact per-case score, reason codes, prompt, timing, state, and selected action are in [the machine-readable audit](../reports/conversation_reliability_audit.json). Six prompts were all the same relevant missing-context question: “Who asked you to make this payment?” Fourteen flows needed no context prompt. The synthetic tests verify answer evidence is stored as an unverified user report and then used by the backend; a previously answered question is not asked again.

## Safety and question checks

- **Explicit confirmation:** All audited payments remained unexecuted until the test driver made its explicit confirm action. Duplicate confirmation is rejected with HTTP 409; attempt creation is idempotent for a reused key, and a different payload cannot reuse that key.
- **Edits and cancellation:** Changing amount or recipient cancels the prior attempt and creates a fresh assessment. Natural-language “I changed my mind” cancels the attempt.
- **Failure handling:** An injected analysis failure returns an error and leaves the attempt in `ERROR`, never authorized. RAG retrieval failure returns no citations while preserving the backend assessment.
- **Prompt instructions:** A chat instruction to set the risk to zero or auto-confirm produced the same risk score and decision as the corresponding baseline message, with no extra action.
- **High-concern handling:** Authority plus pressure now requires verification even if contact identity is uncertain; unknown-contact urgency, job fees, guaranteed returns, remote access, and recipient prior reports trigger review or verification.
- **Question limit:** At most one question was emitted per flow. The design's deterministic question selection does not estimate information gain. Whether every prompt materially improves a decision has not been experimentally established.

## RAG findings

The approved local corpus returns attributed RBI guidance for government-impersonation queries and the cybercrime portal for bank-safety queries. Official URLs are restricted to the RBI and National Cyber Crime Reporting Portal hosts; unrelated queries and unapproved sources return no result. Retrieved content is surfaced with source metadata and hashes. Retrieval is local and does not call a hosted model.

Prompt-injection resistance is architectural: retrieved text and chat instructions cannot set the policy decision or enable a payment action. The assistant does not generate free-form answers from retrieved passages; it uses backend decision templates and presents retrieved citations/excerpts. This is retrieval-grounded guidance, not a generative RAG chatbot. When retrieval is unavailable, it safely returns an empty citation list and keeps payment policy backend-owned.

## False positives and false negatives

No formal false-positive or false-negative rate is reported. The 20 chat scenarios are authored synthetic examples, not independently verified real-world labels. Their intended themes are useful functional checks, but they cannot establish detection accuracy. The labeled synthetic training corpus is not a verified label set for these conversations. In this authored run, all nine scam-themed cases received review or verification interventions; the known-recipient urgent-family case remained eligible for confirmation with a caution. Those counts describe this test set only.

## Windows startup and SQLAlchemy

On this Windows machine, startup preflight (`scripts/start_app.ps1 -CheckOnly`) passed and the documented startup procedure launched both API and frontend successfully. SQLAlchemy's optional compiled `_processors_cy` extension is blocked by Windows Application Control during ordinary test imports. The project now documents `scripts/run_windows_tests.py`; it loads SQLAlchemy's bundled Python implementation for the test process only. The virtual environment and installed packages were not modified. The complete backend suite passes through that runner.

## Latency

One clean localhost run of 20 flows; values are milliseconds. The 50 retrieval samples use the local in-process retriever. These are development-machine measurements, not service-level guarantees.

| Measurement | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Chat API response | 63.80 | 154.40 | 166.40 |
| Complete conversation flow | 180.18 | 245.55 | 251.07 |
| Passive payment analysis | 26.80 | 41.56 | 48.84 |
| Contextual/fusion analysis | 55.27 | 91.36 | 105.09 |
| End-to-end analysis stage | 80.78 | 129.17 | 146.49 |
| Local RAG retrieval (50 samples) | 0.045 | 0.15 | 0.273 |

The contextual/fusion stage is the largest measured component, but its median was about 55 ms; these results do not justify a latency optimization. No hosted LLM latency was measured because no LLM is configured.

## Verification results

- Backend: **318 passed**, one existing Starlette/httpx deprecation warning.
- Focused conversation, policy, and RAG tests: **50 passed**.
- Frontend: **6 passed**; Vite production build succeeded.
- Windows startup preflight: passed; live Windows startup: API and frontend ready.
- Live API conversation audit: **20/20 terminal outcomes**, 0 pre-confirmation executions, maximum one question per flow, 0 repeated prompts.

## Remaining limitations

- All data, conversations, recipient histories, and payment outcomes are simulated. There is no gateway, real recipient verification, or real-world fraud ground truth.
- The RAG corpus is small and locally curated; retrieval uses lexical overlap rather than semantic embeddings, and source freshness is not checked automatically.
- Language understanding relies on deterministic extraction and existing classifiers. Hinglish coverage is limited; the audit does not test broad multilingual phrasing or adversarial paraphrase generation.
- A review/verification intervention can still be followed by a simulated user action. This demo cannot model bank-side holds or identity verification.
- The backend emits one pre-payment question at most. The audit shows bounded friction, not that the selected question is optimal for every user.
- Test output includes one upstream Starlette/httpx deprecation warning.

Do not infer production readiness or real-world fraud-detection effectiveness from this synthetic functional audit.
