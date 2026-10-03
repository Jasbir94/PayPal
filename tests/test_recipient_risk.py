"""Recipient aggregates, temporal windows and stacked risk evidence."""
import pandas as pd
import pytest
from backend.app.features.recipient_features import (
    calculate_account_age, count_unique_senders, calculate_outgoing_ratio,
    calculate_incoming_velocity, calculate_recipient_features)
from backend.app.rules.recipient_rules import score_recipient_rules
from backend.app.services.recipient_service import RecipientService
from backend.app.services.transaction_service import TransactionService
from backend.app.services.risk_service import combine_risk
from tests.test_transaction_risk import ConstantModel


@pytest.fixture
def suspicious_features():
    return dict(account_age_days=5, incoming_transactions_1h=12, incoming_transactions_24h=62,
        unique_senders_1h=10, unique_senders_24h=45, incoming_amount_24h=720000,
        outgoing_amount_24h=676800, outgoing_ratio=.94, observed_outgoing_ratio=.94,
        fraud_report_count=3, transaction_velocity=62/24, sender_diversity=45/62,
        average_incoming_amount=720000/62, median_incoming_amount=10000,
        inflow_outflow_imbalance=.03, average_holding_minutes=20)


def test_account_age():
    assert calculate_account_age('2026-01-01T00:00:00Z', '2026-01-06T00:00:00Z') == 5
    with pytest.raises(ValueError):
        calculate_account_age('2026-02-01T00:00:00Z', '2026-01-01T00:00:00Z')


def test_recipient_history_excludes_future():
    stamp = pd.Timestamp('2026-01-06T12:00:00Z')
    account = dict(account_id='M', created_at='2026-01-01T00:00:00Z', fraud_report_count=0,
                   outgoing_ratio=.2, average_holding_minutes=500)
    history = pd.DataFrame([
        dict(sender_id='A', receiver_id='M', amount=100, timestamp=stamp-pd.Timedelta(minutes=20)),
        dict(sender_id='B', receiver_id='M', amount=200, timestamp=stamp-pd.Timedelta(hours=2)),
        dict(sender_id='M', receiver_id='C', amount=150, timestamp=stamp-pd.Timedelta(minutes=10)),
        dict(sender_id='Z', receiver_id='M', amount=999999, timestamp=stamp),
        dict(sender_id='Z', receiver_id='M', amount=999999, timestamp=stamp+pd.Timedelta(seconds=1)),
        dict(sender_id='Z', receiver_id='M', amount=999999, timestamp=stamp-pd.Timedelta(hours=25)),
    ])
    features = calculate_recipient_features(account, history, stamp)
    assert features['incoming_transactions_1h'] == 1
    assert features['incoming_transactions_24h'] == 2
    assert features['unique_senders_24h'] == 2
    assert features['incoming_amount_24h'] == 300
    assert features['outgoing_ratio'] == .5
    assert features['average_incoming_amount'] == 150
    assert features['median_incoming_amount'] == 150
    assert count_unique_senders(history.iloc[:2]) == 2
    assert calculate_incoming_velocity(history.iloc[:2], 1) == 2


def test_outgoing_ratio_bounds():
    assert calculate_outgoing_ratio(100, 95) == .95
    assert calculate_outgoing_ratio(100, 500) == 1
    assert calculate_outgoing_ratio(0, 500) == 0


def test_suspicious_recipient(suspicious_features):
    result = RecipientService(ConstantModel(.95), None).score_features(suspicious_features)
    assert result['score'] >= 80
    assert result['rule_score'] == 100
    assert 'many_unique_senders' in result['reasons']
    assert 'high_outgoing_ratio' in result['reasons']
    assert 0 <= result['score'] <= 100


def test_combined_critical(suspicious_features):
    empty = pd.DataFrame(columns=['sender_id', 'receiver_id', 'amount', 'timestamp', 'device_id'])
    payment = dict(sender_id='A', receiver_id='M', amount=90000, device_id='D',
                   timestamp='2026-01-06T12:00:00Z')
    profile = dict(average_transaction_amount=3000, usual_device='D')
    transaction = TransactionService(ConstantModel(.95)).score_transaction(payment, empty, profile)
    recipient = RecipientService(ConstantModel(.95), None).score_features(suspicious_features)
    assert combine_risk(transaction, recipient)['risk_level'] == 'CRITICAL'


def test_established_recipient_is_not_max_score(suspicious_features):
    normal = suspicious_features | dict(account_age_days=1460, unique_senders_24h=1,
        incoming_transactions_24h=1, incoming_transactions_1h=0, outgoing_ratio=.2,
        observed_outgoing_ratio=.2, fraud_report_count=0, average_holding_minutes=500)
    assert score_recipient_rules(normal)['score'] == 0
    assert RecipientService(ConstantModel(), None).score_features(normal)['score'] < 30


def test_real_models_preserve_extreme_recipient_evidence(suspicious_features):
    from backend.app.models.transaction_model import TransactionModel
    from backend.app.models.recipient_model import RecipientModel
    empty = pd.DataFrame(columns=['sender_id', 'receiver_id', 'amount', 'timestamp', 'device_id'])
    payment = dict(sender_id='A', receiver_id='M', amount=90000, device_id='D',
                   timestamp='2026-01-06T12:00:00Z')
    profile = dict(average_transaction_amount=3000, usual_device='D')
    transaction = TransactionService(TransactionModel()).score_transaction(payment, empty, profile)
    recipient = RecipientService(RecipientModel(), None).score_features(suspicious_features)
    assert recipient['score'] >= 80
    assert combine_risk(transaction, recipient)['risk_level'] == 'CRITICAL'
    assert 'strong_rule_evidence_floor' in recipient['reasons']


def test_uncalibrated_low_ml_cannot_erase_multiple_strong_signals(suspicious_features):
    result = RecipientService(ConstantModel(0), None).score_features(suspicious_features)
    assert result['score'] == 100
    assert 'strong_rule_evidence_floor' in result['reasons']
