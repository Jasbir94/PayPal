# APP Shield — Day 4 implementation


Implemented: all ten manipulation labels; weighted English/Hinglish rules; hard-negative suppression; a 6,000-message multi-label corpus; TF-IDF + OneVsRest logistic regression; validation-only per-label thresholds; startup-cached inference; independent psychology analysis; combination-based scoring; scenario alignment; context overlap adjustment; and integration into the contextual risk API. Graph/mule-network intelligence is still pending.

The complete source, scoring method, evaluation, commands and verified request/response are in [DAY4_IMPLEMENTATION.md](DAY4_IMPLEMENTATION.md).

### Generate, train, evaluate, test and run

Run from the app-shield project root with the existing Python 3.12 environment and backend requirements:

~~~powershell
.\.venv\Scripts\python.exe -m scripts.generate_psychology_messages
.\.venv\Scripts\python.exe -m ml.psychology.train
.\.venv\Scripts\python.exe -m ml.psychology.evaluate
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
~~~

In another terminal, run the live smoke checks:

~~~powershell
.\.venv\Scripts\python.exe -m scripts.smoke_psychology_api
~~~

Existing Day 2/3 artifacts and account data are required for contextual payment scoring; the text-only endpoint falls back to rules if its psychology model is missing. Train/evaluate commands never run during an API request. The label order comes from ml/psychology/labels.json; model and threshold metadata are checked at startup. Saved files are psychology_pipeline.pkl, psychology_thresholds.json and psychology_pipeline.metadata.json under saved_models/.

### API and scoring contract

POST /api/v1/analyze/psychology accepts {"message": "..."} and returns psychology_risk, all ten scores, detected_techniques, reason_codes, rule_scores, raw ml_probabilities, thresholds and availability flags. Empty/missing text returns zero evidence; non-string inputs, unknown fields and messages over 4,000 characters return 422. Scores are 0–1; risk is 0–100.

Hybrid scores take the maximum of rule evidence and raw ML outputs, preserving each source separately. Explicit benign constructions cap the corresponding hybrid label at 0.15 when that label has no positive rule evidence elsewhere in the message. Suppression is sentence-scoped. Repetition of the same pattern code does not amplify evidence; distinct codes accumulate as 1 - product(1 - weight). These are evidence scores, not calibrated probabilities. Individual terms such as bank/RBI do not activate authority rules.

Psychology risk = 40 × strongest active score + min(24, 8 × additional active technique count) + strongest supported combination bonus, clamped to 100. The bonuses are 35 for authority/fear/urgency and reward/scarcity/urgency, 30 for trust/commitment/secrecy, and 15 for trust/emotional_pressure. Combination bonuses require rule evidence >= 0.60 for every constituent in the hybrid service. ML-only evidence is capped at 45. This conservative guard reflects the baseline's poor unseen-phrase recall; it is not a learned or production-calibrated risk model.

Scenario alignment averages active scores for a scenario's expected techniques, counting absent techniques as zero. An unmapped scenario yields zero alignment. This neither adds labels nor reduces risk when alignment is low.

Contextual overlap uses only structured flags explicitly true: authority, fear, urgency, reward and secrecy. Discount factor = 1 - 0.5 × (overlapping active score sum / all active score sum). This discounts the psychology contribution by at most 50%; raw psychology risk and overlapping labels remain visible. The adjustment is a heuristic, not proof of independent evidence, and does not fully remove scenario/context correlations.

POST /api/v1/risk/contextual adds psychology, scenario_psychology_alignment, psychology_overlap_adjustment, extended_risk and extended_risk_level. Day 4 extended_risk = 0.20 × transaction + 0.25 × recipient + 0.20 × context + 0.15 × scenario + 0.20 × overlap-adjusted psychology. Missing text retains the old Day 3 score rather than diluting it; missing structured context retains the existing Day 2 floor.

For backward compatibility, extended_preliminary_risk and risk_level retain the Day 3 score and classification. Read extended_risk together with extended_risk_level for Day 4 results; the two classifications can differ. The preliminary endpoint's numeric fields and behavior are unchanged. All weights and caps are temporary MVP choices; none of these scores is a final fraud probability.

### Dataset and measured evaluation

The corpus contains 3,000 English and 3,000 Hinglish records: 1,360 neutral, 1,713 single-label and 2,927 multi-label messages. It uses 120 authored source phrases, varied combinations, payment amounts and framing. 6,000 synthetic variants do not imply 6,000 independent narratives. Train/validation/test contain 4,200/900/900 rows (70/15/15). Normalized duplicate text and source-phrase overlap across splits are both zero. Languages are balanced, and every label has positives and negatives in each split. Perfect multi-label stratification is not used: authored co-labels and isolated source families produce prevalence differences, especially trust.

Vectorization fits on training text only. IDs, provenance, split fields and target indicators are excluded from input features. Per-label thresholds maximize validation F1 over 0.30/0.40/0.50/0.60/0.70; ties prefer recall, then proximity to 0.50. No test-set threshold tuning was performed.

Validation micro F1: 0.537. Test micro precision/recall/F1: 0.947 / 0.169 / 0.287. Test macro precision/recall/F1: 0.566 / 0.169 / 0.245. Hamming loss: 0.1281; macro average precision: 0.727. English test micro F1: 0.206; Hinglish: 0.367. These metrics evaluate the text model, not the hybrid rules or the complete fraud engine.

| Technique | Threshold | Precision | Recall | F1 | Average precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| authority | 0.30 | 1.000 | 0.226 | 0.369 | 0.999 |
| fear | 0.30 | 1.000 | 0.030 | 0.059 | 0.523 |
| urgency | 0.40 | 0.000 | 0.000 | 0.000 | 0.322 |
| scarcity | 0.50 | 0.000 | 0.000 | 0.000 | 0.823 |
| trust | 0.30 | 0.818 | 0.151 | 0.255 | 0.543 |
| reward | 0.30 | 0.952 | 0.437 | 0.599 | 0.921 |
| social_proof | 0.50 | 0.000 | 0.000 | 0.000 | 0.770 |
| secrecy | 0.30 | 1.000 | 0.457 | 0.627 | 0.829 |
| commitment | 0.30 | 0.000 | 0.000 | 0.000 | 0.681 |
| emotional_pressure | 0.30 | 0.895 | 0.392 | 0.545 | 0.862 |

The baseline is inadequate as a standalone general manipulation detector. Urgency, scarcity, social_proof and commitment have zero test recall at the validation-selected thresholds; fear also has very low recall. Held-out source phrases use different wording from the small training phrase bank, and longer multi-technique messages dilute known TF-IDF evidence. Good ranking/AP for some classes does not fix thresholded recall. Error analysis shows trust-language messages falsely activating reward/emotional_pressure, and mixed Hinglish narratives losing several true labels. No transformer experiment or repeated test-driven tuning was introduced.

Reports in data/processed/day4/ contain full per-label precision/recall/F1/AP, default-0.5 comparisons, threshold grids, language slices, top terms, dataset quality and error_review.json. Error review preserves 25 false-negative messages and every available false-positive message: 11 test plus 4 clearly marked validation examples, for 15 total; the fitted training set provided no additional false-positive messages. Fewer than the requested approximate 20–30 false-positive examples exist. True labels, predicted labels, error labels, raw probabilities and source partitions are included; no errors were fabricated to meet a count. Validation supplements are review material, not test performance evidence.

### Verification

All 194 tests pass across Days 1–4, including the original 138 tests. One existing upstream Starlette TestClient deprecation warning remains. Fifteen live HTTP examples verify English/Hinglish techniques, legitimate counterexamples, contextual integration, missing-text retention and Day 2 compatibility. Full live requests/responses are in data/processed/day4/psychology_api_examples.json.

The Cyber Crime/Aadhaar/payment/arrest/secrecy example detects authority, fear, urgency and secrecy. With the seeded payment/account artifacts and explicit structured context it returns psychology risk 98.74, scenario government_impersonation, alignment 0.875067, overlap-adjusted psychology 49.37 and extended risk 81.96 (CRITICAL). The legacy Day 3 score remains 90.32 (CRITICAL). Inspect the guide for the exact request; example placeholder account IDs and timestamps from the brief should be replaced with valid seeded IDs and timezone-aware timestamps.

Synthetic performance does not establish real-world accuracy. Rules are finite constructions and can miss paraphrases, indirect coercion, code switching and long-distance context. Negation, quotation and sentence splitting can be misleading. Authority language does not authenticate an institution; emotional appeals do not establish fraud. No graph detection, frontend, transformer, production deployment or automatic payment blocking was introduced.

## Exact verified full request and response

Request:

~~~json
{
  "transaction": {
    "sender_id": "A0001",
    "receiver_id": "A1006",
    "amount": 85000,
    "timestamp": "2026-01-30T23:31:50+00:00",
    "device_id": "D0001",
    "payment_type": "bank_transfer"
  },
  "context": {
    "payment_reason": "government",
    "contacted_by_unknown_person": true,
    "contact_channel": "phone",
    "claimed_authority": true,
    "authority_type": "police",
    "urgent_payment_requested": true,
    "threatened_consequences": true,
    "requested_secrecy": true,
    "fund_transfer_requested": true
  },
  "message": "I am from Cyber Crime. Your Aadhaar is involved in money laundering. Transfer 80000 immediately or you will be arrested. Do not tell anyone."
}
~~~

Response:

~~~json
{
  "transaction_risk": {
    "score": 91.24,
    "ml_probability": 0.954067,
    "rule_score": 85,
    "reasons": [
      "amount_much_higher_than_normal",
      "first_time_recipient",
      "amount_above_recent_average",
      "transaction_model_elevated_risk"
    ],
    "evidence": {
      "amount": 85000,
      "sender_average_amount": 2233.158,
      "amount_ratio": 38.06268969772851,
      "first_time_recipient": 1,
      "transaction_hour": 23,
      "device_changed": 0,
      "transactions_last_1h": 0,
      "transactions_last_24h": 0,
      "amount_vs_recent_average": 38.06268969772851,
      "amount_deviation": 37.06268969772851,
      "recipient_seen_before": 0,
      "outside_usual_hours": 1,
      "history_count": 5,
      "baseline_available": 1
    }
  },
  "recipient_risk": {
    "score": 77.97,
    "ml_probability": 0.999536,
    "rule_score": 45,
    "reasons": [
      "high_outgoing_ratio",
      "multiple_prior_fraud_reports",
      "recipient_model_elevated_risk"
    ],
    "evidence": {
      "account_age_days": 33,
      "incoming_transactions_1h": 0,
      "incoming_transactions_24h": 0,
      "unique_senders_1h": 0,
      "unique_senders_24h": 0,
      "incoming_amount_24h": 0,
      "outgoing_amount_24h": 0,
      "outgoing_ratio": 0.9060308797089864,
      "observed_outgoing_ratio": 0,
      "fraud_report_count": 2,
      "transaction_velocity": 0,
      "sender_diversity": 0,
      "average_incoming_amount": 0,
      "median_incoming_amount": 0,
      "inflow_outflow_imbalance": 0,
      "average_holding_minutes": 316.00930004987663
    }
  },
  "context_risk": {
    "score": 100,
    "reasons": [
      "unknown_contact",
      "authority_claim",
      "urgent_payment_request",
      "threatened_consequences",
      "secrecy_request",
      "fund_transfer_request",
      "authority_threat_urgency_combination"
    ],
    "evidence": {
      "unknown_contact": true,
      "authority_claim": true,
      "urgent_payment_request": true,
      "threatened_consequences": true,
      "secrecy_request": true,
      "fund_transfer_request": true,
      "authority_threat_urgency_combination": true
    },
    "context_available": true
  },
  "scenario": {
    "type": "government_impersonation",
    "confidence": 0.874664,
    "confidence_kind": "structured_and_text_evidence",
    "top_scenarios": [
      {
        "scenario": "government_impersonation",
        "score": 0.874664
      },
      {
        "scenario": "normal_or_unknown",
        "score": 0.011496
      },
      {
        "scenario": "family_emergency_scam",
        "score": 0.00846
      }
    ],
    "reason_codes": [
      "authority_claim",
      "government_impersonation_pattern",
      "crime_or_legal_threat",
      "text_classifier_evidence"
    ],
    "evidence": {
      "structured_scenario": "government_impersonation",
      "structured_strength": 0.9,
      "text_scenario": "government_impersonation",
      "text_support_terms": [
        "money",
        "money laundering",
        "laundering",
        "aadhaar",
        "crime"
      ],
      "message_available": true,
      "text_model_available": true
    }
  },
  "scenario_risk": {
    "score": 95.61,
    "reasons": [
      "government_impersonation_context_supported"
    ],
    "evidence": {
      "matching_structured_strength": 0.9,
      "context_score": 100
    },
    "context_available": null
  },
  "psychology": {
    "psychology_risk": 98.74,
    "scores": {
      "authority": 0.84,
      "fear": 0.9552,
      "urgency": 0.83,
      "scarcity": 0.1981795697899788,
      "trust": 0.15490245323942717,
      "reward": 0.08535103865841927,
      "social_proof": 0.042980629495332046,
      "secrecy": 0.9935509818176811,
      "commitment": 0.15568964172767663,
      "emotional_pressure": 0.06266771139574302
    },
    "rule_scores": {
      "authority": 0.84,
      "fear": 0.9552,
      "urgency": 0.83,
      "scarcity": 0,
      "trust": 0,
      "reward": 0,
      "social_proof": 0,
      "secrecy": 0.88,
      "commitment": 0,
      "emotional_pressure": 0
    },
    "ml_probabilities": {
      "authority": 0.1041955520890529,
      "fear": 0.864909332930434,
      "urgency": 0.5852420784900579,
      "scarcity": 0.1981795697899788,
      "trust": 0.15490245323942717,
      "reward": 0.08535103865841927,
      "social_proof": 0.042980629495332046,
      "secrecy": 0.9935509818176811,
      "commitment": 0.15568964172767663,
      "emotional_pressure": 0.06266771139574302
    },
    "thresholds": {
      "authority": 0.3,
      "fear": 0.3,
      "urgency": 0.4,
      "scarcity": 0.5,
      "trust": 0.3,
      "reward": 0.3,
      "social_proof": 0.5,
      "secrecy": 0.3,
      "commitment": 0.3,
      "emotional_pressure": 0.3
    },
    "detected_techniques": [
      "authority",
      "fear",
      "urgency",
      "secrecy"
    ],
    "reason_codes": [
      "authority_claim_detected",
      "identity_crime_threat",
      "legal_threat_detected",
      "urgent_action_language",
      "secrecy_request_detected",
      "manipulation_evidence_detected",
      "authority_fear_urgency_combination"
    ],
    "evidence": {
      "rule_patterns": {
        "authority": {
          "pattern_codes": [
            "authority_claim_detected"
          ],
          "distinct_pattern_count": 1
        },
        "fear": {
          "pattern_codes": [
            "identity_crime_threat",
            "legal_threat_detected"
          ],
          "distinct_pattern_count": 2
        },
        "urgency": {
          "pattern_codes": [
            "urgent_action_language"
          ],
          "distinct_pattern_count": 1
        },
        "secrecy": {
          "pattern_codes": [
            "secrecy_request_detected"
          ],
          "distinct_pattern_count": 1
        }
      },
      "benign_suppressed_techniques": [],
      "combination_requires_strong_rule_support": true
    },
    "model_available": true,
    "message_available": true,
    "scores_kind": "hybrid_evidence_not_calibrated_probabilities"
  },
  "scenario_psychology_alignment": 0.875067,
  "psychology_overlap_adjustment": {
    "adjusted_psychology_risk": 49.37,
    "discount_factor": 0.5,
    "overlapping_techniques": [
      "authority",
      "fear",
      "urgency",
      "secrecy"
    ],
    "reason_code": "context_psychology_overlap_discounted"
  },
  "extended_risk": 81.96,
  "extended_risk_level": "CRITICAL",
  "extended_preliminary_risk": 90.32,
  "risk_level": "CRITICAL",
  "reason_codes": [
    "amount_much_higher_than_normal",
    "first_time_recipient",
    "amount_above_recent_average",
    "transaction_model_elevated_risk",
    "high_outgoing_ratio",
    "multiple_prior_fraud_reports",
    "recipient_model_elevated_risk",
    "unknown_contact",
    "authority_claim",
    "urgent_payment_request",
    "threatened_consequences",
    "secrecy_request",
    "fund_transfer_request",
    "authority_threat_urgency_combination",
    "government_impersonation_pattern",
    "crime_or_legal_threat",
    "text_classifier_evidence",
    "government_impersonation_context_supported",
    "authority_claim_detected",
    "identity_crime_threat",
    "legal_threat_detected",
    "urgent_action_language",
    "secrecy_request_detected",
    "manipulation_evidence_detected",
    "authority_fear_urgency_combination",
    "context_psychology_overlap_discounted"
  ]
}
~~~

## Complete Day 4 source additions and modified modules

The existing requirements already include pandas, numpy, scikit-learn, scipy, joblib, FastAPI and pytest. No extra dependency was required. Scenario artifacts were retained; the shared TF-IDF factory keeps their previous preprocessing settings. Graph modules remain placeholders.

### ml/psychology/labels.json

~~~json
[
  "authority",
  "fear",
  "urgency",
  "scarcity",
  "trust",
  "reward",
  "social_proof",
  "secrecy",
  "commitment",
  "emotional_pressure"
]
~~~

### ml/psychology/__init__.py

~~~python

~~~

### backend/app/config/psychology_config.py

~~~python
"""Day 4 evidence scoring and overlap controls; no calibrated fraud probability."""
from backend.app.config.risk_config import PROJECT_ROOT, MODEL_DIR

PSYCHOLOGY_LABELS_PATH = PROJECT_ROOT / 'ml' / 'psychology' / 'labels.json'
PSYCHOLOGY_DATA_PATH = PROJECT_ROOT / 'data' / 'synthetic' / 'psychology_messages.csv'
PSYCHOLOGY_MODEL_PATH = MODEL_DIR / 'psychology_pipeline.pkl'
PSYCHOLOGY_THRESHOLDS_PATH = MODEL_DIR / 'psychology_thresholds.json'
PSYCHOLOGY_REPORT_DIR = PROJECT_ROOT / 'data' / 'processed' / 'day4'
SEED = 42
DEFAULT_THRESHOLD = .5
THRESHOLD_GRID = (.30, .40, .50, .60, .70)
STRONG_RULE_THRESHOLD = .60
BENIGN_SCORE_CAP = .15
RISK_STRONGEST_WEIGHT = 40
RISK_ADDITIONAL_TECHNIQUE_POINTS = 8
RISK_COUNT_BONUS_CAP = 24
ML_ONLY_RISK_CAP = 45
DAY4_WEIGHTS = {'transaction': .20, 'recipient': .25, 'context': .20, 'scenario': .15, 'psychology': .20}
MAX_OVERLAP_DISCOUNT = .50
HIGH_RISK_COMBINATIONS = {
    'authority_fear_urgency_combination': (('authority', 'fear', 'urgency'), 35),
    'reward_scarcity_urgency_combination': (('reward', 'scarcity', 'urgency'), 35),
    'trust_commitment_secrecy_combination': (('trust', 'commitment', 'secrecy'), 30),
    'relationship_emotional_pressure_combination': (('trust', 'emotional_pressure'), 15),
}
SCENARIO_TECHNIQUES = {
    'government_impersonation': ('authority', 'fear', 'urgency'),
    'bank_impersonation': ('authority', 'fear', 'urgency'),
    'investment_scam': ('reward', 'scarcity', 'social_proof', 'urgency'),
    'romance_scam': ('trust', 'commitment', 'emotional_pressure'),
    'fake_job_scam': ('authority', 'reward', 'urgency'),
    'tech_support_scam': ('authority', 'fear', 'trust'),
    'family_emergency_scam': ('emotional_pressure', 'urgency', 'secrecy'),
    'marketplace_scam': ('trust', 'urgency'),
    'loan_scam': ('reward', 'urgency', 'commitment'),
    'refund_scam': ('trust', 'urgency', 'commitment'),
}
CONTEXT_OVERLAP_FIELDS = {
    'authority': ('claimed_authority',), 'fear': ('threatened_consequences',),
    'urgency': ('urgent_payment_requested',), 'reward': ('promised_profit', 'guaranteed_returns_promised'),
    'secrecy': ('requested_secrecy',),
}
~~~

### backend/app/utils/psychology_labels.py

~~~python
"""Read the multi-label taxonomy once from its JSON source of truth."""
import json
from functools import lru_cache
from backend.app.config.psychology_config import PSYCHOLOGY_LABELS_PATH


@lru_cache(maxsize=1)
def get_psychology_labels() -> tuple[str, ...]:
    labels = json.loads(PSYCHOLOGY_LABELS_PATH.read_text(encoding='utf-8'))
    if not isinstance(labels, list) or len(labels) != 10 or len(labels) != len(set(labels)):
        raise ValueError('Psychology taxonomy must contain ten unique labels')
    return tuple(labels)


def validate_technique(label: str) -> str:
    if label not in get_psychology_labels():
        raise ValueError(f'Unknown manipulation technique: {label}')
    return label
~~~

### backend/app/features/text_features.py

~~~python
"""Shared light text normalization and TF-IDF construction for both NLP modules."""
from sklearn.feature_extraction.text import TfidfVectorizer


def normalize_text(text: str) -> str:
    """Normalize case and spacing without removing negation or language cues."""
    return ' '.join(text.replace('’', "'").replace('‘', "'").casefold().split())


def make_text_vectorizer(**overrides) -> TfidfVectorizer:
    """Keep the established Day 3 unigram/bigram preprocessing configuration."""
    options = dict(ngram_range=(1, 2), min_df=2, max_features=18000,
                   sublinear_tf=True, strip_accents='unicode')
    options.update(overrides)
    return TfidfVectorizer(**options)
~~~

### ml/scenario/train.py

~~~python
"""Compare TF-IDF logistic regression and linear SVM on unseen template families."""
import hashlib
import json
import joblib
import pandas as pd
import sklearn
from backend.app.features.text_features import make_text_vectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from backend.app.config.context_config import SCENARIO_DATA_PATH, SCENARIO_MODEL_PATH, SCENARIO_REPORT_DIR, SCENARIO_SEED
from backend.app.utils.scenario_labels import get_scenario_labels
from ml.scenario.data_quality import validate_messages
from ml.scenario.metrics import evaluate_pipeline


def make_pipeline(classifier) -> Pipeline:
    return Pipeline([('tfidf', make_text_vectorizer()), ('classifier', classifier)])


def train() -> dict:
    data = pd.read_csv(SCENARIO_DATA_PATH)
    quality = validate_messages(data)
    print(f"Validated {len(data)} unique messages, {quality['template_families']} disjoint template families")
    train_data, validation, test = (data[data.split == role] for role in ('train', 'validation', 'test'))
    models = {
        'tfidf_logistic_regression': make_pipeline(LogisticRegression(C=4, max_iter=2000,
            class_weight='balanced', random_state=SCENARIO_SEED)),
        'tfidf_linear_svm': make_pipeline(LinearSVC(C=1, dual='auto', class_weight='balanced', random_state=SCENARIO_SEED)),
    }
    reports = {}
    for name, model in models.items():
        # Inputs are text only. No labels, source-template identifiers or split flags enter the pipeline.
        model.fit(train_data.text, train_data.scenario_label)
        reports[name] = {'validation': evaluate_pipeline(model, validation), 'test': evaluate_pipeline(model, test)}
    selected = max(reports, key=lambda name: reports[name]['validation']['macro_f1'])
    classifier = models[selected].named_steps['classifier']
    metadata = {'selected_model': selected, 'selected_by': 'validation macro F1', 'seed': SCENARIO_SEED,
        'sklearn_version': sklearn.__version__, 'labels': list(get_scenario_labels()), 'input_features': ['text'],
        'split_strategy': '60/20/20 class/language balanced; template families stay in one split',
        'confidence_kind': 'uncalibrated logistic output' if hasattr(classifier, 'predict_proba') else 'softmax of SVM margins; heuristic evidence',
        'dataset_sha256': hashlib.sha256(SCENARIO_DATA_PATH.read_bytes()).hexdigest(),
        'limitations': 'Synthetic narratives, only 110 source families. No real-world performance or calibrated fraud probability.'}
    SCENARIO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'kind': 'scenario', 'pipeline': models[selected], 'metadata': metadata}, SCENARIO_MODEL_PATH)
    SCENARIO_MODEL_PATH.with_suffix('.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    report = {'metadata': metadata, 'models': reports, 'dataset_quality': quality}
    (SCENARIO_REPORT_DIR / 'scenario_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (SCENARIO_REPORT_DIR / 'dataset_quality.json').write_text(json.dumps(quality, indent=2), encoding='utf-8')
    features = models[selected].named_steps['tfidf'].get_feature_names_out()
    coefficients = classifier.coef_
    importance = {label: [str(features[index]) for index in coefficients[i].argsort()[-12:][::-1]]
                  for i, label in enumerate(classifier.classes_)}
    (SCENARIO_REPORT_DIR / 'top_class_terms.json').write_text(json.dumps(importance, indent=2), encoding='utf-8')
    for name, metrics in reports.items():
        print(f"{name}: validation macro F1={metrics['validation']['macro_f1']:.3f}, test macro F1={metrics['test']['macro_f1']:.3f}")
    print(f'Selected {selected} by validation results; saved {SCENARIO_MODEL_PATH}')
    return report


if __name__ == '__main__':
    train()
~~~

### scripts/generate_scam_messages.py

~~~python
"""Reproducible synthetic narrative corpus with family-disjoint, class-balanced splits."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from backend.app.config.context_config import SCENARIO_SEED, SAMPLES_PER_TEMPLATE, SCENARIO_DATA_PATH
from backend.app.utils.scenario_labels import get_scenario_labels
from scripts.scam_templates import TEMPLATES
from backend.app.features.text_features import normalize_text

NAMES = ('Sharma', 'Patel', 'Khan', 'Mehta', 'Rao', 'Roy', 'Kapoor', 'Verma')
CHANNELS = ('phone', 'SMS', 'WhatsApp', 'Telegram', 'email', 'social media')
DEADLINES = ('immediately', 'within an hour', 'before tonight', 'today', 'abhi', 'aaj hi')
PREFIXES = ('', 'This is what they told me: ', 'Please help me understand this message. ', 'Mujhe ye message mila: ')
SUFFIXES = ('', ' Is this the right way to pay?', ' They keep asking me to respond.', ' Kya mujhe ye payment karna chahiye?')


def normalized_text(text: str) -> str:
    return normalize_text(text)


def generate_messages(seed: int = SCENARIO_SEED, samples_per_template: int = SAMPLES_PER_TEMPLATE) -> pd.DataFrame:
    if samples_per_template < 1:
        raise ValueError('samples_per_template must be positive')
    labels = get_scenario_labels()
    if set(TEMPLATES) != set(labels):
        raise ValueError('Template taxonomy does not match labels.json')
    rng = np.random.default_rng(seed)
    rows = []
    for label in labels:
        templates = TEMPLATES[label]
        if len(templates) != 10:
            raise ValueError('Each class needs five English and five Hinglish narrative families')
        roles = {}
        for offset in (0, 5):
            groups = rng.permutation(np.arange(offset, offset + 5))
            for index, group in enumerate(groups):
                roles[int(group)] = 'train' if index < 3 else 'validation' if index == 3 else 'test'
        for template_index, template in enumerate(templates):
            for _ in range(samples_per_template):
                amount = f'₹{int(rng.integers(10, 1500)) * 100:,}'
                text = template.format(amount=amount, name=rng.choice(NAMES), channel=rng.choice(CHANNELS),
                                       deadline=rng.choice(DEADLINES))
                text = str(rng.choice(PREFIXES)) + text + str(rng.choice(SUFFIXES))
                style = rng.random()
                if style < .04:
                    text = text.upper()
                elif style < .12:
                    text = text.lower()
                elif style < .18:
                    text = text.replace('please', 'pls').replace('immediately', 'immediatly').replace('account', 'acount')
                rows.append({'message_id': f'MSG{len(rows):06d}', 'text': text, 'scenario_label': label,
                             'template_id': f'{label}:{template_index}',
                             'language': 'English' if template_index < 5 else 'Hinglish',
                             'split': roles[template_index]})
    data = pd.DataFrame(rows)
    data['_normalized'] = data.text.map(normalized_text)
    data = data.drop_duplicates('_normalized').drop(columns='_normalized')
    return data.sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=SCENARIO_SEED)
    parser.add_argument('--samples-per-template', type=int, default=SAMPLES_PER_TEMPLATE)
    parser.add_argument('--output', type=Path, default=SCENARIO_DATA_PATH)
    args = parser.parse_args()
    data = generate_messages(args.seed, args.samples_per_template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output, index=False)
    print(f'Saved {len(data)} unique messages to {args.output}')
    print(data.groupby(['scenario_label', 'split']).size().unstack().to_string())


if __name__ == '__main__':
    main()
~~~

### backend/app/rules/psychology_patterns.py

~~~python
"""Weighted coercive constructions, rather than isolated institution or payment words."""
# (reason code, regex, evidence weight). Patterns operate on normalized sentences.
PATTERNS = {
    'authority': [
        ('authority_claim_detected', r"\b(?:i am|i'm|we are|calling from|speaking from|i represent)\b.{0,55}\b(?:police|rbi|government|cyber\s*crime|bank officer|bank|court|tax department|company support|employer|chief executive)\b", .84),
        ('authority_claim_detected', r'\b(?:main|hum)\b.{0,35}\b(?:bank|rbi|police|cyber\s*crime|sarkar|court)\b.{0,35}\b(?:bol raha|bol rahi|se hu|se hoon|se hain)\b', .86),
        ('official_investigation_claim', r'\b(?:confidential|official)\b.{0,25}\b(?:police|government|cyber\s*crime)\b.{0,20}\binvestigation\b', .80),
        ('authority_role_claim', r'\b(?:as your|your assigned|this is|main)\b.{0,25}\b(?:bank officer|police officer|tax officer|support officer|senior executive|officer)\b', .75),
    ],
    'fear': [
        ('legal_threat_detected', r'\b(?:you|your|aap|aapka|tum|tumhara)\b.{0,70}\b(?:arrested|arrest|frozen|freeze|blocked|legal action|police case|penalty|jail|custody)\b', .84),
        ('conditional_threat_detected', r'\b(?:or|otherwise|warna|nahi to)\b.{0,35}\b(?:arrest|jail|freeze|frozen|blocked|block|legal action|penalty|case)\b', .82),
        ('legal_threat_detected', r'\blegal action\b.{0,18}\b(?:will be taken|against you|hoga|hogi)\b', .78),
        ('identity_crime_threat', r'\byour\b.{0,20}\b(?:aadhaar|identity)\b.{0,45}\b(?:money laundering|illegal|criminal)\b', .72),
    ],
    'urgency': [
        ('urgent_action_language', r'\b(?:transfer|pay|send|invest|deposit|payment karo|bhejo)\b.{0,40}\b(?:now|immediately|right now|today|abhi|aaj)\b', .83),
        ('urgent_action_language', r'\b(?:immediately|right now|abhi|aaj hi)\b.{0,35}\b(?:transfer|pay|send|invest|payment|bhejo|karo)\b', .83),
        ('short_payment_deadline', r'\b(?:within|sirf)\s+\d+\s+(?:minutes|min|minute)\b|\b(?:do not delay|act now|today only)\b', .76),
        ('same_day_expiry_pressure', r'\b(?:aaj|today|tonight)\b.{0,18}\b(?:last|only|expires|akhri)\b|\b(?:offer|opportunity)\b.{0,15}\bexpires (?:today|tonight)\b', .77),
    ],
    'scarcity': [
        ('limited_availability_claim', r'\b(?:only|sirf)\s+(?:\d+|one|two|few|ek|do)\s+(?:slots?|seats?|places?)\b|\b(?:last|limited|akhri)\s+(?:slot|slots|seat|opportunity|investment opportunity|chance)\b', .84),
        ('expiring_offer_claim', r'\b(?:offer|opportunity|allocation)\b.{0,20}\b(?:expires|limited|last)\b', .76),
    ],
    'trust': [
        ('credibility_appeal', r'\b(?:you can trust me|trust me|i am helping you|i have handled many cases|bharosa karo|mujh par bharosa|meri baat mano)\b', .79),
        ('relationship_trust_appeal', r'\bif you\b.{0,15}\bcare about me\b|\b(?:agar|tum)\b.{0,25}\b(?:pyar|pyaar|care)\b', .75),
        ('relationship_trust_appeal', r'\b(?:we have been together|our relationship|apna rishta)\b.{0,35}\b(?:trust|help me|bharosa|madad)\b', .72),
    ],
    'reward': [
        ('guaranteed_gain_claim', r'\bguaranteed\s+(?:\d+\s*%?\s*)?(?:returns?|profits?|gains?|cashback)\b|\b(?:investment|return|profit)\s+guaranteed\b', .85),
        ('doubling_or_prize_claim', r'\b(?:double your (?:money|investment)|money will double|paise double|high profit|lottery prize|assured returns|pakka return|return milega)\b', .77),
        ('reward_payment_inducement', r'\b(?:cashback|bonus|lottery)\b.{0,30}\b(?:receive|claim|milega|win)\b', .72),
    ],
    'social_proof': [
        ('others_benefited_claim', r'\b(?:thousands|hundreds|many users|many members|everyone|sab log|hazaron|bahut log)\b.{0,65}\b(?:earned|profit|benefited|kamaya|kama rahe|return mila)\b', .84),
        ('peer_success_claim', r'\b(?:other members|your friends|dusre members|aapke dost)\b.{0,55}\b(?:successful|profits?|joined|earned|kamaya)\b', .74),
    ],
    'secrecy': [
        ('secrecy_request_detected', r"\b(?:do not|don't|dont|never)\s+(?:tell|contact|discuss|inform|share)\b.{0,55}\b(?:anyone|family|bank|police|friends|investigation)\b", .88),
        ('secrecy_request_detected', r'\b(?:kisi ko|family ko|bank ko|ghar par)\s+mat\s+(?:batana|batao|bolna)|\bye baat\b.{0,15}\bsecret\b', .88),
        ('confidential_investigation_pressure', r'\b(?:investigation|inquiry|case)\b.{0,20}\bconfidential\b|\bconfidential\b.{0,20}\binvestigation\b', .65),
    ],
    'commitment': [
        ('prior_payment_leverage', r"\b(?:already|pehle|you've already)\b.{0,35}\b(?:invested|paid|sent|jama|payment)\b.{0,100}\b(?:more|extra|unlock|withdrawal|aur|dobara)\b", .86),
        ('withdrawal_unlock_payment', r'\b(?:pay|send|deposit|payment)\b.{0,40}\b(?:more|extra|additional|aur)\b.{0,40}\b(?:unlock|withdrawal|release|nikalne)\b', .81),
    ],
    'emotional_pressure': [
        ('conditional_care_pressure', r'\bif you\b.{0,15}\bcare about me\b.{0,70}\b(?:send|pay|money|help)\b', .86),
        ('medical_emergency_money_appeal', r'\b(?:i|my family|mujhe|meri family)\b.{0,30}\b(?:urgently need|desperately need|emergency|hospital)\b.{0,60}\b(?:money|payment|paise|treatment)\b', .76),
        ('relationship_emotional_pressure', r'\b(?:agar|tum)\b.{0,25}\b(?:pyar|pyaar|care)\b.{0,55}\b(?:paise|bhejo|madad|send)\b', .84),
    ],
}
# Suppression is sentence-scoped and never overrides positive evidence elsewhere.
BENIGN_QUALIFIERS = {
    'authority': r'\b(?:announced|released|published|guidelines|new policy|statement.{0,25}available|news article)\b',
    'fear': r'\bmy (?:bank )?account is (?:frozen|blocked)\b|\bmera account freeze\b',
    'urgency': r'\b(?:if convenient|when convenient|no rush|not urgent|due tomorrow|koi jaldi nahi|jab suvidha|aaram se)\b',
    'reward': r'\b(?:no guaranteed|not guaranteed|returns are not|profit is not|koi guaranteed.{0,10}nahi)\b',
    'scarcity': r'\b(?:no limited|not limited|no shortage|ample places)\b',
    'trust': r'\b(?:i trust my|trusted existing|known recipient)\b',
    'social_proof': r'\b(?:survey results|news report|statistics published)\b',
    'secrecy': r'\b(?:not confidential|please tell your|do contact your)\b',
    'commitment': r'\b(?:scheduled instalment|regular installment|no extra payment)\b',
    'emotional_pressure': r'\b(?:no emergency|routine hospital bill|not an emergency)\b',
}
~~~

### backend/app/rules/psychology_rules.py

~~~python
"""Sentence-scoped weighted manipulation evidence with explicit hard-negative handling."""
import re
from backend.app.features.text_features import normalize_text
from backend.app.rules.psychology_patterns import PATTERNS, BENIGN_QUALIFIERS
from backend.app.utils.psychology_labels import get_psychology_labels

COMPILED = {label: [(code, re.compile(pattern), weight) for code, pattern, weight in patterns]
            for label, patterns in PATTERNS.items()}
BENIGN = {label: re.compile(pattern) for label, pattern in BENIGN_QUALIFIERS.items()}


def detect_psychology_rules(text: str | None) -> dict:
    labels = get_psychology_labels()
    if set(COMPILED) != set(labels):
        raise ValueError('Pattern taxonomy differs from psychology labels.json')
    scores = dict.fromkeys(labels, 0.0)
    reasons, evidence, suppressed = [], {}, []
    if not text or not text.strip():
        return {'scores': scores, 'reasons': ['message_unavailable'], 'evidence': {}, 'suppressed_techniques': []}
    sentences = [normalize_text(part) for part in re.split(r'(?<=[.!?])\s+|[;\n]+', text) if part.strip()]
    for label in labels:
        matches = {}
        for sentence in sentences:
            if BENIGN[label].search(sentence):
                suppressed.append(label)
                continue
            for code, pattern, weight in COMPILED[label]:
                match = pattern.search(sentence)
                if match:
                    # Count distinct patterns, not repeated copies of the same phrase.
                    matches[code] = max(weight, matches.get(code, 0))
        remaining = 1.0
        for code, weight in matches.items():
            remaining *= 1 - weight
            reasons.append(code)
        scores[label] = round(1 - remaining, 6)
        if matches:
            evidence[label] = {'pattern_codes': list(matches), 'distinct_pattern_count': len(matches)}
    suppressed = [label for label in dict.fromkeys(suppressed) if scores[label] == 0]
    return {'scores': scores, 'reasons': list(dict.fromkeys(reasons)) or ['no_rule_manipulation_evidence'],
            'evidence': evidence, 'suppressed_techniques': suppressed}
~~~

### scripts/psychology_templates.py

~~~python
"""Semantic phrase families: positives are authored independently of detector rules.

Five English and five Hinglish families per technique, plus neutral hard negatives.
Each (text, extra_labels) annotation names additional techniques expressed in that clause.
"""
TECHNIQUE_PHRASES = {
    'authority': [
        ('I am calling from the Cyber Crime Department and you must follow my instructions.', ()),
        ('This is officer {name} from the bank; I represent the official verification desk.', ()),
        ('As your assigned court officer, I require compliance with this investigation.', ()),
        ('The government has assigned me to inspect your identity; I speak on its behalf.', ()),
        ('I am your employer and senior executive, and this instruction comes from my office.', ()),
        ('Main RBI se bol raha hu aur ye official direction hai.', ()),
        ('Main police department se hu, meri instruction follow karni hogi.', ()),
        ('Bank officer {name} bol raha hu, official verification meri duty hai.', ()),
        ('Sarkari officer ke roop me mujhe aapki identity inquiry ka charge mila hai.', ()),
        ('Company support se main official representative hu aur case mujhe assign hua hai.', ()),
    ],
    'fear': [
        ('Your account will be frozen if you refuse this payment.', ()),
        ('You will be arrested if you do not send the requested funds.', ()),
        ('Legal action will be taken against you unless the transfer is completed.', ()),
        ('Refusing the deposit will leave your money blocked and expose you to a penalty.', ()),
        ('An arrest warrant will be issued in your name if you decline to pay.', ()),
        ('Payment nahi kiya to aapka account freeze ho jayega.', ()),
        ('Paise bhejo warna arrest aur jail ka case lagega.', ()),
        ('Transfer mana karoge to legal action hoga aur balance block rahega.', ()),
        ('Deposit refuse kiya to tumhare funds blocked honge aur penalty lagegi.', ()),
        ('Aap pay nahi karoge to warrant niklega aur custody me jana padega.', ()),
    ],
    'urgency': [
        ('Transfer {amount} immediately; there is no time to check this later.', ()),
        ('Pay right now and do not delay the transaction.', ()),
        ('You have within 10 minutes to send the amount.', ()),
        ('Act now; complete the deposit before you do anything else.', ()),
        ('Send the funds today, not after you have time to think.', ()),
        ('Abhi transfer karo, baad me sochne ka time nahi hai.', ()),
        ('Payment aaj hi karo aur bilkul delay mat karna.', ()),
        ('Sirf 10 minutes me {amount} bhejo, rukna allowed nahi hai.', ()),
        ('Pehle turant deposit karo, sawal baad me puchna.', ()),
        ('Isi waqt paise send karne hain, kal tak wait nahi kar sakte.', ()),
    ],
    'scarcity': [
        ('Only two slots remain in this private allocation.', ()),
        ('There is just one seat left for the offer.', ()),
        ('This is a limited opportunity with very few places remaining.', ()),
        ('The last investment slot is reserved for the next person who joins.', ()),
        ('Available places are almost gone and no further allocations will be opened.', ()),
        ('Sirf do slots bache hain is private allocation me.', ()),
        ('Is offer ki bas ek seat available reh gayi hai.', ()),
        ('Ye limited opportunity hai, bahut kam places baaki hain.', ()),
        ('Akhri chance next join karne wale ko milega.', ()),
        ('Allocation ke places lagbhag khatam hain, aur jagah nahi khulegi.', ()),
    ],
    'trust': [
        ('You can trust me; I am helping you handle this payment safely.', ()),
        ('I have handled many cases like yours, so trust my advice.', ()),
        ('We have built our relationship, so please rely on me with your money.', ()),
        ('I am on your side and only trying to help you, not hurt you.', ()),
        ('Believe me personally and stop doubting the account I gave you.', ()),
        ('Mujh par bharosa karo, main tumhari madad kar raha hu.', ()),
        ('Maine aise bahut cases handle kiye, meri baat mano.', ()),
        ('Apna rishta purana hai, paise ke mamle me meri madad par bharosa rakho.', ()),
        ('Main aapke side hu aur aapko bachane ke liye help kar raha.', ()),
        ('Meri personal baat pe yakeen karo aur diye account par doubt mat karo.', ()),
    ],
    'reward': [
        ('This plan guarantees a 30 percent return on your money.', ()),
        ('You will receive guaranteed returns without any investment loss.', ()),
        ('We promise to double your investment without risk.', ()),
        ('Pay {amount} and claim a lottery prize worth much more.', ()),
        ('You are assured a fixed high profit and special cashback from this deposit.', ()),
        ('Sir ye investment guaranteed hai aur pakka profit milega.', ()),
        ('Is plan me paise double honge, koi loss ka risk nahi hai.', ()),
        ('Guaranteed return milega, bas {amount} jama karna hai.', ()),
        ('Payment se lottery prize claim karo, amount se kai guna zyada milega.', ()),
        ('Fixed high profit aur cashback ka pakka wada hai is deposit par.', ()),
    ],
    'social_proof': [
        ('Thousands of users have already earned profits through this process.', ()),
        ('Other members are successful and have received payouts from the plan.', ()),
        ('Your friends already joined and earned using the same account.', ()),
        ('Hundreds of people benefited, and their screenshots prove it works.', ()),
        ('Everyone in our group has collected earnings from this method.', ()),
        ('Hazaron users ne is process se pehle hi profit kamaya hai.', ()),
        ('Dusre members successful hain aur unko payout mil chuka hai.', ()),
        ('Aapke dost isi account se join karke paise kama rahe hain.', ()),
        ('Bahut log benefited hain, unke screenshots dekho.', ()),
        ('Sab log group me is tarike se earning collect kar chuke hain.', ()),
    ],
    'secrecy': [
        ('Do not tell your bank or family about this payment.', ()),
        ("Don't discuss this instruction with anyone else.", ()),
        ('Keep this investigation confidential and do not share its details.', ()),
        ('Never contact the bank to confirm the transfer I requested.', ()),
        ('Please hide this arrangement from your friends and relatives.', ()),
        ('Kisi ko mat batana, ye baat hum dono ke beech rahe.', ()),
        ('Family ko mat batao aur bank ko contact mat karo.', ()),
        ('Ye investigation confidential hai, details share nahi karni.', ()),
        ('Transfer confirm karne ke liye bank ko mat phone karna.', ()),
        ('Ye arrangement friends aur relatives se chhupa kar rakhna.', ()),
    ],
    'commitment': [
        ("You've already invested {amount}; pay extra to unlock your withdrawal.", ()),
        ('You already paid the initial amount, so send more to finish the release.', ()),
        ('Continue the deposit you started by paying an additional amount to access the balance.', ()),
        ('The money you put in is waiting; another payment will unlock withdrawal.', ()),
        ('Having completed the first step, you must add funds before the earlier deposit is released.', ()),
        ('Pehle {amount} invested hai, withdrawal unlock karne ko aur pay karo.', ()),
        ('Initial payment de chuke ho, release finish karne ke liye extra bhejo.', ()),
        ('Jo deposit start kiya use complete karne ko aur amount jama karo.', ()),
        ('Purane paise waiting me hain, ek aur payment se withdrawal khulega.', ()),
        ('First step ho gaya, pehle deposit release se pehle dobara funds dalo.', ()),
    ],
    'emotional_pressure': [
        ('If you really care about me, please send money for my emergency.', ('trust',)),
        ('I desperately need money for hospital treatment and I am depending on you.', ()),
        ('Please do not let my family suffer; I need you to pay for this crisis.', ()),
        ('If our relationship matters to you, prove it by sending {amount}.', ('trust',)),
        ('My medical emergency is unbearable and only your payment can help me.', ()),
        ('Agar mujhse pyar hai to emergency ke liye paise bhejo.', ('trust',)),
        ('Mujhe hospital treatment ke liye urgently paise chahiye, tum par depend hu.', ('urgency',)),
        ('Meri family ko suffer mat hone do, crisis ke liye payment chahiye.', ()),
        ('Apna rishta important hai to {amount} bhejkar prove karo.', ('trust',)),
        ('Medical emergency bardasht nahi hoti, sirf tumhari payment madad karegi.', ()),
    ],
}
NEUTRAL_PHRASES = [
    'RBI announced a new policy today. This is an informational news update.',
    'Your bank statement for September is available for download.',
    'Please make the payment today if convenient; there is no rush.',
    'My bank account is frozen. I am visiting the branch to ask about its status.',
    'Your electricity bill is due tomorrow, as shown on the regular invoice.',
    'The hospital issued a routine hospital bill after the appointment; there is no emergency.',
    'Returns are not guaranteed for my registered investment; the decision is voluntary.',
    'I trust my known recipient and am making a scheduled instalment with no extra payment.',
    'Please tell your family and do contact your bank if you have doubts.',
    'The survey results and statistics published today describe user preferences, not a payment offer.',
    'RBI ne new payment guidelines release ki, ye sirf news update hai.',
    'September ka bank statement download ke liye available hai.',
    'Payment jab suvidha ho tab karna, koi jaldi nahi hai.',
    'Mera account freeze hai, branch me status puchne ja raha hu.',
    'Electricity bill kal due hai, regular invoice check kar raha hu.',
    'Appointment ka routine hospital bill mila, koi emergency nahi hai.',
    'Registered investment me guaranteed profit nahi hai, decision mera khud ka hai.',
    'Purane known recipient ko regular installment hai, extra payment nahi.',
    'Doubt ho to family ko batao aur apne bank se confirm karo.',
    'Aaj published survey me users ki choices hain, koi paisa offer nahi hai.',
]
~~~

### scripts/generate_psychology_messages.py

~~~python
"""Generate a 6,000-row multi-label corpus with disjoint phrase families."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from backend.app.config.psychology_config import SEED, PSYCHOLOGY_DATA_PATH
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.features.text_features import normalize_text
from scripts.psychology_templates import TECHNIQUE_PHRASES, NEUTRAL_PHRASES

PREFIXES = ('', 'The message says: ', 'I received this wording: ', 'Mujhe ye text mila: ')
SUFFIXES = ('', ' What should I do?', ' Is this request appropriate?', ' Is payment ka matlab kya hai?')
DETAILS = ('My payment question involves {amount}.', 'The amount I am asking about is {amount}.',
           'I am considering a payment of {amount}.', 'Mera payment question {amount} ke bare me hai.')


def _family_roles(count: int, rng: np.random.Generator) -> dict[int, str]:
    """Keep families disjoint. Row counts, not family counts, use 70/15/15."""
    if count % 2:
        raise ValueError('English/Hinglish banks must have equal size')
    half = count // 2
    roles = {}
    for offset in (0, half):
        groups = rng.permutation(np.arange(offset, offset+half))
        # At least one source family per language for validation and test.
        for position, index in enumerate(groups):
            roles[int(index)] = 'train' if position < half-2 else 'validation' if position == half-2 else 'test'
    return roles


def generate_psychology_messages(count: int = 6000, seed: int = SEED) -> pd.DataFrame:
    if count < 100:
        raise ValueError('At least 100 messages are required')
    labels = get_psychology_labels()
    if set(TECHNIQUE_PHRASES) != set(labels):
        raise ValueError('Phrase bank taxonomy differs from labels.json')
    rng = np.random.default_rng(seed)
    assignments = {label: _family_roles(len(bank), rng) for label, bank in TECHNIQUE_PHRASES.items()}
    neutral_roles = _family_roles(len(NEUTRAL_PHRASES), rng)
    train_count, validation_count = int(count*.70), int(count*.15)
    sizes = {'train': train_count, 'validation': validation_count, 'test': count-train_count-validation_count}
    rows, seen = [], set()
    for role, size in sizes.items():
        for row_number in range(size):
            language = 'English' if row_number % 2 == 0 else 'Hinglish'
            for attempt in range(100):
                positive_labels, phrases, families = set(), [], []
                neutral = rng.random() < .22
                if neutral:
                    half = len(NEUTRAL_PHRASES)//2
                    pool = [i for i, r in neutral_roles.items() if r == role and (i < half) == (language == 'English')]
                    chosen = int(rng.choice(pool))
                    phrases.append(NEUTRAL_PHRASES[chosen])
                    families.append(f'neutral:{chosen}')
                else:
                    techniques = int(rng.choice([1, 2, 3, 4], p=[.40, .30, .22, .08]))
                    chosen_labels = rng.choice(labels, size=techniques, replace=False)
                    for label in chosen_labels:
                        bank = TECHNIQUE_PHRASES[label]
                        pool = [i for i, r in assignments[label].items() if r == role and (i < 5) == (language == 'English')]
                        chosen = int(rng.choice(pool))
                        phrase, extras = bank[chosen]
                        positive_labels.update((label, *extras))
                        phrases.append(phrase)
                        families.append(f'{label}:{chosen}')
                amount = f'₹{int(rng.integers(10, 1500))*100:,}'
                name = str(rng.choice(['Sharma', 'Patel', 'Rao', 'Verma', 'Khan', 'Mehta']))
                text = ' '.join(phrases).format(amount=amount, name=name)
                # Shared, non-label-bearing framing supplies variation to neutral examples too.
                prefix = str(rng.choice(PREFIXES))
                suffix = str(rng.choice(SUFFIXES))
                detail = str(rng.choice(DETAILS)).format(amount=amount)
                text = prefix + text + ' ' + detail + suffix
                style = rng.random()
                if style < .05:
                    text = text.upper()
                elif style < .15:
                    text = text.lower()
                elif style < .22:
                    text = text.replace('immediately', 'immediatly').replace('please', 'pls')
                normalized = normalize_text(text)
                if normalized not in seen:
                    seen.add(normalized)
                    break
            else:
                raise ValueError('Could not produce a unique psychology message')
            rows.append({'message_id': f'PSY{len(rows):06d}', 'text': text,
                **{label: int(label in positive_labels) for label in labels},
                'language': language, 'split': role, 'source_families': '|'.join(sorted(families)),
                'neutral': neutral})
    return pd.DataFrame(rows).sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=6000)
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--output', type=Path, default=PSYCHOLOGY_DATA_PATH)
    args = parser.parse_args()
    data = generate_psychology_messages(args.count, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output, index=False)
    print(f'Saved {len(data)} unique multi-label messages to {args.output}')
    print(data.groupby('split')[list(get_psychology_labels())].agg(['size', 'sum']).to_string())


if __name__ == '__main__':
    main()
~~~

### ml/psychology/data_quality.py

~~~python
"""Validate multi-label targets and isolation of every source phrase across partitions."""
import numpy as np
import pandas as pd
from backend.app.features.text_features import normalize_text
from backend.app.utils.psychology_labels import get_psychology_labels


def validate_psychology_data(data: pd.DataFrame) -> dict:
    labels = list(get_psychology_labels())
    required = {'message_id', 'text', 'language', 'split', 'source_families', *labels}
    if missing := required - set(data):
        raise ValueError(f'Missing psychology dataset columns: {sorted(missing)}')
    if data.empty or data[list(required)].isna().any().any():
        raise ValueError('Empty psychology dataset or missing required values')
    if data.message_id.duplicated().any() or data.text.map(normalize_text).duplicated().any():
        raise ValueError('Duplicate psychology IDs or normalized messages')
    if data.text.str.strip().eq('').any():
        raise ValueError('Empty psychology text')
    if not np.isin(data[labels].to_numpy(), [0, 1]).all():
        raise ValueError('Psychology targets must be binary indicators')
    if set(data.split) != {'train', 'validation', 'test'} or set(data.language) != {'English', 'Hinglish'}:
        raise ValueError('Expected all splits and both corpus languages')
    families = data[['split', 'source_families']].assign(
        source_families=data.source_families.str.split('|')).explode('source_families')
    if families.groupby('source_families').split.nunique().max() > 1:
        raise ValueError('Source-phrase leakage across psychology splits')
    for split in ('train', 'validation', 'test'):
        for label in labels:
            if data.loc[data.split == split, label].nunique() != 2:
                raise ValueError(f'{split} must contain positives and negatives for {label}')
    counts = data[labels].sum(axis=1)
    return {'rows': len(data), 'positive_counts': data[labels].sum().astype(int).to_dict(),
            'split_counts': data.split.value_counts().to_dict(),
            'positive_counts_by_split': data.groupby('split')[labels].sum().to_dict('index'),
            'language_counts': data.language.value_counts().to_dict(),
            'neutral_rows': int(counts.eq(0).sum()), 'single_label_rows': int(counts.eq(1).sum()),
            'multi_label_rows': int(counts.gt(1).sum()), 'average_label_count': float(counts.mean()),
            'average_text_length': float(data.text.str.len().mean()),
            'source_family_count': int(families.source_families.nunique()),
            'cross_split_source_overlap': 0, 'duplicate_messages': 0,
            'stratification_note': 'Exact 70/15/15 row allocation with balanced languages and randomly sampled label combinations. '
                'Source-family isolation and authored co-labels cause prevalence differences; this is not perfect iterative multi-label stratification.'}
~~~

### ml/psychology/metrics.py

~~~python
"""Multi-label metrics, validation-only threshold choice and reviewable error examples."""
import numpy as np
from sklearn.metrics import (precision_recall_fscore_support, hamming_loss,
                             average_precision_score, f1_score, recall_score)
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.config.psychology_config import THRESHOLD_GRID


def select_thresholds(actual: np.ndarray, probabilities: np.ndarray) -> tuple[dict, dict]:
    selected, comparison = {}, {}
    for index, label in enumerate(get_psychology_labels()):
        candidates = []
        for threshold in THRESHOLD_GRID:
            predicted = probabilities[:, index] >= threshold
            candidates.append({'threshold': threshold,
                'f1': float(f1_score(actual[:, index], predicted, zero_division=0)),
                'recall': float(recall_score(actual[:, index], predicted, zero_division=0))})
        best = max(candidates, key=lambda row: (row['f1'], row['recall'], -abs(row['threshold']-.5)))
        selected[label], comparison[label] = best['threshold'], candidates
    return selected, comparison


def multi_label_metrics(actual: np.ndarray, probabilities: np.ndarray, thresholds: dict) -> dict:
    labels = list(get_psychology_labels())
    cutoffs = np.array([thresholds[label] for label in labels])
    predicted = probabilities >= cutoffs
    per_p, per_r, per_f1, support = precision_recall_fscore_support(actual, predicted, average=None, zero_division=0)
    result = {'sample_count': len(actual), 'hamming_loss': float(hamming_loss(actual, predicted))}
    for average in ('micro', 'macro'):
        precision, recall, f1, _ = precision_recall_fscore_support(actual, predicted, average=average, zero_division=0)
        result[f'{average}_precision'] = float(precision)
        result[f'{average}_recall'] = float(recall)
        result[f'{average}_f1'] = float(f1)
    result['per_label'] = {label: {'precision': float(per_p[i]), 'recall': float(per_r[i]),
        'f1': float(per_f1[i]), 'average_precision': float(average_precision_score(actual[:, i], probabilities[:, i])),
        'support': int(support[i]), 'threshold': thresholds[label],
        'false_positives': int(((actual[:, i] == 0) & predicted[:, i]).sum()),
        'false_negatives': int(((actual[:, i] == 1) & ~predicted[:, i]).sum())}
        for i, label in enumerate(labels)}
    result['macro_average_precision'] = float(np.mean([row['average_precision'] for row in result['per_label'].values()]))
    return result


def review_errors(data, probabilities: np.ndarray, thresholds: dict, count: int = 25) -> dict:
    labels = list(get_psychology_labels())
    actual = data[labels].to_numpy(dtype=int)
    predicted = probabilities >= np.array([thresholds[label] for label in labels])
    examples = {}
    for name, mask in (('false_positives', (actual == 0) & predicted), ('false_negatives', (actual == 1) & ~predicted)):
        positions = np.where(mask.any(axis=1))[0]
        # Rank by number of errors and model confidence; one entry per message.
        positions = sorted(positions, key=lambda i: int(mask[i].sum()), reverse=True)[:count]
        examples[name] = [{'message_id': str(data.iloc[i].message_id), 'text': data.iloc[i].text,
            'true_labels': [label for j, label in enumerate(labels) if actual[i, j]],
            'predicted_labels': [label for j, label in enumerate(labels) if predicted[i, j]],
            'error_labels': [label for j, label in enumerate(labels) if mask[i, j]],
            'probabilities': {label: float(probabilities[i, j]) for j, label in enumerate(labels)}} for i in positions]
    return examples
~~~

### ml/psychology/train.py

~~~python
"""Fit a text-only TF-IDF One-vs-Rest logistic baseline with validation thresholds."""
import hashlib
import json
import joblib
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression
from backend.app.features.text_features import make_text_vectorizer
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.config.psychology_config import (PSYCHOLOGY_DATA_PATH, PSYCHOLOGY_MODEL_PATH,
    PSYCHOLOGY_THRESHOLDS_PATH, PSYCHOLOGY_REPORT_DIR, SEED)
from ml.psychology.data_quality import validate_psychology_data
from ml.psychology.metrics import select_thresholds, multi_label_metrics


def train() -> dict:
    data = pd.read_csv(PSYCHOLOGY_DATA_PATH)
    quality = validate_psychology_data(data)
    labels = list(get_psychology_labels())
    train_data, validation, test = (data[data.split == role] for role in ('train', 'validation', 'test'))
    pipeline = Pipeline([('tfidf', make_text_vectorizer()), ('classifier', OneVsRestClassifier(
        LogisticRegression(C=4, class_weight='balanced', max_iter=2000, random_state=SEED), n_jobs=1))])
    # Text is the sole input; taxonomy indicators, provenance and IDs are never features.
    pipeline.fit(train_data.text, train_data[labels].to_numpy(dtype=int))
    validation_probabilities = pipeline.predict_proba(validation.text)
    thresholds, comparison = select_thresholds(validation[labels].to_numpy(dtype=int), validation_probabilities)
    test_probabilities = pipeline.predict_proba(test.text)
    metadata = {'seed': SEED, 'labels': labels, 'input_features': ['text'], 'sklearn_version': sklearn.__version__,
        'threshold_selection': 'maximum validation F1 per label, recall then closeness to .5 as tie-breakers',
        'split_strategy': quality['stratification_note'], 'probabilities': 'uncalibrated per-label logistic outputs',
        'dataset_sha256': hashlib.sha256(PSYCHOLOGY_DATA_PATH.read_bytes()).hexdigest(),
        'limitations': 'Synthetic component-composed messages; source phrasing and correlations can differ substantially from real conversations.'}
    PSYCHOLOGY_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PSYCHOLOGY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'kind': 'psychology', 'pipeline': pipeline,
                 'thresholds': thresholds, 'metadata': metadata}, PSYCHOLOGY_MODEL_PATH)
    PSYCHOLOGY_THRESHOLDS_PATH.write_text(json.dumps(thresholds, indent=2), encoding='utf-8')
    PSYCHOLOGY_MODEL_PATH.with_suffix('.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    report = {'metadata': metadata, 'thresholds': thresholds, 'threshold_comparison': comparison,
        'validation': multi_label_metrics(validation[labels].to_numpy(dtype=int), validation_probabilities, thresholds),
        'test': multi_label_metrics(test[labels].to_numpy(dtype=int), test_probabilities, thresholds),
        'test_default_0_5': multi_label_metrics(test[labels].to_numpy(dtype=int), test_probabilities, dict.fromkeys(labels, .5)),
        'dataset_quality': quality}
    (PSYCHOLOGY_REPORT_DIR / 'training_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    features = pipeline.named_steps['tfidf'].get_feature_names_out()
    terms = {label: [str(features[i]) for i in estimator.coef_[0].argsort()[-12:][::-1]]
             for label, estimator in zip(labels, pipeline.named_steps['classifier'].estimators_)}
    (PSYCHOLOGY_REPORT_DIR / 'top_label_terms.json').write_text(json.dumps(terms, indent=2), encoding='utf-8')
    print(f"Saved {PSYCHOLOGY_MODEL_PATH}; validation micro F1={report['validation']['micro_f1']:.3f}, "
          f"test micro F1={report['test']['micro_f1']:.3f}, macro F1={report['test']['macro_f1']:.3f}")
    print(json.dumps(thresholds, indent=2))
    return report


if __name__ == '__main__':
    train()
~~~

### backend/app/models/psychology_model.py

~~~python
"""Startup-loaded multi-label pipeline and its validation-selected thresholds."""
import json
from pathlib import Path
import joblib
import numpy as np
from backend.app.config.psychology_config import PSYCHOLOGY_MODEL_PATH, PSYCHOLOGY_THRESHOLDS_PATH
from backend.app.utils.psychology_labels import get_psychology_labels


class PsychologyModel:
    def __init__(self, artifact_path: Path = PSYCHOLOGY_MODEL_PATH,
                 thresholds_path: Path = PSYCHOLOGY_THRESHOLDS_PATH):
        artifact = joblib.load(artifact_path)  # only trusted, locally generated artifacts
        labels = get_psychology_labels()
        if (artifact.get('kind') != 'psychology' or artifact.get('schema_version') != 1 or
                artifact.get('metadata', {}).get('labels') != list(labels)):
            raise ValueError('Incompatible psychology artifact; retrain the current taxonomy')
        self.pipeline, self.metadata = artifact['pipeline'], artifact['metadata']
        self.thresholds = json.loads(thresholds_path.read_text(encoding='utf-8'))
        if (set(self.thresholds) != set(labels) or self.thresholds != artifact.get('thresholds') or
                not all(0 < float(value) < 1 for value in self.thresholds.values())):
            raise ValueError('Psychology thresholds are missing, invalid or incompatible with the model')

    def predict_manipulation(self, text: str | None) -> dict[str, float]:
        labels = get_psychology_labels()
        if not text or not text.strip():
            return dict.fromkeys(labels, 0.0)
        vectorizer = self.pipeline.named_steps['tfidf']
        if vectorizer.transform([text]).nnz == 0:
            return dict.fromkeys(labels, 0.0)
        probabilities = self.pipeline.predict_proba([text])[0]
        if len(probabilities) != len(labels) or not np.isfinite(probabilities).all():
            raise ValueError('Invalid psychology model output')
        return {label: float(np.clip(probability, 0, 1)) for label, probability in zip(labels, probabilities)}
~~~

### ml/psychology/evaluate.py

~~~python
"""Print all per-label metrics and export 25 FP/FN messages for review when available."""
import json
import pandas as pd
from backend.app.models.psychology_model import PsychologyModel
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.config.psychology_config import PSYCHOLOGY_DATA_PATH, PSYCHOLOGY_REPORT_DIR
from ml.psychology.data_quality import validate_psychology_data
from ml.psychology.metrics import multi_label_metrics, review_errors


def evaluate() -> dict:
    model = PsychologyModel()
    data = pd.read_csv(PSYCHOLOGY_DATA_PATH)
    quality = validate_psychology_data(data)
    labels = list(get_psychology_labels())
    test = data[data.split == 'test'].reset_index(drop=True)
    probabilities = model.pipeline.predict_proba(test.text)
    report = {'test': multi_label_metrics(test[labels].to_numpy(dtype=int), probabilities, model.thresholds),
              'dataset_quality': quality, 'language_slices': {}}
    for language in test.language.unique():
        mask = test.language.eq(language).to_numpy()
        report['language_slices'][language] = multi_label_metrics(test.loc[mask, labels].to_numpy(dtype=int), probabilities[mask], model.thresholds)
    errors = review_errors(test, probabilities, model.thresholds)
    for rows in errors.values():
        for row in rows:
            row['split'] = 'test'
    test_review_counts = {kind: len(rows) for kind, rows in errors.items()}
    # Supplement scarce test false positives with clearly marked validation errors.
    validation = data[data.split == 'validation'].reset_index(drop=True)
    validation_errors = review_errors(validation, model.pipeline.predict_proba(validation.text), model.thresholds)
    for kind, rows in errors.items():
        for row in validation_errors[kind][:max(0, 25 - len(rows))]:
            row['split'] = 'validation'
            rows.append(row)
    # Training errors are review material only, never held-out performance evidence.
    training = data[data.split == 'train'].reset_index(drop=True)
    training_errors = review_errors(training, model.pipeline.predict_proba(training.text), model.thresholds)
    for kind, rows in errors.items():
        for row in training_errors[kind][:max(0, 25 - len(rows))]:
            row['split'] = 'train'
            rows.append(row)
    report['test_review_counts'] = test_review_counts
    report['review_note'] = 'Test errors first; insufficient test FP examples supplemented by marked validation then training errors. No test threshold tuning.'
    report['review_counts'] = {kind: len(rows) for kind, rows in errors.items()}
    report['weak_labels'] = sorted(report['test']['per_label'], key=lambda label: report['test']['per_label'][label]['f1'])[:3]
    PSYCHOLOGY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (PSYCHOLOGY_REPORT_DIR / 'saved_model_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (PSYCHOLOGY_REPORT_DIR / 'error_review.json').write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('False-positive and false-negative review examples:')
    print(json.dumps(errors, indent=2, ensure_ascii=True))
    return report


if __name__ == '__main__':
    evaluate()
~~~

### backend/app/schemas/psychology.py

~~~python
"""Validated multi-label evidence and raw, uncalibrated model outputs."""
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator, field_validator
from backend.app.config.context_config import MAX_MESSAGE_LENGTH
from backend.app.utils.psychology_labels import get_psychology_labels, validate_technique

class ManipulationScores(RootModel[dict[str, Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]]]):
    @model_validator(mode='after')
    def complete_taxonomy(self):
        if set(self.root) != set(get_psychology_labels()):
            raise ValueError('Scores must contain exactly the psychology taxonomy')
        return self

class PsychologyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)
    @field_validator('message')
    @classmethod
    def trim_message(cls, value):
        return value.strip() or None if value is not None else None

class PsychologyResult(BaseModel):
    psychology_risk: float = Field(ge=0, le=100)
    scores: ManipulationScores
    rule_scores: ManipulationScores
    ml_probabilities: ManipulationScores | None
    thresholds: ManipulationScores
    detected_techniques: list[str]
    reason_codes: list[str] = Field(min_length=1)
    evidence: dict[str, Any]
    model_available: bool
    message_available: bool
    scores_kind: str = 'hybrid_evidence_not_calibrated_probabilities'
    @field_validator('detected_techniques')
    @classmethod
    def valid_techniques(cls, values):
        for value in values:
            validate_technique(value)
        return values

class PsychologyOverlapAdjustment(BaseModel):
    adjusted_psychology_risk: float = Field(ge=0, le=100)
    discount_factor: float = Field(ge=.5, le=1)
    overlapping_techniques: list[str]
    reason_code: str
~~~

### backend/app/services/psychology_service.py

~~~python
"""Independent manipulation detection and transparent, temporary evidence scoring."""
from backend.app.config.psychology_config import (
    DEFAULT_THRESHOLD, BENIGN_SCORE_CAP, STRONG_RULE_THRESHOLD,
    RISK_STRONGEST_WEIGHT, RISK_ADDITIONAL_TECHNIQUE_POINTS, RISK_COUNT_BONUS_CAP,
    HIGH_RISK_COMBINATIONS, ML_ONLY_RISK_CAP, SCENARIO_TECHNIQUES,
    CONTEXT_OVERLAP_FIELDS, MAX_OVERLAP_DISCOUNT)
from backend.app.config.risk_config import clamp_score
from backend.app.models.psychology_model import PsychologyModel
from backend.app.rules.psychology_rules import detect_psychology_rules
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.schemas.context import PaymentContext
from backend.app.schemas.psychology import ManipulationScores

def calculate_psychology_risk(scores: dict, thresholds: dict | None = None,
                             rule_scores: dict | None = None) -> dict:
    scores = ManipulationScores(scores).root
    thresholds = thresholds or dict.fromkeys(get_psychology_labels(), DEFAULT_THRESHOLD)
    thresholds = ManipulationScores(thresholds).root
    if rule_scores is not None:
        rule_scores = ManipulationScores(rule_scores).root
    active = [label for label in get_psychology_labels() if scores[label] >= thresholds[label] and scores[label] > 0]
    if not active:
        return {'psychology_risk': 0.0, 'detected_techniques': [], 'reason_codes': ['no_manipulation_detected']}
    strongest = max(scores[label] for label in active)
    score = RISK_STRONGEST_WEIGHT * strongest + min(
        RISK_COUNT_BONUS_CAP, RISK_ADDITIONAL_TECHNIQUE_POINTS * (len(active) - 1))
    combinations = [(code, bonus) for code, (labels, bonus) in HIGH_RISK_COMBINATIONS.items()
                    if set(labels).issubset(active) and (rule_scores is None or
                       all(rule_scores[label] >= STRONG_RULE_THRESHOLD for label in labels))]
    codes = ['manipulation_evidence_detected']
    if combinations:
        code, bonus = max(combinations, key=lambda item: item[1])
        score += bonus
        codes.append(code)
    if rule_scores is not None and not any(rule_scores[label] >= STRONG_RULE_THRESHOLD for label in active):
        score = min(score, ML_ONLY_RISK_CAP)
        codes.append('ml_only_risk_capped')
    return {'psychology_risk': clamp_score(score), 'detected_techniques': active, 'reason_codes': codes}

def scenario_psychology_alignment(scenario: str, psychology: dict) -> float:
    expected = SCENARIO_TECHNIQUES.get(scenario, ())
    active = set(psychology['detected_techniques'])
    return round(sum(psychology['scores'][label] for label in expected if label in active) / len(expected), 6) if expected else 0.0

def adjust_context_overlap(psychology: dict, context: PaymentContext) -> dict:
    active = psychology['detected_techniques']
    overlapping = [label for label in active if any(
        getattr(context, field) is True for field in CONTEXT_OVERLAP_FIELDS.get(label, ()))]
    total = sum(psychology['scores'][label] for label in active)
    fraction = sum(psychology['scores'][label] for label in overlapping) / total if total else 0.0
    factor = 1 - MAX_OVERLAP_DISCOUNT * fraction
    return {'adjusted_psychology_risk': clamp_score(psychology['psychology_risk'] * factor),
            'discount_factor': round(factor, 6), 'overlapping_techniques': overlapping,
            'reason_code': 'context_psychology_overlap_discounted' if overlapping else 'no_context_psychology_overlap'}

class PsychologyService:
    def __init__(self, model: PsychologyModel | None = None):
        self.model = model

    def analyze(self, message: str | None) -> dict:
        rules = detect_psychology_rules(message)
        raw = self.model.predict_manipulation(message) if self.model else None
        thresholds = dict(self.model.thresholds) if self.model else dict.fromkeys(get_psychology_labels(), DEFAULT_THRESHOLD)
        scores = {label: max(rules['scores'][label], raw[label] if raw else 0.0)
                  for label in get_psychology_labels()}
        for label in rules['suppressed_techniques']:
            scores[label] = min(scores[label], BENIGN_SCORE_CAP)
        available = bool(message and message.strip())
        if not available:
            scores = dict.fromkeys(get_psychology_labels(), 0.0)
        result = calculate_psychology_risk(scores, thresholds, rules['scores'])
        codes = list(rules['reasons']) + result['reason_codes']
        codes += [label + '_model_evidence' for label in result['detected_techniques']
                  if raw and raw[label] >= thresholds[label] and rules['scores'][label] < thresholds[label]]
        if not self.model:
            codes.append('psychology_model_unavailable_rules_only')
        if not available:
            codes.append('psychology_message_unavailable')
        return {**result, 'scores': scores, 'rule_scores': rules['scores'],
                'ml_probabilities': raw, 'thresholds': thresholds,
                'reason_codes': list(dict.fromkeys(codes)),
                'evidence': {'rule_patterns': rules['evidence'],
                             'benign_suppressed_techniques': rules['suppressed_techniques'],
                             'combination_requires_strong_rule_support': True},
                'model_available': self.model is not None, 'message_available': available,
                'scores_kind': 'hybrid_evidence_not_calibrated_probabilities'}
~~~

### backend/app/api/psychology_routes.py

~~~python
"""Text-only analysis works when payment artifacts are unavailable."""
from fastapi import APIRouter, Request
from backend.app.schemas.psychology import PsychologyRequest, PsychologyResult
router = APIRouter(prefix='/api/v1/analyze', tags=['psychology'])
@router.post('/psychology', response_model=PsychologyResult)
def analyze_psychology(payload: PsychologyRequest, request: Request) -> dict:
    return request.app.state.psychology_service.analyze(payload.message)
~~~

### backend/app/services/risk_service.py

~~~python
"""Preliminary fusion of two modules, not a final APP fraud probability."""
import pandas as pd
from backend.app.config.risk_config import TRANSACTION_WEIGHT, RECIPIENT_WEIGHT, clamp_score, risk_level
from backend.app.database.repository import DataRepository
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService
from backend.app.services.context_service import ContextService
from backend.app.services.scenario_service import ScenarioService, calculate_scenario_risk
from backend.app.schemas.context import PaymentContext
from backend.app.config.context_config import EXTENDED_WEIGHTS, PRESERVE_DAY2_WITHOUT_CONTEXT
from backend.app.config.psychology_config import DAY4_WEIGHTS
from backend.app.services.psychology_service import PsychologyService, scenario_psychology_alignment, adjust_context_overlap


def combine_risk(transaction: dict, recipient: dict) -> dict:
    score = clamp_score(TRANSACTION_WEIGHT * transaction['score'] + RECIPIENT_WEIGHT * recipient['score'])
    reasons = list(dict.fromkeys(transaction['reasons'] + recipient['reasons']))
    return {'transaction_risk': transaction['score'], 'recipient_risk': recipient['score'],
            'preliminary_risk': score, 'risk_level': risk_level(score), 'reasons': reasons,
            'transaction_details': transaction, 'recipient_details': recipient}


class RiskService:
    def __init__(self, repository: DataRepository, transaction: TransactionService,
                 recipient: RecipientService, scenario: ScenarioService | None = None,
                 psychology: PsychologyService | None = None):
        self.repository, self.transaction, self.recipient = repository, transaction, recipient
        self.context = ContextService()
        self.scenario = scenario or ScenarioService()
        self.psychology = psychology or PsychologyService()

    def score(self, payment: dict) -> dict:
        stamp = pd.Timestamp(payment['timestamp']).tz_convert('UTC')
        if stamp < self.repository.start:
            raise ValueError('Scoring before the synthetic observation window is unsupported')
        profile = self.repository.account(payment['sender_id'], stamp)
        self.repository.account(payment['receiver_id'], stamp)
        history = self.repository.sender_history(payment['sender_id'], stamp, payment['transaction_id'])
        transaction = self.transaction.score_transaction(payment, history, profile)
        recipient = self.recipient.score_recipient(payment['receiver_id'], stamp, payment['transaction_id'])
        return combine_risk(transaction, recipient)


    def score_contextual(self, payment: dict, context: PaymentContext, message: str | None = None) -> dict:
        preliminary = self.score(payment)
        transaction, recipient = preliminary['transaction_details'], preliminary['recipient_details']
        new_recipient = bool(transaction['evidence']['first_time_recipient'])
        context_result = self.context.calculate_context_risk(context, new_recipient)
        scenario = self.scenario.predict_scenario(message, context)
        scenario_risk = calculate_scenario_risk(scenario['type'], scenario['confidence'], context, new_recipient)
        score = clamp_score(EXTENDED_WEIGHTS['transaction'] * transaction['score'] +
            EXTENDED_WEIGHTS['recipient'] * recipient['score'] +
            EXTENDED_WEIGHTS['context'] * context_result['score'] +
            EXTENDED_WEIGHTS['scenario'] * scenario_risk['score'])
        retained_without_context = PRESERVE_DAY2_WITHOUT_CONTEXT and not context_result['context_available']
        if retained_without_context:
            score = max(score, preliminary['preliminary_risk'])
        codes = list(dict.fromkeys(transaction['reasons'] + recipient['reasons'] +
                                  context_result['reasons'] + scenario['reason_codes'] + scenario_risk['reasons']))
        if retained_without_context:
            codes.append('day2_risk_retained_missing_context')
        psychology = self.psychology.analyze(message or context.user_message)
        overlap = adjust_context_overlap(psychology, context)
        extended = score
        if psychology['message_available']:
            extended = clamp_score(DAY4_WEIGHTS['transaction'] * transaction['score'] +
                DAY4_WEIGHTS['recipient'] * recipient['score'] +
                DAY4_WEIGHTS['context'] * context_result['score'] +
                DAY4_WEIGHTS['scenario'] * scenario_risk['score'] +
                DAY4_WEIGHTS['psychology'] * overlap['adjusted_psychology_risk'])
            if retained_without_context:
                extended = max(extended, preliminary['preliminary_risk'])
        else:
            codes.append('day3_risk_retained_missing_psychology_message')
        codes = list(dict.fromkeys(codes + psychology['reason_codes'] + [overlap['reason_code']]))
        return {'transaction_risk': transaction, 'recipient_risk': recipient, 'context_risk': context_result,
                'scenario': scenario, 'scenario_risk': scenario_risk, 'extended_preliminary_risk': score,
                'psychology': psychology, 'scenario_psychology_alignment': scenario_psychology_alignment(scenario['type'], psychology),
                'psychology_overlap_adjustment': overlap, 'extended_risk': extended,
                'risk_level': risk_level(score), 'extended_risk_level': risk_level(extended), 'reason_codes': codes}
~~~

### backend/app/schemas/risk.py

~~~python
"""Preliminary risk API contracts reuse the Day 1 payment schema."""
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.transaction import Transaction, PaymentReason


class PreliminaryRiskRequest(Transaction):
    transaction_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    first_time_recipient: bool = False  # recalculated from server history
    payment_reason: PaymentReason = PaymentReason.other  # excluded from Day 2 predictors


class RiskComponent(BaseModel):
    score: float = Field(ge=0, le=100)
    ml_probability: float = Field(ge=0, le=1)
    rule_score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)


class PreliminaryRiskResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction_risk: float = Field(ge=0, le=100)
    recipient_risk: float = Field(ge=0, le=100)
    preliminary_risk: float = Field(ge=0, le=100)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    reasons: list[str] = Field(min_length=1)
    transaction_details: RiskComponent
    recipient_details: RiskComponent


from typing import Any
from pydantic import model_validator, field_validator
from backend.app.schemas.context import PaymentContext
from backend.app.config.context_config import MAX_MESSAGE_LENGTH
from backend.app.utils.scenario_labels import validate_scenario_label


class ContextualRiskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction: PreliminaryRiskRequest
    context: PaymentContext
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)

    @field_validator('message')
    @classmethod
    def trim_message(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode='after')
    def unambiguous_message(self) -> 'ContextualRiskRequest':
        if self.message and self.context.user_message and self.message != self.context.user_message:
            raise ValueError('Provide one message source, or identical message/context.user_message values')
        return self


class EvidenceRiskComponent(RiskComponent):
    evidence: dict[str, float] = Field(default_factory=dict)


class ExplainedScore(BaseModel):
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    context_available: bool | None = None


class ScenarioCandidate(BaseModel):
    scenario: str
    score: float = Field(ge=0, le=1)
    _valid_label = field_validator('scenario')(validate_scenario_label)


class ScenarioResult(BaseModel):
    type: str
    confidence: float = Field(ge=0, le=1)
    confidence_kind: str
    top_scenarios: list[ScenarioCandidate] = Field(min_length=1, max_length=3)
    reason_codes: list[str] = Field(min_length=1)
    evidence: dict[str, Any]
    _valid_type = field_validator('type')(validate_scenario_label)


from backend.app.schemas.psychology import PsychologyResult, PsychologyOverlapAdjustment


class ContextualRiskResponse(BaseModel):
    transaction_risk: EvidenceRiskComponent
    recipient_risk: EvidenceRiskComponent
    context_risk: ExplainedScore
    scenario: ScenarioResult
    scenario_risk: ExplainedScore
    psychology: PsychologyResult
    scenario_psychology_alignment: float = Field(ge=0, le=1)
    psychology_overlap_adjustment: PsychologyOverlapAdjustment
    extended_risk: float = Field(ge=0, le=100)
    extended_risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    extended_preliminary_risk: float = Field(ge=0, le=100)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    reason_codes: list[str] = Field(min_length=1)
~~~

### backend/app/main.py

~~~python
"""FastAPI service with startup-cached data and trained Day 2 baselines."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from backend.app.api.risk_routes import router
from backend.app.database.repository import DataRepository
from backend.app.models.transaction_model import TransactionModel
from backend.app.models.recipient_model import RecipientModel
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService
from backend.app.services.risk_service import RiskService
from backend.app.models.scenario_model import ScenarioModel
from backend.app.services.scenario_service import ScenarioService
from backend.app.models.psychology_model import PsychologyModel
from backend.app.services.psychology_service import PsychologyService
from backend.app.api.psychology_routes import router as psychology_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.risk_service = None
    psychology = PsychologyService()
    try:
        psychology = PsychologyService(PsychologyModel())
    except (OSError, ValueError) as error:
        logging.getLogger(__name__).warning('Psychology model unavailable; rules remain active: %s', error)
    application.state.psychology_service = psychology
    application.state.psychology_model_available = psychology.model is not None
    try:
        repository = DataRepository.load()
        scenario = ScenarioService()
        try:
            scenario = ScenarioService(ScenarioModel())
        except (OSError, ValueError) as error:
            logging.getLogger(__name__).warning('Scenario text model unavailable; structured rules remain active: %s', error)
        application.state.scenario_text_available = scenario.model is not None
        application.state.risk_service = RiskService(repository,
            TransactionService(TransactionModel()), RecipientService(RecipientModel(), repository), scenario, psychology)
    except (OSError, ValueError) as error:
        application.state.risk_error = f'Risk engine unavailable: {error}. Run both training commands and restart.'
        logging.getLogger(__name__).warning(application.state.risk_error)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title='APP Shield', version='0.4.0', lifespan=lifespan)
    application.include_router(router)
    application.include_router(psychology_router)
    application.add_api_route('/', root, methods=['GET'])
    application.add_api_route('/health', health, methods=['GET'])
    application.add_api_route('/ready', ready, methods=['GET'])
    return application


def root() -> dict[str, str]:
    return {'project': 'APP Shield', 'status': 'running'}


def health() -> dict[str, str]:
    """Liveness only; readiness is exposed separately."""
    return {'status': 'healthy'}


def ready(request: Request):
    from fastapi.responses import JSONResponse
    available = getattr(request.app.state, 'risk_service', None) is not None
    return JSONResponse({'status': 'ready' if available else 'unavailable'}, status_code=200 if available else 503)


app = create_app()
~~~

### tests/test_psychology_rules.py

~~~python
"""Weighted evidence, adversarial negatives and English/Hinglish examples."""
import pytest
from backend.app.rules.psychology_rules import detect_psychology_rules
from backend.app.utils.psychology_labels import get_psychology_labels

CASES = [
    ('I am from police. Transfer now or you will be arrested.', {'authority', 'fear', 'urgency'}),
    ('Guaranteed 30% return. Only two slots remain. Invest today.', {'reward', 'scarcity', 'urgency'}),
    ('Do not tell your bank or family. This investigation is confidential.', {'secrecy'}),
    ('If you really care about me, please send money for my emergency.', {'trust', 'emotional_pressure'}),
    ('Main RBI se bol raha hu. Abhi transfer karo warna account freeze ho jayega.', {'authority', 'urgency', 'fear'}),
    ('Sir ye investment guaranteed hai, aaj last opportunity hai.', {'reward', 'scarcity', 'urgency'}),
    ('Kisi ko mat batana, ye confidential police investigation hai.', {'secrecy', 'authority'}),
    ("You've already invested 50000. Pay 10000 more to unlock withdrawal.", {'commitment'}),
    ('Thousands of users have already earned profits.', {'social_proof'}),
]
@pytest.mark.parametrize('text,expected', CASES)
def test_required_techniques(text, expected):
    result = detect_psychology_rules(text)
    assert expected <= {label for label, score in result['scores'].items() if score >= .6}
    assert set(result['scores']) == set(get_psychology_labels())
    assert all(0 <= score <= 1 for score in result['scores'].values())
    assert result['reasons']

@pytest.mark.parametrize('text', [
    'bank RBI police frozen urgent', 'Your bank statement for September is available.',
    'Your electricity bill is due tomorrow.', 'RBI released new payment guidelines.',
    'RBI announced a new policy today.', 'Please make the payment today if convenient.',
    'My bank account is frozen.', None, ''])
def test_hard_negatives(text):
    assert max(detect_psychology_rules(text)['scores'].values()) == 0

def test_repetition_does_not_amplify_same_evidence():
    once = detect_psychology_rules('Transfer now.')
    repeated = detect_psychology_rules('Transfer now. Transfer now. Transfer now.')
    assert once['scores'] == repeated['scores']

def test_benign_sentence_does_not_hide_separate_threat():
    result = detect_psychology_rules('My bank account is frozen. Transfer now or your account will be frozen.')
    assert result['scores']['fear'] >= .6
    assert 'fear' not in result['suppressed_techniques']
~~~

### tests/test_psychology_model.py

~~~python
"""Saved model contracts and leakage-resistant dataset checks."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from backend.app.models.psychology_model import PsychologyModel
from backend.app.config.psychology_config import PSYCHOLOGY_DATA_PATH, PSYCHOLOGY_THRESHOLDS_PATH
from backend.app.utils.psychology_labels import get_psychology_labels
from ml.psychology.data_quality import validate_psychology_data
from ml.psychology.metrics import select_thresholds
from backend.app.schemas.psychology import ManipulationScores

@pytest.fixture(scope='module')
def model():
    return PsychologyModel()

def test_real_multilabel_output_and_missing_text(model):
    scores = model.predict_manipulation('I am from police. Transfer now or you will be arrested.')
    assert set(scores) == set(get_psychology_labels())
    assert all(0 <= score <= 1 for score in scores.values())
    assert all(score == 0 for score in model.predict_manipulation(None).values())
    assert model.thresholds == json.loads(PSYCHOLOGY_THRESHOLDS_PATH.read_text())
    assert model.metadata['input_features'] == ['text']

def test_family_disjoint_data():
    data = pd.read_csv(PSYCHOLOGY_DATA_PATH)
    quality = validate_psychology_data(data)
    assert len(data) == 6000
    assert data.split.value_counts().to_dict() == {'train': 4200, 'validation': 900, 'test': 900}
    assert quality
    assert data.groupby('split').language.nunique().eq(2).all()

def test_invalid_score_contract():
    with pytest.raises(ValueError):
        ManipulationScores({'fear': 1})
    with pytest.raises(ValueError):
        ManipulationScores(dict.fromkeys(get_psychology_labels(), float('nan')))

def test_threshold_selection_uses_supplied_validation_targets():
    actual = np.tile([[0], [1]], (1, 10))
    probabilities = np.tile([[.1], [.4]], (1, 10))
    thresholds, comparison = select_thresholds(actual, probabilities)
    assert set(thresholds) == set(get_psychology_labels())
    assert all(value in (.3, .4) for value in thresholds.values())
    assert all(len(values) == 5 for values in comparison.values())

def test_missing_artifact():
    with pytest.raises(FileNotFoundError):
        PsychologyModel(Path('nonexistent_psychology_artifact.pkl'))
~~~

### tests/test_psychology_service.py

~~~python
"""Independent evidence scoring, risk combinations and overlap guards."""
import pytest
from backend.app.services.psychology_service import (
    PsychologyService, calculate_psychology_risk, scenario_psychology_alignment, adjust_context_overlap)
from backend.app.models.psychology_model import PsychologyModel
from backend.app.schemas.psychology import PsychologyResult
from backend.app.schemas.context import PaymentContext
from backend.app.utils.psychology_labels import get_psychology_labels
from tests.test_psychology_rules import CASES

@pytest.fixture(scope='module')
def service():
    return PsychologyService(PsychologyModel())

@pytest.mark.parametrize('text,expected', CASES)
def test_real_hybrid_examples(service, text, expected):
    result = service.analyze(text)
    PsychologyResult.model_validate(result)
    assert expected <= set(result['detected_techniques'])

@pytest.mark.parametrize('text', [
    'Your bank statement for September is available.',
    'Your electricity bill is due tomorrow.', 'RBI released new payment guidelines.',
    'Please make the payment today if convenient.', 'My bank account is frozen.'])
def test_neutral_hybrid_low(service, text):
    result = service.analyze(text)
    assert result['psychology_risk'] < 30

def test_high_risk_combination(service):
    result = service.analyze('I am from Cyber Crime. Your Aadhaar is involved in money laundering. Transfer 80000 immediately or you will be arrested. Do not tell anyone.')
    assert {'authority', 'fear', 'urgency', 'secrecy'} <= set(result['detected_techniques'])
    assert result['psychology_risk'] >= 90
    assert scenario_psychology_alignment('government_impersonation', result) >= .75
    assert scenario_psychology_alignment('normal_payment', result) == 0
    original = result.copy()
    scenario_psychology_alignment('investment_scam', result)
    assert result == original

def test_combo_stronger_than_one():
    scores = dict.fromkeys(get_psychology_labels(), 0.0)
    scores['authority'] = .9
    one = calculate_psychology_risk(scores)['psychology_risk']
    scores.update(fear=.9, urgency=.9)
    assert calculate_psychology_risk(scores)['psychology_risk'] > one + 30

def test_overlap_true_only(service):
    result = service.analyze('I am from police. Transfer now or you will be arrested.')
    yes = adjust_context_overlap(result, PaymentContext(claimed_authority=True, threatened_consequences=True, urgent_payment_requested=True))
    no = adjust_context_overlap(result, PaymentContext(claimed_authority=False, threatened_consequences=False, urgent_payment_requested=False))
    assert .5 <= yes['discount_factor'] < 1
    assert yes['adjusted_psychology_risk'] < no['adjusted_psychology_risk']
    assert no['overlapping_techniques'] == []

@pytest.mark.parametrize('text', [None, '', '   '])
def test_missing_text(service, text):
    result = service.analyze(text)
    assert result['psychology_risk'] == 0
    assert not result['message_available']

def test_rule_fallback():
    result = PsychologyService().analyze('I am from police. Transfer now or you will be arrested.')
    assert result['psychology_risk'] > 80
    assert not result['model_available']
    assert result['ml_probabilities'] is None

def test_ml_alone_cannot_claim_supported_high_risk_combo():
    scores = dict.fromkeys(get_psychology_labels(), .9)
    rules = dict.fromkeys(get_psychology_labels(), 0.0)
    result = calculate_psychology_risk(scores, rule_scores=rules)
    assert result['psychology_risk'] <= 45
    assert 'authority_fear_urgency_combination' not in result['reason_codes']
~~~

### tests/test_psychology_api.py

~~~python
"""Standalone and contextual API integration with startup fallback."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.schemas.psychology import PsychologyResult

@pytest.fixture(scope='module')
def client():
    with TestClient(create_app()) as instance:
        yield instance

def test_text_endpoint(client):
    with patch('pandas.read_csv', side_effect=AssertionError('disk IO per request')):
        response = client.post('/api/v1/analyze/psychology', json={'message': 'Main RBI se bol raha hu. Abhi transfer karo warna account freeze ho jayega.'})
    assert response.status_code == 200, response.text
    result = PsychologyResult.model_validate(response.json())
    assert {'authority', 'fear', 'urgency'} <= set(result.detected_techniques)

@pytest.mark.parametrize('payload', [{}, {'message': None}, {'message': '   '}])
def test_missing_message(client, payload):
    response = client.post('/api/v1/analyze/psychology', json=payload)
    assert response.status_code == 200
    assert response.json()['psychology_risk'] == 0

@pytest.mark.parametrize('payload', [{'message': 'x' * 4001}, {'message': 42}, {'message': 'hello', 'otp': '123'}])
def test_validation(client, payload):
    assert client.post('/api/v1/analyze/psychology', json=payload).status_code == 422

def test_independent_rule_fallback():
    with patch('backend.app.main.PsychologyModel', side_effect=FileNotFoundError('no model')), patch('backend.app.main.TransactionModel', side_effect=FileNotFoundError('no payments')):
        with TestClient(create_app()) as client:
            assert client.get('/ready').status_code == 503
            response = client.post('/api/v1/analyze/psychology', json={'message': 'I am from police. Transfer now or you will be arrested.'})
            assert response.status_code == 200
            assert response.json()['psychology_risk'] > 80
            assert not response.json()['model_available']

def test_contextual_integration_and_legacy_endpoint(client):
    transaction = dict(sender_id='A0001', receiver_id='A1006', amount=85000,
        timestamp='2026-01-30T23:31:50+00:00', device_id='D0001', payment_type='bank_transfer')
    context = dict(payment_reason='government', claimed_authority=True, authority_type='police',
                   urgent_payment_requested=True, threatened_consequences=True, requested_secrecy=True)
    response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context,
        message='I am from Cyber Crime. Your Aadhaar is involved in money laundering. Transfer 85000 immediately or you will be arrested. Do not tell anyone.'))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['psychology']['psychology_risk'] >= 90
    assert result['scenario_psychology_alignment'] >= .75
    assert result['psychology_overlap_adjustment']['discount_factor'] < 1
    assert 0 <= result['extended_risk'] <= 100
    missing = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context)).json()
    assert missing['extended_risk'] == missing['extended_preliminary_risk']
    assert missing['psychology']['psychology_risk'] == 0
    old = client.post('/api/v1/risk/preliminary', json=transaction)
    assert old.status_code == 200
    assert isinstance(old.json()['transaction_risk'], (int, float))
    assert 'psychology' not in old.json()
~~~

### scripts/smoke_psychology_api.py

~~~python
"""Verify the running Day 4 API and preserve complete request/response examples."""
import json
from backend.app.config.psychology_config import PSYCHOLOGY_REPORT_DIR
from scripts.smoke_contextual_api import post, SUSPICIOUS_PAYMENT
CASES = [
    ('I am from police. Transfer now or you will be arrested.', {'authority', 'fear', 'urgency'}),
    ('Guaranteed 30% return. Only two slots remain. Invest today.', {'reward', 'scarcity', 'urgency'}),
    ('Do not tell your bank or family. This investigation is confidential.', {'secrecy'}),
    ('If you really care about me, please send money for my emergency.', {'trust', 'emotional_pressure'}),
    ('Main RBI se bol raha hu. Abhi transfer karo warna account freeze ho jayega.', {'authority', 'urgency', 'fear'}),
    ('Sir ye investment guaranteed hai, aaj last opportunity hai.', {'reward', 'scarcity', 'urgency'}),
    ('Kisi ko mat batana, ye confidential police investigation hai.', {'secrecy', 'authority'}),
    ("You've already invested 50000. Pay 10000 more to unlock withdrawal.", {'commitment'}),
    ('Thousands of users have already earned profits.', {'social_proof'}),
]

def main():
    examples = {}
    for index, (message, expected) in enumerate(CASES):
        payload = {'message': message}
        response, latency = post('/api/v1/analyze/psychology', payload)
        assert expected <= set(response['detected_techniques'])
        examples[f'techniques_{index + 1}'] = {'request': payload, 'response': response, 'latency_ms': latency}
    for index, message in enumerate([
        'RBI announced a new policy today.', 'My bank account is frozen.',
        'Your bank statement for September is available.', 'Your electricity bill is due tomorrow.',
        'Please make the payment today if convenient.']):
        response, latency = post('/api/v1/analyze/psychology', {'message': message})
        assert response['psychology_risk'] < 30
        examples[f'neutral_{index + 1}'] = {'request': {'message': message}, 'response': response, 'latency_ms': latency}
    message = 'I am from Cyber Crime. Your Aadhaar is involved in money laundering. Transfer 80000 immediately or you will be arrested. Do not tell anyone.'
    payload = {'transaction': SUSPICIOUS_PAYMENT, 'context': {
        'payment_reason': 'government', 'contacted_by_unknown_person': True,
        'contact_channel': 'phone', 'claimed_authority': True, 'authority_type': 'police',
        'urgent_payment_requested': True, 'threatened_consequences': True,
        'requested_secrecy': True, 'fund_transfer_requested': True}, 'message': message}
    response, latency = post('/api/v1/risk/contextual', payload)
    assert response['scenario']['type'] == 'government_impersonation'
    assert response['psychology']['psychology_risk'] >= 90
    assert response['scenario_psychology_alignment'] >= .75
    examples['full_contextual'] = {'request': payload, 'response': response, 'latency_ms': latency}
    missing, _ = post('/api/v1/risk/contextual', dict(transaction=SUSPICIOUS_PAYMENT, context={}))
    assert missing['extended_risk'] == missing['extended_preliminary_risk']
    legacy, _ = post('/api/v1/risk/preliminary', SUSPICIOUS_PAYMENT)
    assert 'psychology' not in legacy
    report = {'examples': examples, 'missing_message_preserves_day3': True,
              'day2_endpoint_compatible': True,
              'latency_note': 'Single localhost requests include transport; not production benchmarks.'}
    PSYCHOLOGY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (PSYCHOLOGY_REPORT_DIR / 'psychology_api_examples.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"Verified {len(examples)} live examples; psychology={response['psychology']['psychology_risk']}, "
          f"alignment={response['scenario_psychology_alignment']}, extended={response['extended_risk']}, "
          f"extended_level={response['extended_risk_level']}, legacy_level={response['risk_level']}")

if __name__ == '__main__':
    main()
~~~

## Evaluation artifacts

- data/processed/day4/training_evaluation.json
- data/processed/day4/saved_model_evaluation.json
- data/processed/day4/top_label_terms.json
- data/processed/day4/error_review.json
- data/processed/day4/psychology_api_examples.json
- data/processed/day4/evaluation_console.txt

The fitted binary model and full 6,000-row corpus are delivered as files; they are not embedded in this source guide. Reproduction uses the commands above. Restart the API after replacing a model: it intentionally caches artifacts for the process lifetime.
