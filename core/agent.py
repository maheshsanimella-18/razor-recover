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

def diagnose_and_decide(amount: float, failure_reason: str, recovery_prob: float, customer_history: str) -> str:
    """Uses Gemini to select recovery strategy with a strict Rate Limit Fallback."""
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
        decision = response.text.strip().upper()
        
        # Clean up conversational AI text (e.g., "Action: IMMEDIATE_RETRY")
        if "IMMEDIATE_RETRY" in decision: return "IMMEDIATE_RETRY"
        if "DELAYED_RETRY" in decision: return "DELAYED_RETRY"
        if "SEND_PAYMENT_LINK" in decision: return "SEND_PAYMENT_LINK"
        return "ESCALATE_TO_HUMAN"
        
    except Exception as e:
        # 🚨 SMART FALLBACK 🚨 
        # If Google Free Tier blocks us, use local simulation for the demo batch
        if recovery_prob >= 0.7: return "IMMEDIATE_RETRY"
        elif recovery_prob >= 0.35: return "DELAYED_RETRY"
        elif failure_reason == "invalid_card": return "SEND_PAYMENT_LINK"
        return "ESCALATE_TO_HUMAN"