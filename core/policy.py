"""
Central Deterministic Recovery Policy Engine.
Defines strict fintech guardrails, risk thresholds, idempotency validation,
and stopping rules governing autonomous recovery interventions.
"""

from typing import Tuple, Dict, Any, Optional
from pydantic import BaseModel, Field

class RecoveryPolicyConfig(BaseModel):
    max_retries_allowed: int = Field(default=3, description="Maximum automated retry cap per payment")
    max_autonomous_amount: float = Field(default=15000.0, description="Amounts > ₹15,000 require manual sign-off if low confidence")
    hard_stop_amount: float = Field(default=50000.0, description="Amounts > ₹50,000 strictly require human review")
    min_recovery_probability: float = Field(default=0.20, description="Minimum ML score for autonomous intervention")
    retry_cooldown_seconds: int = Field(default=300, description="Cooldown before executing delayed retries")
    max_contact_frequency_hours: int = Field(default=24, description="Limit payment links to 1 per 24 hours")
    critical_failure_reasons: set = Field(
        default_factory=lambda: {"suspected_fraud", "invalid_card", "account_frozen", "stolen_card"}
    )

class PolicyEvaluationResult(BaseModel):
    is_allowed: bool
    policy_code: str
    reason: str
    requires_human_escalation: bool
    allowed_action: Optional[str] = None

class RecoveryPolicyEngine:
    def __init__(self, config: Optional[RecoveryPolicyConfig] = None):
        self.config = config or RecoveryPolicyConfig()

    def evaluate_action(
        self,
        action: str,
        amount: float,
        retry_count: int,
        failure_reason: str,
        recovery_probability: float,
        is_fraud_connected: bool = False,
        fraud_cluster_info: str = ""
    ) -> PolicyEvaluationResult:
        """
        Deterministically evaluates if an agent's proposed action is safe and permissible.
        """
        action = (action or "").upper().strip()

        # 1. Hard Graph Fraud Gate (Zero Tolerance)
        if is_fraud_connected:
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_code="FRAUD_GRAPH_BLOCKED",
                reason=f"Syndicate network detected ({fraud_cluster_info}). Autonomous recovery prohibited.",
                requires_human_escalation=True,
                allowed_action="ESCALATE_TO_HUMAN"
            )

        # 2. Critical Security Failure Reason Trigger
        if failure_reason in self.config.critical_failure_reasons:
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_code="SECURITY_CRITICAL_FAILURE",
                reason=f"Failure reason '{failure_reason}' strictly requires manual compliance investigation.",
                requires_human_escalation=True,
                allowed_action="ESCALATE_TO_HUMAN"
            )

        # 3. Maximum Retry Exhaustion Cap
        if retry_count >= self.config.max_retries_allowed:
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_code="MAX_RETRIES_EXCEEDED",
                reason=f"Payment has already attempted {retry_count} retries. Reached maximum safety limit.",
                requires_human_escalation=True,
                allowed_action="STOP_RECOVERY"
            )

        # 4. Ultra-High Value Guardrail (e.g. > ₹50,000)
        if amount >= self.config.hard_stop_amount:
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_code="HIGH_VALUE_MANDATORY_REVIEW",
                reason=f"High transaction value (₹{amount:,.2f}) exceeds autonomous limit (₹{self.config.hard_stop_amount:,.2f}).",
                requires_human_escalation=True,
                allowed_action="ESCALATE_TO_HUMAN"
            )

        # 5. Low Probability + High Value Constraint (₹15,000+ with prob < 0.35)
        if amount >= self.config.max_autonomous_amount and recovery_probability < 0.35:
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_code="HIGH_VALUE_LOW_PROBABILITY",
                reason=f"Amount ₹{amount:,.2f} with low recovery probability ({recovery_probability:.2f}) presents elevated retry failure cost.",
                requires_human_escalation=True,
                allowed_action="ESCALATE_TO_HUMAN"
            )

        # 6. Minimum Viable Probability
        if recovery_probability < self.config.min_recovery_probability:
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_code="SUB_THRESHOLD_PROBABILITY",
                reason=f"ML recovery probability ({recovery_probability:.2f}) below minimum viable execution threshold ({self.config.min_recovery_probability:.2f}).",
                requires_human_escalation=True,
                allowed_action="ESCALATE_TO_HUMAN"
            )

        # 7. Action-Specific Policy Validation
        if action in ["IMMEDIATE_RETRY", "DELAYED_RETRY", "SEND_PAYMENT_LINK"]:
            return PolicyEvaluationResult(
                is_allowed=True,
                policy_code="POLICY_APPROVED",
                reason=f"Proposed action '{action}' conforms to bounded recovery constraints.",
                requires_human_escalation=False,
                allowed_action=action
            )
        elif action == "ESCALATE_TO_HUMAN":
            return PolicyEvaluationResult(
                is_allowed=True,
                policy_code="ESCALATE_AUTHORIZED",
                reason="Voluntary escalation requested by agent diagnosis.",
                requires_human_escalation=True,
                allowed_action="ESCALATE_TO_HUMAN"
            )
        else:
            return PolicyEvaluationResult(
                is_allowed=False,
                policy_code="UNRECOGNIZED_ACTION",
                reason=f"Action '{action}' is not in predefined bounded recovery catalog.",
                requires_human_escalation=True,
                allowed_action="ESCALATE_TO_HUMAN"
            )

policy_engine = RecoveryPolicyEngine()
