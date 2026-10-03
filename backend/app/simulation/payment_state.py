"""Explicit states and legal transitions for a simulated payment attempt."""
from enum import StrEnum


class PaymentState(StrEnum):
    DRAFT = 'DRAFT'
    REVIEW = 'REVIEW'
    ANALYZING = 'ANALYZING'
    CONTEXT_REQUIRED = 'CONTEXT_REQUIRED'
    WARNING = 'WARNING'
    VERIFICATION_REQUIRED = 'VERIFICATION_REQUIRED'
    READY = 'READY'
    SIMULATED_COMPLETED = 'SIMULATED_COMPLETED'
    CANCELLED = 'CANCELLED'
    SIMULATED_HELD = 'SIMULATED_HELD'
    ERROR = 'ERROR'


TERMINAL_STATES = {PaymentState.SIMULATED_COMPLETED, PaymentState.CANCELLED,
                   PaymentState.SIMULATED_HELD, PaymentState.ERROR}

ALLOWED_TRANSITIONS = {
    PaymentState.DRAFT: {PaymentState.REVIEW, PaymentState.CANCELLED},
    PaymentState.REVIEW: {PaymentState.ANALYZING, PaymentState.CANCELLED},
    PaymentState.ANALYZING: {PaymentState.CONTEXT_REQUIRED, PaymentState.WARNING,
        PaymentState.VERIFICATION_REQUIRED, PaymentState.READY,
        PaymentState.SIMULATED_HELD, PaymentState.ERROR},
    PaymentState.CONTEXT_REQUIRED: {PaymentState.ANALYZING, PaymentState.CANCELLED},
    PaymentState.WARNING: {PaymentState.SIMULATED_COMPLETED, PaymentState.CANCELLED},
    PaymentState.VERIFICATION_REQUIRED: {PaymentState.READY, PaymentState.CANCELLED},
    PaymentState.READY: {PaymentState.SIMULATED_COMPLETED, PaymentState.CANCELLED},
    PaymentState.SIMULATED_COMPLETED: set(),
    PaymentState.CANCELLED: set(),
    PaymentState.SIMULATED_HELD: {PaymentState.CANCELLED},
    PaymentState.ERROR: set(),
}


class InvalidPaymentTransition(ValueError):
    pass


def transition(attempt: dict, next_state: PaymentState) -> None:
    current = PaymentState(attempt['state'])
    next_state = PaymentState(next_state)
    if next_state not in ALLOWED_TRANSITIONS[current]:
        raise InvalidPaymentTransition(f'Cannot move payment attempt from {current} to {next_state}')
    attempt['state'] = next_state.value
