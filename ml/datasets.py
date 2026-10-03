"""Shared offline feature construction using the exact inference extractors."""
import pandas as pd
from backend.app.database.repository import DataRepository
from backend.app.features.transaction_features import extract_transaction_features
from backend.app.features.recipient_features import calculate_recipient_features


def transaction_dataset(repository: DataRepository) -> pd.DataFrame:
    rows = []
    for payment in repository.transactions.to_dict('records'):
        stamp = payment['timestamp']
        profile = repository.account(payment['sender_id'], stamp)
        history = repository.sender_history(payment['sender_id'], stamp, payment['transaction_id'])
        features = extract_transaction_features(payment, history, profile)
        rows.append(features | {'entity_id': payment['transaction_id'],
                                'timestamp': stamp, 'target': int(payment['is_fraud'])})
    return pd.DataFrame(rows)


def recipient_dataset(repository: DataRepository) -> pd.DataFrame:
    """One snapshot per account prevents account identity leakage across splits.

    is_suspicious is a synthetic proxy label. is_known_mule only marks a random
    subset of suspicious recipients, so treating unmarked ones as genuine negatives
    would mislabel known synthetic suspicious accounts.
    """
    stamp = repository.end + pd.Timedelta(seconds=1)
    rows = []
    for account_id in repository.accounts.index:
        account = repository.account(account_id, stamp)
        history = repository.recipient_history(account_id, stamp)
        features = calculate_recipient_features(account, history, stamp)
        rows.append(features | {'entity_id': account_id, 'timestamp': stamp,
                                'target': int(account['is_suspicious'])})
    return pd.DataFrame(rows)
