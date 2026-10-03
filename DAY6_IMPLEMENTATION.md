# APP Shield Day 6 — decision and fusion layer

## Delivered

The final assessment endpoint is `POST /api/v1/analyze-payment`. It orchestrates the existing transaction, recipient, graph, context, scenario and psychology services while leaving the Day 2 preliminary and Day 3–5 contextual endpoints intact. It returns a 0–100 risk index separately from a 0–1 evidence confidence, family availability, optional calibrated probability, likely scenario, psychological techniques, protective and canonical evidence, top reasons, recommendation, model versions, component scores, and per-component plus end-to-end latency.

The implementation is under `backend/app/fusion/`: `evidence.py` canonicalizes overlapping reasons and retains source provenance; `grouping.py` combines recipient/graph evidence with a 0.65/0.35 strongest-plus-complement blend and renormalizes only available families; `cross_layer_rules.py` adds capped independent-pattern support; `protective_evidence.py` applies reductions only for affirmative observed facts; `calibration.py` loads validation-trained artifacts only when the live modality profile matches the training profile; `decision_policy.py` maps risk and uncertainty to a recommendation; and `explanation.py` ranks concise, stable reason text. `FraudEngine` owns the final orchestration and emits a JSON log record without raw messages, credentials, OTPs, PINs or passwords.

Default family weights in `backend/app/config/risk_config.py` are 25% user-side, 30% recipient/network and 45% manipulation. They are transparent MVP defaults. Duplicate recipient/network evidence is discounted; scenario classifier confidence is not treated as fraud risk; manipulation score requires underlying context evidence or psychology signal. Protective evidence includes a known recipient, repeated payments, established recipient account, ordinary amount pattern, and explicit absence of reported pressure. Unknown values never count as protective evidence.

## Dataset, model and leakage controls

Run the builder with `.\.venv\Scripts\python.exe -m ml.fusion.build_dataset`. By default it uniformly samples 2,000 rows across the chronological synthetic transaction file. `--limit 0` processes all rows and `--limit N` chooses a deterministic timeline sample. It invokes transaction and recipient services with history strictly before each payment. IDs and timestamps are retained for audit, but `FEATURES` is an explicit whitelist that excludes them and `is_fraud`/`fraud_type`; the target is read only after each score has been calculated. Future reports and graph target labels are never predictors.

The independent scenario and psychology message corpora have no payment IDs or timestamps, and the graph training labels describe synthetic account profiles rather than payment-time outcomes. They cannot be joined to these payment labels without inventing associations or leaking targets. The fusion CSV therefore has explicit availability flags and zero placeholders for those unavailable model inputs. The learned model is valid only for its recorded modality profile. At runtime it is bypassed when graph/context/scenario/psychology coverage differs, and the manual grouped evidence engine handles that request. This makes the limitation visible instead of pretending the trained payment model learned manipulation or network risk.

Run `.\.venv\Scripts\python.exe -m ml.fusion.train` to train an interpretable, class-weighted Logistic Regression on the first 60% of time-ordered rows, fit Platt and isotonic mappings on the next 20%, choose the calibration method by validation Brier score, and select an F1 threshold on validation. The last 20% stays held out. Calibration files are `saved_models/fusion_model.pkl`, `saved_models/calibration_model.pkl`, and `saved_models/fusion_metadata.json`.

## Current synthetic evaluation

The checked-in report is `data/processed/day6/evaluation.json`. On the 2,000-row sampled dataset, split sizes are 1,200/400/400 and the held-out test contains 33 positives. Validation selected isotonic calibration (Brier 0.0320 versus 0.0408 for Platt) and threshold 0.325. Test Brier was 0.0371. Test metrics below use independently validation-selected thresholds for each model:

| Variant | Precision | Recall | F1 | False-positive rate | False-negative rate | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| Learned logistic + isotonic | 0.889 | 0.485 | 0.627 | 0.005 | 0.515 | 0.922 | 0.714 |
| Manual transaction/recipient blend | 0.917 | 0.667 | 0.772 | 0.005 | 0.333 | 0.972 | 0.869 |
| Amount + first-recipient baseline | 0.333 | 0.242 | 0.281 | 0.044 | 0.758 | 0.864 | 0.355 |

The learned model did not beat the manual blend on this small test. That is retained as the result, not described as an improvement. The test has few fraud examples, and its F1-selected operating point still misses 11 of 33 positives for the manual blend and 17 of 33 for the learned model. The saved report contains all 17 learned-model false negatives and two false positives with score inputs for review. A local synthetic API smoke request completed in about 131 ms end-to-end on this machine: transaction 34 ms, recipient 21 ms, graph 47 ms, context 0.1 ms, scenario 4 ms and psychology 8 ms. Treat this as one mixed-cache sample, not a latency guarantee.

Across the 2,000 rows, transaction risk mean/median was 13.66/0.24 for legitimate and 53.42/53.81 for fraudulent payments. Recipient risk mean/median was 11.76/5.24 and 47.78/56.06 respectively. Graph, context, scenario and psychology each have 0 available payment-linked scores; their distributions are recorded as missing, not safe zeros. Ablations removing transaction or recipient signals change the scores; graph/context/scenario/psychology ablations are explicitly non-informative because there are no joined observations for those modalities. The report includes reliability bins, FPR/FNR, confusion matrices, ROC-AUC, average precision, Brier scores, latency for the learned model call and ranked error rows.

These figures describe only the authored synthetic data. They do not establish field accuracy, generalization, or real-world probability calibration. The fusion corpus uses payment rows and sender/recipient histories; no behavioral profile split is claimed, so repeated accounts may appear across chronological partitions. Treat decisions as prototype recommendations and review false negatives before relying on the result.

## API example

~~~http
POST /api/v1/analyze-payment
Content-Type: application/json
~~~

~~~json
{
  "transaction": {
    "transaction_id": "demo-001",
    "sender_id": "A0001",
    "receiver_id": "A0500",
    "amount": 2000,
    "timestamp": "2026-01-30T11:30:00+00:00",
    "device_id": "D0001",
    "payment_type": "upi",
    "first_time_recipient": false,
    "payment_reason": "investment"
  },
  "context": {
    "payment_reason": "investment",
    "contacted_by_unknown_person": true,
    "claimed_authority": false,
    "urgent_payment_requested": true,
    "guaranteed_returns_promised": true
  },
  "message": "Invest now today; returns are guaranteed."
}
~~~

Account IDs and timestamp must exist in the loaded synthetic observation window. `context` may be omitted; missing message/context and unavailable graph evidence are represented in `missing_evidence`, lower confidence, and family availability. The output `decision` is one of `ALLOW`, `ALLOW_WITH_WARNING`, `WARN_AND_REVIEW`, `STEP_UP_VERIFICATION`, or `BLOCK_AND_ESCALATE`; the service does not execute payment actions.

## Rebuild, test and run

From the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m ml.fusion.build_dataset
.\.venv\Scripts\python.exe -m ml.fusion.train
.\.venv\Scripts\python.exe -m ml.fusion.calibrate
.\.venv\Scripts\python.exe -m ml.fusion.evaluate
.\.venv\Scripts\python.exe -m ml.fusion.ablation
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
~~~

The full Day 1–6 suite passes (221 tests; one existing Starlette TestClient deprecation warning). Restart the API after training so startup loads the latest compatible artifacts. Use `Invoke-RestMethod` with the JSON example to exercise the final route.
