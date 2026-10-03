"""Deterministic Day 5 overlays on existing account IDs; Day 1 CSVs stay intact."""
import json
import numpy as np
import pandas as pd
from backend.app.config.risk_config import DATA_DIR, SEED
from backend.app.config.graph_config import GRAPH_DATA_DIR

def generate(seed=SEED):
    rng = np.random.default_rng(seed)
    accounts = pd.read_csv(DATA_DIR / 'accounts.csv')
    assignments = {}
    # Disjoint account targets stratified by known-mule and suspicious flags.
    for _, group in accounts.groupby(['is_known_mule', 'is_suspicious']):
        ids = rng.permutation(group.account_id)
        a, b = int(len(ids) * .6), int(len(ids) * .8)
        for split, subset in [('train', ids[:a]), ('validation', ids[a:b]), ('test', ids[b:])]:
            assignments.update({account: split for account in subset})
    rows, evaluation = [], []
    for split, day in [('train', 5), ('validation', 15), ('test', 25)]:
        eligible = accounts[accounts.account_id.map(assignments).eq(split)]
        normal = eligible[~eligible.is_suspicious].account_id.tolist()
        mules = eligible[eligible.is_suspicious].account_id.tolist()
        merchants = normal[:24]
        for account in eligible.itertuples():
            evaluation.append({'account_id': account.account_id, 'split': split,
                'at': f'2026-01-{day + 1:02d}T06:00:00+00:00',
                'is_known_mule': int(account.is_known_mule),
                'is_suspicious': int(account.is_suspicious),
                'role': 'mule' if account.is_suspicious else
                    ('merchant' if account.account_id in merchants else 'personal')})
        def edge(sender, receiver, amount, stamp):
            rows.append({'transaction_id': f'G{len(rows):06d}', 'sender_id': sender,
                'receiver_id': receiver, 'amount': round(float(amount), 2), 'timestamp': stamp.isoformat()})
        base = pd.Timestamp(f'2026-01-{day:02d}T08:00:00+00:00')
        # Collector -> distributor -> cashout, with some backward small cycles.
        for index, mule in enumerate(mules):
            start = base + pd.Timedelta(minutes=15 * index)
            victims = rng.choice(normal[24:], size=int(rng.integers(15, 56)), replace=False)
            total = 0
            for victim in victims:
                amount = int(rng.integers(1000, 6001))
                edge(victim, mule, amount, start)
                total += amount
            onward = mules[(index + 1) % len(mules)]
            ratio = float(rng.uniform(.82, .98))
            edge(mule, onward, total * ratio, start + pd.Timedelta(minutes=2))
            recipients = rng.choice(normal[24:], size=5, replace=False)
            for receiver in recipients:
                edge(onward, receiver, total * ratio * .96 / 5, start + pd.Timedelta(minutes=4))
            if index % 3 == 0:
                edge(recipients[0], mule, total * .01, start + pd.Timedelta(minutes=6))
        # Six hard-negative businesses plus fast settlement / payroll variants.
        kinds = ['online_merchant', 'restaurant', 'tuition', 'seller', 'payroll', 'fundraiser']
        for index, merchant in enumerate(merchants):
            start = base + pd.Timedelta(minutes=12 * index)
            customers = rng.choice(normal[24:], size=int(rng.integers(25, 61)), replace=False)
            total = 0
            for customer in customers:
                amount = int(rng.integers(500, 5001))
                edge(customer, merchant, amount, start)
                total += amount
            suppliers = rng.choice(normal[24:], size=2 if index % 6 else 8, replace=False)
            # Some genuine fast-settlement accounts deliberately resemble mules.
            delay = 10 if index % 12 == 0 else int(rng.integers(240, 720))
            for supplier in suppliers:
                edge(merchant, supplier, total * .90 / len(suppliers), start + pd.Timedelta(minutes=delay))
            for item in evaluation:
                if item['account_id'] == merchant:
                    item['role'] = kinds[index % len(kinds)]
    overlay = pd.DataFrame(rows).sort_values(['timestamp', 'transaction_id'])
    # Original profile reports are explicitly pre-observation synthetic snapshots.
    intel = [{'account_id': row.account_id, 'kind': 'fraud_report',
              'observed_at': '2025-12-31T00:00:00+00:00'}
             for row in accounts.itertuples() if row.fraud_report_count > 0]
    # Small external reference set; do not expose all target labels as intelligence.
    known = accounts.loc[accounts.is_known_mule, 'account_id'].tolist()
    intel += [{'account_id': account, 'kind': 'known_mule', 'observed_at': '2025-12-31T00:00:00+00:00'}
              for account in (known[0], known[-1])]
    GRAPH_DATA_DIR.mkdir(parents=True, exist_ok=True)
    overlay.to_csv(GRAPH_DATA_DIR / 'network_transactions.csv', index=False)
    pd.DataFrame(evaluation).to_csv(GRAPH_DATA_DIR / 'evaluation_accounts.csv', index=False)
    pd.DataFrame(intel).to_csv(GRAPH_DATA_DIR / 'intelligence.csv', index=False)
    metadata = {'seed': seed, 'base_data_unchanged': True, 'overlay_transactions': len(overlay),
        'evaluation_accounts': len(evaluation), 'intelligence_seed_count': 2,
        'target': 'Original is_known_mule; unlabeled suspicious accounts remain target-negative.',
        'limitations': '40 suspicious accounts drive generated mule patterns; 18 are labeled known. '
                        'Labels and synthetic scenario design are imperfect proxies, not real-world truth.'}
    (GRAPH_DATA_DIR / 'generation_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(metadata, indent=2))
    return overlay

if __name__ == '__main__':
    generate()
