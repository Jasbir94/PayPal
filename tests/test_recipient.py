from pydantic import ValidationError
import pytest
from backend.app.schemas.recipient import Account

def test_account_validation():
    values = dict(account_id='A1', created_at='2025-01-01T00:00:00Z')
    assert Account(**values).fraud_report_count == 0
    with pytest.raises(ValidationError):
        Account(**values, fraud_report_count=-1)
    with pytest.raises(ValidationError):
        Account(**values, password='secret')
