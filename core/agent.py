import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

DIAGNOSIS_PROMPT = """
You are RazorRecover, an autonomous AI payment recovery agent.
A payment has failed. You need to analyze the data and choose the BEST recovery action.

Transaction Data:
- Amount: ₹{amount}
- Failure Reason: {failure_reason}
- ML Recovery Probability: {recovery_probability}
- Customer History: {customer_history}

Allowed Actions:
1. "IMMEDIATE_RETRY"
2. "DELAYED_RETRY"
3. "SEND_PAYMENT_LINK"
4. "ESCALATE_TO_HUMAN"

Respond ONLY with the exact name of the Action you choose. No other text.
"""

def diagnose_and_decide(amount: float, failure_reason: str, recovery_prob: float, customer_history: str) -> tuple[str, int, float]:
    """
    Uses Gemini to select recovery strategy with token tracking and strict fallback.
    Returns: (decision: str, tokens_used: int, cost_inr: float)
    """
    # Baseline pricing for Gemini 1.5 Flash (~$0.15/1M tokens, ~₹13.5 per 1M tokens -> ₹0.0000135/token)
    INR_PER_TOKEN = 0.0000135

    try:
        prompt = DIAGNOSIS_PROMPT.format(
            amount=amount,
            failure_reason=failure_reason,
            recovery_probability=recovery_prob,
            customer_history=customer_history
        )
        
        # Using the stable gemini-1.5-flash model
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        decision_raw = response.text.strip().upper() if response.text else "ESCALATE_TO_HUMAN"
        
        # Extract token usage if available from SDK response metadata
        tokens = 220  # Default prompt+output estimate
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            total_tokens = getattr(response.usage_metadata, 'total_token_count', 220)
            tokens = total_tokens if total_tokens else 220
        
        cost_inr = round(tokens * INR_PER_TOKEN, 5)

        # Parse normalized decision
        if "IMMEDIATE_RETRY" in decision_raw: decision = "IMMEDIATE_RETRY"
        elif "DELAYED_RETRY" in decision_raw: decision = "DELAYED_RETRY"
        elif "SEND_PAYMENT_LINK" in decision_raw: decision = "SEND_PAYMENT_LINK"
        else: decision = "ESCALATE_TO_HUMAN"

        return decision, tokens, cost_inr
        
    except Exception as e:
        # SMART LOCAL FALLBACK (Zero LLM token cost)
        if recovery_prob >= 0.7: decision = "IMMEDIATE_RETRY"
        elif recovery_prob >= 0.35: decision = "DELAYED_RETRY"
        elif failure_reason == "invalid_card": decision = "SEND_PAYMENT_LINK"
        else: decision = "ESCALATE_TO_HUMAN"

        return decision, 0, 0.0