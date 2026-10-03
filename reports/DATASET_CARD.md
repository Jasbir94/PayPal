# APP Shield synthetic dataset card

## Scope and origin

The repository's transaction, recipient, graph, scenario, and message corpora are generated for engineering and demonstration. They do not contain production payment records or represent a population sample. Generation scripts, fixed seeds, known class balance, and field descriptions are documented in the repository's Day 1–8 implementation notes and `scripts/`.

## Intended use

Local software development, pipeline validation, temporal split checks, interface demonstrations, and controlled robustness experiments. Do not use the reported metrics to make decisions about real customers or deploy payment interventions.

## Labels and leakage

Synthetic labels are generated alongside the example records. The Day 9 fusion holdout has 2,000 chronological rows and transaction/recipient features. Graph, context, scenario, psychology, named scenario, and intended hard-negative labels are not reliably linked to that holdout; Day 9 reports mark those results `NOT_EVALUABLE`. Account report counts and ratios are pre-observation synthetic profile snapshots. Future transaction and intelligence events must remain excluded from as-of features.

## Limitations

Synthetic behavior can be easier and cleaner than real behavior, while generated overlap and scenario templates can also create artifacts. There are no measured user outcomes, production base rates, real provider costs, or representative accessibility and demographic evaluation. Confidence intervals are omitted where the limited synthetic test positives make them unstable; raw support is reported.
