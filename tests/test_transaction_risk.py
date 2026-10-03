"""Relative behavior, cold starts, temporal leakage and rule explanations."""
import math
import pandas as pd
import pytest
from backend.app.features.transaction_features import (
    calculate_amount_ratio, calculate_amount_deviation, calculate_sender_average_amount,
    calculate_recent_average_amount, calculate_recent_transaction_count,
    is_first_time_recipient, extract_transaction_features)
from backend.app.rules.transaction_rules import score_transaction_rules
from backend.app.services.transaction_service import TransactionService
from backend.app.services.risk_service import combine_risk


class ConstantModel:
    def __init__(self, value=.05):
        self.value = value

    def probability(self, features):
        return self.value


@pytest.fixture
def empty_history():
    return pd.DataFrame(columns=['transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp', 'device_id'])


@pytest.fixture
def profile():
    return {'account_id': 'A', 'average_transaction_amount': 1800, 'usual_device': 'D',
            'usual_recipients': 'B', 'normal_hour_start': 8, 'normal_hour_end': 22}


@pytest.fixture
def payment():
    return dict(transaction_id='T', sender_id='A', receiver_id='B', amount=1500,
                timestamp=pd.Timestamp('2026-01-10T12:00:00Z'), device_id='D')


def test_ratios_and_zero_baseline():
    assert calculate_amount_ratio(20000, 800) == 25
    assert calculate_amount_ratio(60000, 50000) == 1.2
    assert calculate_amount_ratio(100, 0) == 1
    assert math.isfinite(calculate_amount_ratio(100, 0))
    assert calculate_amount_deviation(20000, 800) == 24


def test_normal_scenario(empty_history, profile, payment):
    result = TransactionService(ConstantModel()).score_transaction(payment, empty_history, profile)
    assert result['score'] < 30
    assert result['rule_score'] == 0
    assert result['reasons']
    combined = combine_risk(result, dict(score=3, ml_probability=.05, rule_score=0,
                                        reasons=['no_recipient_rule_signals']))
    assert combined['risk_level'] == 'LOW'


def test_large_legitimate_relative_amount(empty_history, profile, payment):
    profile['average_transaction_amount'] = 40000
    payment['amount'] = 55000
    features = extract_transaction_features(payment, empty_history, profile)
    assert features['amount_ratio'] == 1.375
    assert score_transaction_rules(features)['score'] == 0
    result = TransactionService(ConstantModel()).score_transaction(payment, empty_history, profile)
    assert result['score'] < 80


def test_late_hour_alone_does_not_add_risk(empty_history, profile, payment):
    payment['timestamp'] = pd.Timestamp('2026-01-10T23:00:00Z')
    features = extract_transaction_features(payment, empty_history, profile)
    assert features['outside_usual_hours'] == 1
    assert score_transaction_rules(features)['score'] == 0


def test_first_time_and_recent_features(empty_history, profile, payment):
    assert not is_first_time_recipient('B', empty_history, 'B|C')
    assert is_first_time_recipient('NEW', empty_history)
    history = pd.DataFrame([
        payment | {'transaction_id': 'OLD', 'amount': 1000, 'timestamp': payment['timestamp'] - pd.Timedelta(minutes=10)},
        payment | {'transaction_id': 'FUTURE', 'amount': 9999999, 'timestamp': payment['timestamp'] + pd.Timedelta(minutes=1)},
        payment | {'transaction_id': 'TIE', 'amount': 9999999},
    ])
    features = extract_transaction_features(payment, history, profile)
    assert features['sender_average_amount'] == 1000
    assert features['transactions_last_1h'] == 1
    assert features['transactions_last_24h'] == 1
    assert features['recipient_seen_before'] == 1
    assert calculate_recent_transaction_count(history, payment['timestamp'], 1) == 1
    assert calculate_recent_average_amount(history, payment['timestamp']) == 1000
    assert calculate_sender_average_amount(empty_history, 1800) == 1800


def test_suspicious_rule_reasons_and_bounds(empty_history, profile, payment):
    profile['average_transaction_amount'] = 3000
    payment.update(amount=90000, receiver_id='NEW', device_id='NEW_DEVICE')
    features = extract_transaction_features(payment, empty_history, profile)
    features['transactions_last_1h'] = 20
    rules = score_transaction_rules(features)
    assert rules['score'] == 100
    assert 'amount_much_higher_than_normal' in rules['reasons']
    assert 'first_time_recipient' in rules['reasons']
    result = TransactionService(ConstantModel(.95)).score_transaction(payment, empty_history, profile)
    assert 0 <= result['score'] <= 100
