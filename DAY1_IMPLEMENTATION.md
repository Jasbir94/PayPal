# Day 1 file-by-file implementation

All commands run from app-shield using the project virtual environment.

## backend/app/schemas/transaction.py

Validated payment data without financial credentials.

~~~python
"""Validated payment data without financial credentials."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime

class PaymentReason(str, Enum):
    family = 'family'
    friend = 'friend'
    shopping = 'shopping'
    investment = 'investment'
    job = 'job'
    government = 'government'
    bank_support = 'bank_support'
    loan = 'loan'
    refund = 'refund'
    relationship = 'relationship'
    other = 'other'

class Transaction(BaseModel):
    """A positive, timestamped authorized payment."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    transaction_id: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)
    receiver_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    timestamp: AwareDatetime
    device_id: str = Field(min_length=1)
    payment_type: str = Field(min_length=1)
    first_time_recipient: bool
    payment_reason: PaymentReason

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/schemas/recipient.py

Account metadata; credentials are deliberately excluded.

~~~python
"""Account metadata; credentials are deliberately excluded."""
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime

class Account(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account_id: str = Field(min_length=1)
    created_at: AwareDatetime
    fraud_report_count: int = Field(default=0, ge=0)
    is_known_mule: bool = False

Recipient = Account

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/main.py

Day 1 service: liveness endpoints only.

~~~python
"""Day 1 service: liveness endpoints only."""
from fastapi import FastAPI
app = FastAPI(title='APP Shield', version='0.1.0')

@app.get('/')
def root() -> dict[str, str]:
    return {'project': 'APP Shield', 'status': 'running'}

@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'healthy'}

~~~

Run/check: `.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.

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

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## scripts/config.py

Reproducible generation settings.

~~~python
"""Reproducible generation settings."""
from dataclasses import dataclass
from datetime import datetime, timezone

FRAUD_TYPES = ('government_impersonation', 'bank_impersonation', 'investment_scam',
               'fake_job', 'tech_support', 'family_emergency', 'marketplace_scam')
REASONS = ('family', 'friend', 'shopping', 'investment', 'job', 'government',
           'bank_support', 'loan', 'refund', 'relationship', 'other')
SCENARIO_REASONS = dict(zip(FRAUD_TYPES, ('government', 'bank_support', 'investment',
                                       'job', 'bank_support', 'family', 'shopping')))

@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    normal_users: int = 1000
    suspicious_accounts: int = 40
    transactions: int = 10000
    fraud_fraction: float = 0.075
    observation_days: int = 30
    start: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def validate(self) -> None:
        if self.normal_users < 10 or self.suspicious_accounts < 1:
            raise ValueError('At least ten users and one suspicious account required')
        if self.transactions < 1 or self.observation_days < 1:
            raise ValueError('Counts and observation days must be positive')
        if not 0 < self.fraud_fraction < 1:
            raise ValueError('Fraud fraction must be between zero and one')

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## scripts/generate_accounts.py

Generate heterogeneous account profiles with overlapping risk signals.

~~~python
"""Generate heterogeneous account profiles with overlapping risk signals."""
from datetime import timedelta
import numpy as np
import pandas as pd
from scripts.config import GeneratorConfig

def generate_accounts(config: GeneratorConfig, rng: np.random.Generator) -> pd.DataFrame:
    """Build normal users and suspicious recipients; flags are evaluation metadata."""
    rows = []
    for index in range(config.normal_users + config.suspicious_accounts):
        suspicious = index >= config.normal_users
        age = int(rng.integers(1, 100 if suspicious and rng.random() < .7 else 1800))
        reports = int(rng.poisson(.8 if suspicious else .06))
        rows.append(dict(account_id=f'A{index:04d}',
            created_at=(config.start - timedelta(days=age)).isoformat(),
            fraud_report_count=reports, is_known_mule=bool(suspicious and rng.random() < .45),
            is_suspicious=suspicious,
            average_transaction_amount=round(float(np.clip(rng.lognormal(8.1, 1.2), 200, 50000)), 2),
            normal_hour_start=int(rng.integers(6, 12)), normal_hour_end=int(rng.integers(18, 24)),
            usual_device=f'D{index:04d}', transaction_frequency=float(rng.lognormal(0, .7)),
            usual_recipients='|'.join(f'A{x:04d}' for x in rng.choice(
                [i for i in range(config.normal_users) if i != index], size=8, replace=False)),
            average_holding_minutes=float(rng.lognormal(3 if suspicious and rng.random() < .7 else 6, 1.2)),
            outgoing_ratio=float(rng.beta(7, 2) if suspicious and rng.random() < .7 else rng.beta(2, 3))))
    return pd.DataFrame(rows)

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## scripts/generate_transactions.py

Generate chronological payments with noisy APP scam scenarios.

~~~python
"""Generate chronological payments with noisy APP scam scenarios."""
import argparse
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.config import GeneratorConfig, FRAUD_TYPES, REASONS, SCENARIO_REASONS
from scripts.generate_accounts import generate_accounts
from backend.app.features.transaction_features import add_derived_features

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def generate_datasets(config: GeneratorConfig = GeneratorConfig()) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return payments and accounts. Rolling recipient counts exclude current payment.

    Sender averages, reports and outgoing ratios are simulated historical snapshots.
    Suspicious/known-mule flags and both target columns must never enter predictors.
    """
    config.validate()
    rng = np.random.default_rng(config.seed)
    accounts = generate_accounts(config, rng)
    users = accounts.iloc[:config.normal_users]
    weights = users.transaction_frequency.to_numpy()
    weights /= weights.sum()
    labels = np.zeros(config.transactions, dtype=bool)
    labels[:round(config.transactions * config.fraud_fraction)] = True
    rng.shuffle(labels)
    drafts = []
    investments: dict[str, tuple[str, float]] = {}
    for index, fraud in enumerate(labels):
        sender = users.iloc[int(rng.choice(len(users), p=weights))]
        scenario = str(rng.choice(FRAUD_TYPES)) if fraud else 'normal'
        if fraud:
            if scenario == 'investment_scam' and sender.account_id in investments:
                receiver_id = investments[sender.account_id][0]
            else:
                pool = accounts.iloc[config.normal_users:] if rng.random() < .85 else users
                receiver_id = str(pool.iloc[int(rng.integers(len(pool)))].account_id)
        elif rng.random() < .72:
            receiver_id = str(rng.choice(sender.usual_recipients.split('|')))
        else:
            receiver_id = str(users.iloc[int(rng.integers(len(users)))].account_id)
        if receiver_id == sender.account_id:
            receiver_id = str(users.iloc[(int(sender.name) + 1) % len(users)].account_id)
        hour = int(rng.integers(24)) if rng.random() < (.35 if fraud else .1) else int(
            rng.integers(sender.normal_hour_start, sender.normal_hour_end))
        stamp = config.start + timedelta(days=int(rng.integers(config.observation_days)),
                                          hours=hour, minutes=int(rng.integers(60)), seconds=int(rng.integers(60)))
        multiplier = float(rng.lognormal(.45 if fraud else -.2, .85))
        if scenario == 'fake_job':
            multiplier *= .4
        amount = round(max(1., float(sender.average_transaction_amount) * multiplier), 2)
        reason = SCENARIO_REASONS[scenario] if fraud and rng.random() < .8 else str(rng.choice(REASONS))
        drafts.append(dict(transaction_id=f'T{index:06d}', sender_id=sender.account_id,
            receiver_id=receiver_id, amount=amount, timestamp=stamp, device_id=(
                sender.usual_device if rng.random() < .94 else f'DNEW{index:06d}'),
            payment_type=str(rng.choice(['upi', 'bank_transfer', 'wallet'], p=[.7,.2,.1])),
            payment_reason=reason, sender_average_amount=sender.average_transaction_amount,
            is_fraud=int(fraud), fraud_type=scenario))
        if scenario == 'investment_scam':
            investments[sender.account_id] = (receiver_id, amount)
    drafts.sort(key=lambda row: (row['timestamp'], row['transaction_id']))
    lookup = accounts.set_index('account_id')
    history: dict[str, deque] = defaultdict(deque)
    seen = {row.account_id: set(row.usual_recipients.split('|')) for row in users.itertuples()}
    investment_amounts: dict[tuple[str, str], float] = {}
    for row in drafts:
        receiver = lookup.loc[row['receiver_id']]
        window = history[row['receiver_id']]
        cutoff = row['timestamp'] - timedelta(hours=24)
        while window and window[0][0] < cutoff:
            window.popleft()
        pair = (row['sender_id'], row['receiver_id'])
        if row['fraud_type'] == 'investment_scam':
            if pair in investment_amounts and rng.random() < .8:
                row['amount'] = round(investment_amounts[pair] * float(rng.uniform(1.05, 1.6)), 2)
            investment_amounts[pair] = row['amount']
        row.update(first_time_recipient=row['receiver_id'] not in seen[row['sender_id']],
            account_age_days=(row['timestamp'] - pd.Timestamp(receiver.created_at).to_pydatetime()).days,
            unique_senders_24h=len({sender for _, sender in window}),
            incoming_transactions_24h=len(window), outgoing_ratio=float(receiver.outgoing_ratio),
            fraud_reports=int(receiver.fraud_report_count))
        seen[row['sender_id']].add(row['receiver_id'])
        window.append((row['timestamp'], row['sender_id']))
        row['timestamp'] = row['timestamp'].isoformat()
    return add_derived_features(pd.DataFrame(drafts)), accounts

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--transactions', type=int, default=10000)
    parser.add_argument('--output-dir', type=Path, default=PROJECT_ROOT / 'data' / 'synthetic')
    args = parser.parse_args()
    transactions, accounts = generate_datasets(GeneratorConfig(seed=args.seed, transactions=args.transactions))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    transactions.to_csv(args.output_dir / 'transactions.csv', index=False)
    accounts.to_csv(args.output_dir / 'accounts.csv', index=False)
    print(f'Saved {len(transactions)} payments and {len(accounts)} accounts to {args.output_dir}')

if __name__ == '__main__':
    main()

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/database/db.py

SQLAlchemy engine factory supporting SQLite and PostgreSQL URLs.

~~~python
"""SQLAlchemy engine factory supporting SQLite and PostgreSQL URLs."""
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

def create_database_engine(url: str | None = None) -> Engine:
    database_url = url or os.getenv('DATABASE_URL', 'sqlite:///./app_shield.db')
    options = {'check_same_thread': False} if database_url.startswith('sqlite:') else {}
    return create_engine(database_url, connect_args=options, pool_pre_ping=True)

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/database/models.py

Portable account and payment storage definitions for later repositories.

~~~python
"""Portable account and payment storage definitions for later repositories."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class AccountRecord(Base):
    __tablename__ = 'accounts'
    account_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fraud_report_count: Mapped[int] = mapped_column(Integer, default=0)
    is_known_mule: Mapped[bool] = mapped_column(Boolean, default=False)

class TransactionRecord(Base):
    __tablename__ = 'transactions'
    transaction_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey('accounts.account_id'))
    receiver_id: Mapped[str] = mapped_column(ForeignKey('accounts.account_id'))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    device_id: Mapped[str] = mapped_column(String(80))
    payment_type: Mapped[str] = mapped_column(String(40))
    first_time_recipient: Mapped[bool] = mapped_column(Boolean)
    payment_reason: Mapped[str] = mapped_column(String(40))

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## scripts/analyze_transactions.py

Explore synthetic data and fail clearly on integrity violations.

~~~python
"""Explore synthetic data and fail clearly on integrity violations."""
import argparse
from pathlib import Path
import pandas as pd
from scripts.config import FRAUD_TYPES
from scripts.generate_transactions import PROJECT_ROOT

def validate_datasets(transactions: pd.DataFrame, accounts: pd.DataFrame) -> dict[str, int]:
    timestamps = pd.to_datetime(transactions.timestamp, utc=True, errors='coerce')
    created = pd.to_datetime(accounts.set_index('account_id').created_at, utc=True, errors='coerce')
    checks = {
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
    if any(checks.values()):
        raise ValueError(f'Dataset integrity failures: {checks}')
    return checks

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

Run/check: `.venv\Scripts\python -m scripts.analyze_transactions --output data/processed/analysis.txt`.

## tests/test_transaction.py

Validate schema boundaries and forbidden credential fields.

~~~python
"""Validate schema boundaries and forbidden credential fields."""
import pytest
from pydantic import ValidationError
from backend.app.schemas.transaction import Transaction, PaymentReason

@pytest.fixture
def payment():
    return dict(transaction_id='T1', sender_id='A1', receiver_id='A2', amount=800,
                timestamp='2026-01-01T12:00:00Z', device_id='D1', payment_type='upi',
                first_time_recipient=True, payment_reason='family')

@pytest.mark.parametrize('reason', list(PaymentReason))
def test_allowed_reasons(payment, reason):
    assert Transaction(**(payment | {'payment_reason': reason})).payment_reason == reason

@pytest.mark.parametrize('amount', [-10, 0, float('nan'), float('inf')])
def test_invalid_amount(payment, amount):
    with pytest.raises(ValidationError):
        Transaction(**(payment | {'amount': amount}))

@pytest.mark.parametrize('changes', [{'payment_reason': 'invalid'}, {'otp': '123456'},
                                     {'timestamp': '2026-01-01T12:00:00'}, {'sender_id': ''}])
def test_invalid_payment(payment, changes):
    with pytest.raises(ValidationError):
        Transaction(**(payment | changes))

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## tests/test_recipient.py

Automated validation for the Day 1 foundation.

~~~python
from pydantic import ValidationError
import pytest
from backend.app.schemas.recipient import Account

def test_account_validation():
    values = dict(account_id='A1', created_at='2025-01-01T00:00:00Z')
    assert Account(**values).fraud_report_count == 0
    with pytest.raises(ValidationError):
        Account(**values, fraud_report_count=-1)
    with pytest.raises(ValidationError):
        Account(**values, password='secret')

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## tests/test_generation.py

Verify realistic sizes, determinism and past-only recipient features.

~~~python
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

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## tests/test_health.py

Automated validation for the Day 1 foundation.

~~~python
from fastapi.testclient import TestClient
from backend.app.main import app

def test_endpoints():
    with TestClient(app) as client:
        assert client.get('/').json() == {'project': 'APP Shield', 'status': 'running'}
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json() == {'status': 'healthy'}
        assert client.get('/predict').status_code == 404

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/requirements.txt

Declares requested backend, data and test dependencies.

~~~text
fastapi>=0.115,<1
uvicorn>=0.30,<1
pydantic>=2.9,<3
pandas>=2.2,<3
numpy>=1.26,<3
scikit-learn>=1.5,<2
networkx>=3.3,<4
SQLAlchemy>=2.0,<3
psycopg[binary]>=3.2,<4
pytest>=8,<10
httpx>=0.27,<1

~~~

Run/check: `.venv\Scripts\python -m pip install -r backend/requirements.txt`.

## .env.example

Documents local and PostgreSQL database configuration.

~~~text
# SQLite for local work; application reads DATABASE_URL from the environment.
DATABASE_URL=sqlite:///./app_shield.db
# PostgreSQL alternative: postgresql+psycopg://user:password@localhost/app_shield

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## .gitignore

Keeps credentials and runtime artifacts out of version control.

~~~text
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
*.db
.ipynb_checkpoints/
saved_models/*.pkl

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## README.md

Project scope, assumptions and local setup instructions.

~~~text
# APP Shield — Context-Aware Authorized Payment Scam Detection Engine

Traditional fraud detection asks: **Is the person making the transaction really the authorized user?**
APP Shield additionally asks: **Is the genuine authorized user being manipulated by a scammer?**

Day 1 implements only the data and backend foundation. No prediction, model training, frontend, or deployment is implemented. Earlier scaffold modules under api, services, models, rules, and ml remain reserved placeholders.

## Run locally (Python 3.11+)

Run these commands from the app-shield directory:

~~~powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
.venv\Scripts\python -m scripts.generate_transactions
.venv\Scripts\python -m scripts.analyze_transactions --output data/processed/analysis.txt
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

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/api/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/schemas/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/services/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/models/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/features/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/rules/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/database/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## backend/app/utils/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## scripts/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_transactions; .venv\Scripts\python -m pytest -q`.

## tests/__init__.py

Empty initializer enables package imports.

~~~python

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## tests/test_database.py

Verifies portable tables using an in-memory SQLite database.

~~~python
"""Check portable tables and SQLite storage without external services."""
from sqlalchemy.orm import Session
from backend.app.database.db import create_database_engine
from backend.app.database.models import Base, AccountRecord
from datetime import datetime, timezone

def test_sqlite_account_storage():
    engine = create_database_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(AccountRecord(account_id='A1', created_at=datetime.now(timezone.utc)))
        session.commit()
        assert session.get(AccountRecord, 'A1').fraud_report_count == 0
    engine.dispose()
~~~

Run: `.venv\Scripts\python -m pytest -q tests/test_database.py`.
