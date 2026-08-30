"""
Unit Tests for State Machine and Idempotency.
Validates state transitions, illegal transition prevention, and deterministic idempotency hashes.
"""

import pytest
from core.state_machine import state_machine, TransactionState, StateTransitionError

def test_valid_state_transitions():
    assert state_machine.validate_transition(TransactionState.AT_RISK.value, TransactionState.DIAGNOSING.value)
    assert state_machine.validate_transition(TransactionState.DIAGNOSING.value, TransactionState.ACTION_PENDING.value)
    assert state_machine.validate_transition(TransactionState.ACTION_PENDING.value, TransactionState.ACTION_EXECUTED.value)
    assert state_machine.validate_transition(TransactionState.ACTION_EXECUTED.value, TransactionState.RECOVERED.value)

def test_illegal_state_transition_raises_error():
    with pytest.raises(StateTransitionError):
        # Cannot jump from RECOVERED back to AT_RISK or DIAGNOSING
        state_machine.validate_transition(TransactionState.RECOVERED.value, TransactionState.AT_RISK.value)

def test_idempotency_key_deterministic():
    key1 = state_machine.generate_idempotency_key("txn_1001", 0, "IMMEDIATE_RETRY")
    key2 = state_machine.generate_idempotency_key("txn_1001", 0, "IMMEDIATE_RETRY")
    key3 = state_machine.generate_idempotency_key("txn_1001", 1, "IMMEDIATE_RETRY")
    
    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 24
