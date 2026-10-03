"""Small log-safety helpers; payment/scam message bodies are never logged."""
import hashlib
import os
import re

_PROCESS_SALT=os.urandom(32)
_SECRET_PATTERNS=(
    re.compile(r'(?i)\b(otp|one[- ]time password|pin|password|passcode|cvv|cvc)\b\s*(?:is|:|=)?\s*[A-Za-z0-9-]{3,}'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*'),
    re.compile(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)'),
)

def redact_sensitive_text(value: str) -> str:
    result=value
    for pattern in _SECRET_PATTERNS:
        result=pattern.sub(lambda match:(match.group(1)+' [REDACTED]') if match.lastindex else '[REDACTED]',result)
    return result

def pseudonymize(identifier: str) -> str:
    """Process-scoped stable reference that cannot be reversed without the salt."""
    return hashlib.sha256(_PROCESS_SALT + str(identifier).encode('utf-8')).hexdigest()[:16]
