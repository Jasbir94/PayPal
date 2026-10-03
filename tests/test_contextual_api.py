"""Contextual API integration, missing-text handling and Day 2 compatibility."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.schemas.risk import ContextualRiskResponse


@pytest.fixture(scope='module')
def client():
    with TestClient(create_app()) as instance:
        assert instance.get('/ready').status_code == 200
        yield instance


@pytest.fixture
def transaction():
    return dict(sender_id='A0001', receiver_id='A1006', amount=85000,
        timestamp='2026-01-30T23:31:50+00:00', device_id='D0001', payment_type='bank_transfer')


@pytest.fixture
def authority_context():
    return dict(payment_reason='government', contacted_by_unknown_person=True, contact_channel='phone',
        claimed_authority=True, authority_type='police', urgent_payment_requested=True,
        threatened_consequences=True, requested_secrecy=True, fund_transfer_requested=True)


def test_government_contextual_api(client, transaction, authority_context):
    with patch('pandas.read_csv', side_effect=AssertionError('Unexpected CSV read during inference')):
        response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction,
            context=authority_context, message='Cyber Crime Department says my Aadhaar is involved in illegal transfers. Pay immediately to avoid arrest.'))
    assert response.status_code == 200, response.text
    result = ContextualRiskResponse.model_validate(response.json())
    assert result.scenario.type == 'government_impersonation'
    assert result.context_risk.score >= 80
    assert result.risk_level == 'CRITICAL'
    assert result.extended_preliminary_risk >= 80
    assert result.reason_codes
    assert result.transaction_risk.evidence
    assert result.recipient_risk.evidence
    assert result.context_risk.evidence


def test_message_optional_and_day2_still_works(client, transaction):
    response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction,
        context=dict(payment_reason='job', asked_to_pay_fee=True, contacted_by_unknown_person=True)))
    assert response.status_code == 200
    assert response.json()['scenario']['type'] == 'fake_job_scam'
    preliminary = client.post('/api/v1/risk/preliminary', json=transaction)
    assert preliminary.status_code == 200
    assert isinstance(preliminary.json()['transaction_risk'], (int, float))
    assert 'extended_preliminary_risk' not in preliminary.json()


def test_known_family_and_legitimate_investment(client):
    transaction = dict(sender_id='A0242', receiver_id='A0928', amount=2381.48,
        timestamp='2026-01-30T23:31:49+00:00', device_id='D0242', payment_type='bank_transfer')
    for reason in ('family', 'investment'):
        context = dict(payment_reason=reason, contacted_by_unknown_person=False, promised_profit=False,
                       urgent_payment_requested=False, threatened_consequences=False)
        response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context))
        assert response.status_code == 200
        assert response.json()['context_risk']['score'] == 0
        assert response.json()['risk_level'] == 'LOW'


def test_message_source_validation(client, transaction):
    context = dict(payment_reason='job', asked_to_pay_fee=True, user_message='registration fee request')
    alias = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context))
    assert alias.status_code == 200
    conflict = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context, message='different story'))
    assert conflict.status_code == 422


@pytest.mark.parametrize('change', [{'message': 'x'*4001}, {'context': {'payment_reason': 'invalid'}},
                                   {'context': {'otp': '123456'}}])
def test_invalid_contextual_request(client, transaction, change):
    request = dict(transaction=transaction, context={}) | change
    assert client.post('/api/v1/risk/contextual', json=request).status_code == 422


def test_rule_fallback_preserves_day2_availability(transaction, authority_context):
    with patch('backend.app.main.ScenarioModel', side_effect=FileNotFoundError('missing text artifact')):
        with TestClient(create_app()) as fallback:
            assert fallback.get('/ready').status_code == 200
            result = fallback.post('/api/v1/risk/contextual', json=dict(transaction=transaction,
                context=authority_context, message='Police requested an urgent transfer'))
            assert result.status_code == 200
            assert result.json()['scenario']['type'] == 'government_impersonation'
            assert 'text_model_unavailable_rule_fallback' in result.json()['scenario']['reason_codes']
            assert fallback.post('/api/v1/risk/preliminary', json=transaction).status_code == 200


def test_missing_context_does_not_erase_existing_risk(client, transaction):
    baseline = client.post('/api/v1/risk/preliminary', json=transaction).json()
    response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context={}))
    assert response.status_code == 200
    result = response.json()
    assert result['extended_preliminary_risk'] >= baseline['preliminary_risk']
    assert result['context_risk']['context_available'] is False
    assert 'day2_risk_retained_missing_context' in result['reason_codes']
