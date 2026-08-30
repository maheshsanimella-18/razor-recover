"""
Razorpay Payment Gateway Interface.
Delegates to closed-loop payment simulator in test mode.
"""

from core.simulator import payment_simulator

# Alias for backwards compatibility
razorpay_gateway = payment_simulator