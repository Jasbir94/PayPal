"""Day 4 evidence scoring and overlap controls; no calibrated fraud probability."""
from backend.app.config.risk_config import PROJECT_ROOT, MODEL_DIR

PSYCHOLOGY_LABELS_PATH = PROJECT_ROOT / 'ml' / 'psychology' / 'labels.json'
PSYCHOLOGY_DATA_PATH = PROJECT_ROOT / 'data' / 'synthetic' / 'psychology_messages.csv'
PSYCHOLOGY_MODEL_PATH = MODEL_DIR / 'psychology_pipeline.pkl'
PSYCHOLOGY_THRESHOLDS_PATH = MODEL_DIR / 'psychology_thresholds.json'
PSYCHOLOGY_REPORT_DIR = PROJECT_ROOT / 'data' / 'processed' / 'day4'
SEED = 42
DEFAULT_THRESHOLD = .5
THRESHOLD_GRID = (.30, .40, .50, .60, .70)
STRONG_RULE_THRESHOLD = .60
BENIGN_SCORE_CAP = .15
RISK_STRONGEST_WEIGHT = 40
RISK_ADDITIONAL_TECHNIQUE_POINTS = 8
RISK_COUNT_BONUS_CAP = 24
ML_ONLY_RISK_CAP = 45
DAY4_WEIGHTS = {'transaction': .20, 'recipient': .25, 'context': .20, 'scenario': .15, 'psychology': .20}
MAX_OVERLAP_DISCOUNT = .50
HIGH_RISK_COMBINATIONS = {
    'authority_fear_urgency_combination': (('authority', 'fear', 'urgency'), 35),
    'reward_scarcity_urgency_combination': (('reward', 'scarcity', 'urgency'), 35),
    'trust_commitment_secrecy_combination': (('trust', 'commitment', 'secrecy'), 30),
    'relationship_emotional_pressure_combination': (('trust', 'emotional_pressure'), 15),
}
SCENARIO_TECHNIQUES = {
    'government_impersonation': ('authority', 'fear', 'urgency'),
    'bank_impersonation': ('authority', 'fear', 'urgency'),
    'investment_scam': ('reward', 'scarcity', 'social_proof', 'urgency'),
    'romance_scam': ('trust', 'commitment', 'emotional_pressure'),
    'fake_job_scam': ('authority', 'reward', 'urgency'),
    'tech_support_scam': ('authority', 'fear', 'trust'),
    'family_emergency_scam': ('emotional_pressure', 'urgency', 'secrecy'),
    'marketplace_scam': ('trust', 'urgency'),
    'loan_scam': ('reward', 'urgency', 'commitment'),
    'refund_scam': ('trust', 'urgency', 'commitment'),
}
CONTEXT_OVERLAP_FIELDS = {
    'authority': ('claimed_authority',), 'fear': ('threatened_consequences',),
    'urgency': ('urgent_payment_requested',), 'reward': ('promised_profit', 'guaranteed_returns_promised'),
    'secrecy': ('requested_secrecy',),
}
