"""Conservative reductions supported only by observed, affirmative facts."""
from backend.app.config.risk_config import MAX_PROTECTIVE_REDUCTION, PROTECTIVE_EVIDENCE_WEIGHTS, clamp_score

def assess_protective_evidence(transaction, recipient, context):
    tx = transaction.get('evidence', {})
    rec = recipient.get('evidence', {})
    ctx = context.get('evidence', {})
    found = []
    if tx.get('recipient_seen_before') is True:
        found.append(('KNOWN_RECIPIENT_LONG_TERM', PROTECTIVE_EVIDENCE_WEIGHTS['known_recipient']))
    if int(tx.get('prior_payments_to_recipient', 0) or 0) >= 3:
        found.append(('REPEATED_PRIOR_PAYMENTS', PROTECTIVE_EVIDENCE_WEIGHTS['repeated_payments']))
    # An old account is not evidence that this sender knows or trusts its owner.
    # Only describe it as established relationship evidence when we have observed
    # a prior payment relationship with this recipient.
    if (tx.get('recipient_seen_before') is True
            and rec.get('account_age_days') is not None
            and float(rec['account_age_days']) >= 365):
        found.append(('ESTABLISHED_RECIPIENT_ACCOUNT', PROTECTIVE_EVIDENCE_WEIGHTS['established_account']))
    if tx.get('baseline_available') and float(tx.get('amount_ratio', 9)) <= 1.5:
        found.append(('NORMAL_AMOUNT_PATTERN', PROTECTIVE_EVIDENCE_WEIGHTS['normal_amount']))
    if ctx.get('contacted_by_unknown_person') is False:
        found.append(('NO_UNKNOWN_CONTACT_REPORTED', PROTECTIVE_EVIDENCE_WEIGHTS['no_unknown_contact']))
    explicit = ('urgent_payment_requested', 'threatened_consequences', 'claimed_authority',
                'requested_secrecy', 'asked_to_install_remote_access')
    if any(ctx.get(key) is True for key in explicit):
        pass
    elif context.get('available') and all(ctx.get(key) is False for key in explicit):
        found.append(('NO_REPORTED_MANIPULATION_SIGNALS', PROTECTIVE_EVIDENCE_WEIGHTS['no_manipulation_signals']))
    amount = min(MAX_PROTECTIVE_REDUCTION, sum(weight for _, weight in found))
    return {'items': [name for name, _ in found], 'reduction': amount}

def apply_protective_evidence(score, protective):
    return clamp_score(max(0, score - float(protective['reduction'])))
