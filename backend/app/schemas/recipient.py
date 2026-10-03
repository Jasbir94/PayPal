"""Account metadata; credentials are deliberately excluded."""
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime

class Account(BaseModel):
    model_config = ConfigDict(extra='forbid')
    account_id: str = Field(min_length=1)
    created_at: AwareDatetime
    fraud_report_count: int = Field(default=0, ge=0)
    is_known_mule: bool = False

Recipient = Account
