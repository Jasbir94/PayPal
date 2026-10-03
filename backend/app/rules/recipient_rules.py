"""Interpretable recipient evidence, with no mule identity hardcoding."""
from backend.app.config.risk_config import RECIPIENT_RULES as C, clamp_score


def score_recipient_rules(features: dict) -> dict:
    score, reasons = 0, []
    if features['account_age_days'] < C['new_days']:
        score += C['new_points']
        reasons.append('new_recipient_account')
    elif features['account_age_days'] < C['young_days']:
        score += C['young_points']
        reasons.append('young_recipient_account')
    if features['unique_senders_24h'] >= C['unique_senders']:
        score += C['diversity_points']
        reasons.append('many_unique_senders')
    if (features['incoming_transactions_1h'] >= C['incoming_1h'] or
            features['incoming_transactions_24h'] >= C['incoming_24h']):
        score += C['velocity_points']
        reasons.append('high_recipient_transaction_velocity')
    if features['outgoing_ratio'] >= C['outgoing_ratio']:
        score += C['outgoing_points']
        reasons.append('high_outgoing_ratio')
    reports = features['fraud_report_count']
    if reports >= C['reports']:
        score += C['reports_points']
        reasons.append('multiple_prior_fraud_reports')
    elif reports:
        score += C['single_report_points']
        reasons.append('prior_fraud_report')
    if (features['observed_outgoing_ratio'] >= C['outgoing_ratio'] and
            features['incoming_transactions_24h'] >= C['incoming_24h'] and
            0 < features['average_holding_minutes'] < C['rapid_holding_minutes']):
        score += C['rapid_points']
        reasons.append('high_outflow_with_short_historical_holding')
    return {'score': clamp_score(score), 'reasons': reasons or ['no_recipient_rule_signals']}
