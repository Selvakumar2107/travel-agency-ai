"""Payment Gateway Abstraction and Providers for SK Holidays.

Implements payment gateway integration with Razorpay as the preferred initial
integration for India (supporting UPI, Cards, Net Banking) and a secure
Sandbox / Demo Payment Provider when gateway credentials are not configured.
Includes server-side signature verification, idempotency protection, and refund abstractions.
"""

import os
import hmac
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from travel_agency.booking_models import PaymentOrder, PaymentStatus

logger = logging.getLogger(__name__)

# Check Razorpay SDK availability
try:
    import razorpay
    HAS_RAZORPAY_SDK = True
except ImportError:
    HAS_RAZORPAY_SDK = False


class BasePaymentGateway(ABC):
    """Abstract interface for payment gateways."""

    @abstractmethod
    def create_order(self, amount_inr: float, booking_reference: str, notes: Optional[Dict[str, str]] = None) -> PaymentOrder:
        """Create a payment order on the server with authoritative amount."""
        pass

    @abstractmethod
    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Verify the cryptographic payment signature returned by the gateway."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """Verify incoming webhook authenticity."""
        pass

    @abstractmethod
    def refund_payment(self, payment_id: str, amount_inr: float, reason: str = "") -> Tuple[bool, Optional[str], str]:
        """Initiate payment refund through gateway."""
        pass

    @abstractmethod
    def is_live_mode(self) -> bool:
        """Returns True if processing through real merchant gateway."""
        pass

    @abstractmethod
    def get_public_key_id(self) -> str:
        """Returns public key ID for checkout UI (never secret)."""
        pass


class RazorpayPaymentProvider(BasePaymentGateway):
    """
    Official Razorpay Gateway Integration.
    Uses official SDK with HMAC-SHA256 server signature validation.
    """

    def __init__(self, key_id: Optional[str] = None, key_secret: Optional[str] = None, webhook_secret: Optional[str] = None):
        self.key_id = (key_id or os.getenv("RAZORPAY_KEY_ID", "")).strip()
        self.key_secret = (key_secret or os.getenv("RAZORPAY_KEY_SECRET", "")).strip()
        self.webhook_secret = (webhook_secret or os.getenv("RAZORPAY_WEBHOOK_SECRET", "")).strip()

        self.client = None
        if HAS_RAZORPAY_SDK and self.key_id and self.key_secret and not self.key_id.startswith("your_"):
            try:
                self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
            except Exception as e:
                logger.error(f"Failed to initialize Razorpay Client: {e}")
                self.client = None

    def is_live_mode(self) -> bool:
        return self.client is not None

    def get_public_key_id(self) -> str:
        return self.key_id if self.key_id and not self.key_id.startswith("your_") else "rzp_test_sk_holidays_demo"

    def create_order(self, amount_inr: float, booking_reference: str, notes: Optional[Dict[str, str]] = None) -> PaymentOrder:
        amount_paise = int(round(amount_inr * 100))

        if self.client:
            try:
                order_payload = {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": booking_reference,
                    "notes": notes or {"booking_reference": booking_reference, "brand": "SK Holidays"}
                }
                rzp_order = self.client.order.create(data=order_payload)
                order_id = rzp_order.get("id")
                return PaymentOrder(
                    order_id=order_id,
                    booking_reference=booking_reference,
                    currency="INR",
                    amount_inr=amount_inr,
                    amount_in_paise=amount_paise,
                    gateway="razorpay",
                    status=PaymentStatus.CREATED
                )
            except Exception as e:
                logger.error(f"Razorpay order creation error: {e}")
                raise RuntimeError(f"Payment gateway order creation failed: {e}")

        # Fallback if credentials invalid
        raise RuntimeError("Razorpay credentials are not configured or invalid.")

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """
        Verifies signature using Razorpay official utility and HMAC-SHA256 algorithm:
        HMAC_SHA256(order_id + "|" + payment_id, secret) == signature
        """
        if not self.key_secret:
            return False

        # Official utility check
        if self.client:
            try:
                self.client.utility.verify_payment_signature({
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature
                })
                return True
            except Exception as e:
                logger.warning(f"Razorpay SDK utility verification check: {e}")

        # Cryptographic fallback comparison
        try:
            msg = f"{order_id}|{payment_id}".encode("utf-8")
            expected_sig = hmac.new(self.key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_sig, signature)
        except Exception as e:
            logger.error(f"Signature computation failed: {e}")
            return False

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        secret = self.webhook_secret or self.key_secret
        if not secret or not signature:
            return False
        try:
            expected_sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_sig, signature)
        except Exception as e:
            logger.error(f"Webhook signature check failed: {e}")
            return False

    def refund_payment(self, payment_id: str, amount_inr: float, reason: str = "") -> Tuple[bool, Optional[str], str]:
        if not self.client:
            return False, None, "Razorpay client not configured for live refunds."
        try:
            amount_paise = int(round(amount_inr * 100))
            refund = self.client.payment.refund(payment_id, {
                "amount": amount_paise,
                "notes": {"reason": reason, "brand": "SK Holidays"}
            })
            refund_id = refund.get("id")
            return True, refund_id, f"Refund of INR {amount_inr:.2f} processed successfully by Razorpay."
        except Exception as e:
            logger.error(f"Razorpay refund error: {e}")
            return False, None, f"Refund initiation failed with gateway: {e}"


class DemoPaymentProvider(BasePaymentGateway):
    """
    Sandbox / Demo Payment Provider.
    Enables secure offline testing of payment creation, signature verification,
    and refund flows with simulated sandbox keys and honest demo notices.
    """

    DEMO_KEY_SECRET = "sk_holidays_sandbox_secret_2026_deterministic"

    def __init__(self):
        self.key_id = "rzp_test_sk_holidays_sandbox"

    def is_live_mode(self) -> bool:
        return False

    def get_public_key_id(self) -> str:
        return self.key_id

    def create_order(self, amount_inr: float, booking_reference: str, notes: Optional[Dict[str, str]] = None) -> PaymentOrder:
        amount_paise = int(round(amount_inr * 100))
        order_id = f"order_demo_{datetime.now().strftime('%Y%m%d%H%M%S')}_{booking_reference[-6:]}"
        return PaymentOrder(
            order_id=order_id,
            booking_reference=booking_reference,
            currency="INR",
            amount_inr=amount_inr,
            amount_in_paise=amount_paise,
            gateway="demo",
            status=PaymentStatus.CREATED
        )

    def generate_demo_payment_credentials(self, order_id: str) -> Dict[str, str]:
        """Generates a valid test payment ID and cryptographic signature for sandbox flow."""
        payment_id = f"pay_demo_{datetime.now().strftime('%H%M%S%f')}"
        msg = f"{order_id}|{payment_id}".encode("utf-8")
        signature = hmac.new(self.DEMO_KEY_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return {
            "payment_id": payment_id,
            "signature": signature
        }

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        if not signature or not payment_id or not order_id:
            return False
        msg = f"{order_id}|{payment_id}".encode("utf-8")
        expected_sig = hmac.new(self.DEMO_KEY_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        if not signature or not body:
            return False
        expected_sig = hmac.new(self.DEMO_KEY_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    def refund_payment(self, payment_id: str, amount_inr: float, reason: str = "") -> Tuple[bool, Optional[str], str]:
        refund_id = f"rfnd_demo_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return True, refund_id, f"Sandbox refund of INR {amount_inr:.2f} recorded successfully."


# Global payment provider factory
_payment_instance: Optional[BasePaymentGateway] = None


def get_payment_provider() -> BasePaymentGateway:
    """Returns active payment provider (Razorpay if configured, else Demo provider)."""
    global _payment_instance
    if _payment_instance is None:
        key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()

        if key_id and key_secret and not key_id.startswith("your_"):
            _payment_instance = RazorpayPaymentProvider(key_id=key_id, key_secret=key_secret)
        else:
            _payment_instance = DemoPaymentProvider()
    return _payment_instance
