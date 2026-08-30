"""
Transaction Lifecycle State Machine and Idempotency Manager.
Guarantees deterministic, valid state transitions for all revenue recovery events.
"""

from enum import Enum
import hashlib
from datetime import datetime, timezone
from typing import Optional

class TransactionState(str, Enum):
    AT_RISK = "AT_RISK"
    DIAGNOSING = "DIAGNOSING"
    ACTION_PENDING = "ACTION_PENDING"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    RECOVERED = "RECOVERED"
    ESCALATED = "ESCALATED"
    STOPPED = "STOPPED"

# Allowed unidirectional / acyclic state transitions
VALID_TRANSITIONS = {
    TransactionState.AT_RISK: {
        TransactionState.DIAGNOSING,
        TransactionState.ESCALATED,
        TransactionState.STOPPED
    },
    TransactionState.DIAGNOSING: {
        TransactionState.ACTION_PENDING,
        TransactionState.ESCALATED,
        TransactionState.STOPPED
    },
    TransactionState.ACTION_PENDING: {
        TransactionState.ACTION_EXECUTED,
        TransactionState.ESCALATED,
        TransactionState.STOPPED
    },
    TransactionState.ACTION_EXECUTED: {
        TransactionState.RECOVERED,
        TransactionState.AT_RISK,       # For retry loop (bounded by policy)
        TransactionState.ESCALATED,
        TransactionState.STOPPED
    },
    TransactionState.RECOVERED: set(),   # Terminal state
    TransactionState.ESCALATED: {
        TransactionState.ACTION_PENDING, # Human approved action
        TransactionState.STOPPED         # Human rejected
    },
    TransactionState.STOPPED: set()      # Terminal state
}

class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass

class TransactionStateMachine:
    @staticmethod
    def validate_transition(current_state: str, next_state: str) -> bool:
        try:
            curr = TransactionState(current_state)
            nxt = TransactionState(next_state)
        except ValueError:
            raise StateTransitionError(f"Invalid state name: '{current_state}' or '{next_state}'")

        if nxt not in VALID_TRANSITIONS.get(curr, set()):
            raise StateTransitionError(f"Illegal state transition from {curr.value} to {nxt.value}")
        return True

    @staticmethod
    def generate_idempotency_key(txn_id: str, retry_count: int, action: str) -> str:
        """Generates a deterministic idempotency key for bounded execution."""
        payload = f"{txn_id}:{retry_count}:{action}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

state_machine = TransactionStateMachine()
