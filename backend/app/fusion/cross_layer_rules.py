"""Small capped cross-layer bonuses for independent corroborating evidence."""
from backend.app.config.risk_config import MAX_CROSS_LAYER_BONUS

def score_cross_layer(transaction, recipient, graph, context, scenario, psychology):
    ctx = context.get('evidence', {})
    tx = transaction.get('evidence', {})
    psych = set(psychology.get('detected_techniques', ()))
    scenario_name = scenario.get('type', 'normal_or_unknown')
    matches = []
    new_payee = bool(tx.get('first_time_recipient'))
    if new_payee and scenario_name in ('government_impersonation', 'bank_impersonation') and (
        ctx.get('authority_claimed') or ctx.get('claimed_authority')):
        matches.append(('new_recipient_authority_scam_pattern', 8))
    if new_payee and scenario_name == 'investment_scam' and (
        ctx.get('guaranteed_returns_promised') or 'reward' in psych):
        matches.append(('new_recipient_guaranteed_investment_pattern', 8))
    if float(recipient.get('score', 0)) >= 60 and ctx.get('contacted_by_unknown_person') is True and (
        ctx.get('urgent_payment_requested') is True):
        matches.append(('suspicious_recipient_unknown_urgent_pattern', 10))
    if {'authority', 'fear', 'urgency'}.issubset(psych) and ctx.get('contacted_by_unknown_person') is True:
        matches.append(('authority_fear_urgency_unknown_contact_pattern', 10))
    raw = sum(value for _, value in matches)
    return {'bonus': min(MAX_CROSS_LAYER_BONUS, raw), 'patterns': [name for name, _ in matches]}
