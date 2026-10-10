"""Automated tests for Payment Providers, Razorpay HMAC Verification, and Idempotency."""

import hmac
import hashlib
import pytest
from travel_agency.payment_service import (
    RazorpayPaymentProvider,
    DemoPaymentProvider,
    get_payment_provider,
)
from travel_agency.booking_repository import BookingRepository


@pytest.fixture
def demo_payment_provider():
    return DemoPaymentProvider()


@pytest.fixture
def test_repo(tmp_path):
    db_file = tmp_path / "test_payments.db"
    return BookingRepository(db_path=db_file)


def test_razorpay_hmac_signature_verification_success():
    key_secret = "secret_test_key_12345"
    provider = RazorpayPaymentProvider(key_id="rzp_test_12345", key_secret=key_secret)

    order_id = "order_EK12345678"
    payment_id = "pay_FK98765432"

    # Compute expected valid signature: HMAC_SHA256(order_id + "|" + payment_id, key_secret)
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    valid_sig = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    assert provider.verify_payment_signature(order_id, payment_id, valid_sig) is True


def test_razorpay_hmac_signature_verification_failure():
    key_secret = "secret_test_key_12345"
    provider = RazorpayPaymentProvider(key_id="rzp_test_12345", key_secret=key_secret)

    order_id = "order_EK12345678"
    payment_id = "pay_FK98765432"
    invalid_sig = "tampered_signature_checksum_12345"

    assert provider.verify_payment_signature(order_id, payment_id, invalid_sig) is False


def test_razorpay_webhook_signature_verification():
    webhook_secret = "whsec_super_secret_999"
    provider = RazorpayPaymentProvider(
        key_id="rzp_test_12345",
        key_secret="sec_12345",
        webhook_secret=webhook_secret
    )

    body = '{"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_123"}}}}'
    valid_sig = hmac.new(webhook_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()

    assert provider.verify_webhook_signature(body, valid_sig) is True
    assert provider.verify_webhook_signature(body, "invalid_sig") is False


def test_demo_payment_provider_order_and_credentials(demo_payment_provider):
    order = demo_payment_provider.create_order(
        amount_inr=5400.0,
        booking_reference="SKH-BK-TEST-1"
    )
    assert order.amount_inr == 5400.0
    assert order.amount_in_paise == 540000
    assert "order_demo" in order.order_id

    # Generate sandbox credentials and verify
    creds = demo_payment_provider.generate_demo_payment_credentials(order.order_id)
    assert "payment_id" in creds
    assert "signature" in creds

    is_valid = demo_payment_provider.verify_payment_signature(
        order_id=order.order_id,
        payment_id=creds["payment_id"],
        signature=creds["signature"]
    )
    assert is_valid is True

    # Check tampering
    assert demo_payment_provider.verify_payment_signature(
        order_id=order.order_id,
        payment_id=creds["payment_id"],
        signature="bad_sig"
    ) is False


def test_payment_idempotency_protection(test_repo):
    payment_id = "pay_unique_12345"
    assert test_repo.is_payment_processed(payment_id) is False

    test_repo.mark_payment_processed(payment_id, "SKH-BK-1", "order_1", 3500.0)
    assert test_repo.is_payment_processed(payment_id) is True

    # Re-marking should not error
    test_repo.mark_payment_processed(payment_id, "SKH-BK-1", "order_1", 3500.0)
    assert test_repo.is_payment_processed(payment_id) is True


def test_demo_payment_service_all_simulation_scenarios():
    from travel_agency.demo_payment_service import get_demo_payment_service
    from travel_agency.booking_models import PaymentStatus

    sim = get_demo_payment_service()

    # Scenario 1: Success
    res_success = sim.process_simulation("SKH-BK-TEST-1", 4500.0, "success")
    assert res_success.success is True
    assert res_success.status == PaymentStatus.SIMULATED_SUCCESS
    assert "DEMO-PAY-" in res_success.demo_payment_reference
    assert "DEMO PAID" in res_success.message

    # Scenario 2: Declined
    res_declined = sim.process_simulation("SKH-BK-TEST-2", 4500.0, "declined")
    assert res_declined.success is False
    assert res_declined.status == PaymentStatus.SIMULATED_FAILED
    assert "declined" in res_declined.message.lower() or "rejection" in res_declined.message.lower()

    # Scenario 3: Pending
    res_pending = sim.process_simulation("SKH-BK-TEST-3", 4500.0, "pending")
    assert res_pending.success is False
    assert res_pending.status == PaymentStatus.SIMULATED_PENDING
    assert "pending" in res_pending.message.lower()

    # Scenario 4: Timeout
    res_timeout = sim.process_simulation("SKH-BK-TEST-4", 4500.0, "timeout")
    assert res_timeout.success is False
    assert res_timeout.status == PaymentStatus.SIMULATED_TIMEOUT
    assert "timed out" in res_timeout.message.lower()


def test_demo_payment_safety_disclaimer_and_no_real_credentials():
    from travel_agency.demo_payment_service import DemoPaymentService

    sim = DemoPaymentService()
    assert "DEMO CHECKOUT" in sim.DISCLAIMER
    assert "No real payment will be collected" in sim.DISCLAIMER

    order = sim.create_simulated_order(3500.0, "SKH-BK-SAFE-1")
    assert order.gateway == "simulated_demo"
    assert "demo_ord_" in order.order_id

