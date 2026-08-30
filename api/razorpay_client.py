import random

class RazorpaySimulator:
    """
    Simulates Razorpay Payment Retry & Payment Link APIs.
    In real production, this connects to Razorpay's Test Mode API.
    """
    @staticmethod
    def execute_retry(amount: float, recovery_probability: float) -> bool:
        """Simulates automated charge retry outcome based on calculated probability."""
        return random.random() < recovery_probability

    @staticmethod
    def send_payment_link(amount: float) -> bool:
        """Simulates customer paying via sent SMS/Email payment link (45% baseline conversion)."""
        return random.random() < 0.45

razorpay_gateway = RazorpaySimulator()