"""Independent evidence scoring, risk combinations and overlap guards."""
import pytest
from backend.app.services.psychology_service import (
    PsychologyService, calculate_psychology_risk, scenario_psychology_alignment, adjust_context_overlap)
from backend.app.models.psychology_model import PsychologyModel
from backend.app.schemas.psychology import PsychologyResult
from backend.app.schemas.context import PaymentContext
from backend.app.utils.psychology_labels import get_psychology_labels
from tests.test_psychology_rules import CASES

@pytest.fixture(scope='module')
def service():
    return PsychologyService(PsychologyModel())

@pytest.mark.parametrize('text,expected', CASES)
def test_real_hybrid_examples(service, text, expected):
    result = service.analyze(text)
    PsychologyResult.model_validate(result)
    assert expected <= set(result['detected_techniques'])

@pytest.mark.parametrize('text', [
    'Your bank statement for September is available.',
    'Your electricity bill is due tomorrow.', 'RBI released new payment guidelines.',
    'Please make the payment today if convenient.', 'My bank account is frozen.'])
def test_neutral_hybrid_low(service, text):
    result = service.analyze(text)
    assert result['psychology_risk'] < 30

def test_high_risk_combination(service):
    result = service.analyze('I am from Cyber Crime. Your Aadhaar is involved in money laundering. Transfer 80000 immediately or you will be arrested. Do not tell anyone.')
    assert {'authority', 'fear', 'urgency', 'secrecy'} <= set(result['detected_techniques'])
    assert result['psychology_risk'] >= 90
    assert scenario_psychology_alignment('government_impersonation', result) >= .75
    assert scenario_psychology_alignment('normal_payment', result) == 0
    original = result.copy()
    scenario_psychology_alignment('investment_scam', result)
    assert result == original

def test_combo_stronger_than_one():
    scores = dict.fromkeys(get_psychology_labels(), 0.0)
    scores['authority'] = .9
    one = calculate_psychology_risk(scores)['psychology_risk']
    scores.update(fear=.9, urgency=.9)
    assert calculate_psychology_risk(scores)['psychology_risk'] > one + 30

def test_overlap_true_only(service):
    result = service.analyze('I am from police. Transfer now or you will be arrested.')
    yes = adjust_context_overlap(result, PaymentContext(claimed_authority=True, threatened_consequences=True, urgent_payment_requested=True))
    no = adjust_context_overlap(result, PaymentContext(claimed_authority=False, threatened_consequences=False, urgent_payment_requested=False))
    assert .5 <= yes['discount_factor'] < 1
    assert yes['adjusted_psychology_risk'] < no['adjusted_psychology_risk']
    assert no['overlapping_techniques'] == []

@pytest.mark.parametrize('text', [None, '', '   '])
def test_missing_text(service, text):
    result = service.analyze(text)
    assert result['psychology_risk'] == 0
    assert not result['message_available']

def test_rule_fallback():
    result = PsychologyService().analyze('I am from police. Transfer now or you will be arrested.')
    assert result['psychology_risk'] > 80
    assert not result['model_available']
    assert result['ml_probabilities'] is None

def test_ml_alone_cannot_claim_supported_high_risk_combo():
    scores = dict.fromkeys(get_psychology_labels(), .9)
    rules = dict.fromkeys(get_psychology_labels(), 0.0)
    result = calculate_psychology_risk(scores, rule_scores=rules)
    assert result['psychology_risk'] <= 45
    assert 'authority_fear_urgency_combination' not in result['reason_codes']
