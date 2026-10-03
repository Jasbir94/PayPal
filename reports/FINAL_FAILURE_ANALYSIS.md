# APP Shield final failure analysis

## Observed failures

- On the 400-row synthetic fusion test segment, the registered fusion missed **17 of 33** positive rows at its existing threshold (recall 0.485). The transaction+recipient ablation missed 12 of 33 at its validation-selected threshold.
- The 1,000-case synthetic message probe missed **322 of 500** scam messages after text normalization (recall 0.356). The probe includes obfuscation, indirect wording, small amounts, and mixed-language wrappers, but all are authored templates.
- In the live mule-network demo, passive risk was 44.85 but full risk was 16.37 and the decision was ALLOW. The current local fixture does not show sufficient graph evidence in the final decision. This is a concrete integration case to investigate rather than a claimed detection success.
- Scenario and payment hard-negative slices have no linked trusted labels, so their false-negative/false-positive behavior is unknown.

## Three largest remaining problems

1. **Synthetic-to-real gap and sparse positives:** a 33-positive test segment cannot establish stable operating performance or subgroup reliability.
2. **Missing linked outcomes for context and network evidence:** graph, context, scenario, psychology, and intent-level legitimate hard negatives cannot be compared in the same supervised holdout.
3. **Cold-start and graph integration uncertainty:** new recipients and sparse/mule networks can produce uncertain or conflicting evidence; the observed mule demo is a direct example.

## Failure categories

Subtle/novel language, obfuscation, missing conversation, cold-start recipients, sparse graph evidence, and legitimate urgency remain plausible weak points. The current benchmark does not isolate each of these at transaction level, so no numeric category ranking is asserted. The model card and dataset card describe the intended use and limits.
