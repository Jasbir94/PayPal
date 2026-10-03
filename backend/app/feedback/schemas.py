"""Strict local/research feedback API payloads."""
from datetime import datetime, timezone
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.app.feedback.models import FraudLabel, LabelSource, UserAction
_CREDENTIAL=re.compile(r'(?i)\b(?:otp|pin|cvv|cvc|password)\s*[:=]?\s*\S{3,}|(?<!\d)(?:\d[ -]?){13,19}(?!\d)')


class UserActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: UserAction
    detail: str | None = Field(default=None, max_length=240)

    @field_validator('detail')
    @classmethod
    def reject_credentials(cls,value):
        if value and _CREDENTIAL.search(value):raise ValueError('Do not submit payment credentials or card numbers.')
        return value


class FraudLabelRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: FraudLabel
    source: LabelSource
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    label_timestamp: datetime | None = None
    note: str | None = Field(default=None, max_length=240)

    @field_validator('label_timestamp')
    @classmethod
    def timestamp_must_be_aware_and_not_future(cls, value):
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError('label_timestamp must include a timezone')
        if value.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError('label_timestamp cannot be in the future')
        return value.astimezone(timezone.utc)

    @field_validator('note')
    @classmethod
    def reject_credentials(cls,value):
        if value and _CREDENTIAL.search(value):raise ValueError('Do not submit payment credentials or card numbers.')
        return value
