"""Build point-in-time transaction/recipient fusion data; unlinked modalities stay missing."""
import argparse
import pandas as pd
from backend.app.config.risk_config import PROJECT_ROOT
from backend.app.database.repository import DataRepository
from backend.app.models.transaction_model import TransactionModel
from backend.app.models.recipient_model import RecipientModel
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService

OUT = PROJECT_ROOT / 'data' / 'processed' / 'fusion_dataset.csv'
FEATURES = ['transaction_risk', 'transaction_confidence', 'recipient_risk', 'recipient_confidence',
            'graph_risk', 'graph_confidence', 'graph_available', 'context_risk', 'context_confidence',
            'context_available', 'scenario_risk', 'scenario_confidence', 'scenario_available',
            'psychology_risk', 'psychology_confidence', 'psychology_available',
            'amount_ratio_baseline', 'new_recipient_baseline']

def build(limit=None):
    repo = DataRepository.load()
    tx_service, rec_service = TransactionService(TransactionModel()), RecipientService(RecipientModel(), repo)
    source = repo.transactions
    # Uniformly sample the timeline if requested; indices remain sorted by time.
    if limit and len(source) > limit:
        source = source.iloc[sorted(set(round(i * (len(source) - 1) / (limit - 1)) for i in range(limit)))]
    rows = []
    for row in source.to_dict('records'):
        stamp = pd.Timestamp(row['timestamp'])
        profile = repo.account(str(row['sender_id']), stamp)
        history = repo.sender_history(str(row['sender_id']), stamp, str(row['transaction_id']))
        tx = tx_service.score_transaction(row, history, profile)
        rec = rec_service.score_recipient(str(row['receiver_id']), stamp, str(row['transaction_id']))
        tf, rf = tx['evidence'], rec['evidence']
        # The scenario/psychology corpora have no transaction IDs or timestamps;
        # the mule graph labels are generated account-profile targets. Those
        # signals cannot be joined without leakage, so their availability is 0.
        row_features = {
            'transaction_risk': tx['score'], 'transaction_confidence': .9 if tf['baseline_available'] else .55,
            'recipient_risk': rec['score'], 'recipient_confidence': .85 if rf.get('history_count', 0) else .55,
            'graph_risk': 0.0, 'graph_confidence': 0.0, 'graph_available': 0,
            'context_risk': 0.0, 'context_confidence': 0.0, 'context_available': 0,
            'scenario_risk': 0.0, 'scenario_confidence': 0.0, 'scenario_available': 0,
            'psychology_risk': 0.0, 'psychology_confidence': 0.0, 'psychology_available': 0,
            'amount_ratio_baseline': min(float(tf['amount_ratio']), 20),
            'new_recipient_baseline': int(bool(tf['first_time_recipient'])),
            'transaction_id': row['transaction_id'], 'timestamp': stamp.isoformat(),
            'is_fraud': int(row['is_fraud']),
        }
        rows.append(row_features)
    result = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f'Wrote {len(result)} rows to {OUT}')
    print(f"Class counts: {result.is_fraud.value_counts().to_dict()}")
    print('Leakage exclusions: fraud_type, IDs, future reports, graph target labels, and unrelated text labels.')
    print('Modality coverage: transaction + recipient only; graph/context/scenario/psychology unavailable.')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=2000, help='uniform timeline sample size (default 2000; use 0 for all rows)')
    args = parser.parse_args()
    build(args.limit or None)
