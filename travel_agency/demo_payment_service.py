"""Simulated Payment Gateway Service for SK Holidays Demo.

Implements safe demonstration payment workflows with selectable test scenarios:
- Simulate Successful Payment (DEMO_PAID / SIMULATED_SUCCESS)
- Simulate Declined Payment (SIMULATED_FAILED)
- Simulate Pending Payment (SIMULATED_PENDING)
- Simulate Payment Timeout (SIMULATED_TIMEOUT)

Never contacts real payment gateways or collects card numbers, CVVs, or UPI PINs.
All transactions are strictly labeled as SIMULATED PAYMENT.
"""

import random
import string
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

from travel_agency.booking_models import PaymentStatus, PaymentOrder

logger = logging.getLogger(__name__)


class SimulatedPaymentResult(BaseModel):
    """Result of a simulated payment transaction."""
    success: bool
    status: PaymentStatus
    demo_payment_reference: str
    booking_reference: str
    amount_inr: float
    scenario: str
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DemoPaymentService:
    """Safe payment simulator providing selectable test scenarios for evaluation and testing."""

    DISCLAIMER = "DEMO CHECKOUT — No real payment will be collected."

    @staticmethod
    def generate_demo_payment_ref() -> str:
        date_str = datetime.now().strftime("%Y%m%d%H%M%S")
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"DEMO-PAY-{date_str}-{suffix}"

    def create_simulated_order(self, amount_inr: float, booking_reference: str) -> PaymentOrder:
        """Creates a mock payment order for display."""
        order_id = f"demo_ord_{datetime.now().strftime('%Y%m%d%H%M%S')}_{booking_reference[-5:]}"
        return PaymentOrder(
            order_id=order_id,
            booking_reference=booking_reference,
            currency="INR",
            amount_inr=amount_inr,
            amount_in_paise=int(round(amount_inr * 100)),
            gateway="simulated_demo",
            status=PaymentStatus.SIMULATED_PENDING
        )

    def process_simulation(
        self,
        booking_reference: str,
        amount_inr: float,
        scenario: str = "success"
    ) -> SimulatedPaymentResult:
        """
        Executes one of the 4 selectable simulation scenarios:
        - 'success': Marks payment as DEMO_PAID / SIMULATED_SUCCESS
        - 'declined': Returns SIMULATED_FAILED
        - 'pending': Returns SIMULATED_PENDING
        - 'timeout': Returns SIMULATED_TIMEOUT
        """
        pay_ref = self.generate_demo_payment_ref()

        if scenario == "success":
            return SimulatedPaymentResult(
                success=True,
                status=PaymentStatus.SIMULATED_SUCCESS,
                demo_payment_reference=pay_ref,
                booking_reference=booking_reference,
                amount_inr=amount_inr,
                scenario="Simulate Successful Payment",
                message="Simulated payment authorization approved successfully (DEMO PAID)."
            )

        elif scenario == "declined":
            return SimulatedPaymentResult(
                success=False,
                status=PaymentStatus.SIMULATED_FAILED,
                demo_payment_reference=pay_ref,
                booking_reference=booking_reference,
                amount_inr=amount_inr,
                scenario="Simulate Declined Payment",
                message="Simulated bank rejection: Insufficient demo funds or bank authorization declined."
            )

        elif scenario == "pending":
            return SimulatedPaymentResult(
                success=False,
                status=PaymentStatus.SIMULATED_PENDING,
                demo_payment_reference=pay_ref,
                booking_reference=booking_reference,
                amount_inr=amount_inr,
                scenario="Simulate Pending Payment",
                message="Simulated transaction is pending bank reconciliation. Please check status later."
            )

        elif scenario == "timeout":
            return SimulatedPaymentResult(
                success=False,
                status=PaymentStatus.SIMULATED_TIMEOUT,
                demo_payment_reference=pay_ref,
                booking_reference=booking_reference,
                amount_inr=amount_inr,
                scenario="Simulate Payment Timeout",
                message="Simulated gateway connection timed out before bank response. Please retry."
            )

        else:
            return SimulatedPaymentResult(
                success=False,
                status=PaymentStatus.SIMULATED_FAILED,
                demo_payment_reference=pay_ref,
                booking_reference=booking_reference,
                amount_inr=amount_inr,
                scenario=scenario,
                message="Unknown simulation scenario requested."
            )


# Global singleton
_demo_payment_service_instance: Optional[DemoPaymentService] = None


def get_demo_payment_service() -> DemoPaymentService:
    global _demo_payment_service_instance
    if _demo_payment_service_instance is None:
        _demo_payment_service_instance = DemoPaymentService()
    return _demo_payment_service_instance
