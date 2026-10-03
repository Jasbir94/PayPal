from backend.app.services.conversation_service import ConversationService


class StubPsychology:
    def analyze(self,text,normalize=True):
        urgency=0.9 if 'now' in text.lower() else 0.1
        scores={'authority':0.0,'fear':0.0,'urgency':urgency,'secrecy':0.0,
                'scarcity':0.0,'trust':0.0,'reward':0.0,'social_proof':0.0,
                'commitment':0.0,'emotional_pressure':0.0}
        return {'scores':scores,'detected_techniques':['urgency'] if urgency>=.3 else [],
                'psychology_risk':35.0 if urgency>=.3 else 0.0}


def test_conversation_ignores_requester_messages_and_caps_repeat_bonus():
    service=ConversationService(StubPsychology())
    messages=[{'speaker':'user','text':'I will not pay now.'},
              {'speaker':'other','text':'Pay now please.'},
              {'speaker':'other','text':'Pay now please.'}]
    result=service.analyze(messages)
    assert result['other_message_count']==2
    assert result['user_message_count']==1
    assert result['detected_techniques']==['urgency']
    assert result['conversation_psychology_risk']==40


def test_empty_or_missing_context_does_not_create_payment_escalation():
    result=ConversationService(StubPsychology()).analyze([
       {'speaker':'other','text':'Hello there.'}, {'speaker':'user','text':'Thanks.'}])
    assert result['payment_escalation_ratio'] is None
    assert result['other_message_count']==1
