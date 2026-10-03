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

# Day 6 grouped fusion and intervention policy. These are transparent MVP
# defaults, not claimed optimal thresholds; ml.fusion.evaluate selects and
# reports validation thresholds for the synthetic training corpus.
FUSION_WEIGHTS = {'user_side': .25, 'recipient_side': .30, 'manipulation_side': .45}
FUSION_MODEL_VERSION = 'manual-grouped-v1'
FUSION_MODEL_PATH = MODEL_DIR / 'fusion_model.pkl'
FUSION_CALIBRATION_PATH = MODEL_DIR / 'calibration_model.pkl'
DECISION_THRESHOLDS = {'allow': .20, 'review': .40, 'step_up': .65, 'block': .88}
CONFIDENCE_FAMILY_PENALTY = .12
CONFIDENCE_AGREEMENT_FLOOR = .55
CONFIDENCE_AGREEMENT_WEIGHT = .25
LOW_CONFIDENCE_REVIEW_THRESHOLD = .45
MAX_CROSS_LAYER_BONUS = 18.0
MAX_PROTECTIVE_REDUCTION = 20.0
PROTECTIVE_EVIDENCE_WEIGHTS = {
    'known_recipient': 6.0, 'repeated_payments': 5.0, 'established_account': 5.0,
    'normal_amount': 4.0, 'no_unknown_contact': 2.0, 'no_manipulation_signals': 3.0,
}
MAX_REQUEST_BODY_BYTES = 65_536
API_RATE_LIMIT_REQUESTS = 120
API_RATE_LIMIT_WINDOW_SECONDS = 60
MAX_CONVERSATION_MESSAGES = 20
MAX_CONVERSATION_MESSAGE_LENGTH = 2_000
MAX_CONVERSATION_TOTAL_CHARS = 6_000
MAX_IDENTIFIER_LENGTH = 128


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
