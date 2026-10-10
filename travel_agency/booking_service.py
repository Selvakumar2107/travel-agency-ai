"""Booking Lifecycle Service & State Machine Orchestrator for SK Holidays.

Coordinates the complete booking lifecycle:
- Offer re-checking & price verification
- Payment order creation & backend signature verification
- Idempotency & duplicate submission protection
- Supplier reservation coordination
- Failure recovery (payment success with supplier failure -> safe refund/support)
- Cancellation & refund state transitions
"""

import logging
import random
import string
from datetime import datetime, date
from typing import Tuple, Optional, Dict, Any, List

from travel_agency.booking_models import (
    BookingStatus,
    PaymentStatus,
    HotelOffer,
    RoomOffer,
    GuestInformation,
    HotelBookingRecord,
    PaymentOrder,
)
from travel_agency.booking_repository import get_booking_repository, BookingRepository
from travel_agency.hotel_provider import get_hotel_provider, BaseHotelProvider
from travel_agency.payment_service import get_payment_provider, BasePaymentGateway

logger = logging.getLogger(__name__)

# Valid state machine transitions
VALID_BOOKING_TRANSITIONS: Dict[BookingStatus, List[BookingStatus]] = {
    BookingStatus.DRAFT: [BookingStatus.AVAILABILITY_CHECKED, BookingStatus.FAILED],
    BookingStatus.AVAILABILITY_CHECKED: [BookingStatus.PAYMENT_PENDING, BookingStatus.FAILED],
    BookingStatus.PAYMENT_PENDING: [BookingStatus.PAYMENT_VERIFIED, BookingStatus.FAILED],
    BookingStatus.PAYMENT_VERIFIED: [BookingStatus.BOOKING_PENDING, BookingStatus.FAILED, BookingStatus.REQUIRES_SUPPORT],
    BookingStatus.BOOKING_PENDING: [BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.REQUIRES_SUPPORT],
    BookingStatus.CONFIRMED: [BookingStatus.CANCELLATION_PENDING, BookingStatus.CANCELLED],
    BookingStatus.CANCELLATION_PENDING: [BookingStatus.CANCELLED, BookingStatus.REFUND_PENDING, BookingStatus.CONFIRMED],
    BookingStatus.CANCELLED: [BookingStatus.REFUND_PENDING, BookingStatus.REFUNDED],
    BookingStatus.REFUND_PENDING: [BookingStatus.REFUNDED, BookingStatus.REQUIRES_SUPPORT],
    BookingStatus.FAILED: [BookingStatus.REFUND_PENDING, BookingStatus.REQUIRES_SUPPORT],
    BookingStatus.REQUIRES_SUPPORT: [BookingStatus.CONFIRMED, BookingStatus.CANCELLED, BookingStatus.REFUNDED],
    BookingStatus.REFUNDED: [],
}


def generate_booking_reference() -> str:
    """Generates unique, non-sequential booking reference e.g., SKH-BK-20261010-8F92A."""
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"SKH-BK-{date_part}-{random_part}"


class BookingService:
    """Coordinates hotel booking lifecycle and payment state machine."""

    def __init__(
        self,
        repository: Optional[BookingRepository] = None,
        hotel_provider: Optional[BaseHotelProvider] = None,
        payment_gateway: Optional[BasePaymentGateway] = None,
        bank_service: Optional[Any] = None,
    ):
        self.repo = repository or get_booking_repository()
        self.hotel_provider = hotel_provider or get_hotel_provider()
        self.payment_gateway = payment_gateway or get_payment_provider()
        if bank_service is not None:
            self.bank_service = bank_service
        else:
            from travel_agency.bank_service import get_demo_bank_service
            self.bank_service = get_demo_bank_service(self.repo.db_path)

    def initiate_booking(
        self,
        offer: HotelOffer,
        selected_room: RoomOffer,
        guest_info: GuestInformation,
        check_in: str,
        check_out: str,
        num_rooms: int,
        num_adults: int,
        num_children: int = 0
    ) -> Tuple[bool, Optional[HotelBookingRecord], str]:
        """
        Step 1: Rechecks live room availability and authoritative price before creating booking draft.
        """
        # 1. Validate dates
        try:
            d_in = date.fromisoformat(check_in)
            d_out = date.fromisoformat(check_out)
            if d_out <= d_in:
                return False, None, "Check-out date must be strictly after check-in date."
            num_nights = max(1, (d_out - d_in).days)
        except Exception as e:
            return False, None, f"Invalid dates provided: {e}"

        # 2. Validate room occupancy
        total_guests = num_adults + num_children
        max_allowed_occupancy = num_rooms * getattr(selected_room, "max_occupancy", 2)
        if total_guests > max_allowed_occupancy:
            return (
                False,
                None,
                f"Occupancy exceeded: {num_rooms} room(s) can accommodate at most {max_allowed_occupancy} guests (requested {total_guests}). Please select additional rooms.",
            )

        # 3. Server-side availability recheck
        is_avail, live_price, message = self.hotel_provider.recheck_availability(
            offer.hotel_id, selected_room.room_id
        )

        if not is_avail:
            return False, None, f"Availability check failed: {message}. Please select an alternative room."

        # Compute authoritative pricing
        price_per_night = live_price if live_price is not None else selected_room.base_price_per_night

        room_subtotal = round(price_per_night * num_rooms * num_nights, 2)
        taxes = round(room_subtotal * 0.12, 2)  # 12% GST
        fees = 0.0
        total_amount = round(room_subtotal + taxes + fees, 2)

        pricing = {
            "price_per_night": price_per_night,
            "room_subtotal": room_subtotal,
            "tax_amount": taxes,
            "service_fees": fees,
            "total_amount": total_amount,
        }

        booking_ref = generate_booking_reference()

        record = HotelBookingRecord(
            booking_reference=booking_ref,
            supplier_booking_reference=None,
            hotel_id=offer.hotel_id,
            hotel_name=offer.name,
            hotel_address=offer.address,
            room_id=selected_room.room_id,
            room_name=selected_room.room_name,
            destination_name=offer.destination_name,
            check_in=check_in,
            check_out=check_out,
            num_nights=num_nights,
            num_rooms=num_rooms,
            num_adults=num_adults,
            num_children=num_children,
            meal_inclusion=selected_room.meal_inclusion,
            cancellation_policy=selected_room.cancellation_policy,
            guest_info=guest_info,
            pricing=pricing,
            booking_status=BookingStatus.AVAILABILITY_CHECKED,
            payment_status=PaymentStatus.PENDING,
            payment_gateway="razorpay" if self.payment_gateway.is_live_mode() else "demo",
            is_demo=not self.hotel_provider.is_live_provider(),
        )

        self.repo.save_booking(record)
        self.repo.add_audit_log(
            booking_ref,
            "BOOKING_INITIATED",
            {"room_id": selected_room.room_id, "total_amount": total_amount, "live_checked": True}
        )

        return True, record, "Room availability verified. Booking order initialized."

    def create_payment_order_for_booking(self, booking_reference: str) -> Tuple[bool, Optional[PaymentOrder], str]:
        """
        Step 2: Creates payment order on payment gateway with authoritative server amount.
        """
        booking = self.repo.get_booking_by_reference(booking_reference)
        if not booking:
            return False, None, "Booking record not found."

        total_amount = booking.pricing.get("total_amount", 0.0)
        if total_amount <= 0:
            return False, None, "Invalid booking amount."

        try:
            order = self.payment_gateway.create_order(
                amount_inr=total_amount,
                booking_reference=booking.booking_reference,
                notes={
                    "hotel_name": booking.hotel_name,
                    "guest_name": booking.guest_info.lead_guest_name,
                    "check_in": booking.check_in,
                }
            )

            # Update booking record with order ID and PAYMENT_PENDING status
            booking.payment_order_id = order.order_id
            booking.booking_status = BookingStatus.PAYMENT_PENDING
            self.repo.save_booking(booking)

            self.repo.add_audit_log(
                booking.booking_reference,
                "PAYMENT_ORDER_CREATED",
                {"order_id": order.order_id, "amount_inr": total_amount}
            )

            return True, order, "Payment order created successfully."
        except Exception as e:
            logger.error(f"Failed to create payment order: {e}")
            return False, None, f"Payment gateway error: {e}"

    def process_payment_callback(
        self,
        order_id: str,
        payment_id: str,
        signature: str
    ) -> Tuple[bool, Optional[HotelBookingRecord], str]:
        """
        Step 3: Cryptographic backend verification of payment signature, idempotency check,
        and supplier booking confirmation trigger.
        """
        booking = self.repo.get_booking_by_order_id(order_id)
        if not booking:
            return False, None, f"No booking found for payment order ID: {order_id}"

        # 1. Idempotency Check: Prevent duplicate payment processing or double charges
        if self.repo.is_payment_processed(payment_id):
            logger.info(f"Payment ID {payment_id} already processed. Returning cached confirmation.")
            return True, booking, "Payment already verified previously (idempotent response)."

        # 2. Server-side Cryptographic Signature Verification
        is_valid_sig = self.payment_gateway.verify_payment_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature
        )

        if not is_valid_sig:
            logger.warning(f"Invalid payment signature for order {order_id}, payment {payment_id}")
            self.repo.update_booking_status(
                reference=booking.booking_reference,
                booking_status=BookingStatus.FAILED,
                payment_status=PaymentStatus.FAILED,
                note="Signature verification failed on server."
            )
            updated_booking = self.repo.get_booking_by_reference(booking.booking_reference)
            return False, updated_booking, "Payment verification failed: Invalid cryptographic signature."


        # 3. Mark payment processed & record captured status
        total_amount = booking.pricing.get("total_amount", 0.0)
        self.repo.mark_payment_processed(payment_id, booking.booking_reference, order_id, total_amount)

        self.repo.update_booking_status(
            reference=booking.booking_reference,
            booking_status=BookingStatus.PAYMENT_VERIFIED,
            payment_status=PaymentStatus.CAPTURED,
            payment_id=payment_id,
            note="Payment signature cryptographically verified and captured."
        )

        # 4. Trigger Supplier Confirmation
        return self._confirm_with_supplier(booking.booking_reference)

    def _confirm_with_supplier(self, booking_reference: str) -> Tuple[bool, Optional[HotelBookingRecord], str]:
        """
        Coordinates with supplier API to finalize booking reservation.
        Handles the critical scenario: Payment Succeeded but Supplier Booking Failed.
        """
        booking = self.repo.get_booking_by_reference(booking_reference)
        if not booking:
            return False, None, "Booking reference not found."

        # Transition to BOOKING_PENDING
        self.repo.update_booking_status(
            reference=booking_reference,
            booking_status=BookingStatus.BOOKING_PENDING,
            note="Confirming reservation with hotel inventory provider."
        )

        try:
            success, supplier_ref, msg = self.hotel_provider.create_hotel_booking(booking)

            if success and supplier_ref:
                # Booking confirmed successfully!
                self.repo.update_booking_status(
                    reference=booking_reference,
                    booking_status=BookingStatus.CONFIRMED,
                    supplier_ref=supplier_ref,
                    note=f"Supplier confirmed: {msg}"
                )
                updated_booking = self.repo.get_booking_by_reference(booking_reference)
                return True, updated_booking, "Reservation successfully confirmed by hotel provider!"
            else:
                # CRITICAL FAILURE SCENARIO: Payment succeeded but supplier failed
                logger.error(f"Supplier booking failed for paid booking {booking_reference}: {msg}")
                self.repo.update_booking_status(
                    reference=booking_reference,
                    booking_status=BookingStatus.REQUIRES_SUPPORT,
                    payment_status=PaymentStatus.REFUND_PENDING,
                    note=f"Supplier reservation failed after payment: {msg}. Recovery initiated."
                )

                # Attempt automatic gateway refund
                if booking.payment_id:
                    total_amount = booking.pricing.get("total_amount", 0.0)
                    ref_ok, ref_id, ref_msg = self.payment_gateway.refund_payment(
                        booking.payment_id,
                        total_amount,
                        reason="Hotel supplier inventory unavailable after payment capture."
                    )
                    if ref_ok:
                        self.repo.update_booking_status(
                            reference=booking_reference,
                            booking_status=BookingStatus.CANCELLED,
                            payment_status=PaymentStatus.REFUNDED,
                            note=f"Automatic refund completed: {ref_id}"
                        )
                        updated = self.repo.get_booking_by_reference(booking_reference)
                        return False, updated, (
                            "Hotel room became unavailable during checkout. "
                            f"Your payment has been automatically refunded ({ref_id})."
                        )

                updated = self.repo.get_booking_by_reference(booking_reference)
                return False, updated, (
                    "Hotel inventory confirmation encountered an issue. "
                    "Our customer support team is actively resolving this and our refund guarantee applies."
                )
        except Exception as e:
            logger.error(f"Exception during supplier confirmation: {e}")
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.REQUIRES_SUPPORT,
                note=f"Supplier exception: {e}"
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return False, updated, f"Supplier confirmation error: {e}"

    def cancel_booking(self, booking_reference: str, reason: str = "Customer requested cancellation") -> Tuple[bool, str]:
        """
        Handles cancellation request adhering strictly to hotel cancellation policy
        and processing gateway refund if eligible.
        """
        booking = self.repo.get_booking_by_reference(booking_reference)
        if not booking:
            return False, "Booking not found."

        if booking.booking_status == BookingStatus.CANCELLED:
            return False, "This booking has already been cancelled."

        # Check supplier cancellation
        supplier_ref = booking.supplier_booking_reference or "DEMO-REF"
        sup_ok, sup_msg = self.hotel_provider.cancel_hotel_booking(supplier_ref, reason)

        if not sup_ok:
            return False, f"Supplier could not cancel reservation: {sup_msg}"

        # Restore demo room inventory
        try:
            from travel_agency.hotel_service import get_hotel_service
            get_hotel_service().update_mock_inventory(booking.room_id, +booking.num_rooms)
        except Exception as e:
            logger.warning(f"Could not restore mock inventory: {e}")

        # Determine refund eligibility based on policy
        policy_lower = (booking.cancellation_policy or "").lower()
        if "non-refundable" in policy_lower or "non refundable" in policy_lower or "no refund" in policy_lower:
            is_refundable = False
        else:
            is_refundable = "free cancellation" in policy_lower or "refundable" in policy_lower
        total_amount = booking.pricing.get("total_amount", 0.0)

        refund_success = False
        refund_note = "Non-refundable rate as per policy."

        if is_refundable and booking.payment_id:
            # Check if booking was paid using SK Demo Bank
            is_bank_pay = getattr(booking, "payment_gateway", "") == "sk_demo_bank" or (booking.payment_id and booking.payment_id.startswith("SKTXN"))
            if is_bank_pay:
                ref_ok, ref_txn, ref_rec, ref_msg = self.bank_service.process_cancellation_refund(
                    booking_reference=booking_reference,
                    hotel_name=booking.hotel_name,
                    amount_inr=total_amount,
                    reason=reason
                )
                if ref_ok:
                    refund_success = True
                    refund_note = f"Simulated refund of INR {total_amount:,.2f} credited back to SK Demo Bank (Txn Ref: {ref_txn})."
                else:
                    refund_note = f"SK Demo Bank refund: {ref_msg}"
            else:
                # Record simulated refund for standard demo provider
                refund_success = True
                refund_note = f"Simulated refund of INR {total_amount:,.2f} recorded (DEMO REFUNDED)."

        new_pay_status = PaymentStatus.SIMULATED_SUCCESS if refund_success else booking.payment_status

        self.repo.update_booking_status(
            reference=booking_reference,
            booking_status=BookingStatus.CANCELLED_DEMO,
            payment_status=new_pay_status,
            note=f"Demo booking cancelled: {reason}. {refund_note}"
        )

        return True, f"Demo booking {booking_reference} successfully cancelled. {refund_note}"

    def process_simulated_payment(
        self,
        booking_reference: str,
        scenario: str = "success"
    ) -> Tuple[bool, Optional[HotelBookingRecord], str]:
        """
        Processes simulated payment test scenarios (success, declined, pending, timeout)
        and transitions booking state machine accordingly.
        """
        from travel_agency.demo_payment_service import get_demo_payment_service
        from travel_agency.hotel_service import get_hotel_service

        booking = self.repo.get_booking_by_reference(booking_reference)
        if not booking:
            return False, None, "Booking reference not found."

        # Idempotency / Duplicate submission prevention
        if booking.booking_status in (BookingStatus.CONFIRMED_DEMO, BookingStatus.DEMO_PAID):
            return True, booking, "This booking has already been confirmed and processed (idempotent)."

        # Recheck mock inventory availability before confirming
        hotel_service = get_hotel_service()
        is_avail, avail_msg, _ = hotel_service.check_mock_availability(
            booking.hotel_id, booking.room_id, booking.num_rooms
        )
        if not is_avail:
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.PAYMENT_FAILED,
                payment_status=PaymentStatus.SIMULATED_FAILED,
                note=f"Inventory unavailable: {avail_msg}"
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return False, updated, f"Room availability check failed: {avail_msg}"

        # Execute simulation scenario
        demo_payment_service = get_demo_payment_service()
        total_amount = booking.pricing.get("total_amount", 0.0)
        sim_result = demo_payment_service.process_simulation(
            booking_reference=booking_reference,
            amount_inr=total_amount,
            scenario=scenario
        )

        if sim_result.success:
            # Payment success: transition DRAFT -> DEMO_PAID -> CONFIRMED_DEMO
            hotel_service.update_mock_inventory(booking.room_id, -booking.num_rooms)
            self.repo.mark_payment_processed(
                payment_id=sim_result.demo_payment_reference,
                booking_reference=booking_reference,
                order_id=booking.payment_order_id or "ORDER_SIMULATED",
                amount=total_amount
            )
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.CONFIRMED_DEMO,
                payment_status=PaymentStatus.SIMULATED_SUCCESS,
                supplier_ref=f"MOCK-CONF-{booking_reference[-6:]}",
                payment_id=sim_result.demo_payment_reference,
                note=sim_result.message
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return True, updated, sim_result.message
        elif scenario == "declined":
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.PAYMENT_FAILED,
                payment_status=PaymentStatus.SIMULATED_FAILED,
                payment_id=sim_result.demo_payment_reference,
                note=sim_result.message
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return False, updated, sim_result.message
        elif scenario == "pending":
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.PAYMENT_PENDING,
                payment_status=PaymentStatus.SIMULATED_PENDING,
                payment_id=sim_result.demo_payment_reference,
                note=sim_result.message
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return False, updated, sim_result.message
        elif scenario == "timeout":
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.PAYMENT_PENDING,
                payment_status=PaymentStatus.SIMULATED_TIMEOUT,
                payment_id=sim_result.demo_payment_reference,
                note=sim_result.message
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return False, updated, sim_result.message
        else:
            return False, booking, sim_result.message

    def pay_with_demo_bank(
        self,
        booking_reference: str
    ) -> Tuple[bool, Optional[HotelBookingRecord], str, Dict[str, Any]]:
        """
        Executes hotel booking payment using the simulated SK Demo Bank account.

        Flow:
        1. Checks booking validity and idempotency.
        2. Rechecks room availability.
        3. Deducts funds from SK Demo Bank using atomic database transactions.
        4. On success: decrements room inventory, marks payment processed, and confirms booking.
        5. On failure: leaves funds undeducted and reports error / shortfall.
        """
        from travel_agency.bank_service import get_demo_bank_service
        from travel_agency.hotel_service import get_hotel_service

        booking = self.repo.get_booking_by_reference(booking_reference)
        if not booking:
            return False, None, "Booking reference not found.", {}

        # Idempotency / Duplicate payment check
        if booking.booking_status in (BookingStatus.CONFIRMED_DEMO, BookingStatus.DEMO_PAID):
            return True, booking, "This booking has already been paid and confirmed (idempotent).", {}

        # Recheck inventory availability
        hotel_service = get_hotel_service()
        is_avail, avail_msg, _ = hotel_service.check_mock_availability(
            booking.hotel_id, booking.room_id, booking.num_rooms
        )
        if not is_avail:
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.PAYMENT_FAILED,
                payment_status=PaymentStatus.SIMULATED_FAILED,
                note=f"Inventory unavailable: {avail_msg}"
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return False, updated, f"Room availability check failed: {avail_msg}", {}

        total_amount = booking.pricing.get("total_amount", 0.0)
        # Execute debit via SK Demo Bank
        debit_ok, txn_ref, txn_record, debit_msg = self.bank_service.process_booking_payment(
            booking_reference=booking_reference,
            hotel_name=booking.hotel_name,
            amount_inr=total_amount,
        )

        if not debit_ok or not txn_ref:
            # Payment failed or insufficient funds
            self.repo.update_booking_status(
                reference=booking_reference,
                booking_status=BookingStatus.PAYMENT_FAILED,
                payment_status=PaymentStatus.SIMULATED_FAILED,
                note=f"SK Demo Bank payment failed: {debit_msg}"
            )
            updated = self.repo.get_booking_by_reference(booking_reference)
            return False, updated, debit_msg, {}

        # Payment succeeded: update mock inventory & confirm booking
        hotel_service.update_mock_inventory(booking.room_id, -booking.num_rooms)
        self.repo.mark_payment_processed(
            payment_id=txn_ref,
            booking_reference=booking_reference,
            order_id=booking.payment_order_id or "ORDER_DEMO_BANK",
            amount=total_amount
        )
        self.repo.update_booking_status(
            reference=booking_reference,
            booking_status=BookingStatus.CONFIRMED_DEMO,
            payment_status=PaymentStatus.SIMULATED_SUCCESS,
            payment_gateway="sk_demo_bank",
            payment_id=txn_ref,
            supplier_ref=f"MOCK-CONF-{booking_reference[-6:]}",
            note=f"Paid via SK Demo Bank (Txn Ref: {txn_ref}). {debit_msg}"
        )
        updated_booking = self.repo.get_booking_by_reference(booking_reference)
        return True, updated_booking, debit_msg, {
            "transaction_reference": txn_ref,
            "balance_after_inr": txn_record.balance_after_inr if txn_record else None,
        }




# Global booking service instance
_booking_service_instance: Optional[BookingService] = None


def get_booking_service() -> BookingService:
    global _booking_service_instance
    if _booking_service_instance is None:
        _booking_service_instance = BookingService()
    return _booking_service_instance
