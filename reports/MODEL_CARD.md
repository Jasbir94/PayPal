# APP Shield fusion model card

## Model

The active registry entry is a calibrated transaction/recipient fusion model. It combines engineered transaction and recipient risk features and returns a calibrated probability for its synthetic training profile. The wider APP Shield application also computes graph, context, scenario, and psychology evidence, but those modalities are not represented in the Day 6 linked fusion training corpus.

## Evaluation

Use `python -m scripts.run_final_evaluation` to regenerate chronological train/validation/test comparison, calibration, drift, scenario, hard-negative, and illustrative cost outputs. Threshold selection is confined to validation where applicable; final metrics use the later test period. See `reports/final_evaluation.json` and `reports/final_model_comparison.csv`.

## Limitations and use

All evidence is synthetic. The probability is not established as calibrated on live payment traffic. Named scenarios and hard negatives do not have linked trusted labels and are excluded from performance claims. No autonomous retraining or model promotion runs. Candidate models remain challengers until they pass same-holdout guardrails and an operator explicitly approves promotion.
