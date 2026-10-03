from backend.app.security.privacy import pseudonymize, redact_sensitive_text


def test_sensitive_values_are_redacted():
    text = 'OTP 123456 PIN: 4321 CVV 123 card 4111111111111111 Bearer abc.def'
    cleaned = redact_sensitive_text(text)
    assert '123456' not in cleaned
    assert '4321' not in cleaned
    assert '4111111111111111' not in cleaned
    assert 'abc.def' not in cleaned


def test_identifier_pseudonyms_are_stable_but_not_raw():
    pseudonym = pseudonymize('customer-123')
    assert pseudonym == pseudonymize('customer-123')
    assert pseudonym != 'customer-123'
