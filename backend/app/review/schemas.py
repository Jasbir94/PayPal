"""Constrained analyst review outcomes."""
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field
from pydantic import field_validator
_CREDENTIAL=re.compile(r'(?i)\b(?:otp|pin|cvv|cvc|password)\s*[:=]?\s*\S{3,}|(?<!\d)(?:\d[ -]?){13,19}(?!\d)')


class ReviewOutcomeRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    outcome: Literal['CONFIRMED_SCAM','LIKELY_SCAM','LEGITIMATE','NEEDS_MORE_INFORMATION']
    note: str | None=Field(default=None,max_length=240)

    @field_validator('note')
    @classmethod
    def reject_credentials(cls,value):
        if value and _CREDENTIAL.search(value):raise ValueError('Do not submit payment credentials or card numbers.')
        return value
