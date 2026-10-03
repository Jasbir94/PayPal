"""Stable human-readable reason ranking from canonical evidence and patterns."""
REASON_TEXT = {
    'TX_NEW_RECIPIENT': 'This is a first payment to the recipient.',
    'TX_AMOUNT_DEVIATION': 'The amount differs substantially from the sender’s observed pattern.',
    'CTX_UNKNOWN_CONTACT': 'An unknown person is involved in requesting the payment.',
    'CTX_AUTHORITY_CLAIM': 'The requester claims authority or institutional affiliation.',
    'CTX_URGENT_REQUEST': 'The payment is being presented as urgent.',
    'CTX_THREAT': 'Consequences or threats are reported.', 'CTX_REMOTE_ACCESS': 'Remote-access software was requested.',
    'CTX_GUARANTEED_RETURN': 'A guaranteed investment return was promised.',
    'NETWORK_MULE_CONNECTION': 'The recipient is connected to suspicious transaction-network activity.',
    'RECIPIENT_HIGH_FAN_IN': 'The recipient has unusually concentrated incoming payment activity.',
    'RECIPIENT_RAPID_OUTFLOW': 'Funds appear to move rapidly onward from the recipient.',
    'PSY_AUTHORITY': 'The message uses authority pressure.', 'PSY_FEAR': 'The message uses fear or threat pressure.',
    'PSY_URGENCY': 'The message pressures the user to act quickly.',
    'TX_DEVICE_CHANGE': 'The payment came from a device not observed in the sender’s usual pattern.',
    'RECIPIENT_NEW_ACCOUNT': 'The recipient account is newly created.',
    'RECIPIENT_HIGH_VELOCITY': 'The recipient has unusually high recent payment activity.',
    'RECIPIENT_PRIOR_REPORTS': 'The recipient has prior fraud reports.',
    'NETWORK_LAYERING': 'The payment network shows a layered or pass-through pattern.',
    'SCENARIO_GOV_IMPERSONATION': 'Structured evidence supports a government impersonation scenario.',
    'SCENARIO_INVESTMENT_SCAM': 'Structured evidence supports an investment scam scenario.',
    'NEW_RECIPIENT_AUTHORITY_SCAM_PATTERN': 'A new recipient is paired with an urgent authority claim.',
    'NEW_RECIPIENT_GUARANTEED_INVESTMENT_PATTERN': 'This is a first payment to a new recipient with guaranteed investment returns.',
    'AUTHORITY_FEAR_URGENCY_UNKNOWN_CONTACT_PATTERN': 'An unknown contact combined authority, fear and urgency.',
    'SUSPICIOUS_RECIPIENT_UNKNOWN_URGENT_PATTERN': 'An unknown contact is urging payment to a recipient with elevated risk signals.',
    'CRIME_OR_LEGAL_THREAT': 'The request mentions legal or criminal consequences to pressure the payment.',
    'GOVERNMENT_IMPERSONATION_PATTERN': 'The payment context matches indicators associated with government impersonation.',
    'BANK_IMPERSONATION_PATTERN': 'The payment context matches indicators associated with bank impersonation.',
    'INVESTMENT_PAYMENT_PATTERN': 'The payment is connected to an investment request with pressure or promised returns.',
    'FAMILY_EMERGENCY_PATTERN': 'The request uses an urgent family-emergency story.',
    'AUTHORITY_MODEL_EVIDENCE': 'The message includes language associated with authority pressure.',
    'FEAR_MODEL_EVIDENCE': 'The message includes language associated with fear or threat pressure.',
    'SECRECY_MODEL_EVIDENCE': 'The message includes a request to keep the payment secret.',
    'EMOTIONAL_PRESSURE_MODEL_EVIDENCE': 'The message includes language associated with emotional pressure.',
    'FUND_TRANSFER_REQUEST': 'The requester asked for money to be transferred.',
    'MANIPULATION_EVIDENCE_DETECTED': 'The message contains patterns associated with pressure or manipulation.',
}
REASON_PRIORITY = {
    'CTX_REMOTE_ACCESS': 100, 'CTX_THREAT': 98, 'NETWORK_MULE_CONNECTION': 96,
    'NETWORK_LAYERING': 92, 'SCENARIO_GOV_IMPERSONATION': 91, 'SCENARIO_INVESTMENT_SCAM': 89,
    'CTX_GUARANTEED_RETURN': 90, 'CTX_AUTHORITY_CLAIM': 88,
    'CTX_UNKNOWN_CONTACT': 84, 'CTX_URGENT_REQUEST': 80, 'RECIPIENT_PRIOR_REPORTS': 78,
    'RECIPIENT_RAPID_OUTFLOW': 76, 'RECIPIENT_HIGH_FAN_IN': 70,
    'TX_AMOUNT_DEVIATION': 60, 'TX_NEW_RECIPIENT': 56, 'TX_DEVICE_CHANGE': 48,
}

def rank_reasons(canonical_items, cross_layer, protective, groups, limit=5):
    rows = []
    for item in canonical_items:
        key = item['id']
        rows.append({'code': key, 'description': REASON_TEXT.get(key, key.replace('_', ' ').lower()),
                     'evidence_family': next((family for family, ids in __import__(
                         'backend.app.fusion.evidence', fromlist=['EVIDENCE_GROUPS']).EVIDENCE_GROUPS.items()
                         if key in ids), 'supporting'), 'impact': 'risk_increasing'})
    for pattern in cross_layer.get('patterns', ()):
        rows.append({'code': pattern, 'description': REASON_TEXT.get(
                         pattern.upper(), pattern.replace('_', ' ').lower()),
                     'evidence_family': 'cross_layer', 'impact': 'risk_increasing', 'priority': 94})
    for name in protective.get('items', ()):
        rows.append({'code': name, 'description': name.replace('_', ' ').lower(),
                     'evidence_family': 'protective', 'impact': 'risk_reducing'})
    # Keep observable reasons deterministically ordered; callers have already
    # supplied subsystem relevance order, while rule-patterns rank first.
    for row in rows:
        row.setdefault('priority', REASON_PRIORITY.get(row['code'], 20))
    return [{key:value for key,value in row.items() if key!='priority'}
            for row in sorted(rows,key=lambda row:row['priority'],reverse=True)[:limit]]
