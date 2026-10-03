"""Validated payment data without financial credentials."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime

class PaymentReason(str, Enum):
    family = 'family'
    friend = 'friend'
    shopping = 'shopping'
    investment = 'investment'
    job = 'job'
    government = 'government'
    bank_support = 'bank_support'
    loan = 'loan'
    refund = 'refund'
    relationship = 'relationship'
    other = 'other'

class Transaction(BaseModel):
    """A positive, timestamped authorized payment."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    transaction_id: str = Field(min_length=1,max_length=128)
    sender_id: str = Field(min_length=1,max_length=128)
    receiver_id: str = Field(min_length=1,max_length=128)
    amount: float = Field(gt=0)
    timestamp: AwareDatetime
    device_id: str = Field(min_length=1,max_length=128)
    payment_type: str = Field(min_length=1,max_length=40)
    first_time_recipient: bool
    payment_reason: PaymentReason
