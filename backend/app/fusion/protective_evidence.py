"""Conservative reductions supported only by observed, affirmative facts."""
from backend.app.config.risk_config import MAX_PROTECTIVE_REDUCTION, PROTECTIVE_EVIDENCE_WEIGHTS, clamp_score

def _affirmative(value):
    return value is True or (isinstance(value, (int, float)) and not isinstance(value, bool) and value == 1)

def assess_protective_evidence(transaction, recipient, context):
    tx = transaction.get('evidence', {})
    rec = recipient.get('evidence', {})
    ctx = context.get('evidence', {})
    found = []
    if _affirmative(tx.get('recipient_seen_before')):
        found.append(('KNOWN_RECIPIENT_LONG_TERM', PROTECTIVE_EVIDENCE_WEIGHTS['known_recipient']))
    if int(tx.get('prior_payments_to_recipient', 0) or 0) >= 3:
        found.append(('REPEATED_PRIOR_PAYMENTS', PROTECTIVE_EVIDENCE_WEIGHTS['repeated_payments']))
    # An old account is not evidence that this sender knows or trusts its owner.
    # Only describe it as established relationship evidence when we have observed
    # a prior payment relationship with this recipient.
    if (_affirmative(tx.get('recipient_seen_before'))
            and rec.get('account_age_days') is not None
            and float(rec['account_age_days']) >= 365):
        found.append(('ESTABLISHED_RECIPIENT_ACCOUNT', PROTECTIVE_EVIDENCE_WEIGHTS['established_account']))
    if tx.get('baseline_available') and float(tx.get('amount_ratio', 9)) <= 1.5:
        found.append(('NORMAL_AMOUNT_PATTERN', PROTECTIVE_EVIDENCE_WEIGHTS['normal_amount']))
    # Answers about the absence of pressure are useful context, but they are
    # not independent protective facts and cannot subtract risk from backend
    # or model evidence.
    amount = min(MAX_PROTECTIVE_REDUCTION, sum(weight for _, weight in found))
    return {'items': [name for name, _ in found], 'reduction': amount}

def apply_protective_evidence(score, protective):
    return clamp_score(max(0, score - float(protective['reduction'])))
