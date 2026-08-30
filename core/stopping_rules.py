"""
Safety Guardrails and Stopping Rules for Autonomous Payment Recovery.
Prevents infinite retry loops, limits financial risk, and handles safety escalations.
"""

MAX_RETRIES_ALLOWED = 3
HIGH_VALUE_THRESHOLD = 10000.0  # ₹10,000+ requires cautious intervention
CRITICAL_FAILURE_REASONS = {"suspected_fraud", "invalid_card"}

def evaluate_safety_guardrails(
    retry_count: int,
    amount: float,
    failure_reason: str,
    recovery_probability: float,
    is_fraud_connected: bool = False,
    fraud_cluster_details: str = ""
) -> tuple[bool, str]:
    """
    Evaluates whether an automated intervention is allowed.
    Returns: (is_allowed: bool, reason: str)
    """
    # 1. Networked Fraud Detection Hard Guardrail (Graph Theory Engine)
    if is_fraud_connected:
        return False, f"FRAUD_GRAPH_SYNDICATE_BLOCK: Shared entity infrastructure with confirmed fraud syndicate ({fraud_cluster_details}). Automated recovery blocked."

    # 2. Hard Maximum Retry Cap
    if retry_count >= MAX_RETRIES_ALLOWED:
        return False, f"EXCEEDED_MAX_RETRIES: Payment has already failed {retry_count} times."

    # 3. Critical/Security Failure Trigger
    if failure_reason in CRITICAL_FAILURE_REASONS:
        return False, f"SECURITY_BLOCK: Failure reason '{failure_reason}' strictly requires manual investigation."

    # 4. Low Probability + High Value Guardrail
    if amount >= HIGH_VALUE_THRESHOLD and recovery_probability < 0.35:
        return False, f"HIGH_VALUE_RISK: High amount (₹{amount}) with low recovery probability ({recovery_probability}). Escalating."

    # 5. Extremely Low Probability
    if recovery_probability < 0.15:
        return False, f"LOW_CONFIDENCE: Recovery probability {recovery_probability} is below automated execution threshold."

    return True, "SAFE_FOR_AUTOMATED_INTERVENTION"