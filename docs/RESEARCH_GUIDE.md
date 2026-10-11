# Research guide

Research views use actual APP Shield backend outputs and stored evaluation artifacts. All bundled evaluation data is synthetic; it cannot establish real-world fraud-prevention performance.

## In the browser

- `/research/comparison` compares the transaction-only result with the full assessment for a selected synthetic case. Its emergency comparison contrasts an unknown-contact emergency with a familiar-recipient hospital case. Both cases are independently scored by the backend.
- `/research/failures` replays the measured false positives and false negatives in `reports/final_adversarial_results.csv`. The source contains message-level predictions only, so payment-risk and confidence fields are correctly shown as unavailable.
- `/research/adversarial` reruns the backend for message variants or conversation prefixes. These are scenario experiments, not a user study or benchmark.

## Run the frozen research evaluation

From the project root, with dependencies and source artifacts present:

```powershell
.venv\Scripts\python.exe -m scripts.run_final_evaluation
```

The command uses the existing leakage-conscious temporal and fusion evaluation framework, then writes `reports/final_evaluation.json` and the reports listed in that output. It can take several minutes. Review the report's dataset split, source, limitations, and model metadata before quoting a metric. The current web app does not launch this CLI evaluation job; use the command above for a fresh run.

The failure replay page reads the frozen adversarial CSV and is not refreshed by this command. Do not call synthetic labels verified real-world outcomes.

## Reproducibility

`python -m scripts.reproduce_results` reproduces the documented reports. `python -m scripts.seed_demo` validates bundled demo assets without overwriting them. `python -m pytest -q` runs backend tests; `cd frontend && npm test` runs frontend API-client tests.
