"""Risk-to-action policy; uncertainty can trigger verification even at moderate risk."""
from backend.app.config.risk_config import DECISION_THRESHOLDS, LOW_CONFIDENCE_REVIEW_THRESHOLD

def recommend(score, confidence, family_count):
    risk = float(score) / 100
    if risk >= DECISION_THRESHOLDS['block'] and confidence >= .75:
        return 'BLOCK_AND_ESCALATE'
    if risk >= DECISION_THRESHOLDS['step_up']:
        return 'STEP_UP_VERIFICATION'
    if risk >= DECISION_THRESHOLDS['review'] or (risk >= .30 and confidence < LOW_CONFIDENCE_REVIEW_THRESHOLD):
        return 'WARN_AND_REVIEW'
    if risk >= DECISION_THRESHOLDS['allow'] or family_count < 3:
        return 'ALLOW_WITH_WARNING'
    return 'ALLOW'
