"""Structured narrative classification. Evidence strengths are heuristic, not probabilities."""
from backend.app.schemas.context import PaymentContext
from backend.app.utils.scenario_labels import get_scenario_labels


def classify_scenario_rules(context: PaymentContext) -> dict:
    labels = get_scenario_labels()
    scores = dict.fromkeys(labels, 0.0)
    reasons: dict[str, list[str]] = {label: [] for label in labels}
    reason, authority = context.payment_reason, context.authority_type
    threat = context.threatened_consequences is True
    urgency = context.urgent_payment_requested is True
    unknown = context.contacted_by_unknown_person is True
    claim = context.claimed_authority is True
    fee = context.asked_to_pay_fee is True
    transfer = context.fund_transfer_requested is True
    profit = context.promised_profit is True or context.guaranteed_returns_promised is True
    remote = context.asked_to_install_remote_access is True
    online = context.online_relationship is True or context.contact_channel in ('social_media', 'telegram', 'whatsapp')

    def support(label: str, strength: float, codes: list[str]) -> None:
        scores[label], reasons[label] = strength, codes

    if claim and (reason == 'government' or authority in ('police', 'government', 'rbi', 'tax_department', 'court')) and (threat or urgency or transfer):
        support('government_impersonation', min(.98, .55 + .15*threat + .10*urgency + .10*unknown),
                ['authority_claim', 'government_impersonation_pattern'] + (['crime_or_legal_threat'] if threat else []))
    if (reason == 'bank_support' or authority == 'bank') and claim and (threat or transfer or urgency):
        support('bank_impersonation', min(.96, .55 + .15*threat + .15*transfer + .10*unknown),
                ['bank_authority_claim', 'bank_impersonation_pattern'])
    if reason == 'investment' and profit and (unknown or transfer or urgency):
        support('investment_scam', min(.96, .60 + .15*unknown + .10*transfer + .10*urgency),
                ['profit_offer', 'investment_payment_pattern'])
    if reason == 'job' and fee:
        support('fake_job_scam', .80 + .10*unknown, ['job_fee_request', 'fake_job_payment_pattern'])
    if remote and (reason in ('tech_support', 'bank_support') or authority == 'company_support'):
        support('tech_support_scam', min(.98, .65 + .15*transfer + .10*unknown),
                ['remote_access_request', 'support_payment_pattern'])
    if reason in ('romance', 'relationship') and online and (transfer or urgency or fee):
        support('romance_scam', .65 + .15*urgency + .10*unknown,
                ['online_relationship_money_request', 'romance_payment_pattern'])
    if reason in ('family', 'friend', 'emergency') and urgency and (unknown or context.requested_secrecy is True):
        support('family_emergency_scam', .65 + .15*unknown, ['urgent_family_request', 'family_emergency_pattern'])
    if reason in ('shopping', 'marketplace') and (fee or transfer) and (unknown or urgency):
        support('marketplace_scam', .60 + .15*unknown + .10*urgency, ['marketplace_payment_pattern'])
    if reason == 'loan' and fee:
        support('loan_scam', .75 + .10*unknown, ['advance_loan_fee_request'])
    if reason == 'refund' and (fee or transfer or remote):
        support('refund_scam', min(.95, .65 + .10*unknown + .10*remote), ['payment_to_receive_refund'])
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        scores[labels[0]] = 1.0
        best = labels[0]
        reasons[best] = ['insufficient_scenario_evidence']
    return {'scenario': best, 'confidence': scores[best], 'scores': scores,
            'reason_codes': reasons[best], 'reasons_by_label': reasons}
