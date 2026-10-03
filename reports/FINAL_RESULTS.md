# APP Shield final results

## Dataset

The measured fusion holdout contains 400 chronologically later synthetic rows, including 33 positive labels. The registered fusion model was evaluated on a transaction/recipient modality profile; graph/context/scenario/psychology features were not joined to payment IDs and labels. The benchmark freeze at `data/benchmark/final_benchmark_v1/` is reproducible but its source was already examined during Day 9.

## Baselines and full model

See [`final_model_comparison.csv`](final_model_comparison.csv) for precision, recall, F1, PR-AUC, ROC-AUC, FPR, FNR, Brier, and validation-selected operating points. The registered fusion at its existing threshold measured precision **0.889**, recall **0.485**, F1 **0.627**, PR-AUC **0.714**, ROC-AUC **0.922**, FPR **0.005**, and Brier **0.037**. Transaction+recipient ablation measured precision **0.875**, recall **0.636**, F1 **0.737**, PR-AUC **0.769**, ROC-AUC **0.957**, FPR **0.008**, and Brier **0.039**. Its threshold was selected on validation, then applied once to test.

## Ablation study

Transaction+recipient outperformed the registered full fusion on recall and PR-AUC in this synthetic holdout. This does not establish that extra modalities hurt: the associated graph/context/scenario/psychology evidence is unavailable in the supervised training dataset, so modality-specific ablations are `NOT_EVALUABLE`. The separate live simulator demonstrates how those signals change illustrative cases, not their measured generalization.

## Scenario and hard-negative performance

`final_scenario_performance.csv` and `final_hard_negative_results.csv` list requested categories and mark them `NOT_EVALUABLE` because no verified transaction-linked scenario or intent-level hard-negative labels exist. No category recall or hard-negative payment FPR is claimed.

## Adversarial performance

The authored 1,000-message synthetic probe measured raw-text precision 1.000, recall 0.336, F1 0.503, and FPR 0 at its explicitly illustrative score threshold 25. Text normalization measured precision 1.000, recall 0.356, F1 0.525, and FPR 0. This leaves 322 of 500 scam messages missed; it is a message-level template benchmark, not a payment evaluation. See `final_adversarial_results.csv` and `evaluation/day7_adversarial_evaluation.json`.

`final_language_robustness.csv` breaks out authored base-English, Hinglish-wrapper and obfuscation variants. The corpus applies transformations one at a time; combined obfuscated-Hinglish performance is marked `NOT_EVALUABLE`. `final_message_hard_negative.json` records the zero message-level false positives among 500 synthetic benign messages at the same probe threshold. This must not be read as payment-level hard-negative performance.

## Calibration and cost

The registered fusion test Brier score is 0.037 and its reliability bins and ECE appear in `calibration_report.json`. This is calibration against synthetic test labels only. Threshold costs in `cost_analysis_config.json` are named simulation assumptions and do not represent payment-provider economics.

## Latency

`latency_summary.json` summarizes measured Day 8 in-process simulation phases, five current case-level component timings, and Day 7 API smoke/stress data. The current component sample has only five requests; all timings are single-process and are not a throughput or production latency guarantee.

## Five flagship demonstrations

See [`demo_scenario_results.json`](demo_scenario_results.json) for outputs from the actual simulator. The government case rose from 13.69 transaction-only to 35.16 full risk and received a warning. The ₹80,000 established-merchant case scored 54.81 transaction-only versus 7.0 full risk and was allowed. The ₹500 investment-pressure case scored 16.5 versus 34.75 and received an investment warning. The mule-network fixture's full score fell to 16.37 and was allowed despite 44.85 passive risk; this is an observed weakness requiring investigation. The urgent family message to an established contact scored 0 full risk and was allowed. These five runs are examples, not labeled performance statistics.

## Key finding and limitations

The project does **not** establish that APP Shield outperforms transaction-focused detection for authorized social-engineering scams. The registered fusion did not outperform the transaction+recipient ablation on the available holdout, and no holdout contains linked manipulation/context labels. The live examples do demonstrate the intended behavior, but further validation needs consented, representative, transaction-linked outcomes, especially cold-start and mule-network cases. All results are synthetic; the system is not deployed by or integrated with PayPal, Paytm, a bank, or UPI.
