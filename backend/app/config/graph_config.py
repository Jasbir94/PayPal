"""Temporal graph and temporary evidence scoring configuration."""
from backend.app.config.risk_config import PROJECT_ROOT, MODEL_DIR
GRAPH_DATA_DIR = PROJECT_ROOT / 'data' / 'graph'
GRAPH_REPORT_DIR = PROJECT_ROOT / 'data' / 'processed' / 'day5'
GRAPH_MODEL_PATH = MODEL_DIR / 'graph_model.pkl'
GRAPH_FEATURE_PATH = GRAPH_DATA_DIR / 'account_features.csv'
LOOKBACK_HOURS = 24
RAPID_WINDOW_MINUTES = 30
MAX_CACHE_SNAPSHOTS = 4
MAX_CYCLE_LENGTH = 4
MAX_SEARCH_STEPS = 2000
MAX_PATH_DEPTH = 4
MAX_GRAPH_ML_ONLY_SCORE = 45
# Structural features only: intelligence labels, reports and account metadata excluded.
GRAPH_ML_FEATURES = [
    'in_degree', 'out_degree', 'unique_incoming_senders', 'unique_outgoing_receivers',
    'incoming_amount', 'outgoing_amount', 'in_out_amount_ratio', 'rapid_outflow_ratio',
    'median_fund_holding_time', 'matched_outflow_ratio', 'cycle_count',
    'connected_component_size', 'pagerank', 'suspicious_path_depth',
]
