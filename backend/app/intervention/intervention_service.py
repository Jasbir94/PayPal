"""Map decision and supported scam evidence to a calm user-facing message."""
from backend.app.intervention.templates import GENERIC,TEMPLATES

def build_intervention(decision, scenario, component_scores, payment_reason='other'):
    if decision=='ALLOW':
        return {'level':0,'type':'NO_INTERVENTION','title':'No additional check needed',
                'message':'No additional payment warning is indicated from the information provided.',
                'recommended_action':'Continue only if the payment details are correct.'}
    score=float(component_scores.get('scenario') or 0)
    # A scenario-specific warning requires actual context-supported scenario risk,
    # never classifier confidence or an ungrounded label by itself.
    if scenario in TEMPLATES and score>=20:
        template=TEMPLATES[scenario]
        level=4 if decision in ('STEP_UP_VERIFICATION','BLOCK_AND_ESCALATE') else 3
        return {'level':level,'type':scenario.upper()+'_WARNING',**template}
    template=GENERIC
    levels={'ALLOW_WITH_WARNING':1,'WARN_AND_REVIEW':2,
            'STEP_UP_VERIFICATION':4,'BLOCK_AND_ESCALATE':4}
    level=levels.get(decision,1)
    warning_type='CONTEXT_CHECK' if decision=='WARN_AND_REVIEW' else 'GENERAL_PAYMENT_CAUTION'
    if payment_reason=='investment':
        # Avoid asserting an investment scam when supporting evidence is weak.
        template={'title':'Review this investment payment',
                  'message':'Before sending money, check the recipient and investment terms independently. Be cautious of pressure or promises that returns are guaranteed.',
                  'recommended_action':'Use a regulated provider and a contact method you found independently.'}
        warning_type='INVESTMENT_CONTEXT_CHECK'
    return {'level':level,'type':warning_type,**template}
