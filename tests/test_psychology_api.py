"""Standalone and contextual API integration with startup fallback."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.schemas.psychology import PsychologyResult

@pytest.fixture(scope='module')
def client():
    with TestClient(create_app()) as instance:
        yield instance

def test_text_endpoint(client):
    with patch('pandas.read_csv', side_effect=AssertionError('disk IO per request')):
        response = client.post('/api/v1/analyze/psychology', json={'message': 'Main RBI se bol raha hu. Abhi transfer karo warna account freeze ho jayega.'})
    assert response.status_code == 200, response.text
    result = PsychologyResult.model_validate(response.json())
    assert {'authority', 'fear', 'urgency'} <= set(result.detected_techniques)

@pytest.mark.parametrize('payload', [{}, {'message': None}, {'message': '   '}])
def test_missing_message(client, payload):
    response = client.post('/api/v1/analyze/psychology', json=payload)
    assert response.status_code == 200
    assert response.json()['psychology_risk'] == 0

@pytest.mark.parametrize('payload', [{'message': 'x' * 4001}, {'message': 42}, {'message': 'hello', 'otp': '123'}])
def test_validation(client, payload):
    assert client.post('/api/v1/analyze/psychology', json=payload).status_code == 422

def test_independent_rule_fallback():
    with patch('backend.app.main.PsychologyModel', side_effect=FileNotFoundError('no model')), patch('backend.app.main.TransactionModel', side_effect=FileNotFoundError('no payments')):
        with TestClient(create_app()) as client:
            assert client.get('/ready').status_code == 503
            response = client.post('/api/v1/analyze/psychology', json={'message': 'I am from police. Transfer now or you will be arrested.'})
            assert response.status_code == 200
            assert response.json()['psychology_risk'] > 80
            assert not response.json()['model_available']

def test_contextual_integration_and_legacy_endpoint(client):
    transaction = dict(sender_id='A0001', receiver_id='A1006', amount=85000,
        timestamp='2026-01-30T23:31:50+00:00', device_id='D0001', payment_type='bank_transfer')
    context = dict(payment_reason='government', claimed_authority=True, authority_type='police',
                   urgent_payment_requested=True, threatened_consequences=True, requested_secrecy=True)
    response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context,
        message='I am from Cyber Crime. Your Aadhaar is involved in money laundering. Transfer 85000 immediately or you will be arrested. Do not tell anyone.'))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['psychology']['psychology_risk'] >= 90
    assert result['scenario_psychology_alignment'] >= .75
    assert result['psychology_overlap_adjustment']['discount_factor'] < 1
    assert 0 <= result['extended_risk'] <= 100
    missing = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context)).json()
    assert missing['extended_risk'] == missing['extended_preliminary_risk']
    assert missing['psychology']['psychology_risk'] == 0
    old = client.post('/api/v1/risk/preliminary', json=transaction)
    assert old.status_code == 200
    assert isinstance(old.json()['transaction_risk'], (int, float))
    assert 'psychology' not in old.json()


def test_graph_account_api_and_grouped_contextual(client):
    response = client.get('/api/v1/accounts/A1006/graph-risk')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['account_id'] == 'A1006'
    assert 0 <= result['graph_risk'] <= 100
    assert 'unique_incoming_senders' in result['features']
    assert result['as_of'].endswith('+00:00')
    at = client.get('/api/v1/accounts/A1006/graph-risk?at=2026-01-30T23%3A31%3A50%2B00%3A00')
    assert at.status_code == 200
    assert client.get('/api/v1/accounts/UNKNOWN/graph-risk').status_code == 404
    assert client.get('/api/v1/accounts/A1006/graph-risk?at=2026-01-30T23:31:50').status_code == 422

    transaction = dict(sender_id='A0001', receiver_id='A1006', amount=85000,
        timestamp='2026-01-30T23:31:50+00:00', device_id='D0001', payment_type='bank_transfer')
    context = dict(payment_reason='government', claimed_authority=True, authority_type='police',
                   urgent_payment_requested=True, threatened_consequences=True)
    full = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context,
        message='I am from police. Transfer now or you will be arrested.'))
    assert full.status_code == 200, full.text
    data = full.json()
    assert data['graph_risk'] is not None
    assert set(data['grouped_scores']) == {'user_side','recipient_side','manipulation_side'}
    assert 0 <= data['overall_risk'] <= 100
    assert data['overall_risk_level'] in {'LOW','MEDIUM','HIGH','CRITICAL'}
