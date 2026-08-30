"""
RazorRecover Closed-Loop Autonomous Decision Agent.
Uses Gemini with Pydantic structured output, bounded tool execution, 
and deterministic policy fallbacks.
"""

import os
import json
import re
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field, ValidationError
from google import genai
from dotenv import load_dotenv

load_dotenv()
try:
    client = genai.Client()
except Exception:
    client = None

# --- Structured Pydantic Decision Output ---
class AgentDecisionOutput(BaseModel):
    transaction_id: str
    diagnosis: str
    risk_level: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    recovery_probability: float = Field(ge=0.0, le=1.0)
    recommended_action: str = Field(description="IMMEDIATE_RETRY | DELAYED_RETRY | SEND_PAYMENT_LINK | ESCALATE_TO_HUMAN")
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human: bool
    stop_reason: Optional[str] = None

DIAGNOSIS_STRUCTURED_PROMPT = """
You are RazorRecover, an autonomous AI revenue recovery agent for Razorpay.
Analyze the failed transaction context and select the optimal, safe recovery intervention.

Context:
- Transaction ID: {transaction_id}
- Amount: ₹{amount:,.2f}
- Failure Reason: {failure_reason}
- Payment Method: {payment_method}
- Retry Count: {retry_count}
- ML Recovery Probability: {recovery_probability}
- Customer Profile: {customer_summary}
- Fraud Risk Status: {fraud_status}

Allowed Recommended Actions:
1. "IMMEDIATE_RETRY": Use for temporary network timeouts or high-probability transient gateway hiccups.
2. "DELAYED_RETRY": Use for insufficient balance when customer tenure is positive and amount is moderate.
3. "SEND_PAYMENT_LINK": Use for invalid card details, OTP drop-offs, or abandoned checkout.
4. "ESCALATE_TO_HUMAN": Use for high-value anomalies, security warnings, or ambiguous repeated failures.

You MUST respond strictly with valid JSON conforming to this schema:
{{
  "transaction_id": "{transaction_id}",
  "diagnosis": "Brief summary of why payment failed and context",
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "recovery_probability": {recovery_probability},
  "recommended_action": "IMMEDIATE_RETRY|DELAYED_RETRY|SEND_PAYMENT_LINK|ESCALATE_TO_HUMAN",
  "reason": "Clear justification for the selected intervention",
  "confidence": 0.85,
  "requires_human": false,
  "stop_reason": null
}}
"""

class AutonomousRecoveryAgent:
    def __init__(self):
        # Gemini 1.5 Flash token unit pricing (~₹0.0000135/token)
        self.inr_per_token = 0.0000135

    def diagnose_and_decide(
        self,
        transaction_id: str,
        amount: float,
        failure_reason: str,
        recovery_prob: float,
        customer_summary: str,
        payment_method: str = "card",
        retry_count: int = 0,
        fraud_status: str = "CLEAN"
    ) -> Tuple[AgentDecisionOutput, int, float]:
        """
        Executes structured agent reasoning using Gemini 1.5 Flash with deterministic fallback.
        Returns: (decision_output: AgentDecisionOutput, tokens_used: int, cost_inr: float)
        """
        prompt = DIAGNOSIS_STRUCTURED_PROMPT.format(
            transaction_id=transaction_id,
            amount=amount,
            failure_reason=failure_reason,
            payment_method=payment_method,
            retry_count=retry_count,
            recovery_probability=recovery_prob,
            customer_summary=customer_summary,
            fraud_status=fraud_status
        )

        tokens = 220
        cost_inr = round(tokens * self.inr_per_token, 5)

        # 1. Attempt LLM Structured Generation
        if client is not None and os.getenv("GEMINI_API_KEY"):
            try:
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt,
                )
                
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    total_tokens = getattr(response.usage_metadata, 'total_token_count', 220)
                    tokens = total_tokens if total_tokens else 220
                    cost_inr = round(tokens * self.inr_per_token, 5)

                raw_text = response.text.strip() if response.text else ""
                
                # Extract JSON block if wrapped in markdown
                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if json_match:
                    parsed_json = json.loads(json_match.group())
                    decision_obj = AgentDecisionOutput(**parsed_json)
                    return decision_obj, tokens, cost_inr
            except Exception:
                # Graceful degradation to deterministic policy
                pass

        # 2. Deterministic Rule-Based Fallback Engine (Zero LLM API cost)
        decision_obj = self._fallback_deterministic_decision(
            transaction_id=transaction_id,
            amount=amount,
            failure_reason=failure_reason,
            recovery_prob=recovery_prob,
            payment_method=payment_method,
            retry_count=retry_count
        )
        return decision_obj, 0, 0.0

    def _fallback_deterministic_decision(
        self,
        transaction_id: str,
        amount: float,
        failure_reason: str,
        recovery_prob: float,
        payment_method: str,
        retry_count: int
    ) -> AgentDecisionOutput:
        """Deterministic policy fallback ensuring 100% demo uptime and crash resilience."""
        if failure_reason in ["suspected_fraud", "invalid_card"] or retry_count >= 3:
            action = "ESCALATE_TO_HUMAN"
            risk = "HIGH"
            requires_human = True
            reason = "Security failure or retry exhaustion requires manual review."
            diag = f"High risk failure profile '{failure_reason}' flagged for human investigation."
        elif failure_reason == "network_timeout" or (recovery_prob >= 0.70 and amount < 15000):
            action = "IMMEDIATE_RETRY"
            risk = "LOW"
            requires_human = False
            reason = "Transient network issue with high recovery probability."
            diag = "Identified temporary bank switch timeout; safe for immediate re-attempt."
        elif failure_reason == "insufficient_balance" and recovery_prob >= 0.35:
            action = "DELAYED_RETRY"
            risk = "MEDIUM"
            requires_human = False
            reason = "Customer funds expected to replenish; schedule delayed retry."
            diag = "Moderate balance deficit; delayed re-attempt optimizes success rate."
        elif failure_reason in ["otp_abandoned", "invalid_card"]:
            action = "SEND_PAYMENT_LINK"
            risk = "MEDIUM"
            requires_human = False
            reason = "Customer interaction needed to provide updated payment credentials."
            diag = "Checkout abandoned prior to authorization; dispatching WhatsApp/SMS recovery link."
        else:
            action = "ESCALATE_TO_HUMAN"
            risk = "MEDIUM"
            requires_human = True
            reason = "Ambiguous recovery probability requires human triage."
            diag = "Recovery probability below automated threshold; escalated."

        return AgentDecisionOutput(
            transaction_id=transaction_id,
            diagnosis=diag,
            risk_level=risk,
            recovery_probability=recovery_prob,
            recommended_action=action,
            reason=reason,
            confidence=round(recovery_prob, 2),
            requires_human=requires_human,
            stop_reason=None
        )

# Global Agent Instance
recovery_agent = AutonomousRecoveryAgent()

# Helper function for backwards compatibility
def diagnose_and_decide(
    amount: float,
    failure_reason: str,
    recovery_prob: float,
    customer_history: str
) -> Tuple[str, int, float]:
    decision_obj, tokens, cost = recovery_agent.diagnose_and_decide(
        transaction_id="txn_in_flight",
        amount=amount,
        failure_reason=failure_reason,
        recovery_prob=recovery_prob,
        customer_summary=customer_history
    )
    return decision_obj.recommended_action, tokens, cost