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
