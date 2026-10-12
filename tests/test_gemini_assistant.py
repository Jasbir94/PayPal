import json
from types import SimpleNamespace

from backend.app.conversation.gemini_assistant import GeminiChatAssistant


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(text=json.dumps(value))


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def test_missing_key_disables_gemini_and_uses_fallback(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    assistant = GeminiChatAssistant()
    assert not assistant.enabled
    assert assistant.classify_intent('Check my available funds') is None
    assert assistant.generate_menu_reply('hello') is None


def test_classifier_only_returns_allowed_non_authoritative_intents():
    client = FakeClient([{'intent':'CHECK_BALANCE'}, {'intent':'PAYMENT_CONFIRM'}])
    assistant = GeminiChatAssistant(client=client)
    assert assistant.classify_intent('How much money do I have?') == 'CHECK_BALANCE'
    assert assistant.classify_intent('please confirm this') is None
    assert client.models.calls[0]['config']['temperature'] == 0


def test_menu_reply_is_rejected_if_it_invents_payment_facts_or_actions():
    client = FakeClient([
        {'reply':'I can help you review your account. What would you like to know?'},
        {'reply':'I sent ₹500 to Riya.'},
        {'reply':'Please confirm the transfer.'},
    ])
    assistant = GeminiChatAssistant(client=client)
    assert assistant.generate_menu_reply('hello') == 'I can help you review your account. What would you like to know?'
    assert assistant.generate_menu_reply('hello') is None
    assert assistant.generate_menu_reply('hello') is None


def test_gemini_failure_returns_fallback_signal():
    assistant = GeminiChatAssistant(client=FakeClient([RuntimeError('offline')]))
    assert assistant.classify_intent('Can you check my money?') is None


def test_agent_uses_gemini_only_for_unknown_intents_and_safe_menu_copy(monkeypatch):
    from backend.app.conversation.payment_conversation_agent import PaymentConversationAgent

    class FakeAssistant:
        def classify_intent(self, _message):
            return 'CHECK_BALANCE'

        def generate_menu_reply(self, _message):
            return 'Tell me what you would like help with.'

    agent = PaymentConversationAgent(None, None, gemini_assistant=FakeAssistant())
    assert agent._intent('What remains after earlier activity?', allow_gemini=True) == 'CHECK_BALANCE'
    assert agent._intent('Confirm and send', allow_gemini=True) == 'PAYMENT_CONFIRM'
    assert agent._intent('What remains after earlier activity?', allow_gemini=False) == 'UNKNOWN'
    session = {'session_id':'s1','messages':[{'role':'user','text':'hello'}],
        'payment_attempt_id':None,'claims':[],'current_question':None,'question_count':0}
    result = agent._prompt(session, 'deterministic fallback', 'MAIN_MENU')
    assert result['message'] == 'Tell me what you would like help with.'
    payment_session = {'session_id':'s2','messages':[],'payment_attempt_id':'payment-1',
        'claims':[],'current_question':None,'question_count':0}
    result = agent._prompt(payment_session, 'Safety warning stays backend-authored.', 'WARNING')
    assert result['message'] == 'Safety warning stays backend-authored.'