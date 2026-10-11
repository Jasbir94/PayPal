"""Risk-to-action policy; uncertainty can trigger verification even at moderate risk."""
from backend.app.config.risk_config import DECISION_THRESHOLDS, LOW_CONFIDENCE_REVIEW_THRESHOLD

def recommend(score, confidence, family_count, reason_codes=(), context=None, recipient_score=None):
    risk = float(score) / 100
    # A calibrated aggregate must not erase directly observed, high-concern
    # evidence. These are policy floors, not claims of verified fraud.
    codes = set(reason_codes or ())
    context = context or {}
    authority = bool(context.get('claimed_authority'))
    unknown = context.get('contacted_by_unknown_person') is True
    pressure = any(context.get(key) is True for key in (
        'urgent_payment_requested', 'threatened_consequences', 'requested_secrecy'))
    if authority and pressure:
        return 'STEP_UP_VERIFICATION'
    if unknown and context.get('urgent_payment_requested') is True:
        return 'WARN_AND_REVIEW'
    if context.get('asked_to_install_remote_access') is True:
        return 'STEP_UP_VERIFICATION'
    if context.get('guaranteed_returns_promised') is True or context.get('promised_profit') is True:
        return 'WARN_AND_REVIEW'
    if context.get('asked_to_pay_fee') is True and unknown:
        return 'WARN_AND_REVIEW'
    if (recipient_score is not None and float(recipient_score) >= 60
            and context.get('payment_reason') in ('investment', 'job', 'bank_support', 'government')):
        return 'WARN_AND_REVIEW'
    if any(code in codes for code in ('NETWORK_MULE_CONNECTION', 'NETWORK_LAYERING',
                                      'RECIPIENT_PRIOR_REPORTS')):
        return 'WARN_AND_REVIEW'
    if risk >= DECISION_THRESHOLDS['block'] and confidence >= .75:
        return 'BLOCK_AND_ESCALATE'
    if risk >= DECISION_THRESHOLDS['step_up']:
        return 'STEP_UP_VERIFICATION'
    if risk >= DECISION_THRESHOLDS['review'] or (risk >= .30 and confidence < LOW_CONFIDENCE_REVIEW_THRESHOLD):
        return 'WARN_AND_REVIEW'
    if risk >= DECISION_THRESHOLDS['allow'] or family_count < 3:
        return 'ALLOW_WITH_WARNING'
    return 'ALLOW'
