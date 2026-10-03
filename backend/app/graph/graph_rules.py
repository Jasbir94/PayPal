"""Stacked interpretable evidence; high volume or PageRank alone never means fraud."""
from backend.app.config.risk_config import clamp_score

def score_graph_rules(features, account_age_days):
    score, reasons = 0, []
    fan_in = features['unique_incoming_senders'] >= 20
    fan_out = features['unique_outgoing_receivers'] >= 5
    rapid = features['rapid_outflow_ratio'] >= .8 and features['incoming_amount'] >= 10000
    young = account_age_days <= 30
    known = features['known_mule_neighbors']
    if fan_in:
        score += 12
        reasons.append('high_fan_in')
    if fan_out:
        score += 8
        reasons.append('high_fan_out')
    if rapid:
        score += 35
        reasons.append('rapid_pass_through')
    if fan_in and rapid:
        score += 25
        reasons.append('collector_pass_through_combination')
    if young and rapid:
        score += 10
        reasons.append('young_account_rapid_flow')
    if known:
        score += min(20, 10 * known)
        reasons.append('known_mule_connection')
    elif features['distance_to_known_mule'] == 2:
        score += 5
        reasons.append('two_hop_known_mule_proximity')
    if features['fraud_reported_neighbors']:
        score += min(10, 3 * features['fraud_reported_neighbors'])
        reasons.append('reported_neighbor_connection')
    if features['suspicious_path_depth'] >= 2 and rapid:
        score += 15
        reasons.append('suspicious_layering_pattern')
    if features['cycle_count'] and rapid:
        score += 15
        reasons.append('cycle_rapid_flow_combination')
    # Dense shared components make weak 2-hop paths/cycles noisy for old businesses.
    established = account_age_days >= 365 and known == 0 and features['fraud_reported_neighbors'] <= 1
    if established and score > 65:
        score = 65
        reasons.append('established_account_network_guard')
    return {'score': clamp_score(score), 'reasons': reasons or ['no_graph_rule_signals']}
