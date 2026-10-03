# Day 2 — complete file-by-file implementation

Run all commands from app-shield. Python 3.12.10 was used locally. Train models before running the full integration suite.

## Commands

~~~powershell
.venv\Scripts\python -m pip install -r backend/requirements.lock.txt
.venv\Scripts\python -m ml.transaction.train
.venv\Scripts\python -m ml.recipient.train
.venv\Scripts\python -m ml.transaction.evaluate
.venv\Scripts\python -m ml.recipient.evaluate
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m scripts.benchmark_risk
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# In another terminal while the server runs:
.venv\Scripts\python -m scripts.smoke_risk_api
~~~

## Design decisions

History is strictly earlier than the scoring timestamp. Both training and inference reuse the same extractors. Explicit feature allowlists exclude labels and identity fields. Transaction splits are chronological; recipient snapshots are split by account. Synthetic pre-observation profiles supply cold-start averages, reports, outflow and holding approximations. These must be replaced by timestamped ledger/profile/report data for production. Model and threshold selection use validation results, never test results. Fused scores are evidence indices, not final APP probabilities. Strong rules (80+) set a minimum component score so an uncalibrated model cannot erase multiple extreme signals. See README for full limitations.

## backend/app/config/__init__.py

Empty package initializer enabling module imports.

~~~python

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## ml/__init__.py

Empty package initializer enabling module imports.

~~~python

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## ml/transaction/__init__.py

Empty package initializer enabling module imports.

~~~python

~~~

Run/test: `.venv\Scripts\python -m ml.transaction.train`.

## ml/recipient/__init__.py

Empty package initializer enabling module imports.

~~~python

~~~

Run/test: `.venv\Scripts\python -m ml.recipient.train`.

## backend/app/config/risk_config.py

Central MVP scoring, feature, and training configuration.

~~~python
"""Central MVP scoring, feature, and training configuration."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / 'data' / 'synthetic'
MODEL_DIR = PROJECT_ROOT / 'saved_models'
REPORT_DIR = PROJECT_ROOT / 'data' / 'processed' / 'day2'
SEED = 42
ML_WEIGHT = 0.60
RULE_WEIGHT = 0.40
TRANSACTION_WEIGHT = 0.45
RECIPIENT_WEIGHT = 0.55
RISK_THRESHOLDS = {'MEDIUM': 30, 'HIGH': 60, 'CRITICAL': 80}
MODEL_REASON_THRESHOLD = 0.5
STRONG_RULE_EVIDENCE_THRESHOLD = 80.0
TRANSACTION_RULES = {
    'extreme_ratio': 10.0, 'high_ratio': 3.0, 'recent_ratio': 3.0,
    'velocity_1h': 5, 'velocity_24h': 15,
    'extreme_points': 60, 'high_points': 25, 'new_recipient_points': 15,
    'recent_points': 10, 'device_points': 10, 'velocity_points': 15,
}
RECIPIENT_RULES = {
    'new_days': 7, 'young_days': 30, 'unique_senders': 20,
    'incoming_1h': 10, 'incoming_24h': 30, 'outgoing_ratio': .85,
    'reports': 2, 'rapid_holding_minutes': 60,
    'new_points': 20, 'young_points': 10, 'diversity_points': 30,
    'velocity_points': 20, 'outgoing_points': 20, 'reports_points': 25,
    'single_report_points': 10, 'rapid_points': 10,
}
# Absolute amount and labels are deliberately excluded from transaction predictors.
TRANSACTION_FEATURES = [
    'amount_ratio', 'amount_vs_recent_average', 'first_time_recipient',
    'device_changed', 'transactions_last_1h', 'transactions_last_24h',
    'recipient_seen_before', 'outside_usual_hours',
]
RECIPIENT_FEATURES = [
    'account_age_days', 'incoming_transactions_1h', 'incoming_transactions_24h',
    'unique_senders_1h', 'unique_senders_24h', 'incoming_amount_24h',
    'outgoing_amount_24h', 'outgoing_ratio', 'observed_outgoing_ratio',
    'fraud_report_count', 'transaction_velocity', 'sender_diversity',
    'average_incoming_amount', 'median_incoming_amount', 'inflow_outflow_imbalance',
    'average_holding_minutes',
]


def risk_level(score: float) -> str:
    for level in ('CRITICAL', 'HIGH', 'MEDIUM'):
        if score >= RISK_THRESHOLDS[level]:
            return level
    return 'LOW'


def clamp_score(score: float) -> float:
    return round(max(0.0, min(100.0, float(score))), 2)


def component_score(probability: float, rule_score: float) -> tuple[float, bool]:
    """Strong stacked evidence cannot be erased by an uncalibrated baseline."""
    blended = ML_WEIGHT * probability * 100 + RULE_WEIGHT * rule_score
    guarded = rule_score >= STRONG_RULE_EVIDENCE_THRESHOLD and blended < rule_score
    return clamp_score(max(blended, rule_score) if guarded else blended), guarded

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/utils/data_validation.py

Fail fast on incomplete or inconsistent Day 1 datasets.

~~~python
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

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## scripts/analyze_transactions.py

Explore synthetic data and fail clearly on integrity violations.

~~~python
"""Explore synthetic data and fail clearly on integrity violations."""
import argparse
from pathlib import Path
import pandas as pd
from backend.app.utils.data_validation import validate_datasets
from scripts.generate_transactions import PROJECT_ROOT


def analysis_report(transactions: pd.DataFrame, accounts: pd.DataFrame) -> str:
    checks = validate_datasets(transactions, accounts)
    summary = transactions.groupby('is_fraud').agg(
        count=('transaction_id', 'size'), average_amount=('amount', 'mean'),
        new_recipient_rate=('first_time_recipient', 'mean'), average_amount_ratio=('amount_ratio', 'mean'))
    return '\n'.join([
        f'Transactions: {len(transactions)}', f'Accounts: {len(accounts)}',
        f'Fraud percentage: {transactions.is_fraud.mean() * 100:.2f}%',
        'Class balance (0 legitimate, 1 fraud):', summary.to_string(),
        'Fraud count by type:', transactions.fraud_type.value_counts().to_string(),
        'Recipient fraud-report distribution (one row per account):',
        accounts.fraud_report_count.value_counts().sort_index().to_string(),
        f'Integrity checks: {checks}',
        'Class imbalance is intentional. Use stratified/temporal evaluation and PR-AUC later.',
        'Synthetic data is for pipeline development; it does not establish real-world model performance.',
    ])

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=PROJECT_ROOT / 'data' / 'synthetic')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = analysis_report(pd.read_csv(args.data_dir / 'transactions.csv'),
                             pd.read_csv(args.data_dir / 'accounts.csv'))
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()

~~~

Run/test: `.venv\Scripts\python -m scripts.analyze_transactions`.

## backend/app/database/repository.py

Read-only, indexed in-memory repository loaded once from synthetic CSVs.

~~~python
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

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/features/transaction_features.py

Features from information available before the current payment.

~~~python
"""Features from information available before the current payment."""
import numpy as np
import pandas as pd

LARGE_DEVIATION_RATIO = 3.0
MODEL_FEATURES = ['amount_ratio', 'is_large_deviation', 'is_new_recipient',
                  'recipient_age_bucket', 'recipient_activity_level', 'recipient_reported']

def add_derived_features(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return a copy; never use labels or known-mule flags as predictors."""
    result = transactions.copy()
    if (result.sender_average_amount <= 0).any():
        raise ValueError('Sender averages must be positive')
    result['amount_ratio'] = result.amount / result.sender_average_amount
    result['is_large_deviation'] = result.amount_ratio > LARGE_DEVIATION_RATIO
    result['is_new_recipient'] = result.first_time_recipient.astype(bool)
    result['recipient_age_bucket'] = pd.cut(result.account_age_days,
        bins=[-1, 7, 30, 180, np.inf], labels=['week', 'month', 'six_months', 'established'])
    result['recipient_activity_level'] = pd.cut(result.incoming_transactions_24h,
        bins=[-1, 5, 20, np.inf], labels=['low', 'medium', 'high'])
    result['recipient_reported'] = result.fraud_reports > 0
    return result


def calculate_amount_ratio(amount: float, average: float) -> float:
    """Unknown/zero baseline yields neutral ratio, not infinity or fabricated risk."""
    return float(amount / average) if average > 0 else 1.0


def calculate_sender_average_amount(history: pd.DataFrame, fallback: float = 0.0) -> float:
    return float(history.amount.mean()) if not history.empty else float(fallback)


def is_first_time_recipient(receiver_id: str, history: pd.DataFrame,
                            usual_recipients: str = '') -> bool:
    known = set(usual_recipients.split('|')) if usual_recipients else set()
    return receiver_id not in known and (history.empty or not history.receiver_id.eq(receiver_id).any())


def calculate_recent_transaction_count(history: pd.DataFrame, timestamp: pd.Timestamp,
                                       hours: int = 24) -> int:
    if history.empty:
        return 0
    return int(((history.timestamp >= timestamp - pd.Timedelta(hours=hours)) &
                (history.timestamp < timestamp)).sum())


def calculate_recent_average_amount(history: pd.DataFrame, timestamp: pd.Timestamp,
                                     hours: int = 24, fallback: float = 0.0) -> float:
    if history.empty:
        return float(fallback)
    recent = history[(history.timestamp >= timestamp - pd.Timedelta(hours=hours)) &
                     (history.timestamp < timestamp)]
    return float(recent.amount.mean()) if not recent.empty else float(fallback)


def calculate_amount_deviation(amount: float, average: float) -> float:
    return calculate_amount_ratio(amount, average) - 1.0


def extract_transaction_features(transaction: dict, history: pd.DataFrame,
                                 sender_profile: dict | None = None) -> dict[str, float]:
    """Extract past-only behavioral features; ignore client-supplied first-time flags.

    Timestamp must carry a timezone. Profile fallback represents Day 1's simulated
    pre-observation average, usual device and usual recipients, not future activity.
    """
    profile = sender_profile or {}
    timestamp = pd.Timestamp(transaction['timestamp'])
    if timestamp.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    timestamp = timestamp.tz_convert('UTC')
    past = history.copy()
    if not past.empty:
        past['timestamp'] = pd.to_datetime(past.timestamp, utc=True)
        past = past[(past.sender_id == transaction['sender_id']) & (past.timestamp < timestamp)]
        if transaction.get('transaction_id'):
            past = past[past.transaction_id != transaction['transaction_id']]
    average = calculate_sender_average_amount(past, float(profile.get('average_transaction_amount', 0)))
    recent_average = calculate_recent_average_amount(past, timestamp, fallback=average)
    first_time = is_first_time_recipient(transaction['receiver_id'], past,
                                         str(profile.get('usual_recipients', '')))
    usual_device = profile.get('usual_device')
    if not usual_device and not past.empty:
        usual_device = past.device_id.mode().iloc[0]
    hour = timestamp.hour
    start, end = int(profile.get('normal_hour_start', 0)), int(profile.get('normal_hour_end', 24))
    amount = float(transaction['amount'])
    return {
        'amount': amount, 'sender_average_amount': average,
        'amount_ratio': calculate_amount_ratio(amount, average),
        'first_time_recipient': int(first_time), 'transaction_hour': hour,
        'device_changed': int(bool(usual_device and transaction['device_id'] != usual_device)),
        'transactions_last_1h': calculate_recent_transaction_count(past, timestamp, 1),
        'transactions_last_24h': calculate_recent_transaction_count(past, timestamp, 24),
        'amount_vs_recent_average': calculate_amount_ratio(amount, recent_average),
        'amount_deviation': calculate_amount_deviation(amount, average),
        'recipient_seen_before': int(not first_time),
        'outside_usual_hours': int(not start <= hour < end),
        'history_count': len(past), 'baseline_available': int(average > 0),
    }

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/features/recipient_features.py

Past-only recipient inflow/outflow features; no network or target features.

~~~python
"""Past-only recipient inflow/outflow features; no network or target features."""
import numpy as np
import pandas as pd


def calculate_account_age(created_at, timestamp) -> int:
    created, current = pd.Timestamp(created_at), pd.Timestamp(timestamp)
    if created.tzinfo is None or current.tzinfo is None:
        raise ValueError('Timezone-aware account and payment timestamps required')
    if current < created:
        raise ValueError('Account creation is after scoring timestamp')
    return int((current - created).days)


def count_unique_senders(incoming: pd.DataFrame) -> int:
    return int(incoming.sender_id.nunique()) if not incoming.empty else 0


def calculate_incoming_velocity(incoming: pd.DataFrame, hours: int = 24) -> float:
    return float(len(incoming) / hours)


def calculate_outgoing_ratio(incoming_amount: float, outgoing_amount: float) -> float:
    """Bounded same-window outflow/inflow ratio; no inflow gives neutral zero.

    Outflows can use prior balances, so this is not proof of rapid onward transfer.
    """
    return min(1.0, max(0.0, outgoing_amount / incoming_amount)) if incoming_amount > 0 else 0.0


def calculate_recipient_features(account: dict, history: pd.DataFrame, timestamp) -> dict[str, float]:
    current = pd.Timestamp(timestamp)
    age = calculate_account_age(account['created_at'], current)
    past = history.copy()
    if not past.empty:
        past['timestamp'] = pd.to_datetime(past.timestamp, utc=True)
        past = past[(past.timestamp < current) & (past.timestamp >= current - pd.Timedelta(hours=24))]
    incoming = past[past.receiver_id == account['account_id']]
    outgoing = past[past.sender_id == account['account_id']]
    hour = incoming[incoming.timestamp >= current - pd.Timedelta(hours=1)]
    inflow, outflow = float(incoming.amount.sum()), float(outgoing.amount.sum())
    observed_ratio = calculate_outgoing_ratio(inflow, outflow)
    # Synthetic mule accounts have little outgoing history. Use the documented
    # pre-observation profile as a separate historical approximation, never a target.
    historical_ratio = float(account.get('outgoing_ratio', 0.0))
    effective_ratio = max(observed_ratio, historical_ratio)
    unique = count_unique_senders(incoming)
    return {
        'account_age_days': age,
        'incoming_transactions_1h': len(hour), 'incoming_transactions_24h': len(incoming),
        'unique_senders_1h': count_unique_senders(hour), 'unique_senders_24h': unique,
        'incoming_amount_24h': inflow, 'outgoing_amount_24h': outflow,
        'outgoing_ratio': effective_ratio, 'observed_outgoing_ratio': observed_ratio,
        'fraud_report_count': int(account.get('fraud_report_count', 0)),
        'transaction_velocity': calculate_incoming_velocity(incoming),
        'sender_diversity': unique / len(incoming) if len(incoming) else 0.0,
        'average_incoming_amount': float(incoming.amount.mean()) if len(incoming) else 0.0,
        'median_incoming_amount': float(incoming.amount.median()) if len(incoming) else 0.0,
        'inflow_outflow_imbalance': (inflow - outflow) / max(inflow + outflow, 1.0),
        'average_holding_minutes': float(account.get('average_holding_minutes', 0)),
    }

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/rules/transaction_rules.py

Stack relative behavioral evidence without penalizing clock hour alone.

~~~python
"""Stack relative behavioral evidence without penalizing clock hour alone."""
from backend.app.config.risk_config import TRANSACTION_RULES as C, clamp_score


def score_transaction_rules(features: dict) -> dict:
    score, reasons = 0, []
    ratio = features['amount_ratio']
    if ratio > C['extreme_ratio']:
        score += C['extreme_points']
        reasons.append('amount_much_higher_than_normal')
    elif ratio > C['high_ratio']:
        score += C['high_points']
        reasons.append('amount_higher_than_normal')
    if features['first_time_recipient']:
        score += C['new_recipient_points']
        reasons.append('first_time_recipient')
    if features['amount_vs_recent_average'] > C['recent_ratio']:
        score += C['recent_points']
        reasons.append('amount_above_recent_average')
    if features['device_changed']:
        score += C['device_points']
        reasons.append('device_changed')
    if (features['transactions_last_1h'] >= C['velocity_1h'] or
            features['transactions_last_24h'] >= C['velocity_24h']):
        score += C['velocity_points']
        reasons.append('high_sender_transaction_velocity')
    return {'score': clamp_score(score), 'reasons': reasons or ['within_expected_transaction_pattern']}

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/rules/recipient_rules.py

Interpretable recipient evidence, with no mule identity hardcoding.

~~~python
"""Interpretable recipient evidence, with no mule identity hardcoding."""
from backend.app.config.risk_config import RECIPIENT_RULES as C, clamp_score


def score_recipient_rules(features: dict) -> dict:
    score, reasons = 0, []
    if features['account_age_days'] < C['new_days']:
        score += C['new_points']
        reasons.append('new_recipient_account')
    elif features['account_age_days'] < C['young_days']:
        score += C['young_points']
        reasons.append('young_recipient_account')
    if features['unique_senders_24h'] >= C['unique_senders']:
        score += C['diversity_points']
        reasons.append('many_unique_senders')
    if (features['incoming_transactions_1h'] >= C['incoming_1h'] or
            features['incoming_transactions_24h'] >= C['incoming_24h']):
        score += C['velocity_points']
        reasons.append('high_recipient_transaction_velocity')
    if features['outgoing_ratio'] >= C['outgoing_ratio']:
        score += C['outgoing_points']
        reasons.append('high_outgoing_ratio')
    reports = features['fraud_report_count']
    if reports >= C['reports']:
        score += C['reports_points']
        reasons.append('multiple_prior_fraud_reports')
    elif reports:
        score += C['single_report_points']
        reasons.append('prior_fraud_report')
    if (features['observed_outgoing_ratio'] >= C['outgoing_ratio'] and
            features['incoming_transactions_24h'] >= C['incoming_24h'] and
            0 < features['average_holding_minutes'] < C['rapid_holding_minutes']):
        score += C['rapid_points']
        reasons.append('high_outflow_with_short_historical_holding')
    return {'score': clamp_score(score), 'reasons': reasons or ['no_recipient_rule_signals']}

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/models/baseline.py

Shared persisted baseline loader; trusted local artifacts only.

~~~python
"""Shared persisted baseline loader; trusted local artifacts only."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd


class BaselineModel:
    def __init__(self, artifact_path: Path, expected_features: list[str], expected_kind: str):
        # joblib/pickle can execute code: never load user-uploaded artifacts.
        artifact = joblib.load(artifact_path)
        if (artifact.get('features') != expected_features or
                artifact.get('kind') != expected_kind or artifact.get('schema_version') != 1):
            raise ValueError(f'Incompatible {expected_kind} model artifact; retrain the Day 2 model')
        self.model = artifact['model']
        self.features = artifact['features']
        self.threshold = float(artifact['threshold'])
        self.metadata = artifact['metadata']

    def probability(self, features: dict) -> float:
        row = pd.DataFrame([{column: features[column] for column in self.features}])
        if not np.isfinite(row.to_numpy(dtype=float)).all():
            raise ValueError('Model input contains non-finite features')
        positive = list(self.model.classes_).index(1)
        return float(self.model.predict_proba(row)[0, positive])

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/models/transaction_model.py

Transaction baseline inference; training is an explicit CLI step.

~~~python
"""Transaction baseline inference; training is an explicit CLI step."""
from pathlib import Path
from backend.app.config.risk_config import MODEL_DIR, TRANSACTION_FEATURES
from backend.app.models.baseline import BaselineModel


class TransactionModel(BaselineModel):
    def __init__(self, artifact_path: Path = MODEL_DIR / 'transaction_model.pkl'):
        super().__init__(artifact_path, TRANSACTION_FEATURES, 'transaction')

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/models/recipient_model.py

Recipient suspicious-account baseline inference.

~~~python
"""Recipient suspicious-account baseline inference."""
from pathlib import Path
from backend.app.config.risk_config import MODEL_DIR, RECIPIENT_FEATURES
from backend.app.models.baseline import BaselineModel


class RecipientModel(BaselineModel):
    def __init__(self, artifact_path: Path = MODEL_DIR / 'recipient_model.pkl'):
        super().__init__(artifact_path, RECIPIENT_FEATURES, 'recipient')

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/schemas/risk.py

Preliminary risk API contracts reuse the Day 1 payment schema.

~~~python
"""Preliminary risk API contracts reuse the Day 1 payment schema."""
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.transaction import Transaction, PaymentReason


class PreliminaryRiskRequest(Transaction):
    transaction_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    first_time_recipient: bool = False  # recalculated from server history
    payment_reason: PaymentReason = PaymentReason.other  # excluded from Day 2 predictors


class RiskComponent(BaseModel):
    score: float = Field(ge=0, le=100)
    ml_probability: float = Field(ge=0, le=1)
    rule_score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)


class PreliminaryRiskResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction_risk: float = Field(ge=0, le=100)
    recipient_risk: float = Field(ge=0, le=100)
    preliminary_risk: float = Field(ge=0, le=100)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    reasons: list[str] = Field(min_length=1)
    transaction_details: RiskComponent
    recipient_details: RiskComponent

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/transaction_service.py

Fuse behavioral rules with a loaded synthetic transaction baseline.

~~~python
"""Fuse behavioral rules with a loaded synthetic transaction baseline."""
import pandas as pd
from backend.app.config.risk_config import MODEL_REASON_THRESHOLD, component_score
from backend.app.features.transaction_features import extract_transaction_features
from backend.app.models.transaction_model import TransactionModel
from backend.app.rules.transaction_rules import score_transaction_rules


class TransactionService:
    def __init__(self, model: TransactionModel):
        self.model = model

    def score_transaction(self, transaction: dict, history: pd.DataFrame, profile: dict) -> dict:
        features = extract_transaction_features(transaction, history, profile)
        rules = score_transaction_rules(features)
        probability = self.model.probability(features)
        reasons = list(rules['reasons'])
        if probability >= MODEL_REASON_THRESHOLD:
            reasons = [code for code in reasons if code != 'within_expected_transaction_pattern']
            reasons.append('transaction_model_elevated_risk')
        if not features['baseline_available']:
            reasons.append('sender_baseline_unavailable')
        score, guarded = component_score(probability, rules['score'])
        if guarded:
            reasons.append('strong_rule_evidence_floor')
        return {'score': score,
                'ml_probability': round(probability, 6), 'rule_score': rules['score'], 'reasons': reasons}

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/recipient_service.py

Recipient risk service using cached account and past payment history.

~~~python
"""Recipient risk service using cached account and past payment history."""
import pandas as pd
from backend.app.config.risk_config import MODEL_REASON_THRESHOLD, component_score
from backend.app.database.repository import DataRepository
from backend.app.features.recipient_features import calculate_recipient_features
from backend.app.models.recipient_model import RecipientModel
from backend.app.rules.recipient_rules import score_recipient_rules


class RecipientService:
    def __init__(self, model: RecipientModel, repository: DataRepository):
        self.model, self.repository = model, repository

    def score_recipient(self, receiver_id: str, timestamp: pd.Timestamp,
                        exclude_id: str | None = None) -> dict:
        account = self.repository.account(receiver_id, timestamp)
        history = self.repository.recipient_history(receiver_id, timestamp, exclude_id)
        features = calculate_recipient_features(account, history, timestamp)
        return self.score_features(features)

    def score_features(self, features: dict) -> dict:
        rules = score_recipient_rules(features)
        probability = self.model.probability(features)
        reasons = list(rules['reasons'])
        if probability >= MODEL_REASON_THRESHOLD:
            reasons = [code for code in reasons if code != 'no_recipient_rule_signals']
            reasons.append('recipient_model_elevated_risk')
        score, guarded = component_score(probability, rules['score'])
        if guarded:
            reasons.append('strong_rule_evidence_floor')
        return {'score': score,
                'ml_probability': round(probability, 6), 'rule_score': rules['score'], 'reasons': reasons}

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/risk_service.py

Preliminary fusion of two modules, not a final APP fraud probability.

~~~python
"""Preliminary fusion of two modules, not a final APP fraud probability."""
import pandas as pd
from backend.app.config.risk_config import TRANSACTION_WEIGHT, RECIPIENT_WEIGHT, clamp_score, risk_level
from backend.app.database.repository import DataRepository
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService


def combine_risk(transaction: dict, recipient: dict) -> dict:
    score = clamp_score(TRANSACTION_WEIGHT * transaction['score'] + RECIPIENT_WEIGHT * recipient['score'])
    reasons = list(dict.fromkeys(transaction['reasons'] + recipient['reasons']))
    return {'transaction_risk': transaction['score'], 'recipient_risk': recipient['score'],
            'preliminary_risk': score, 'risk_level': risk_level(score), 'reasons': reasons,
            'transaction_details': transaction, 'recipient_details': recipient}


class RiskService:
    def __init__(self, repository: DataRepository, transaction: TransactionService,
                 recipient: RecipientService):
        self.repository, self.transaction, self.recipient = repository, transaction, recipient

    def score(self, payment: dict) -> dict:
        stamp = pd.Timestamp(payment['timestamp']).tz_convert('UTC')
        if stamp < self.repository.start:
            raise ValueError('Scoring before the synthetic observation window is unsupported')
        profile = self.repository.account(payment['sender_id'], stamp)
        self.repository.account(payment['receiver_id'], stamp)
        history = self.repository.sender_history(payment['sender_id'], stamp, payment['transaction_id'])
        transaction = self.transaction.score_transaction(payment, history, profile)
        recipient = self.recipient.score_recipient(payment['receiver_id'], stamp, payment['transaction_id'])
        return combine_risk(transaction, recipient)

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/api/risk_routes.py

Validated preliminary scoring endpoint; no training or disk reads per request.

~~~python
"""Validated preliminary scoring endpoint; no training or disk reads per request."""
from fastapi import APIRouter, HTTPException, Request
from backend.app.schemas.risk import PreliminaryRiskRequest, PreliminaryRiskResponse

router = APIRouter(prefix='/api/v1/risk', tags=['preliminary risk'])


@router.post('/preliminary', response_model=PreliminaryRiskResponse)
def preliminary_risk(payment: PreliminaryRiskRequest, request: Request) -> dict:
    service = getattr(request.app.state, 'risk_service', None)
    if service is None:
        raise HTTPException(status_code=503, detail=getattr(request.app.state, 'risk_error',
            'Risk models unavailable. Run both Day 2 training commands and restart the service.'))
    try:
        return service.score(payment.model_dump())
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/app/main.py

FastAPI service with startup-cached data and trained Day 2 baselines.

~~~python
"""FastAPI service with startup-cached data and trained Day 2 baselines."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from backend.app.api.risk_routes import router
from backend.app.database.repository import DataRepository
from backend.app.models.transaction_model import TransactionModel
from backend.app.models.recipient_model import RecipientModel
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService
from backend.app.services.risk_service import RiskService


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.risk_service = None
    try:
        repository = DataRepository.load()
        application.state.risk_service = RiskService(repository,
            TransactionService(TransactionModel()), RecipientService(RecipientModel(), repository))
    except (OSError, ValueError) as error:
        application.state.risk_error = f'Risk engine unavailable: {error}. Run both training commands and restart.'
        logging.getLogger(__name__).warning(application.state.risk_error)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title='APP Shield', version='0.2.0', lifespan=lifespan)
    application.include_router(router)
    application.add_api_route('/', root, methods=['GET'])
    application.add_api_route('/health', health, methods=['GET'])
    application.add_api_route('/ready', ready, methods=['GET'])
    return application


def root() -> dict[str, str]:
    return {'project': 'APP Shield', 'status': 'running'}


def health() -> dict[str, str]:
    """Liveness only; readiness is exposed separately."""
    return {'status': 'healthy'}


def ready(request: Request):
    from fastapi.responses import JSONResponse
    available = getattr(request.app.state, 'risk_service', None) is not None
    return JSONResponse({'status': 'ready' if available else 'unavailable'}, status_code=200 if available else 503)


app = create_app()

~~~

Run/test: `.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.

## ml/datasets.py

Shared offline feature construction using the exact inference extractors.

~~~python
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

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## ml/metrics.py

Imbalance-aware metrics and validation-only operating threshold selection.

~~~python
"""Imbalance-aware metrics and validation-only operating threshold selection."""
import numpy as np
from sklearn.metrics import (precision_score, recall_score, f1_score, roc_auc_score,
                             average_precision_score, confusion_matrix)


def evaluate_probabilities(labels, probabilities, threshold: float = .5) -> dict:
    predictions = np.asarray(probabilities) >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        'threshold': float(threshold),
        'precision': float(precision_score(labels, predictions, zero_division=0)),
        'recall': float(recall_score(labels, predictions, zero_division=0)),
        'f1': float(f1_score(labels, predictions, zero_division=0)),
        'roc_auc': float(roc_auc_score(labels, probabilities)),
        'pr_auc_average_precision': float(average_precision_score(labels, probabilities)),
        'false_positive_rate': float(fp / (fp + tn)) if fp + tn else 0.0,
        'confusion_matrix': [[int(tn), int(fp)], [int(fn), int(tp)]],
        'positive_count': int(sum(labels)), 'sample_count': int(len(labels)),
        'always_legitimate_accuracy': float(1 - np.mean(labels)),
    }


def choose_threshold(labels, probabilities) -> float:
    """Prefer recall under a 10% validation FPR cap; do not inspect test labels."""
    candidates = [evaluate_probabilities(labels, probabilities, threshold)
                  for threshold in np.linspace(.05, .95, 91)]
    feasible = [result for result in candidates if result['false_positive_rate'] <= .1]
    best = max(feasible or candidates, key=lambda result: (result['recall'], result['f1'],
                                                          -result['false_positive_rate']))
    return best['threshold']

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## ml/training.py

Compare two baselines on validation data and persist the selected model.

~~~python
"""Compare two baselines on validation data and persist the selected model."""
import json
import joblib
import sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from backend.app.config.risk_config import SEED, MODEL_DIR, REPORT_DIR
from ml.metrics import evaluate_probabilities, choose_threshold


def assign_splits(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    result = frame.copy()
    result['split'] = 'train'
    if kind == 'transaction':
        # Timestamp cutoffs put ties in the same partition; history is strictly earlier.
        first = result.timestamp.iloc[int(len(result) * .6)]
        second = result.timestamp.iloc[int(len(result) * .8)]
        result.loc[result.timestamp >= first, 'split'] = 'validation'
        result.loc[result.timestamp >= second, 'split'] = 'test'
    else:
        train, remaining = train_test_split(result.index, test_size=.4,
            stratify=result.target, random_state=SEED)
        validation, test = train_test_split(remaining, test_size=.5,
            stratify=result.loc[remaining, 'target'], random_state=SEED)
        result.loc[validation, 'split'] = 'validation'
        result.loc[test, 'split'] = 'test'
    for split in ('train', 'validation', 'test'):
        if result.loc[result.split == split, 'target'].nunique() != 2:
            raise ValueError(f'{kind} {split} split requires both target classes')
    return result


def feature_importance(model, features: list[str]) -> dict[str, float]:
    if hasattr(model, 'feature_importances_'):
        weights = model.feature_importances_
    else:
        # Signed coefficients are for standardized inputs, not causal explanations.
        weights = model.steps[-1][1].coef_[0]
    return {name: float(value) for name, value in sorted(zip(features, weights),
                                                        key=lambda item: abs(item[1]), reverse=True)}


def train_baselines(frame: pd.DataFrame, features: list[str], kind: str, target_description: str) -> dict:
    data = assign_splits(frame, kind)
    if not np.isfinite(data[features].to_numpy(dtype=float)).all():
        raise ValueError('Training features must be finite')
    train = data[data.split == 'train']
    validation = data[data.split == 'validation']
    test = data[data.split == 'test']
    candidates = {
        'logistic_regression': make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=2000, class_weight='balanced', C=.5, random_state=SEED)),
        'random_forest': RandomForestClassifier(n_estimators=200, max_depth=8,
            min_samples_leaf=4, class_weight='balanced', random_state=SEED, n_jobs=1),
    }
    reports = {}
    for name, model in candidates.items():
        model.fit(train[features], train.target)
        validation_probabilities = model.predict_proba(validation[features])[:, 1]
        threshold = choose_threshold(validation.target, validation_probabilities)
        reports[name] = {
            'validation': evaluate_probabilities(validation.target, validation_probabilities, threshold),
            'test': evaluate_probabilities(test.target, model.predict_proba(test[features])[:, 1], threshold),
            'feature_importance': feature_importance(model, features),
        }
    # Test metrics are reported, never used for model/threshold selection.
    selected = max(reports, key=lambda name: reports[name]['validation']['pr_auc_average_precision'])
    threshold = reports[selected]['validation']['threshold']
    metadata = {
        'seed': SEED, 'sklearn_version': sklearn.__version__, 'selected_model': selected,
        'target': target_description, 'selected_by': 'validation average precision',
        'split_strategy': 'chronological 60/20/20' if kind == 'transaction' else 'account-disjoint stratified 60/20/20',
        'feature_window': 'strictly before scoring timestamp; 24h recipient snapshot',
        'probabilities': 'uncalibrated synthetic baseline outputs; not APP fraud probabilities',
        'split_counts': data.groupby('split').target.agg(['size', 'sum']).to_dict('index'),
        'feature_columns': features,
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'kind': kind, 'model': candidates[selected],
                 'features': features, 'threshold': threshold, 'metadata': metadata},
                MODEL_DIR / f'{kind}_model.pkl')
    report = {'metadata': metadata, 'models': reports}
    (MODEL_DIR / f'{kind}_model.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    (REPORT_DIR / f'{kind}_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    data.to_csv(REPORT_DIR / f'{kind}_features.csv', index=False)
    print(json.dumps(report, indent=2))
    return report


def evaluate_saved_model(kind: str) -> dict:
    artifact = joblib.load(MODEL_DIR / f'{kind}_model.pkl')
    frame = pd.read_csv(REPORT_DIR / f'{kind}_features.csv')
    test = frame[frame.split == 'test']
    probabilities = artifact['model'].predict_proba(test[artifact['features']])[:, 1]
    report = {'kind': kind, 'selected_model': artifact['metadata']['selected_model'],
              'test': evaluate_probabilities(test.target, probabilities, artifact['threshold']),
              'feature_importance': feature_importance(artifact['model'], artifact['features'])}
    print(json.dumps(report, indent=2))
    return report

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## ml/transaction/train.py

Train and compare transaction baselines; run from the project root.

~~~python
"""Train and compare transaction baselines; run from the project root."""
from backend.app.database.repository import DataRepository
from backend.app.config.risk_config import TRANSACTION_FEATURES
from ml.datasets import transaction_dataset
from ml.training import train_baselines


def main() -> None:
    repository = DataRepository.load()
    print(f'Validated {len(repository.transactions)} transactions, {len(repository.accounts)} accounts; '
          f'fraud rate {repository.transactions.is_fraud.mean():.2%}')
    train_baselines(transaction_dataset(repository), TRANSACTION_FEATURES, 'transaction',
                    'is_fraud: synthetic transaction fraud-propensity baseline')


if __name__ == '__main__':
    main()

~~~

Run/test: `.venv\Scripts\python -m ml.transaction.train`.

## ml/transaction/evaluate.py

Print held-out metrics and feature importances for the saved transaction model.

~~~python
"""Print held-out metrics and feature importances for the saved transaction model."""
from ml.training import evaluate_saved_model


if __name__ == '__main__':
    evaluate_saved_model('transaction')

~~~

Run/test: `.venv\Scripts\python -m ml.transaction.evaluate`.

## ml/recipient/train.py

Train and compare recipient baselines; run from the project root.

~~~python
"""Train and compare recipient baselines; run from the project root."""
from backend.app.database.repository import DataRepository
from backend.app.config.risk_config import RECIPIENT_FEATURES
from ml.datasets import recipient_dataset
from ml.training import train_baselines


def main() -> None:
    repository = DataRepository.load()
    print(f'Validated {len(repository.transactions)} transactions, {len(repository.accounts)} accounts; '
          f'fraud rate {repository.transactions.is_fraud.mean():.2%}')
    train_baselines(recipient_dataset(repository), RECIPIENT_FEATURES, 'recipient',
                    'is_suspicious: synthetic suspicious-account proxy label')


if __name__ == '__main__':
    main()

~~~

Run/test: `.venv\Scripts\python -m ml.recipient.train`.

## ml/recipient/evaluate.py

Print held-out metrics and feature importances for the saved recipient model.

~~~python
"""Print held-out metrics and feature importances for the saved recipient model."""
from ml.training import evaluate_saved_model


if __name__ == '__main__':
    evaluate_saved_model('recipient')

~~~

Run/test: `.venv\Scripts\python -m ml.recipient.evaluate`.

## backend/requirements.txt

Requested backend, ML and test dependencies.

~~~text
fastapi>=0.115,<1
uvicorn>=0.30,<1
pydantic>=2.9,<3
pandas>=2.2,<3
numpy==2.1.3
scikit-learn==1.5.2
networkx>=3.3,<4
SQLAlchemy>=2.0,<3
psycopg[binary]>=3.2,<4
pytest>=8,<10
httpx>=0.27,<1
joblib>=1.4,<2
scipy==1.14.1

~~~

Run/test: `.venv\Scripts\python -m pip install -r backend/requirements.txt`.

## tests/test_transaction_risk.py

Relative behavior, cold starts, temporal leakage and rule explanations.

~~~python
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

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## tests/test_recipient_risk.py

Recipient aggregates, temporal windows and stacked risk evidence.

~~~python
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

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## tests/test_risk_api.py

Real artifact integration plus validation, caching and availability behavior.

~~~python
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

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## scripts/benchmark_risk.py

Measure warmed local API pipeline latency and save a reproducible example.

~~~python
"""Measure warmed local API pipeline latency and save a reproducible example."""
import json
from time import perf_counter
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config.risk_config import REPORT_DIR


def main() -> None:
    with TestClient(app) as client:
        if client.get('/ready').status_code != 200:
            raise RuntimeError('Train both models before benchmarking')
        row = app.state.risk_service.repository.transactions.iloc[-1]
        payment = {key: (row[key].isoformat() if key == 'timestamp' else row[key])
                   for key in ('sender_id', 'receiver_id', 'amount', 'timestamp', 'device_id', 'payment_type')}
        for _ in range(5):
            client.post('/api/v1/risk/preliminary', json=payment).raise_for_status()
        samples = []
        for _ in range(30):
            start = perf_counter()
            response = client.post('/api/v1/risk/preliminary', json=payment)
            response.raise_for_status()
            samples.append((perf_counter() - start) * 1000)
        repository = app.state.risk_service.repository
        timestamp = repository.end + pd.Timedelta(seconds=1)
        candidates = repository.accounts[repository.accounts.is_suspicious].account_id
        receiver = max(candidates, key=lambda account_id:
            app.state.risk_service.recipient.score_recipient(account_id, timestamp)['score'])
        sender = 'A0001'
        sender_history = repository.sender_history(sender, timestamp)
        average = float(sender_history.amount.mean()) if len(sender_history) else float(
            repository.account(sender)['average_transaction_amount'])
        suspicious_payment = dict(sender_id=sender, receiver_id=receiver, amount=round(average * 30, 2),
            timestamp=timestamp.isoformat(), device_id=repository.account(sender)['usual_device'], payment_type='bank_transfer')
        suspicious = client.post('/api/v1/risk/preliminary', json=suspicious_payment)
        suspicious.raise_for_status()
        report = {'suspicious_request': suspicious_payment, 'suspicious_response': suspicious.json(), 'method': '30 warm FastAPI TestClient requests, excludes startup and network transport',
                  'median_ms': float(np.median(samples)), 'p95_ms': float(np.percentile(samples, 95)),
                  'mean_ms': float(np.mean(samples)), 'request': payment, 'response': response.json()}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / 'latency_and_example.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

~~~

Run/test: `.venv\Scripts\python -m scripts.benchmark_risk`.

## README.md

Local setup, model scope, reproducibility, leakage assumptions and observed results.

~~~markdown
# APP Shield — Context-Aware Authorized Payment Scam Detection Engine

Traditional fraud detection asks: **Is the person making the transaction really the authorized user?**
APP Shield additionally asks: **Is the genuine authorized user being manipulated by a scammer?**

Day 1 provides the data and backend foundation. Day 2 adds transaction abnormality and recipient suspiciousness baselines. Context, psychology, graph and deployment modules remain reserved placeholders.

## Run locally (Python 3.11+)

Run these commands from the app-shield directory:

~~~powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
.venv\Scripts\python -m scripts.generate_transactions
.venv\Scripts\python -m scripts.analyze_transactions --output data/processed/analysis.txt
.venv\Scripts\python -m ml.transaction.train
.venv\Scripts\python -m ml.recipient.train
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
~~~

GET / returns project=APP Shield and status=running. GET /health returns status=healthy.
Open http://127.0.0.1:8000/docs for endpoint documentation.

## Data

The default seed 42 creates 1,000 normal users, 40 suspicious accounts and 10,000 payments (7.5% fraud), covering seven APP scenarios. Regenerate with --seed or --transactions. Files are saved in data/synthetic/transactions.csv and accounts.csv. Amounts are synthetic INR values.

Users have distinct spending averages, active hours, devices, recipient sets and frequencies. Both classes contain small and large payments. Investment scenarios reuse recipients and often increase payments. Suspicious account behavior overlaps with ordinary accounts. Account report counts and outgoing ratios are simulated pre-observation historical snapshots; they are not measured from the generated stream. Incoming velocity and distinct senders use the preceding 24 hours, excluding the current payment. First-time status includes a simulated pre-observation recipient history. Timestamps use a fixed January 2026 UTC observation window.

Derived features: amount_ratio, is_large_deviation (ratio > 3), is_new_recipient, recipient_age_bucket, recipient_activity_level, recipient_reported. Thresholds are illustrative rather than validated risk rules.

Exclude is_fraud, fraud_type, is_suspicious, is_known_mule, transaction/account identifiers and profile-only metadata from future model predictors. Keep labels for evaluation only. Split future experiments by time/user as appropriate; do not evaluate on duplicated profiles across random splits without checking leakage. Synthetic results cannot establish real-world fraud-detection accuracy. No PIN, OTP, CVV, passwords or banking secrets are stored; schemas reject extra fields.

## Database

SQLAlchemy account/payment tables and an engine factory support SQLite locally and PostgreSQL via DATABASE_URL. No database is initialized on service startup. Export DATABASE_URL explicitly; .env.example is documentation and is not automatically loaded.

## Future architecture

~~~text
Transaction Risk + Recipient Risk + Graph/Mule Risk + Payment Context
+ Scam Scenario Detection + Psychological Manipulation Detection
                         ↓
                    APP Scam Risk
~~~

See DAY1_IMPLEMENTATION.md for every implemented file's complete code, purpose and run/test commands. Empty package initializers enable imports. Existing notebooks and model placeholders are unused in Day 1.


## Day 2

Implemented: transaction feature engineering, transaction rules and two ML baselines; recipient feature engineering, recipient rules and two ML baselines; preliminary risk fusion; explainable reason codes; POST /api/v1/risk/preliminary.

**This is not yet the final APP scam detector.** Scam context, psychological manipulation and transaction-network intelligence will be added later. Transaction training uses synthetic is_fraud labels to compare baseline fraud-propensity signals, not validated abnormality labels. Recipient training uses is_suspicious (40 synthetic positives); is_known_mule marks only a random subset and is not a complete negative label.

Run training, evaluation and benchmarking from this directory:

~~~powershell
.venv\Scripts\python -m ml.transaction.train
.venv\Scripts\python -m ml.recipient.train
.venv\Scripts\python -m ml.transaction.evaluate
.venv\Scripts\python -m ml.recipient.evaluate
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m scripts.benchmark_risk
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
~~~

Restart FastAPI after training. Data and model artifacts are loaded once during lifespan startup. Missing models produce a clear 503 on scoring and /ready; /health remains a liveness check. Requests are read-only previews and do not append payments to history. Unknown accounts return 404. Invalid input, naive timestamps and dates before the observation window return 422. Use account IDs from accounts.csv (A0000–A1039), rather than the illustrative U101/M012 identifiers.

### Features and leakage boundaries

Both training and inference call identical extractors. Sender counts/averages and recipient inflows/outflows use timestamps strictly before the payment; same-timestamp transactions and the current transaction ID are excluded. Sender average falls back to the pre-observation profile for a cold start. Zero baseline yields a neutral amount ratio of 1 plus a baseline-unavailable reason. First-time recipients are derived server-side, including pre-observation usual recipients; a client's first_time_recipient value is ignored. Transaction models exclude absolute amount, labels, payment reasons, identifiers and mule flags. Clock hour alone never adds a rule penalty; outside-usual-hours is only one learned behavioral feature. All timestamps/hours are UTC, matching the synthetic profiles.

Fraud reports, holding times and historical outgoing ratios are **simulated pre-observation snapshots**, not timestamped production observations. The recipient outgoing_ratio is the maximum of bounded observed 24h outflow/inflow and the historical profile ratio; observed_outgoing_ratio and both measured amounts are exposed separately. The synthetic accounts lack realistic onward transfers, so this approximation must be replaced with ledger and report-event data before production use. Short historical holding time plus high observed outflow is supporting evidence, not a causal rapid-transfer reconstruction.

Transaction evaluation uses chronological 60/20/20 train/validation/test partitions. Prior test-period payments may be used as history for later test payments, but their labels never enter features. Recipient evaluation uses one snapshot per account at the end of the observation window and stratified account-disjoint 60/20/20 partitions. Test accounts' earlier activity is available as unlabeled feature history, as it would be when scoring them. This is not a future temporal recipient benchmark. Only training uses balanced class weights. Neither validation nor test data is oversampled.

Logistic regression and random forest are compared. Selection uses validation average precision; threshold selection maximizes validation recall subject to a 10% FPR cap. Test metrics include precision, recall, F1, ROC-AUC, PR-AUC (average precision), confusion matrix and false-positive rate. Accuracy alone is misleading: predicting every payment as legitimate yields 92.5% overall accuracy and zero fraud recall. Recipient metrics have only eight positive test accounts, so estimates are especially uncertain. Feature importances/standardized coefficients describe model associations, not causal explanations.

### MVP scores

Each component score = 60% × ML output × 100 + 40% × rule score. Preliminary score = 45% × transaction score + 55% × recipient score. When stacked rule evidence reaches 80 or above, the component score is floored at its rule score, with reason strong_rule_evidence_floor. This prevents an uncalibrated model trained on sparse synthetic activity from erasing extreme recipient evidence outside its training range. These configurable weights and this safeguard are illustrative, not optimized or calibrated. ML outputs are uncalibrated probabilities from synthetic supervised baselines. The fused score is an evidence index, not an APP fraud probability. Levels: LOW 0–29, MEDIUM 30–59, HIGH 60–79, CRITICAL 80–100 (floating scores use cutoffs 30, 60, 80). See backend/app/config/risk_config.py.

Saved artifacts: saved_models/transaction_model.pkl and recipient_model.pkl, with adjacent feature/config metadata. Only load locally trained, trusted pickle artifacts. Reports and held-out feature tables are saved under data/processed/day2/. Retrain after changing features or regenerating the dataset.

The numeric top-level transaction_risk and recipient_risk fields support concise clients. transaction_details and recipient_details include score, rule_score, ml_probability and reason codes. Combined reasons preserve both sets.

See DAY2_IMPLEMENTATION.md for complete code for every changed/new file, run instructions, and an actual example response. requirements.txt pins the ML dependency versions used locally; the official scikit-learn 1.5 documentation lists support through Python 3.12: [installation documentation](https://scikit-learn.org/1.5/install.html). This setup was tested with Python 3.12.10.


### Verified local results

53 automated tests pass. A live HTTP payment returned transaction risk 91.24, recipient risk 77.97 and preliminary risk 83.94 (CRITICAL); the normal example returned 0.10 (LOW). The latest measurement on this machine was median 122.0 ms / p95 170.9 ms across 20 warmed localhost HTTP requests. TestClient measurements ranged from roughly 15 to 96 ms across runs; these are environment-sensitive smoke measurements, not a production latency guarantee. Run scripts.smoke_risk_api after starting the server for the HTTP check.

| Selected baseline | Precision | Recall | F1 | ROC-AUC | PR-AUC | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Transaction: random forest | 0.309 | 0.538 | 0.393 | 0.887 | 0.424 | 0.093 |
| Recipient: logistic regression | 0.556 | 0.625 | 0.588 | 0.979 | 0.788 | 0.020 |

The recipient random forest scored better on the test partition but was not selected, because selection was locked to validation average precision. Do not switch models based on the held-out test results without introducing a fresh evaluation set. These baselines miss substantial positives; synthetic results do not demonstrate production readiness.

For the exact tested environment, install backend/requirements.lock.txt. One upstream Starlette TestClient deprecation warning remains; all tests pass.

Example request (use an explicit timezone):

~~~powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/risk/preliminary' -Method Post -ContentType 'application/json' -Body '{"sender_id":"A0001","receiver_id":"A1006","amount":66994.74,"timestamp":"2026-01-30T23:31:50+00:00","device_id":"D0001","payment_type":"bank_transfer"}'
~~~

Expected numeric scores with the seeded artifacts: transaction_risk=91.24, recipient_risk=77.97, preliminary_risk=83.94, risk_level=CRITICAL. The complete response and both normal/suspicious examples are in data/processed/day2/latency_and_example.json and DAY2_IMPLEMENTATION.md.

~~~

Run/test: `.venv\Scripts\python -m pytest -q`.

## backend/requirements.lock.txt

Exact tested dependency versions for reproducible installation.

~~~text
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
certifi==2026.7.22
click==8.5.0
cloudpickle==3.1.2
colorama==0.4.6
fastapi==0.142.2
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
iniconfig==2.3.0
joblib==1.6.0
narwhals==2.26.0
networkx==3.7
numpy==2.1.3
opentelemetry-api==1.45.0
packaging==26.3
pandas==2.3.3
pluggy==1.6.0
psycopg==3.3.6
psycopg-binary==3.3.6
pydantic==2.13.5
pydantic_core==2.46.5
Pygments==2.21.0
pytest==9.1.1
python-dateutil==2.9.0.post0
pytz==2026.4
scikit-learn==1.5.2
scipy==1.14.1
six==1.17.0
SQLAlchemy==2.1.3
starlette==1.7.0
threadpoolctl==3.7.0
typing-inspection==0.4.4
typing_extensions==4.16.0
tzdata==2026.4
uvicorn==0.54.0

~~~

Run/test: `.venv\Scripts\python -m pip install -r backend/requirements.lock.txt`.

## scripts/smoke_risk_api.py

Verify the running localhost API and measure end-to-end HTTP latency.

~~~python
"""Verify the running localhost API and measure end-to-end HTTP latency."""
import json
from time import perf_counter
from urllib.request import Request, urlopen
import numpy as np
from backend.app.config.risk_config import REPORT_DIR


def main() -> None:
    example = json.loads((REPORT_DIR / 'latency_and_example.json').read_text(encoding='utf-8'))
    body = json.dumps(example['suspicious_request']).encode('utf-8')
    url = 'http://127.0.0.1:8000/api/v1/risk/preliminary'
    with urlopen('http://127.0.0.1:8000/ready', timeout=10) as ready:
        assert json.load(ready)['status'] == 'ready'
    samples = []
    result = None
    for index in range(25):
        start = perf_counter()
        with urlopen(Request(url, data=body, headers={'Content-Type': 'application/json'}), timeout=10) as response:
            result = json.load(response)
        if index >= 5:
            samples.append((perf_counter() - start) * 1000)
    assert result['risk_level'] == 'CRITICAL', result
    report = {'method': '20 warmed localhost HTTP requests; startup excluded; transport included',
              'median_ms': float(np.median(samples)), 'p95_ms': float(np.percentile(samples, 95)),
              'mean_ms': float(np.mean(samples)), 'request': example['suspicious_request'], 'response': result}
    (REPORT_DIR / 'http_smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

~~~

Run/test: `.venv\Scripts\python -m scripts.smoke_risk_api`.

## Verified request and expected response

POST http://127.0.0.1:8000/api/v1/risk/preliminary

~~~json
{
  "sender_id": "A0001",
  "receiver_id": "A1006",
  "amount": 66994.74,
  "timestamp": "2026-01-30T23:31:50+00:00",
  "device_id": "D0001",
  "payment_type": "bank_transfer"
}
~~~

Observed response from the running HTTP server:

~~~json
{
  "transaction_risk": 91.24,
  "recipient_risk": 77.97,
  "preliminary_risk": 83.94,
  "risk_level": "CRITICAL",
  "reasons": [
    "amount_much_higher_than_normal",
    "first_time_recipient",
    "amount_above_recent_average",
    "transaction_model_elevated_risk",
    "high_outgoing_ratio",
    "multiple_prior_fraud_reports",
    "recipient_model_elevated_risk"
  ],
  "transaction_details": {
    "score": 91.24,
    "ml_probability": 0.954067,
    "rule_score": 85,
    "reasons": [
      "amount_much_higher_than_normal",
      "first_time_recipient",
      "amount_above_recent_average",
      "transaction_model_elevated_risk"
    ]
  },
  "recipient_details": {
    "score": 77.97,
    "ml_probability": 0.999536,
    "rule_score": 45,
    "reasons": [
      "high_outgoing_ratio",
      "multiple_prior_fraud_reports",
      "recipient_model_elevated_risk"
    ]
  }
}
~~~

53 automated tests passed. Both model comparison reports include validation/test metrics, confusion matrices and feature importances. Runtime artifacts: saved_models/transaction_model.pkl, saved_models/recipient_model.pkl; adjacent metadata JSON; data/processed/day2/*_evaluation.json, *_features.csv, latency_and_example.json, http_smoke.json. Generated CSV feature tables include targets and split markers for evaluation only; model loaders use the explicit predictor allowlist.
