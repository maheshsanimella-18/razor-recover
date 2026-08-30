"""
Unit Tests for Agent Decision Schemas, Fallback Engine, and Bounded Tools.
"""

import pytest
from core.agent import recovery_agent, AgentDecisionOutput
from core.simulator import payment_simulator

def test_deterministic_fallback_decision_structure():
    decision = recovery_agent._fallback_deterministic_decision(
        transaction_id="txn_test_1",
        amount=4500.0,
        failure_reason="network_timeout",
        recovery_prob=0.85,
        payment_method="card",
        retry_count=0
    )
    assert isinstance(decision, AgentDecisionOutput)
    assert decision.recommended_action == "IMMEDIATE_RETRY"
    assert decision.risk_level == "LOW"
    assert not decision.requires_human

def test_fallback_escalates_on_fraud():
    decision = recovery_agent._fallback_deterministic_decision(
        transaction_id="txn_test_fraud",
        amount=18000.0,
        failure_reason="suspected_fraud",
        recovery_prob=0.10,
        payment_method="card",
        retry_count=0
    )
    assert decision.recommended_action == "ESCALATE_TO_HUMAN"
    assert decision.requires_human

def test_payment_simulator_retry():
    res_success = payment_simulator.execute_retry(5000.0, 0.9, force_success=True)
    assert res_success.success
    assert res_success.status_code == "PAYMENT_CAPTURED"
    assert res_success.execution_mode == "SIMULATED_TEST_MODE"

    res_fail = payment_simulator.execute_retry(5000.0, 0.1, force_success=False)
    assert not res_fail.success
    assert res_fail.status_code == "PAYMENT_FAILED"

def test_payment_simulator_payment_link():
    res = payment_simulator.send_payment_link(2500.0, force_success=True)
    assert res.success
    assert res.status_code == "LINK_PAID"
