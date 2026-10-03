"""Fail fast on incomplete or inconsistent Day 1 datasets."""
import numpy as np
import pandas as pd
from scripts.config import FRAUD_TYPES

def validate_datasets(transactions: pd.DataFrame, accounts: pd.DataFrame) -> dict[str, int]:
    required_transactions = {
        'transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp', 'device_id',
        'payment_type', 'payment_reason', 'first_time_recipient', 'sender_average_amount',
        'account_age_days', 'unique_senders_24h', 'incoming_transactions_24h',
        'outgoing_ratio', 'fraud_reports', 'is_fraud', 'fraud_type',
    }
    required_accounts = {
        'account_id', 'created_at', 'fraud_report_count', 'is_known_mule', 'is_suspicious',
        'average_transaction_amount', 'normal_hour_start', 'normal_hour_end', 'usual_device',
        'usual_recipients', 'outgoing_ratio', 'average_holding_minutes',
    }
    missing = {'transactions': sorted(required_transactions - set(transactions.columns)),
               'accounts': sorted(required_accounts - set(accounts.columns))}
    if any(missing.values()):
        raise ValueError(f'Missing critical dataset columns: {missing}')
    if transactions.empty or accounts.empty:
        raise ValueError('Datasets must not be empty')
    numeric = ['amount', 'sender_average_amount', 'account_age_days', 'unique_senders_24h',
               'incoming_transactions_24h', 'outgoing_ratio', 'fraud_reports', 'is_fraud']
    account_numeric = ['fraud_report_count', 'average_transaction_amount', 'outgoing_ratio',
                       'average_holding_minutes', 'normal_hour_start', 'normal_hour_end']
    for frame, columns in ((transactions, numeric), (accounts, account_numeric)):
        for column in columns:
            if not pd.api.types.is_numeric_dtype(frame[column]) or not np.isfinite(frame[column]).all():
                raise ValueError(f'Column {column} must contain finite numeric values')
    if not transactions.is_fraud.between(0, 1).all() or transactions.is_fraud.nunique() != 2:
        raise ValueError('Expected both legitimate and fraud labels')
    if not .01 <= transactions.is_fraud.mean() <= .25:
        raise ValueError('Unexpected synthetic fraud distribution; expected 1–25%')
    timestamps = pd.to_datetime(transactions.timestamp, utc=True, errors='coerce')
    created = pd.to_datetime(accounts.set_index('account_id').created_at, utc=True, errors='coerce')
    checks = {
        'invalid_sender_averages': int((transactions.sender_average_amount <= 0).sum()),
        'invalid_account_outgoing_ratio': int((~accounts.outgoing_ratio.between(0, 1)).sum()),
        'negative_reports': int((transactions.fraud_reports < 0).sum() + (accounts.fraud_report_count < 0).sum()),
        'negative_activity': int((transactions.incoming_transactions_24h < 0).sum()
                                 + (transactions.unique_senders_24h < 0).sum()),
        'invalid_profiles': int((accounts.average_transaction_amount <= 0).sum()
                                + (accounts.average_holding_minutes < 0).sum()
                                + (~accounts.normal_hour_start.between(0, 23)).sum()
                                + (~accounts.normal_hour_end.between(1, 24)).sum()
                                + (accounts.normal_hour_start >= accounts.normal_hour_end).sum()),
        'invalid_account_labels': int((~accounts.is_known_mule.isin([True, False])).sum()
                                      + (~accounts.is_suspicious.isin([True, False])).sum()),
        'invalid_first_time_flags': int((~transactions.first_time_recipient.isin([True, False])).sum()),
        'missing_values': int(transactions.isna().sum().sum() + accounts.isna().sum().sum()),
        'duplicate_transaction_ids': int(transactions.transaction_id.duplicated().sum()),
        'duplicate_account_ids': int(accounts.account_id.duplicated().sum()),
        'nonpositive_amounts': int((transactions.amount <= 0).sum()),
        'invalid_timestamps': int(timestamps.isna().sum() + created.isna().sum()),
        'future_timestamps': int((timestamps > pd.Timestamp.now(tz='UTC')).sum()),
        'unknown_accounts': int((~transactions.sender_id.isin(accounts.account_id)).sum()
                                + (~transactions.receiver_id.isin(accounts.account_id)).sum()),
        'negative_account_ages': int((transactions.account_age_days < 0).sum()),
        'invalid_labels': int((~transactions.is_fraud.isin([0, 1])).sum()),
        'invalid_scenarios': int((~transactions.fraud_type.isin(['normal', *FRAUD_TYPES])).sum()),
        'inconsistent_labels': int(((transactions.is_fraud == 0) != (transactions.fraud_type == 'normal')).sum()),
        'impossible_velocity': int((transactions.unique_senders_24h > transactions.incoming_transactions_24h).sum()),
        'invalid_outgoing_ratio': int((~transactions.outgoing_ratio.between(0, 1)).sum()),
    }
    if not checks['unknown_accounts'] and not checks['duplicate_account_ids']:
        checks['payments_before_account_creation'] = int(
            (timestamps < transactions.sender_id.map(created)).sum() +
            (timestamps < transactions.receiver_id.map(created)).sum())
    if not checks['unknown_accounts'] and not checks['duplicate_account_ids']:
        expected_ages = (timestamps - transactions.receiver_id.map(created)).dt.days
        checks['inconsistent_account_ages'] = int((expected_ages != transactions.account_age_days).sum())
    if any(checks.values()):
        raise ValueError(f'Dataset integrity failures: {checks}')
    return checks
