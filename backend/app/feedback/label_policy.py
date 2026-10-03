"""Eligibility rules that prevent weak or behavior-derived labels entering training."""
from datetime import datetime, timedelta, timezone
from backend.app.feedback.models import (FraudLabel, LabelSource, TRAINABLE_LABELS,
    TRAINABLE_SOURCES)

LABEL_MATURITY_DAYS = 7
MIN_TRAINING_LABEL_CONFIDENCE = 0.90


def training_eligibility(label: str, source: str, confidence: float,
                         prediction_timestamp: str | datetime,
                         now: datetime | None = None,
                         maturity_days: int = LABEL_MATURITY_DAYS) -> tuple[bool, str]:
    try:
        label_value, source_value = FraudLabel(label), LabelSource(source)
        confidence_value = float(confidence)
        predicted_at = (datetime.fromisoformat(prediction_timestamp.replace('Z', '+00:00'))
                        if isinstance(prediction_timestamp, str) else prediction_timestamp)
    except (ValueError, TypeError, AttributeError):
        return False, 'invalid_label_metadata'
    if label_value not in TRAINABLE_LABELS:
        return False, 'label_not_final'
    if source_value not in TRAINABLE_SOURCES:
        return False, 'source_not_trusted_for_training'
    if confidence_value < MIN_TRAINING_LABEL_CONFIDENCE:
        return False, 'label_confidence_below_policy'
    if predicted_at.tzinfo is None:
        return False, 'prediction_timestamp_not_timezone_aware'
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return False, 'evaluation_time_not_timezone_aware'
    if predicted_at.astimezone(timezone.utc) > now.astimezone(timezone.utc) - timedelta(days=maturity_days):
        return False, 'prediction_not_mature'
    return True, 'eligible'
