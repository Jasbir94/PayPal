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
