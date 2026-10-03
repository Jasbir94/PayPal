"""Verify realistic sizes, determinism and past-only recipient features."""
import pandas as pd
import pytest
from scripts.config import GeneratorConfig, FRAUD_TYPES
from scripts.generate_transactions import generate_datasets
from scripts.analyze_transactions import validate_datasets
from backend.app.features.transaction_features import add_derived_features, MODEL_FEATURES

@pytest.fixture(scope='module')
def datasets():
    return generate_datasets()

def test_default_generation(datasets):
    transactions, accounts = datasets
    assert len(transactions) == 10000
    assert len(accounts) == 1040
    assert accounts.is_suspicious.sum() == 40
    assert transactions.transaction_id.is_unique
    assert .05 <= transactions.is_fraud.mean() <= .1
    assert set(FRAUD_TYPES) <= set(transactions.fraud_type)
    assert not any(validate_datasets(transactions, accounts).values())
    assert (transactions.loc[transactions.is_fraud == 1, 'amount_ratio'] < 1).any()
    assert (transactions.loc[transactions.is_fraud == 0, 'amount_ratio'] > 3).any()

def test_reproducible():
    config = GeneratorConfig(transactions=300)
    first = generate_datasets(config)
    second = generate_datasets(config)
    for left, right in zip(first, second):
        pd.testing.assert_frame_equal(left, right)

def test_rolling_features(datasets):
    transactions, _ = datasets
    stamps = pd.to_datetime(transactions.timestamp, utc=True)
    for position in [0, 50, 1000, 5000, 9999]:
        row = transactions.iloc[position]
        past = transactions.iloc[:position]
        window = past[(past.receiver_id == row.receiver_id) &
                      (stamps.iloc[:position] >= stamps.iloc[position] - pd.Timedelta(hours=24))]
        assert row.incoming_transactions_24h == len(window)
        assert row.unique_senders_24h == window.sender_id.nunique()

def test_features_do_not_use_targets(datasets):
    transactions, _ = datasets
    changed = transactions.copy()
    changed['is_fraud'] = 1 - changed.is_fraud
    changed['fraud_type'] = 'changed'
    pd.testing.assert_frame_equal(add_derived_features(transactions)[MODEL_FEATURES],
                                  add_derived_features(changed)[MODEL_FEATURES])

def test_analysis_rejects_bad_data(datasets):
    transactions, accounts = datasets
    bad = transactions.copy()
    bad.loc[0, 'amount'] = -1
    with pytest.raises(ValueError):
        validate_datasets(bad, accounts)
