"""Features from information available before the current payment."""
import numpy as np
import pandas as pd

LARGE_DEVIATION_RATIO = 3.0
MODEL_FEATURES = ['amount_ratio', 'is_large_deviation', 'is_new_recipient',
                  'recipient_age_bucket', 'recipient_activity_level', 'recipient_reported']

def add_derived_features(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return a copy; never use labels or known-mule flags as predictors."""
    result = transactions.copy()
    if (result.sender_average_amount <= 0).any():
        raise ValueError('Sender averages must be positive')
    result['amount_ratio'] = result.amount / result.sender_average_amount
    result['is_large_deviation'] = result.amount_ratio > LARGE_DEVIATION_RATIO
    result['is_new_recipient'] = result.first_time_recipient.astype(bool)
    result['recipient_age_bucket'] = pd.cut(result.account_age_days,
        bins=[-1, 7, 30, 180, np.inf], labels=['week', 'month', 'six_months', 'established'])
    result['recipient_activity_level'] = pd.cut(result.incoming_transactions_24h,
        bins=[-1, 5, 20, np.inf], labels=['low', 'medium', 'high'])
    result['recipient_reported'] = result.fraud_reports > 0
    return result


def calculate_amount_ratio(amount: float, average: float) -> float:
    """Unknown/zero baseline yields neutral ratio, not infinity or fabricated risk."""
    return float(amount / average) if average > 0 else 1.0


def calculate_sender_average_amount(history: pd.DataFrame, fallback: float = 0.0) -> float:
    return float(history.amount.mean()) if not history.empty else float(fallback)


def is_first_time_recipient(receiver_id: str, history: pd.DataFrame,
                            usual_recipients: str = '') -> bool:
    known = set(usual_recipients.split('|')) if usual_recipients else set()
    return receiver_id not in known and (history.empty or not history.receiver_id.eq(receiver_id).any())


def calculate_recent_transaction_count(history: pd.DataFrame, timestamp: pd.Timestamp,
                                       hours: int = 24) -> int:
    if history.empty:
        return 0
    return int(((history.timestamp >= timestamp - pd.Timedelta(hours=hours)) &
                (history.timestamp < timestamp)).sum())


def calculate_recent_average_amount(history: pd.DataFrame, timestamp: pd.Timestamp,
                                     hours: int = 24, fallback: float = 0.0) -> float:
    if history.empty:
        return float(fallback)
    recent = history[(history.timestamp >= timestamp - pd.Timedelta(hours=hours)) &
                     (history.timestamp < timestamp)]
    return float(recent.amount.mean()) if not recent.empty else float(fallback)


def calculate_amount_deviation(amount: float, average: float) -> float:
    return calculate_amount_ratio(amount, average) - 1.0


def extract_transaction_features(transaction: dict, history: pd.DataFrame,
                                 sender_profile: dict | None = None) -> dict[str, float]:
    """Extract past-only behavioral features; ignore client-supplied first-time flags.

    Timestamp must carry a timezone. Profile fallback represents Day 1's simulated
    pre-observation average, usual device and usual recipients, not future activity.
    """
    profile = sender_profile or {}
    timestamp = pd.Timestamp(transaction['timestamp'])
    if timestamp.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    timestamp = timestamp.tz_convert('UTC')
    past = history.copy()
    if not past.empty:
        past['timestamp'] = pd.to_datetime(past.timestamp, utc=True)
        past = past[(past.sender_id == transaction['sender_id']) & (past.timestamp < timestamp)]
        if transaction.get('transaction_id'):
            past = past[past.transaction_id != transaction['transaction_id']]
    average = calculate_sender_average_amount(past, float(profile.get('average_transaction_amount', 0)))
    recent_average = calculate_recent_average_amount(past, timestamp, fallback=average)
    first_time = is_first_time_recipient(transaction['receiver_id'], past,
                                         str(profile.get('usual_recipients', '')))
    usual_device = profile.get('usual_device')
    if not usual_device and not past.empty:
        usual_device = past.device_id.mode().iloc[0]
    hour = timestamp.hour
    start, end = int(profile.get('normal_hour_start', 0)), int(profile.get('normal_hour_end', 24))
    amount = float(transaction['amount'])
    return {
        'amount': amount, 'sender_average_amount': average,
        'amount_ratio': calculate_amount_ratio(amount, average),
        'first_time_recipient': int(first_time), 'transaction_hour': hour,
        'device_changed': int(bool(usual_device and transaction['device_id'] != usual_device)),
        'transactions_last_1h': calculate_recent_transaction_count(past, timestamp, 1),
        'transactions_last_24h': calculate_recent_transaction_count(past, timestamp, 24),
        'amount_vs_recent_average': calculate_amount_ratio(amount, recent_average),
        'amount_deviation': calculate_amount_deviation(amount, average),
        'recipient_seen_before': int(not first_time),
        'outside_usual_hours': int(not start <= hour < end),
        'history_count': len(past), 'baseline_available': int(average > 0),
    }
