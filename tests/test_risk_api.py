"""Real artifact integration plus validation, caching and availability behavior."""
from unittest.mock import patch
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app, create_app
from backend.app.schemas.risk import PreliminaryRiskResponse
from backend.app.database.repository import DataRepository
from backend.app.config.risk_config import risk_level, TRANSACTION_FEATURES, RECIPIENT_FEATURES
from ml.training import assign_splits


@pytest.fixture(scope='module')
def client():
    with TestClient(app) as instance:
        assert instance.get('/ready').status_code == 200, 'Train both Day 2 models first'
        yield instance


@pytest.fixture
def payment(client):
    row = app.state.risk_service.repository.transactions.iloc[-1]
    return {key: (row[key].isoformat() if key == 'timestamp' else row[key])
            for key in ('sender_id', 'receiver_id', 'amount', 'timestamp', 'device_id', 'payment_type')}


def test_api_response_and_cached_loading(client, payment):
    with patch('pandas.read_csv', side_effect=AssertionError('CSV reread during inference')):
        response = client.post('/api/v1/risk/preliminary', json=payment)
        assert response.status_code == 200, response.text
        result = PreliminaryRiskResponse.model_validate(response.json())
        assert 0 <= result.preliminary_risk <= 100
        assert result.reasons
        assert result.transaction_details.reasons
        assert result.recipient_details.reasons


@pytest.mark.parametrize('change', [{'amount': -1}, {'amount': 0}, {'otp': '123456'},
                                    {'timestamp': '2026-01-10T12:00:00'}])
def test_api_invalid_inputs(client, payment, change):
    assert client.post('/api/v1/risk/preliminary', json=payment | change).status_code == 422


def test_unknown_account(client, payment):
    assert client.post('/api/v1/risk/preliminary', json=payment | {'sender_id': 'UNKNOWN'}).status_code == 404


def test_before_observation_window(client, payment):
    assert client.post('/api/v1/risk/preliminary', json=payment | {'timestamp': '2025-01-01T00:00:00Z'}).status_code == 422


def test_no_model_training_fallback():
    with patch('backend.app.main.TransactionModel', side_effect=FileNotFoundError('missing artifact')):
        with TestClient(create_app()) as instance:
            assert instance.get('/health').status_code == 200
            assert instance.get('/ready').status_code == 503
            payment = dict(sender_id='A0001', receiver_id='A0002', amount=100,
                           timestamp='2026-01-30T12:00:00Z', device_id='D0001', payment_type='upi')
            assert instance.post('/api/v1/risk/preliminary', json=payment).status_code == 503


def test_level_boundaries():
    assert [risk_level(value) for value in (0, 29, 30, 59, 60, 79, 80, 100)] == [
        'LOW', 'LOW', 'MEDIUM', 'MEDIUM', 'HIGH', 'HIGH', 'CRITICAL', 'CRITICAL']


def test_model_feature_allowlists():
    forbidden = {'is_fraud', 'fraud_type', 'is_known_mule', 'is_suspicious', 'target', 'entity_id'}
    assert not forbidden.intersection(TRANSACTION_FEATURES + RECIPIENT_FEATURES)
    assert 'amount' not in TRANSACTION_FEATURES


def test_recipient_split_has_no_account_overlap():
    frame = pd.DataFrame({'entity_id': [f'A{i}' for i in range(100)],
                          'target': [0]*80 + [1]*20})
    data = assign_splits(frame, 'recipient')
    groups = [set(data.loc[data.split == name, 'entity_id']) for name in ('train', 'validation', 'test')]
    assert not (groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])


def test_missing_columns_fail_clearly():
    with pytest.raises(ValueError, match='Missing critical dataset columns'):
        DataRepository(pd.DataFrame({'amount': [100]}), pd.DataFrame({'account_id': ['A']}))
