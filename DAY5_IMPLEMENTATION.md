# APP Shield Day 5: transaction graph and mule intelligence

## Implemented

A directed, temporal NetworkX MultiDiGraph models accounts and individual payments. The graph layer includes fan-in/out, FIFO pass-through, bounded cycle/path checks, PageRank, known-mule proximity, explainable rules, a structural Logistic Regression model, an account API, and grouped contextual fusion. NetworkX is declared in backend/requirements.txt. GNNs and graph databases are not used.

The deterministic generator keeps Day 1 payment/account files intact and adds a separate overlay with collector-distributor-cashout patterns, some cycles, and legitimate merchant, restaurant, tuition, seller, payroll, and fundraiser accounts.

## Commands

Run from the app-shield root:

~~~powershell
.\\.venv\\Scripts\\python.exe -m scripts.generate_mule_network
.\\.venv\\Scripts\\python.exe -m ml.graph.build_graph
.\\.venv\\Scripts\\python.exe -m ml.graph.train
.\\.venv\\Scripts\\python.exe -m ml.graph.evaluate
.\\.venv\\Scripts\\python.exe -m pytest -q
.\\.venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
~~~

In another terminal, verify the live routes:

~~~powershell
.\\.venv\\Scripts\\python.exe -m scripts.smoke_day5
~~~

Generated network rows, evaluation accounts, intelligence, and features live in data/graph/. The fitted model is saved_models/graph_model.pkl. Evaluation/build reports are in data/processed/day5/. The API loads model and graph data once at startup; restart after retraining.

## Temporal graph and features

Every scored snapshot includes only transactions strictly before the requested instant and within the preceding 24 hours. A NetworkX MultiDiGraph preserves parallel transfers, including each transaction ID, amount and timestamp. Future and same-time transfers are excluded. Account nodes are available from their creation instant. The requested payment is removed if its ID exists in historical data.

Snapshots are immutable and kept in a four-entry LRU. Unknown current-payment IDs share a cache key because they cannot match historical rows. Node features are cached per snapshot. The builder reuses the in-memory Day 1 payment repository and does not reread CSVs per feature.

Features include directed transaction degree, unique incoming senders/outgoing receivers, total amounts, outflow/inflow ratio, FIFO-matched rapid-outflow and matched-outflow ratios, median matched holding time, direct known-mule neighbors, reported neighbors, known-mule distance, bounded cycle count, weak-component size, PageRank, and time-ordered path depth. PageRank alone never adds fraud risk.

FIFO matching consumes earlier inflows against later outflows. It approximates money holding time and cannot trace fungible funds or balances before the 24-hour window. Unmatched outflows do not count as rapid pass-through. Cycle search stops at length four and 2,000 steps. Time-ordered paths stop at four edges and 2,000 steps, with every hop within 30 minutes. Truncation flags appear in the features.

Mule and report intelligence is used only when observed before the request time. The synthetic intelligence table exposes two selected known-mule IDs and pre-observation reports, not every target label.

## Explainable score

The rules combine fan-in, fan-out, at least 80% rapid outflow on at least 10,000 incoming amount, account age, mule proximity, reported neighbors, cycles and layered paths. A lone high fan-in, large component, PageRank or cycle cannot trigger a critical result.

Dense synthetic connectivity made cycles and two-hop proximity noisy for established businesses. The added established-account guard caps graph risk at 65 when the account is at least 365 days old, has no direct known-mule neighbor and has at most one reported neighbor. Strong direct evidence bypasses this cap. This is a hand-built MVP safeguard that needs real merchant evaluation.

## Model and evaluation

The Logistic Regression model predicts sparse is_known_mule labels from graph structure only. It excludes is_known_mule, is_suspicious, fraud_type, account age, reports and mule proximity. The account target split is disjoint and time-ordered: January 6 training, January 16 validation, January 26 test. A threshold is selected on validation F1 only. Neighbor accounts can cross target splits, so this is not component-disjoint evaluation.

The known-mule test contains only four positives out of 209 accounts. At selected threshold 0.80, graph model precision was 0.148, recall 1.000, F1 0.258, ROC-AUC 0.977, average precision 0.390 and false-positive rate 0.112. It generated 23 false positives. Four positives are too few for a reliable recall estimate; 22 other synthetic suspicious accounts are treated as negative because they lack known-mule labels.

For the broader synthetic is_suspicious target (nine positives), graph-only score at 0.60 had precision 0.800, recall 0.889, F1 0.842, ROC-AUC 0.993, average precision 0.920 and 0.010 false-positive rate. Recipient-only F1 was 0.588 and recipient-plus-graph F1 was 0.800. This scenario topology is generated using synthetic suspicious-profile membership, so the comparison cannot establish generalization to real networks.

The full risk ablation uses the same neutral context and message for every test account; labels are read only after scoring. At fixed 0.60 threshold both versions had zero recall; PR-AUC changed from 0.819 without graph to 1.000 with graph. The synthetic graph itself was generated from profile membership, so this is a code-path comparison, not independent fraud-detection evidence. No operational improvement claim follows from it.

There are 24 high-volume business hard negatives in this test set. None scored critical after the established-account guard; the maximum was 65. This authored set is small. Build timings for 10,000 base and 4,892 overlay transactions used three snapshots for 1,040 accounts: approximately 362, 16 and 75 ms. Median/p95 feature extraction was 0.31/1.53 ms. Warm-cache end-to-end core scoring median/p95 was 15/26 ms in this run; it is not a production-scale benchmark.

Full account metrics and limits are in data/processed/day5/evaluation.json. Model threshold, confusion matrix and coefficients are in data/processed/day5/training_evaluation.json. Feature build timing and split details are in data/processed/day5/build_report.json.

## API and fusion

GET /api/v1/accounts/{account_id}/graph-risk returns graph_risk, risk_level, feature values, reasons, rule/model outputs, scoring instant, lookback and timings. Optional at must be timezone-aware ISO 8601. Without at, the endpoint scores just after the latest available transaction. Invalid naive times return 422 and unknown accounts 404.

~~~http
GET /api/v1/accounts/A1002/graph-risk?at=2026-01-26T06:00:00%2B00:00
~~~

POST /api/v1/risk/contextual adds graph_risk, grouped_scores, overall_risk, overall_risk_level and fusion_policy. Existing Day 2 preliminary response and Day 3/4 contextual fields retain their meaning. Graph reason codes are included in the top-level reasons.

Recipient-side fusion is 0.7 x max(recipient, graph) + 0.3 x min(recipient, graph), which reduces duplicate network evidence. Manipulation-side fusion uses 0.7 x its strongest context/scenario/psychology signal plus 0.3 x the mean of the rest. Overall risk is 0.25 x transaction + 0.35 x recipient-side + 0.40 x manipulation-side. When context and text are both absent, known group weights are renormalized. All weights are temporary, uncalibrated MVP values.

## Source map

- backend/app/config/graph_config.py — model schema, limits and paths.
- backend/app/graph/graph_builder.py — validation and temporal MultiDiGraph snapshots.
- backend/app/graph/graph_features.py — money flow, topology and bounded searches.
- backend/app/graph/graph_rules.py — evidence scoring and merchant guard.
- backend/app/graph/data.py — shared repository and optional overlay loading.
- backend/app/services/graph_service.py — model/rule scoring.
- backend/app/services/grouped_risk.py — recipient and manipulation grouping.
- backend/app/models/graph_model.py — startup-loaded structural model.
- backend/app/api/graph_routes.py — account endpoint.
- ml/graph/build_graph.py, train.py, evaluate.py — feature export, training and ablations.
- scripts/generate_mule_network.py — deterministic mule network and hard negatives.
- tests/test_graph_*.py — graph, time, risk, hard-negative and leakage tests.

The project is still a synthetic MVP. Graph patterns are generated from profile membership, account neighbors cross target splits, known labels are sparse, and unlabeled suspicious accounts are treated as negative. FIFO matching is approximate; probabilities and grouped risk are not calibrated. Review false positives before relying on this evidence. Graph Neural Networks, real-bank feeds, production blocking and deployment are outside this day's scope.
