"""Stack relative behavioral evidence without penalizing clock hour alone."""
from backend.app.config.risk_config import TRANSACTION_RULES as C, clamp_score


def score_transaction_rules(features: dict) -> dict:
    score, reasons = 0, []
    ratio = features['amount_ratio']
    if ratio > C['extreme_ratio']:
        score += C['extreme_points']
        reasons.append('amount_much_higher_than_normal')
    elif ratio > C['high_ratio']:
        score += C['high_points']
        reasons.append('amount_higher_than_normal')
    if features['first_time_recipient']:
        score += C['new_recipient_points']
        reasons.append('first_time_recipient')
    if features['amount_vs_recent_average'] > C['recent_ratio']:
        score += C['recent_points']
        reasons.append('amount_above_recent_average')
    if features['device_changed']:
        score += C['device_points']
        reasons.append('device_changed')
    if (features['transactions_last_1h'] >= C['velocity_1h'] or
            features['transactions_last_24h'] >= C['velocity_24h']):
        score += C['velocity_points']
        reasons.append('high_sender_transaction_velocity')
    return {'score': clamp_score(score), 'reasons': reasons or ['within_expected_transaction_pattern']}
