"""Past-only recipient inflow/outflow features; no network or target features."""
import numpy as np
import pandas as pd


def calculate_account_age(created_at, timestamp) -> int:
    created, current = pd.Timestamp(created_at), pd.Timestamp(timestamp)
    if created.tzinfo is None or current.tzinfo is None:
        raise ValueError('Timezone-aware account and payment timestamps required')
    if current < created:
        raise ValueError('Account creation is after scoring timestamp')
    return int((current - created).days)


def count_unique_senders(incoming: pd.DataFrame) -> int:
    return int(incoming.sender_id.nunique()) if not incoming.empty else 0


def calculate_incoming_velocity(incoming: pd.DataFrame, hours: int = 24) -> float:
    return float(len(incoming) / hours)


def calculate_outgoing_ratio(incoming_amount: float, outgoing_amount: float) -> float:
    """Bounded same-window outflow/inflow ratio; no inflow gives neutral zero.

    Outflows can use prior balances, so this is not proof of rapid onward transfer.
    """
    return min(1.0, max(0.0, outgoing_amount / incoming_amount)) if incoming_amount > 0 else 0.0


def calculate_recipient_features(account: dict, history: pd.DataFrame, timestamp) -> dict[str, float]:
    current = pd.Timestamp(timestamp)
    age = calculate_account_age(account['created_at'], current)
    past = history.copy()
    if not past.empty:
        past['timestamp'] = pd.to_datetime(past.timestamp, utc=True)
        past = past[(past.timestamp < current) & (past.timestamp >= current - pd.Timedelta(hours=24))]
    incoming = past[past.receiver_id == account['account_id']]
    outgoing = past[past.sender_id == account['account_id']]
    hour = incoming[incoming.timestamp >= current - pd.Timedelta(hours=1)]
    inflow, outflow = float(incoming.amount.sum()), float(outgoing.amount.sum())
    observed_ratio = calculate_outgoing_ratio(inflow, outflow)
    # Synthetic mule accounts have little outgoing history. Use the documented
    # pre-observation profile as a separate historical approximation, never a target.
    historical_ratio = float(account.get('outgoing_ratio', 0.0))
    effective_ratio = max(observed_ratio, historical_ratio)
    unique = count_unique_senders(incoming)
    return {
        'account_age_days': age,
        'incoming_transactions_1h': len(hour), 'incoming_transactions_24h': len(incoming),
        'unique_senders_1h': count_unique_senders(hour), 'unique_senders_24h': unique,
        'incoming_amount_24h': inflow, 'outgoing_amount_24h': outflow,
        'outgoing_ratio': effective_ratio, 'observed_outgoing_ratio': observed_ratio,
        'fraud_report_count': int(account.get('fraud_report_count', 0)),
        'transaction_velocity': calculate_incoming_velocity(incoming),
        'sender_diversity': unique / len(incoming) if len(incoming) else 0.0,
        'average_incoming_amount': float(incoming.amount.mean()) if len(incoming) else 0.0,
        'median_incoming_amount': float(incoming.amount.median()) if len(incoming) else 0.0,
        'inflow_outflow_imbalance': (inflow - outflow) / max(inflow + outflow, 1.0),
        'average_holding_minutes': float(account.get('average_holding_minutes', 0)),
    }
