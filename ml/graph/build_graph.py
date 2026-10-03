"""Export temporally safe account features from the shared transaction history."""
import json
from time import perf_counter
import pandas as pd
from backend.app.database.repository import DataRepository
from backend.app.graph.data import load_graph_builder
from backend.app.graph.graph_features import calculate_graph_features
from backend.app.features.recipient_features import calculate_account_age
from backend.app.config.graph_config import GRAPH_DATA_DIR, GRAPH_FEATURE_PATH, GRAPH_REPORT_DIR

def build():
    repository = DataRepository.load()
    builder = load_graph_builder(repository)
    evaluation = pd.read_csv(GRAPH_DATA_DIR / 'evaluation_accounts.csv')
    rows, timings = [], []
    for item in evaluation.itertuples():
        stamp = pd.Timestamp(item.at)
        graph = builder.build_graph_until(stamp)
        started = perf_counter()
        features = calculate_graph_features(graph, item.account_id)
        timings.append((perf_counter() - started) * 1000)
        rows.append({**item._asdict(), **features,
            'account_age_days': calculate_account_age(repository.accounts.loc[item.account_id, 'created_at'], stamp)})
    data = pd.DataFrame(rows)
    data.to_csv(GRAPH_FEATURE_PATH, index=False)
    GRAPH_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {'base_transactions': len(repository.transactions), 'total_transactions': len(builder.transactions),
        'accounts': len(data), 'snapshot_build_count': builder.build_count,
        'snapshot_build_ms': [graph.graph['build_ms'] for graph in builder._cache.values()],
        'feature_ms_median': float(pd.Series(timings).median()),
        'feature_ms_p95': float(pd.Series(timings).quantile(.95)),
        'lookback_hours': 24,
        'split_note': 'Disjoint target accounts, 60/20/20 stratified within profile-label groups. '
                      'Training Jan 6, validation Jan 16, testing Jan 26. Base graph neighbors may cross splits; '
                      'not a fully component-disjoint graph-inductive evaluation.'}
    (GRAPH_REPORT_DIR / 'build_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return data

if __name__ == '__main__':
    build()
