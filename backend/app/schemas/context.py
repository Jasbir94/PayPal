"""Optional structured circumstances; unknown answers remain distinct from false."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from backend.app.schemas.transaction import PaymentReason
from backend.app.config.context_config import MAX_MESSAGE_LENGTH, MAX_CONTEXT_PERSON_LENGTH

ContextPaymentReason = PaymentReason | Literal['romance', 'marketplace', 'tech_support', 'emergency']


class ContactChannel(str, Enum):
    phone = 'phone'
    sms = 'sms'
    whatsapp = 'whatsapp'
    telegram = 'telegram'
    email = 'email'
    social_media = 'social_media'
    in_person = 'in_person'
    other = 'other'


class AuthorityType(str, Enum):
    police = 'police'
    government = 'government'
    bank = 'bank'
    rbi = 'rbi'
    tax_department = 'tax_department'
    court = 'court'
    company_support = 'company_support'
    employer = 'employer'
    none = 'none'
    other = 'other'


class PaymentContext(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    payment_reason: ContextPaymentReason = PaymentReason.other
    contacted_by_unknown_person: StrictBool | None = None
    contact_channel: ContactChannel | None = None
    who_requested_payment: str | None = Field(default=None, max_length=MAX_CONTEXT_PERSON_LENGTH)
    claimed_authority: StrictBool | None = None
    authority_type: AuthorityType | None = None
    urgent_payment_requested: StrictBool | None = None
    threatened_consequences: StrictBool | None = None
    promised_profit: StrictBool | None = None
    guaranteed_returns_promised: StrictBool | None = None
    requested_secrecy: StrictBool | None = None
    asked_to_install_remote_access: StrictBool | None = None
    asked_to_pay_fee: StrictBool | None = None
    fund_transfer_requested: StrictBool | None = None
    online_relationship: StrictBool | None = None
    relationship_duration_days: int | None = Field(default=None, ge=0, le=36500)
    reported_contradictions: list[str] = Field(default_factory=list, max_length=20)
    user_message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)

    @field_validator('user_message')
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None
