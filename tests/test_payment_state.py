import pytest
from backend.app.simulation.payment_state import PaymentState, transition, InvalidPaymentTransition


def test_valid_state_transition_and_invalid_double_analysis_transition():
    attempt={'state':PaymentState.DRAFT.value}
    transition(attempt,PaymentState.REVIEW)
    transition(attempt,PaymentState.ANALYZING)
    transition(attempt,PaymentState.READY)
    transition(attempt,PaymentState.SIMULATED_COMPLETED)
    with pytest.raises(InvalidPaymentTransition):
        transition(attempt,PaymentState.ANALYZING)


def test_held_payment_can_be_cancelled_but_not_completed():
    attempt={'state':PaymentState.SIMULATED_HELD.value}
    with pytest.raises(InvalidPaymentTransition):
        transition(attempt,PaymentState.SIMULATED_COMPLETED)
    transition(attempt,PaymentState.CANCELLED)
