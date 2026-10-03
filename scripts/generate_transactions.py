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
