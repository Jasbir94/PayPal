"""Validate schema boundaries and forbidden credential fields."""
import pytest
from pydantic import ValidationError
from backend.app.schemas.transaction import Transaction, PaymentReason

@pytest.fixture
def payment():
    return dict(transaction_id='T1', sender_id='A1', receiver_id='A2', amount=800,
                timestamp='2026-01-01T12:00:00Z', device_id='D1', payment_type='upi',
                first_time_recipient=True, payment_reason='family')

@pytest.mark.parametrize('reason', list(PaymentReason))
def test_allowed_reasons(payment, reason):
    assert Transaction(**(payment | {'payment_reason': reason})).payment_reason == reason

@pytest.mark.parametrize('amount', [-10, 0, float('nan'), float('inf')])
def test_invalid_amount(payment, amount):
    with pytest.raises(ValidationError):
        Transaction(**(payment | {'amount': amount}))

@pytest.mark.parametrize('changes', [{'payment_reason': 'invalid'}, {'otp': '123456'},
                                     {'timestamp': '2026-01-01T12:00:00'}, {'sender_id': ''}])
def test_invalid_payment(payment, changes):
    with pytest.raises(ValidationError):
        Transaction(**(payment | changes))
