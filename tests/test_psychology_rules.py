"""Weighted evidence, adversarial negatives and English/Hinglish examples."""
import pytest
from backend.app.rules.psychology_rules import detect_psychology_rules
from backend.app.utils.psychology_labels import get_psychology_labels

CASES = [
    ('I am from police. Transfer now or you will be arrested.', {'authority', 'fear', 'urgency'}),
    ('Guaranteed 30% return. Only two slots remain. Invest today.', {'reward', 'scarcity', 'urgency'}),
    ('Do not tell your bank or family. This investigation is confidential.', {'secrecy'}),
    ('If you really care about me, please send money for my emergency.', {'trust', 'emotional_pressure'}),
    ('Main RBI se bol raha hu. Abhi transfer karo warna account freeze ho jayega.', {'authority', 'urgency', 'fear'}),
    ('Sir ye investment guaranteed hai, aaj last opportunity hai.', {'reward', 'scarcity', 'urgency'}),
    ('Kisi ko mat batana, ye confidential police investigation hai.', {'secrecy', 'authority'}),
    ("You've already invested 50000. Pay 10000 more to unlock withdrawal.", {'commitment'}),
    ('Thousands of users have already earned profits.', {'social_proof'}),
]
@pytest.mark.parametrize('text,expected', CASES)
def test_required_techniques(text, expected):
    result = detect_psychology_rules(text)
    assert expected <= {label for label, score in result['scores'].items() if score >= .6}
    assert set(result['scores']) == set(get_psychology_labels())
    assert all(0 <= score <= 1 for score in result['scores'].values())
    assert result['reasons']

@pytest.mark.parametrize('text', [
    'bank RBI police frozen urgent', 'Your bank statement for September is available.',
    'Your electricity bill is due tomorrow.', 'RBI released new payment guidelines.',
    'RBI announced a new policy today.', 'Please make the payment today if convenient.',
    'My bank account is frozen.', None, ''])
def test_hard_negatives(text):
    assert max(detect_psychology_rules(text)['scores'].values()) == 0

def test_repetition_does_not_amplify_same_evidence():
    once = detect_psychology_rules('Transfer now.')
    repeated = detect_psychology_rules('Transfer now. Transfer now. Transfer now.')
    assert once['scores'] == repeated['scores']

def test_benign_sentence_does_not_hide_separate_threat():
    result = detect_psychology_rules('My bank account is frozen. Transfer now or your account will be frozen.')
    assert result['scores']['fear'] >= .6
    assert 'fear' not in result['suppressed_techniques']
