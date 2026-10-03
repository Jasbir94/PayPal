"""Context boundaries, stacked evidence and legitimate-like counterexamples."""
import pytest
from pydantic import ValidationError
from backend.app.schemas.context import PaymentContext, ContactChannel, AuthorityType
from backend.app.schemas.transaction import PaymentReason
from backend.app.rules.context_rules import calculate_context_risk
from backend.app.rules.scenario_rules import classify_scenario_rules


@pytest.mark.parametrize('reason', [item.value for item in PaymentReason] + ['romance', 'marketplace', 'tech_support', 'emergency'])
def test_supported_payment_reasons(reason):
    assert PaymentContext(payment_reason=reason).payment_reason == reason


@pytest.mark.parametrize('channel', list(ContactChannel))
def test_supported_channels(channel):
    assert PaymentContext(contact_channel=channel).contact_channel == channel


@pytest.mark.parametrize('authority', list(AuthorityType))
def test_supported_authorities(authority):
    assert PaymentContext(authority_type=authority).authority_type == authority


@pytest.mark.parametrize('invalid', [{'payment_reason': 'crypto_magic'}, {'contact_channel': 'fax'},
    {'authority_type': 'unknown_agency'}, {'relationship_duration_days': -1},
    {'otp': '123456'}, {'urgent_payment_requested': 'yes'}, {'user_message': 'x'*4001}])
def test_invalid_context_rejected(invalid):
    with pytest.raises(ValidationError):
        PaymentContext(**invalid)


def test_optional_fields_and_empty_message():
    assert PaymentContext().contacted_by_unknown_person is None
    assert PaymentContext(user_message='   ').user_message is None


def test_government_stacked_evidence():
    context = PaymentContext(payment_reason='government', contacted_by_unknown_person=True,
        claimed_authority=True, authority_type='police', urgent_payment_requested=True,
        threatened_consequences=True, requested_secrecy=True)
    result = calculate_context_risk(context)
    assert 80 <= result['score'] <= 100
    assert 'authority_claim' in result['reasons']
    assert result['evidence']['threatened_consequences']
    assert classify_scenario_rules(context)['scenario'] == 'government_impersonation'


@pytest.mark.parametrize('flag', ['contacted_by_unknown_person', 'claimed_authority', 'urgent_payment_requested',
                                 'threatened_consequences', 'promised_profit', 'requested_secrecy',
                                 'asked_to_install_remote_access', 'asked_to_pay_fee'])
def test_single_signal_not_maximum(flag):
    assert calculate_context_risk(PaymentContext(**{flag: True}))['score'] < 60


def test_investment_and_legitimate_counterexample():
    suspicious = PaymentContext(payment_reason='investment', promised_profit=True, contacted_by_unknown_person=True)
    assert calculate_context_risk(suspicious)['score'] >= 60
    assert classify_scenario_rules(suspicious)['scenario'] == 'investment_scam'
    legitimate = PaymentContext(payment_reason='investment', contacted_by_unknown_person=False,
        promised_profit=False, urgent_payment_requested=False, claimed_authority=False)
    assert calculate_context_risk(legitimate)['score'] == 0
    assert classify_scenario_rules(legitimate)['scenario'] == 'normal_or_unknown'


def test_no_guarantee_inferred_from_ordinary_profit_promise():
    context = PaymentContext(payment_reason='investment', promised_profit=True)
    assert 'promised_profit_claim' in calculate_context_risk(context)['reasons']
    assert 'guaranteed_profit_claim' not in calculate_context_risk(context)['reasons']


def test_job_without_message_and_remote_access():
    job = PaymentContext(payment_reason='job', contacted_by_unknown_person=True, asked_to_pay_fee=True)
    assert classify_scenario_rules(job)['scenario'] == 'fake_job_scam'
    tech = PaymentContext(payment_reason='tech_support', contacted_by_unknown_person=True,
        asked_to_install_remote_access=True, fund_transfer_requested=True)
    assert calculate_context_risk(tech)['score'] >= 60
    assert classify_scenario_rules(tech)['scenario'] == 'tech_support_scam'


def test_family_payment_and_score_bounds():
    family = PaymentContext(payment_reason='family', contacted_by_unknown_person=False,
        urgent_payment_requested=False, threatened_consequences=False)
    assert calculate_context_risk(family)['score'] == 0
    intense = PaymentContext(**(family.model_dump() | dict(payment_reason='investment', contacted_by_unknown_person=True,
        claimed_authority=True, urgent_payment_requested=True, threatened_consequences=True,
        promised_profit=True, guaranteed_returns_promised=True, requested_secrecy=True)))
    assert calculate_context_risk(intense, new_recipient=True)['score'] == 100
