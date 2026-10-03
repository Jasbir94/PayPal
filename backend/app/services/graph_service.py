"""Cached graph evidence layer independent of transaction/recipient models."""
from time import perf_counter
from backend.app.graph.graph_builder import utc_timestamp
from backend.app.graph.graph_features import calculate_graph_features
from backend.app.graph.graph_rules import score_graph_rules
from backend.app.features.recipient_features import calculate_account_age
from backend.app.config.graph_config import MAX_GRAPH_ML_ONLY_SCORE
from backend.app.config.risk_config import clamp_score, risk_level

class GraphService:
    def __init__(self, builder, model=None):
        self.builder, self.model = builder, model

    def score_graph_risk(self, recipient_id, transaction_timestamp, exclude_id=None):
        started = perf_counter()
        stamp = utc_timestamp(transaction_timestamp)
        if recipient_id not in self.builder.accounts.index:
            raise KeyError(f'Unknown account: {recipient_id}')
        age = calculate_account_age(self.builder.accounts.loc[recipient_id, 'created_at'], stamp)
        graph = self.builder.build_graph_until(stamp, exclude_id)
        features = calculate_graph_features(graph, recipient_id)
        rules = score_graph_rules(features, age)
        probability = self.model.probability(features) if self.model else None
        # ML can complement a rule but never erase strong stacked rule evidence.
        ml_score = min(MAX_GRAPH_ML_ONLY_SCORE, probability * 100) if probability is not None else 0.0
        score = clamp_score(max(rules['score'], ml_score))
        reasons = list(rules['reasons'])
        if probability is not None and probability >= self.model.threshold:
            reasons.append('graph_model_elevated_risk')
        if self.model is None:
            reasons.append('graph_model_unavailable_rules_only')
        return {'score': score, 'features': features, 'reasons': reasons,
                'rule_score': rules['score'], 'ml_probability': probability,
                'model_available': self.model is not None, 'risk_level': risk_level(score),
                'as_of': stamp.isoformat(), 'lookback_hours': graph.graph['lookback_hours'],
                'account_age_days': age,
                'timing_ms': {'snapshot_build': graph.graph['build_ms'],
                              'total': (perf_counter() - started) * 1000}}
