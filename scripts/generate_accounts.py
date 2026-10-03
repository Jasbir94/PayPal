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
