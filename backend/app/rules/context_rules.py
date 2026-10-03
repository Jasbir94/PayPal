"""Stack structured APP-context evidence; a single signal never sets max risk."""
from backend.app.config.context_config import CONTEXT_POINTS
from backend.app.config.risk_config import clamp_score
from backend.app.schemas.context import PaymentContext


def calculate_context_risk(context: PaymentContext, new_recipient: bool = False) -> dict:
    flags = {
        'unknown_contact': context.contacted_by_unknown_person is True,
        'authority_claim': context.claimed_authority is True,
        'urgent_payment_request': context.urgent_payment_requested is True,
        'threatened_consequences': context.threatened_consequences is True,
        'promised_profit_claim': context.promised_profit is True,
        'guaranteed_profit_claim': context.guaranteed_returns_promised is True,
        'secrecy_request': context.requested_secrecy is True,
        'remote_access_request': context.asked_to_install_remote_access is True,
        'payment_fee_request': context.asked_to_pay_fee is True,
        'fund_transfer_request': context.fund_transfer_requested is True,
    }
    reason = context.payment_reason
    profit = flags['promised_profit_claim'] or flags['guaranteed_profit_claim']
    combinations = {
        'authority_threat_urgency_combination': all(flags[key] for key in (
            'unknown_contact', 'authority_claim', 'urgent_payment_request', 'threatened_consequences')),
        'unsolicited_profit_offer': reason == 'investment' and profit and flags['unknown_contact'],
        'profit_offer_new_recipient': reason == 'investment' and profit and new_recipient,
        'job_fee_request': reason == 'job' and flags['payment_fee_request'],
        'bank_support_transfer_request': reason == 'bank_support' and flags['fund_transfer_request'],
        'remote_access_payment_instruction': flags['remote_access_request'] and flags['fund_transfer_request'],
        'online_relationship_money_request': reason in ('romance', 'relationship') and
            context.online_relationship is True and (flags['fund_transfer_request'] or flags['urgent_payment_request']),
    }
    evidence = flags | combinations
    reasons = [key for key, value in evidence.items() if value]
    score = sum(CONTEXT_POINTS[key] for key in reasons)
    available = any(value is not None for key, value in context.model_dump().items()
                    if key not in ('payment_reason', 'user_message'))
    return {'score': clamp_score(score), 'reasons': reasons or (['no_reported_context_risk_signals'] if available else ['insufficient_context_information']),
            'evidence': {key: value for key, value in evidence.items() if value},
            'context_available': available}
