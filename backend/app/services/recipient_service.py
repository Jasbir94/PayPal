"""Recipient risk service using cached account and past payment history."""
import pandas as pd
from time import perf_counter
from backend.app.config.risk_config import MODEL_REASON_THRESHOLD, component_score
from backend.app.database.repository import DataRepository
from backend.app.features.recipient_features import calculate_recipient_features
from backend.app.models.recipient_model import RecipientModel
from backend.app.rules.recipient_rules import score_recipient_rules


class RecipientService:
    def __init__(self, model: RecipientModel, repository: DataRepository):
        self.model, self.repository = model, repository

    def score_recipient(self, receiver_id: str, timestamp: pd.Timestamp,
                        exclude_id: str | None = None) -> dict:
        started = perf_counter()
        account = self.repository.account(receiver_id, timestamp)
        history = self.repository.recipient_history(receiver_id, timestamp, exclude_id)
        features = calculate_recipient_features(account, history, timestamp)
        result = self.score_features(features)
        result['timing_ms']['total'] = round((perf_counter() - started) * 1000, 3)
        return result

    def score_features(self, features: dict) -> dict:
        started = perf_counter()
        rules = score_recipient_rules(features)
        probability = self.model.probability(features)
        reasons = list(rules['reasons'])
        if probability >= MODEL_REASON_THRESHOLD:
            reasons = [code for code in reasons if code != 'no_recipient_rule_signals']
            reasons.append('recipient_model_elevated_risk')
        score, guarded = component_score(probability, rules['score'])
        if guarded:
            reasons.append('strong_rule_evidence_floor')
        return {'score': score,
                'ml_probability': round(probability, 6), 'rule_score': rules['score'], 'reasons': reasons,
                'evidence': features, 'timing_ms': {'scoring': round((perf_counter() - started) * 1000, 3)}}
