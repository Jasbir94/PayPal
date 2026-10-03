"""Read-only, indexed in-memory repository loaded once from synthetic CSVs."""
from pathlib import Path
import numpy as np
import pandas as pd
from backend.app.config.risk_config import DATA_DIR
from backend.app.utils.data_validation import validate_datasets


class DataRepository:
    """Profiles are simulated pre-observation snapshots, not live account state."""

    def __init__(self, transactions: pd.DataFrame, accounts: pd.DataFrame):
        validate_datasets(transactions, accounts)
        self.transactions = transactions.copy()
        self.transactions['timestamp'] = pd.to_datetime(self.transactions.timestamp, utc=True)
        self.transactions = self.transactions.sort_values(['timestamp', 'transaction_id']).reset_index(drop=True)
        self.accounts = accounts.copy().set_index('account_id', drop=False)
        self.accounts['created_at'] = pd.to_datetime(self.accounts.created_at, utc=True)
        self.start = self.transactions.timestamp.min()
        self.end = self.transactions.timestamp.max()
        self._senders = self._index('sender_id')
        self._receivers = self._index('receiver_id')
        self._empty = self.transactions.iloc[:0]

    @classmethod
    def load(cls, directory: Path = DATA_DIR) -> 'DataRepository':
        return cls(pd.read_csv(directory / 'transactions.csv'), pd.read_csv(directory / 'accounts.csv'))

    def _index(self, column: str) -> dict[str, tuple[pd.DataFrame, np.ndarray]]:
        return {str(key): (frame, frame.timestamp.astype('int64').to_numpy())
                for key, frame in self.transactions.groupby(column, sort=False)}

    def account(self, account_id: str, timestamp: pd.Timestamp | None = None) -> dict:
        if account_id not in self.accounts.index:
            raise KeyError(f'Unknown account: {account_id}')
        result = self.accounts.loc[account_id].to_dict()
        if timestamp is not None and result['created_at'] > timestamp:
            raise ValueError(f'Account {account_id} did not exist at the payment timestamp')
        return result

    def _before(self, index: dict, account_id: str, timestamp: pd.Timestamp,
                exclude_id: str | None = None) -> pd.DataFrame:
        if account_id not in index:
            return self._empty.copy()
        frame, times = index[account_id]
        stop = int(np.searchsorted(times, timestamp.value, side='left'))
        result = frame.iloc[:stop]
        if exclude_id:
            result = result[result.transaction_id != exclude_id]
        return result.copy()

    def sender_history(self, sender_id: str, timestamp: pd.Timestamp,
                       exclude_id: str | None = None) -> pd.DataFrame:
        return self._before(self._senders, sender_id, timestamp, exclude_id)

    def recipient_history(self, receiver_id: str, timestamp: pd.Timestamp,
                          exclude_id: str | None = None) -> pd.DataFrame:
        incoming = self._before(self._receivers, receiver_id, timestamp, exclude_id)
        outgoing = self._before(self._senders, receiver_id, timestamp, exclude_id)
        return pd.concat([incoming, outgoing]).drop_duplicates('transaction_id')
