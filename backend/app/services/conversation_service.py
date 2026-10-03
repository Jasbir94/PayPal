"""Bounded cumulative analysis; only messages from the requester are scored."""
import re
from backend.app.security.text_normalization import normalize_text_view
from backend.app.utils.psychology_labels import get_psychology_labels

_PAYMENT_CUE=re.compile(r'(?i)\b(pay|payment|transfer|send money|fee|deposit|bhejo|jama|paisa|paise)\b')

class ConversationService:
    def __init__(self, psychology_service):
        self.psychology=psychology_service

    def analyze(self, messages, current_payment_amount=None):
        if hasattr(messages[0],'model_dump'):
            rows=[message.model_dump() for message in messages]
        else:
            rows=list(messages)
        other=[(index,row) for index,row in enumerate(rows) if row['speaker']=='other']
        user_count=len(rows)-len(other)
        per_turn=[]; normalized_messages=[]; amounts=[]; scores_by_turn=[]
        for index,row in other:
            view=normalize_text_view(row['text'])
            normalized_messages.append(view.normalized_text)
            result=self.psychology.analyze(view.normalized_text, normalize=False)
            scores=result['scores']
            if hasattr(scores,'root'): scores=scores.root
            scores_by_turn.append(scores)
            per_turn.append({'turn_index':index,'techniques':list(result['detected_techniques']),
                             'risk':float(result['psychology_risk'])})
            if row.get('payment_amount') is not None: amounts.append(float(row['payment_amount']))
        if current_payment_amount is not None:
            amounts.append(float(current_payment_amount))
        labels=get_psychology_labels()
        aggregated={}
        for label in labels:
            observed=[float(item[label]) for item in scores_by_turn if float(item.get(label,0))>0]
            # Max evidence prevents dilution across turns; repetition is a small,
            # bounded corroborator rather than an unbounded sum.
            aggregated[label]=round(min(1.0,(max(observed) if observed else 0)+.08*max(0,len(observed)-1)),6)
        techniques=sorted(label for label,value in aggregated.items() if value>=.30)
        base=max([item['risk'] for item in per_turn] or [0.0])
        repeat_bonus=min(20.0,5.0*max(0,len(per_turn)-1))
        conversation_risk=round(min(100.0,base+repeat_bonus),2)
        stages=[]; stage_positions=[]
        for stage,labels_for_stage in (('authority',('authority',)),('fear',('fear',)),
                ('urgency',('urgency',)),('payment_request',()),('secrecy',('secrecy',))):
            position=None
            for turn,(index,row) in enumerate(other):
                text=normalized_messages[turn]
                hit=(_PAYMENT_CUE.search(text) is not None) if stage=='payment_request' else any(
                    float(scores_by_turn[turn].get(label,0))>=.30 for label in labels_for_stage)
                if hit: position=index; break
            if position is not None:
                stages.append(stage); stage_positions.append(position)
        if len(stages)<2:
            progression=20.0*len(stages)
        else:
            ordered=sum(stage_positions[i]<stage_positions[i+1] for i in range(len(stage_positions)-1))
            progression=round(70*len(stages)/5+30*ordered/max(1,len(stages)-1),2)
        escalation=(round(amounts[-1]/amounts[0],4) if len(amounts)>=2 and amounts[0]>0 else None)
        return {'other_message_count':len(other),'user_message_count':user_count,
            'detected_techniques':techniques,'technique_scores':aggregated,
            'conversation_psychology_risk':conversation_risk,
            'manipulation_progression_score':progression,'progression_stages':stages,
            'payment_escalation_ratio':escalation,
            'normalization_applied':any(normalize_text_view(row['text']).transformations for _,row in other),
            # Kept internal for the combined assessment; never logged or returned.
            'analysis_message':'\n'.join(normalized_messages)[:6000] or None,
            'turn_evidence':per_turn}
