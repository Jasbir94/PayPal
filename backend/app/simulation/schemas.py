"""Strict inputs and user-safe views for the synthetic payment simulator."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.app.schemas.context import PaymentContext
from backend.app.schemas.conversation import ConversationMessage


class CreatePaymentAttempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sender_alias: str = Field(min_length=1, max_length=16)
    recipient_alias: str = Field(min_length=1, max_length=16)
    amount: float = Field(gt=0, le=10_000_000, allow_inf_nan=False)
    payment_reason: Literal['family','friend','shopping','investment','job','government',
        'bank_support','loan','refund','relationship','marketplace','emergency','tech_support','other'] = 'other'
    payment_type: Literal['upi','wallet','bank_transfer'] = 'upi'
    note: str = Field(default='', max_length=240)
    idempotency_key: str = Field(min_length=8, max_length=100)


class AnalyzePaymentAttempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: PaymentContext = Field(default_factory=PaymentContext)
    messages: list[ConversationMessage] = Field(default_factory=list, max_length=20)


class ContinuePaymentAttempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    acknowledged_warning: bool = False


class VerifyPaymentAttempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['verified_independently','reviewed_warning','cancel']


class UserMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=300)

    @field_validator('message')
    @classmethod
    def reject_blank(cls, value):
        return value.strip()
