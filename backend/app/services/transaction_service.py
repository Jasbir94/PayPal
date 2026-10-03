"""Fuse behavioral rules with a loaded synthetic transaction baseline."""
import pandas as pd
from time import perf_counter
from backend.app.config.risk_config import MODEL_REASON_THRESHOLD, component_score
from backend.app.features.transaction_features import extract_transaction_features
from backend.app.models.transaction_model import TransactionModel
from backend.app.rules.transaction_rules import score_transaction_rules


class TransactionService:
    def __init__(self, model: TransactionModel):
        self.model = model

    def score_transaction(self, transaction: dict, history: pd.DataFrame, profile: dict) -> dict:
        started = perf_counter()
        features = extract_transaction_features(transaction, history, profile)
        rules = score_transaction_rules(features)
        probability = self.model.probability(features)
        reasons = list(rules['reasons'])
        if probability >= MODEL_REASON_THRESHOLD:
            reasons = [code for code in reasons if code != 'within_expected_transaction_pattern']
            reasons.append('transaction_model_elevated_risk')
        if not features['baseline_available']:
            reasons.append('sender_baseline_unavailable')
        score, guarded = component_score(probability, rules['score'])
        if guarded:
            reasons.append('strong_rule_evidence_floor')
        return {'score': score,
                'ml_probability': round(probability, 6), 'rule_score': rules['score'], 'reasons': reasons,
                'evidence': features, 'timing_ms': round((perf_counter() - started) * 1000, 3)}
