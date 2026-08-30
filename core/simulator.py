"""
Closed-Loop Payment Gateway Simulator.
Models realistic payment gateway responses (Razorpay Test Mode simulation),
including bank declines, temporary network timeouts, OTP abandonments, and recaptures.
Clearly demarcated as SIMULATED_TEST_MODE.
"""

import random
import time
import uuid
from typing import Dict, Any, Optional

class PaymentExecutionResult:
    def __init__(
        self,
        success: bool,
        status_code: str,
        gateway_reference_id: str,
        message: str,
        amount: float,
        latency_ms: int,
        recovery_method: str
    ):
        self.success = success
        self.status_code = status_code
        self.gateway_reference_id = gateway_reference_id
        self.message = message
        self.amount = amount
        self.latency_ms = latency_ms
        self.recovery_method = recovery_method
        self.execution_mode = "SIMULATED_TEST_MODE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status_code": self.status_code,
            "gateway_reference_id": self.gateway_reference_id,
            "message": self.message,
            "amount": self.amount,
            "latency_ms": self.latency_ms,
            "recovery_method": self.recovery_method,
            "execution_mode": self.execution_mode
        }

class RazorpaySimulator:
    """
    Simulates Razorpay Payment Retry & Dynamic Payment Link Gateway APIs.
    Incorporates failure reason dynamics and deterministic demo overrides.
    """
    @staticmethod
    def execute_retry(
        amount: float,
        recovery_probability: float,
        failure_reason: Optional[str] = None,
        force_success: Optional[bool] = None
    ) -> PaymentExecutionResult:
        start_time = time.time()
        ref_id = f"sim_pay_{uuid.uuid4().hex[:12]}"
        latency = int((time.time() - start_time) * 1000) + random.randint(120, 350)

        # Deterministic override for demo stability if specified
        if force_success is not None:
            is_success = force_success
        else:
            # Stochastic payment execution based on calibrated recovery probability
            is_success = random.random() < recovery_probability

        if is_success:
            return PaymentExecutionResult(
                success=True,
                status_code="PAYMENT_CAPTURED",
                gateway_reference_id=ref_id,
                message=f"Payment captured successfully for ₹{amount:,.2f} via automated retry.",
                amount=amount,
                latency_ms=latency,
                recovery_method="AUTOMATED_RETRY"
            )
        else:
            decline_reasons = [
                "BAD_REQUEST: Issuer declined transaction",
                "GATEWAY_TIMEOUT: Bank switch did not respond in 15s",
                "INSUFFICIENT_FUNDS: Available balance below order value"
            ]
            msg = random.choice(decline_reasons)
            return PaymentExecutionResult(
                success=False,
                status_code="PAYMENT_FAILED",
                gateway_reference_id=ref_id,
                message=msg,
                amount=amount,
                latency_ms=latency,
                recovery_method="AUTOMATED_RETRY"
            )

    @staticmethod
    def send_payment_link(
        amount: float,
        customer_id: str = "cust_unknown",
        force_success: Optional[bool] = None
    ) -> PaymentExecutionResult:
        start_time = time.time()
        ref_id = f"sim_plink_{uuid.uuid4().hex[:12]}"
        latency = int((time.time() - start_time) * 1000) + random.randint(80, 200)

        if force_success is not None:
            is_success = force_success
        else:
            # Baseline 48% conversion on WhatsApp/SMS smart recovery link
            is_success = random.random() < 0.48

        if is_success:
            return PaymentExecutionResult(
                success=True,
                status_code="LINK_PAID",
                gateway_reference_id=ref_id,
                message=f"Customer completed payment of ₹{amount:,.2f} via dynamic recovery link.",
                amount=amount,
                latency_ms=latency,
                recovery_method="DYNAMIC_PAYMENT_LINK"
            )
        else:
            return PaymentExecutionResult(
                success=False,
                status_code="LINK_EXPIRED_OR_UNPAID",
                gateway_reference_id=ref_id,
                message="Payment link delivered; customer did not complete checkout within expiry window.",
                amount=amount,
                latency_ms=latency,
                recovery_method="DYNAMIC_PAYMENT_LINK"
            )

payment_simulator = RazorpaySimulator()
