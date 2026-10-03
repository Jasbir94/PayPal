# APP Shield Day 7 — adversarial tests and API hardening

Day 7 adds conservative text normalization, bounded multi-turn analysis, user-facing intervention templates, request limits, privacy-safe assessment logging, and a deterministic synthetic robustness benchmark. The existing preliminary, contextual, and final payment endpoints remain available.

## Robustness corpus and measured result

Run `scripts/generate_day7_benchmark.py` to regenerate `data/adversarial/benchmark.json` and `evaluation/day7_adversarial.py` to write `evaluation/day7_adversarial_evaluation.json`. The corpus has 1,000 authored message examples from 50 templates: 500 positive scam-message labels and 500 legitimate-message labels. It varies Hinglish wrappers, leetspeak, split letters, zero-width and full-width Unicode, punctuation, indirect requests, typos, casing, small amounts, and paraphrase-like substitutions. Source templates—not individual variants—define the split; the 200-case holdout uses unseen template families.

The evaluation compares raw text against the normalization-enabled psychology rule service at a fixed evidence-index threshold of 25. On all cases, precision was 1.000 and recall rose from 0.336 to 0.356 (F1 0.503 to 0.525). On the untouched template holdout, recall rose from 0.350 to 0.370 (F1 0.519 to 0.540); both had 0 false positives among 100 authored legitimate holdout messages. These are deliberately synthetic, balanced, message-level results. The score is not a probability, the threshold is a benchmark probe rather than a production operating point, and the 64.4% hardened false-negative rate shows that normalization alone is insufficient. The report retains each false-negative case and category counts for review.

The corpus does not contain linked payment IDs, recipient account types, or ground-truth payment outcomes. Therefore it cannot validate end-to-end fraud accuracy, and recipient-versus-claimed-organization consistency is reported as unavailable rather than inferred from names or message text. Hinglish coverage is limited to short code-switched wrappers. No synthetic result here should be read as field performance.

## Input and privacy safeguards

`POST /api/v1/analyze-conversation` accepts 1–20 ordered messages, at most 2,000 characters per message and 6,000 characters total. Only `speaker="other"` messages are scored. The response contains aggregated evidence, capped progression and the payment assessment; individual message text and internal per-turn evidence are not returned or logged. Repeated technique evidence and risk bonuses are capped. Amount escalation is reported only when amounts are present.

API requests under `/api/v1/` are limited to 65,536 body bytes and 120 requests per client IP per 60 seconds. The in-process limiter has a bounded 4,096-client LRU and is intended for a single-process prototype; production deployments need a shared rate-limit store and trusted proxy configuration. CORS allows no origins by default; set `APP_SHIELD_CORS_ORIGINS` to a comma-separated explicit allowlist. The application limits methods and headers, does not enable credentialed CORS, validates request schemas, and returns a generic unexpected-error body. `/health` remains liveness, `/ready` reports model-service readiness, and `GET /api/v1/model-info` exposes component availability and score semantics without filesystem paths.

Assessment logs omit message content and pseudonymize transaction references with a process-scoped salt. The privacy helper redacts credential-like values if used on diagnostic text. Text normalization returns a separate view and retains the original only in memory; it does not persist the original or include it in the API response. Prompt-like message content is treated as ordinary untrusted text; there is no tool execution or model instruction channel in this service.

## Interventions and conversation behavior

The final assessment now includes a level 0–4 intervention with a concise title, evidence-matched message, and recommended action. A scenario-specific warning is used only when that scenario has context-supported scenario risk; otherwise the service uses a generic warning. The intervention does not disclose thresholds or claim an unsupported scam category. These recommendations do not execute, cancel, or block a payment.

The conversation route calls the existing final assessment engine once with the bounded combined counterparty text. It also reports technique scores, detected stages and progression separately. Counterparty messages are analyzed in order; messages from the requester are counted but not scored. Conversation escalation is a prototype evidence feature, not a learned temporal model.

## Verification

Focused Day 7 tests cover text obfuscation, preservation of numeric references, log redaction and pseudonyms, 413/429 request rejection, conversation bounds/aggregation, intervention gating, and model-info privacy. Run the full suite with:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~

Run the local end-to-end latency smoke with:

~~~powershell
.\.venv\Scripts\python.exe evaluation\day7_api_stress.py
~~~

It sends 30 sequential requests through FastAPI `TestClient`, records status counts and latency percentiles in `evaluation/day7_api_stress.json`, and is not a concurrent or production-capacity test. The evaluation script also records per-case timing for 1,000 raw/normalized message pairs.
