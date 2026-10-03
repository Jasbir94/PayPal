"""Central Day 3 MVP weights and evidence thresholds, not calibrated probabilities."""
from backend.app.config.risk_config import PROJECT_ROOT, MODEL_DIR

LABELS_PATH = PROJECT_ROOT / 'ml' / 'scenario' / 'labels.json'
SCENARIO_MODEL_PATH = MODEL_DIR / 'scenario_pipeline.pkl'
SCENARIO_DATA_PATH = PROJECT_ROOT / 'data' / 'synthetic' / 'scam_messages.csv'
SCENARIO_REPORT_DIR = PROJECT_ROOT / 'data' / 'processed' / 'day3'
CONTEXT_POINTS = {
    'unknown_contact': 10, 'authority_claim': 15, 'urgent_payment_request': 10,
    'threatened_consequences': 20, 'promised_profit_claim': 15,
    'guaranteed_profit_claim': 10, 'secrecy_request': 10, 'remote_access_request': 20,
    'payment_fee_request': 10, 'fund_transfer_request': 10,
    'authority_threat_urgency_combination': 30, 'unsolicited_profit_offer': 35,
    'profit_offer_new_recipient': 10, 'job_fee_request': 40,
    'bank_support_transfer_request': 25, 'remote_access_payment_instruction': 30,
    'online_relationship_money_request': 20,
}
EXTENDED_WEIGHTS = {'transaction': .25, 'recipient': .30, 'context': .25, 'scenario': .20}
TEXT_WEIGHT = .35
CONTEXT_SCENARIO_WEIGHT = .65
MIN_SCENARIO_EVIDENCE = .55
MODEL_MIN_CONFIDENCE = .40
MODEL_MIN_MARGIN = .10
MIN_CONTEXT_FOR_SCENARIO_RISK = 20
MAX_MESSAGE_LENGTH = 4000
MAX_CONTEXT_PERSON_LENGTH = 120
SCENARIO_SEED = 42
SAMPLES_PER_TEMPLATE = 50

SCENARIO_RISK_CONTEXT_FACTOR = .65
SCENARIO_RISK_CONFIDENCE_FACTOR = .35
PRESERVE_DAY2_WITHOUT_CONTEXT = True
