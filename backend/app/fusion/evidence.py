"""Canonical evidence vocabulary and lossless deduplication helpers."""
from collections import defaultdict

REASON_CANONICAL = {
    'first_time_recipient': 'TX_NEW_RECIPIENT', 'new_recipient': 'TX_NEW_RECIPIENT',
    'new_recipient_account': 'RECIPIENT_NEW_ACCOUNT', 'young_recipient_account': 'RECIPIENT_YOUNG_ACCOUNT',
    'device_changed': 'TX_DEVICE_CHANGE', 'high_sender_transaction_velocity': 'TX_VELOCITY_CHANGE',
    'amount_above_recent_average': 'TX_AMOUNT_DEVIATION',
    'amount_deviation': 'TX_AMOUNT_DEVIATION', 'amount_higher_than_normal': 'TX_AMOUNT_DEVIATION',
    'amount_much_higher_than_normal': 'TX_AMOUNT_DEVIATION', 'extreme_amount_deviation': 'TX_AMOUNT_DEVIATION',
    'high_amount_deviation': 'TX_AMOUNT_DEVIATION', 'transaction_model_elevated_risk': 'TX_MODEL_ELEVATED',
    'recipient_model_elevated_risk': 'RECIPIENT_MODEL_ELEVATED',
    'high_fan_in': 'RECIPIENT_HIGH_FAN_IN', 'rapid_pass_through': 'RECIPIENT_RAPID_OUTFLOW',
    'many_unique_senders': 'RECIPIENT_HIGH_FAN_IN', 'high_recipient_transaction_velocity': 'RECIPIENT_HIGH_VELOCITY',
    'high_outgoing_ratio': 'RECIPIENT_RAPID_OUTFLOW', 'high_outflow_with_short_historical_holding': 'RECIPIENT_RAPID_OUTFLOW',
    'multiple_prior_fraud_reports': 'RECIPIENT_PRIOR_REPORTS', 'prior_fraud_report': 'RECIPIENT_PRIOR_REPORTS',
    'known_mule_proximity': 'NETWORK_MULE_CONNECTION', 'mule_neighbor': 'NETWORK_MULE_CONNECTION',
    'known_mule_connection': 'NETWORK_MULE_CONNECTION', 'two_hop_known_mule_proximity': 'NETWORK_MULE_CONNECTION',
    'suspicious_layering_pattern': 'NETWORK_LAYERING', 'collector_pass_through_combination': 'NETWORK_LAYERING',
    'unknown_contact': 'CTX_UNKNOWN_CONTACT', 'unknown_contact_evidence': 'CTX_UNKNOWN_CONTACT',
    'authority_claim': 'CTX_AUTHORITY_CLAIM', 'urgent_payment_request': 'CTX_URGENT_REQUEST',
    'threatened_consequences': 'CTX_THREAT', 'secrecy_request': 'CTX_SECRECY',
    'remote_access_request': 'CTX_REMOTE_ACCESS', 'guaranteed_profit_claim': 'CTX_GUARANTEED_RETURN',
    'guaranteed_gain_claim': 'CTX_GUARANTEED_RETURN', 'profit_offer_new_recipient': 'CTX_GUARANTEED_RETURN',
    'unsolicited_profit_offer': 'CTX_GUARANTEED_RETURN',
    'authority': 'PSY_AUTHORITY', 'fear': 'PSY_FEAR', 'urgency': 'PSY_URGENCY',
    'short_payment_deadline': 'PSY_URGENCY', 'urgent_action_language': 'PSY_URGENCY',
    'government_impersonation': 'SCENARIO_GOV_IMPERSONATION',
    'government_impersonation_context_supported': 'SCENARIO_GOV_IMPERSONATION',
    'investment_scam': 'SCENARIO_INVESTMENT_SCAM', 'investment_context_supported': 'SCENARIO_INVESTMENT_SCAM',
}

EVIDENCE_GROUPS = {
    'user_side': ('TX_AMOUNT_DEVIATION', 'TX_NEW_RECIPIENT', 'TX_MODEL_ELEVATED'),
    'recipient_side': ('RECIPIENT_MODEL_ELEVATED', 'RECIPIENT_HIGH_FAN_IN',
                       'RECIPIENT_RAPID_OUTFLOW', 'RECIPIENT_NEW_ACCOUNT','RECIPIENT_PRIOR_REPORTS',
                       'NETWORK_MULE_CONNECTION','NETWORK_LAYERING'),
    'manipulation_side': ('CTX_UNKNOWN_CONTACT', 'CTX_AUTHORITY_CLAIM', 'CTX_URGENT_REQUEST',
                          'CTX_THREAT', 'CTX_SECRECY', 'CTX_REMOTE_ACCESS',
                          'CTX_GUARANTEED_RETURN', 'PSY_AUTHORITY', 'PSY_FEAR', 'PSY_URGENCY',
                          'SCENARIO_GOV_IMPERSONATION','SCENARIO_INVESTMENT_SCAM'),
}

def canonicalize(reasons):
    """Return canonical IDs once, retaining every originating reason in provenance."""
    provenance = defaultdict(list)
    for reason in reasons or ():
        canonical = REASON_CANONICAL.get(str(reason), str(reason).upper())
        if str(reason) not in provenance[canonical]:
            provenance[canonical].append(str(reason))
    return [{'id': key, 'source_reasons': values} for key, values in sorted(provenance.items())]

def deduplicate_reasons(reasons):
    return [item['id'] for item in canonicalize(reasons)]
