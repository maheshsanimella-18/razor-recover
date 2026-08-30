"""
Safety Guardrails and Stopping Rules for Autonomous Payment Recovery.
Prevents infinite retry loops, limits financial risk, and handles safety escalations.
"""

from .policy import policy_engine, PolicyEvaluationResult

def evaluate_safety_guardrails(
    retry_count: int,
    amount: float,
    failure_reason: str,
    recovery_probability: float,
    is_fraud_connected: bool = False,
    fraud_cluster_details: str = "",
    proposed_action: str = "IMMEDIATE_RETRY"
) -> tuple[bool, str]:
    """
    Evaluates whether an automated intervention is allowed.
    Returns: (is_allowed: bool, reason: str)
    """
    result: PolicyEvaluationResult = policy_engine.evaluate_action(
        action=proposed_action,
        amount=amount,
        retry_count=retry_count,
        failure_reason=failure_reason,
        recovery_probability=recovery_probability,
        is_fraud_connected=is_fraud_connected,
        fraud_cluster_info=fraud_cluster_details
    )
    return result.is_allowed, f"{result.policy_code}: {result.reason}"