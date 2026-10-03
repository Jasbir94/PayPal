# APP Shield pitches

## 30 seconds

Authorized payment scams can pass normal account and device checks because the real user approves the transfer. APP Shield is a research prototype that adds recipient/network history and optional payment-context and manipulation evidence before a simulated payment completes. It explains its warning and keeps risk separate from confidence. Our current results are synthetic, so the demo shows the approach rather than production accuracy.

## 2 minutes

APP Shield explores a gap in transaction-focused detection: a payment can look ordinary while a genuine user is being pressured or impersonated. The simulator first analyzes transaction, recipient, and timestamp-bounded graph evidence. When useful, it asks for structured context and optional conversation text, then evaluates scam scenario and manipulation signals. The backend normalizes and deduplicates evidence, includes protective signals, and produces risk, confidence, reason codes, a decision, and an intervention. Every demo stays local and simulated. Day 9 adds delayed trusted labels, immutable prediction-time snapshots, audit history, monitoring, and guarded challenger workflows. In a 400-row chronological synthetic test, registered fusion achieved precision 0.889, recall 0.485, and PR-AUC 0.714. A transaction-plus-recipient ablation had recall 0.636 and PR-AUC 0.769, so we do not claim the broad system beats that measured baseline. The strongest demonstration is qualitative: the small investment pressure case gains contextual risk while a large established-merchant purchase is allowed. Linked real outcomes are the next research requirement.

## 5-minute technical outline

1. **Problem and threat model:** the user/device can be genuine while social engineering drives authorization.
2. **Evidence:** point-in-time transaction, recipient, and graph features plus optional structured context and bounded conversation.
3. **NLP and scenario layer:** existing rules and optional trained text components identify scenario/manipulation evidence; absent text stays absent.
4. **Fusion and policy:** evidence is normalized/deduplicated; risk and confidence remain separate; backend returns reasons and proportionate interventions.
5. **Feedback lifecycle:** user actions are not labels; final labels record source/confidence/time; snapshots are immutable and events hash chained.
6. **Evaluation:** chronological split, validation-only threshold selection, common holdout, ablations, adversarial message probe, and illustrative costs.
7. **Results:** report the measured synthetic figures and the fact that broader modalities are not linked to the supervised holdout.
8. **Demo:** run government impersonation, large merchant purchase, small investment pressure, mule-network, and family emergency cases.
9. **Limitations:** synthetic data, sparse test positives, no real outcome study, no production integration, and no claim of calibrated live risk.

## Presentation outline (8–10 slides)

1. APP Shield and research question
2. Genuine user, genuine device, manipulated payment
3. Why amount/device checks alone can miss the story
4. Evidence-to-intervention architecture
5. Context and manipulation signals with privacy boundaries
6. Recipient graph and temporal safety
7. Live simulator demonstration
8. Measured baseline and ablation table
9. Limitations, data governance, and next validation steps
10. Conclusion: test context-aware interventions against real, consented outcomes

## Resume bullets

- Built a local pre-payment authorized-scam research simulator with FastAPI and React, combining transaction, recipient, graph, context, scenario, and psychology evidence with explainable interventions.
- Added timestamp-bounded features, delayed-label provenance, immutable prediction snapshots, hash-linked audit events, aggregate drift/calibration monitoring, and guarded challenger evaluation.
- Evaluated on a chronological synthetic holdout (400 rows, 33 positives); registered fusion measured precision 0.889, recall 0.485, and PR-AUC 0.714, while documenting that additional modalities lack linked labels.

## Interview explanation

The 30-second pitch above introduces the problem. The 2-minute pitch explains the architecture and measured result. For a deeper discussion, use the technical outline and be explicit that the current dataset is synthetic and the measured fusion profile covers transaction/recipient features rather than every live evidence modality.
