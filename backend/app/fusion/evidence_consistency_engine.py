"""Evidence provenance and conservative comparisons for payment assessments.

This module describes what a source supports. It does not decide fraud and it
does not promote customer statements into verified account facts.
"""
from datetime import datetime, timezone
from hashlib import sha256
import re


SOURCE_TYPES = {
    'VERIFIED_BACKEND', 'TRUSTED_REFERENCE', 'USER_REPORTED',
    'MODEL_INFERRED', 'UNVERIFIED_EXTERNAL',
}


def evidence_record(*, payment_id, source_type, source_reference, interpretation,
                    confidence, verification_status, observed_at=None,
                    confidence_kind='source_reliability'):
    if source_type not in SOURCE_TYPES:
        raise ValueError(f'Unsupported evidence source type: {source_type}')
    stamp = observed_at or datetime.now(timezone.utc).isoformat()
    stable = '|'.join((str(payment_id), source_type, source_reference, interpretation))
    return {
        'evidence_id': sha256(stable.encode('utf-8')).hexdigest()[:24],
        'source_type': source_type,
        'source_reference': source_reference,
        'timestamp': stamp,
        'confidence': round(max(0.0, min(1.0, float(confidence))), 4),
        'confidence_kind': confidence_kind,
        'verification_status': verification_status,
        'payment_id': str(payment_id),
        'supported_interpretation': interpretation,
    }


_RELATIONSHIP = re.compile(
    r'(?i)\b(known recipient|saved recipient|usual recipient|regular landlord|landlord|'
    r'paid (?:this recipient|them|him|her) before|previously paid|(?:my )?(?:brother|sister|friend|family))\b')
_AUTHORITY = re.compile(r'(?i)\b(police|government officer|bank officer|rbi|tax department|court)\b')


def merge_reported_answer(context, field, answer):
    """Keep an earlier concerning user report when a later answer denies it."""
    previous = context.get(field)
    if previous is True and answer is False:
        detail = (f'Earlier conversation reported {field}; a later answer denied it. '
                 'Neither statement is independently verified.')
        conflicts = context.setdefault('reported_contradictions', [])
        if detail not in conflicts:
            conflicts.append(detail)
        return True, detail
    context[field] = answer
    return answer, None


def _months_span(history):
    if history is None or history.empty or 'timestamp' not in history:
        return 0
    values = history['timestamp']
    try:
        first, last = values.min(), values.max()
        return max(0, (last.year - first.year) * 12 + last.month - first.month)
    except (AttributeError, TypeError, ValueError):
        return 0


def compare_claims(*, payment_id, context, history, backend_history_available=True):
    """Compare reported relationship/identity claims with available records.

    A missing platform record is explicitly *not* interpreted as deception or
    fraud. It only means the platform cannot verify the reported relationship.
    """
    context = context or {}
    message = context.get('user_message') or ''
    requester = context.get('who_requested_payment') or ''
    text = f'{message} {requester}'
    count = len(history) if history is not None else 0
    relationship_claim = bool(_RELATIONSHIP.search(text)) or context.get('online_relationship') is True \
        or int(context.get('relationship_duration_days') or 0)>0
    results = []
    if relationship_claim:
        if not backend_history_available:
            status = 'RELATIONSHIP_NOT_VERIFIED'
            detail = 'The payment-history source is unavailable; no relationship conclusion can be drawn.'
        elif count >= 3 and _months_span(history) >= 2:
            status = 'HISTORICAL_RELATIONSHIP_SUPPORTED'
            detail = (f'The sender has {count} recorded prior payments to this recipient across '
                      f'{_months_span(history)} months. This supports a payment relationship, not recipient identity.')
        elif count:
            status = 'RELATIONSHIP_PARTIALLY_SUPPORTED'
            detail = f'The sender has {count} recorded prior payment(s); this does not verify recipient identity.'
        else:
            status = 'RELATIONSHIP_NOT_VERIFIED'
            detail = 'No prior transfer to this recipient is recorded in the available account history; this does not prove deception.'
        results.append({'code': status, 'detail': detail})

    if context.get('claimed_authority') is True or _AUTHORITY.search(text):
        results.append({'code': 'IDENTITY_UNVERIFIED',
            'detail': 'No authorized identity-verification source is connected; names or customer reports do not verify an official identity.'})

    if re.search(r'(?i)\b(rent|landlord)\b', text) and re.search(r'(?i)\b(investment|returns?|profit)\b', text):
        results.append({'code':'PAYMENT_PURPOSE_CONFLICT',
            'detail':'The supplied payment narrative mentions both rent and investment; clarify the purpose before relying on either claim.'})

    conflicts = context.get('reported_contradictions') or []
    results.extend({'code': 'USER_REPORT_CONFLICT', 'detail': str(item)} for item in conflicts)
    return results


def build_evidence_records(*, payment_id, transaction, context, history,
                           assessment=None, trusted_references=(),
                           backend_history_available=True):
    """Create an analyst-only provenance ledger for a single payment assessment."""
    records = [evidence_record(payment_id=payment_id,
        source_type='VERIFIED_BACKEND', source_reference='payment_attempt.server_state',
        interpretation=(f"Backend attempt records INR {transaction['amount']:g} to recipient "
                        f"{transaction['receiver_id']} from sender {transaction['sender_id']}."),
        confidence=1.0, verification_status='verified')]

    context = context or {}
    history_count = len(history) if history is not None else 0
    records.append(evidence_record(payment_id=payment_id,
        source_type='VERIFIED_BACKEND', source_reference='account_history.sender_history',
        interpretation=(f'{history_count} prior transfer(s) from this sender to this recipient are recorded in the available simulated account history.'
                        if backend_history_available else 'Historical payment records are unavailable.'),
        confidence=1.0 if backend_history_available else 0.0,
        verification_status='verified' if backend_history_available else 'unavailable'))

    for field, value in sorted(context.items()):
        if value is None or field in ('reported_contradictions',):
            continue
        safe_value='[customer-supplied text]' if isinstance(value,str) else value
        records.append(evidence_record(payment_id=payment_id,
            source_type='USER_REPORTED', source_reference=f'conversation.context.{field}',
            interpretation=f'Customer reported {field}={safe_value!s}; this is not independently verified.',
            confidence=0.5, verification_status='unverified'))
    for index, conflict in enumerate(context.get('reported_contradictions') or []):
        records.append(evidence_record(payment_id=payment_id,source_type='USER_REPORTED',
            source_reference=f'conversation.report_conflict.{index+1}',
            interpretation='The conversation contains conflicting unverified customer reports; neither statement is treated as established fact.',
            confidence=0.5,verification_status='conflicting_unverified_reports'))
    if context.get('user_message'):
        records.append(evidence_record(payment_id=payment_id,
            source_type='UNVERIFIED_EXTERNAL', source_reference='conversation.customer_supplied_text',
            interpretation='Customer-supplied narrative may contain claims about a third party; no external claim was independently verified.',
            confidence=0.35, verification_status='unverified'))

    for reference in trusted_references or ():
        records.append(evidence_record(payment_id=payment_id,
            source_type='TRUSTED_REFERENCE',
            source_reference=str(reference.get('source_reference') or reference.get('url') or reference.get('document_id') or 'approved_knowledge_base'),
            interpretation=str(reference.get('supported_interpretation') or reference.get('title') or 'Approved fraud-prevention guidance retrieved.'),
            confidence=float(reference.get('confidence', 0.9)),
            verification_status='approved_source'))

    if assessment:
        records.append(evidence_record(payment_id=payment_id,
            source_type='MODEL_INFERRED', source_reference='fraud_engine.final_assessment',
            interpretation=(f"Model/rule assessment: {assessment.get('decision')} at risk "
                            f"{assessment.get('app_scam_risk')} with confidence {assessment.get('confidence')}."),
            confidence=float(assessment.get('confidence', 0.0)),
            verification_status='inference', confidence_kind='model_output_confidence'))
    return records
