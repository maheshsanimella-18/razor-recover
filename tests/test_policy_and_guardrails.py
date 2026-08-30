"""
Unit Tests for Policy Engine and Safety Guardrails.
Covers retry limits, high-value limits, fraud blocks, and sub-threshold probability rules.
"""

import pytest
from core.policy import RecoveryPolicyEngine, RecoveryPolicyConfig

@pytest.fixture
def policy():
    return RecoveryPolicyEngine()

def test_fraud_syndicate_blocked(policy):
    res = policy.evaluate_action(
        action="IMMEDIATE_RETRY",
        amount=5000.0,
        retry_count=0,
        failure_reason="network_timeout",
        recovery_probability=0.85,
        is_fraud_connected=True,
        fraud_cluster_info="Linked to bad IP"
    )
    assert not res.is_allowed
    assert res.policy_code == "FRAUD_GRAPH_BLOCKED"
    assert res.requires_human_escalation

def test_max_retries_exceeded(policy):
    res = policy.evaluate_action(
        action="IMMEDIATE_RETRY",
        amount=2000.0,
        retry_count=3,
        failure_reason="network_timeout",
        recovery_probability=0.80
    )
    assert not res.is_allowed
    assert res.policy_code == "MAX_RETRIES_EXCEEDED"

def test_critical_security_failure_reason(policy):
    res = policy.evaluate_action(
        action="IMMEDIATE_RETRY",
        amount=1000.0,
        retry_count=0,
        failure_reason="suspected_fraud",
        recovery_probability=0.50
    )
    assert not res.is_allowed
    assert res.policy_code == "SECURITY_CRITICAL_FAILURE"

def test_high_value_mandatory_review(policy):
    res = policy.evaluate_action(
        action="IMMEDIATE_RETRY",
        amount=60000.0,  # Exceeds 50k hard cap
        retry_count=0,
        failure_reason="network_timeout",
        recovery_probability=0.90
    )
    assert not res.is_allowed
    assert res.policy_code == "HIGH_VALUE_MANDATORY_REVIEW"

def test_sub_threshold_probability_blocked(policy):
    res = policy.evaluate_action(
        action="IMMEDIATE_RETRY",
        amount=3000.0,
        retry_count=0,
        failure_reason="network_timeout",
        recovery_probability=0.10  # Below 0.20 min threshold
    )
    assert not res.is_allowed
    assert res.policy_code == "SUB_THRESHOLD_PROBABILITY"

def test_valid_action_permitted(policy):
    res = policy.evaluate_action(
        action="IMMEDIATE_RETRY",
        amount=4500.0,
        retry_count=0,
        failure_reason="network_timeout",
        recovery_probability=0.85
    )
    assert res.is_allowed
    assert res.policy_code == "POLICY_APPROVED"
