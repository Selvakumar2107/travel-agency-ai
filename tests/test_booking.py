"""Automated tests for Booking Service, State Machine Transitions, and SQLite Persistence."""

import pytest
from datetime import date, timedelta
from travel_agency.booking_models import (
    GuestInformation,
    BookingStatus,
    PaymentStatus,
    HotelSearchQuery,
)
from travel_agency.hotel_provider import DemoHotelProvider
from travel_agency.booking_repository import BookingRepository
from travel_agency.booking_service import BookingService
from travel_agency.payment_service import DemoPaymentProvider


@pytest.fixture
def test_repo(tmp_path):
    db_file = tmp_path / "test_bookings.db"
    return BookingRepository(db_path=db_file)


@pytest.fixture
def hotel_provider():
    return DemoHotelProvider()


@pytest.fixture
def payment_gateway():
    return DemoPaymentProvider()


@pytest.fixture
def booking_service(test_repo, hotel_provider, payment_gateway):
    return BookingService(
        repository=test_repo,
        hotel_provider=hotel_provider,
        payment_gateway=payment_gateway
    )


@pytest.fixture
def sample_offer(hotel_provider):
    today = date.today()
    q = HotelSearchQuery(
        destination_id="ooty",
        check_in_date=today + timedelta(days=7),
        check_out_date=today + timedelta(days=10),
        num_rooms=1,
        num_adults=2,
    )
    offers = hotel_provider.search_hotels(q)
    return offers[0]


@pytest.fixture
def valid_guest():
    return GuestInformation(
        lead_guest_name="Aarav Sharma",
        email="aarav.sharma@example.com",
        phone="+91 9876543210",
        special_requests="High floor preferred",
        accepted_terms=True
    )


def test_guest_information_validation():
    # Invalid email
    with pytest.raises(ValueError, match="valid email"):
        GuestInformation(
            lead_guest_name="Test User",
            email="invalid-email-string",
            phone="+91 9876543210",
            accepted_terms=True
        )

    # Invalid phone
    with pytest.raises(ValueError, match="valid contact number"):
        GuestInformation(
            lead_guest_name="Test User",
            email="test@example.com",
            phone="1234567",
            accepted_terms=True
        )

    # Unaccepted terms
    with pytest.raises(ValueError, match="must accept"):
        GuestInformation(
            lead_guest_name="Test User",
            email="test@example.com",
            phone="+91 9876543210",
            accepted_terms=False
        )


def test_initiate_booking_and_pricing(booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]
    check_in = "2026-10-20"
    check_out = "2026-10-23"

    ok, record, msg = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in=check_in,
        check_out=check_out,
        num_rooms=2,
        num_adults=4,
    )

    assert ok is True
    assert record is not None
    assert record.booking_status == BookingStatus.AVAILABILITY_CHECKED
    assert record.num_rooms == 2
    assert record.num_nights == 3

    # Pricing calculation verification: base * 2 rooms * 3 nights + 12% GST
    base_subtotal = round(selected_room.base_price_per_night * 2 * 3, 2)
    expected_tax = round(base_subtotal * 0.12, 2)
    expected_total = round(base_subtotal + expected_tax, 2)

    assert record.pricing["room_subtotal"] == base_subtotal
    assert record.pricing["tax_amount"] == expected_tax
    assert record.pricing["total_amount"] == expected_total


def test_complete_booking_payment_and_confirmation_flow(booking_service, payment_gateway, sample_offer, valid_guest):
    # 1. Initiate booking
    selected_room = sample_offer.rooms[0]
    ok, record, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )
    assert ok is True

    # 2. Create Payment Order
    p_ok, order, _ = booking_service.create_payment_order_for_booking(record.booking_reference)
    assert p_ok is True
    assert order is not None

    # 3. Process payment callback with verified signature
    creds = payment_gateway.generate_demo_payment_credentials(order.order_id)
    c_ok, confirmed_record, msg = booking_service.process_payment_callback(
        order_id=order.order_id,
        payment_id=creds["payment_id"],
        signature=creds["signature"]
    )

    assert c_ok is True
    assert confirmed_record.booking_status == BookingStatus.CONFIRMED
    assert confirmed_record.payment_status == PaymentStatus.CAPTURED
    assert confirmed_record.supplier_booking_reference is not None
    assert "SKH-SUP" in confirmed_record.supplier_booking_reference


def test_payment_failure_handling(booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]
    _, record, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )

    _, order, _ = booking_service.create_payment_order_for_booking(record.booking_reference)

    # Submit invalid signature
    c_ok, failed_record, msg = booking_service.process_payment_callback(
        order_id=order.order_id,
        payment_id="pay_failed_123",
        signature="invalid_sig"
    )

    assert c_ok is False
    assert failed_record.booking_status == BookingStatus.FAILED
    assert failed_record.payment_status == PaymentStatus.FAILED


def test_cancellation_and_refund_flow(booking_service, payment_gateway, sample_offer, valid_guest):
    # Book first
    selected_room = sample_offer.rooms[0]
    _, record, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )
    _, order, _ = booking_service.create_payment_order_for_booking(record.booking_reference)
    creds = payment_gateway.generate_demo_payment_credentials(order.order_id)
    _, confirmed_record, _ = booking_service.process_payment_callback(
        order_id=order.order_id,
        payment_id=creds["payment_id"],
        signature=creds["signature"]
    )

    # Cancel booking
    cancel_ok, cancel_msg = booking_service.cancel_booking(confirmed_record.booking_reference)
    assert cancel_ok is True

    # Check updated record in DB
    updated = booking_service.repo.get_booking_by_reference(confirmed_record.booking_reference)
    assert updated.booking_status == BookingStatus.CANCELLED
    assert updated.payment_status == PaymentStatus.REFUNDED


def test_sqlite_persistence_list_and_filter(test_repo, booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]
    booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )

    bookings = test_repo.list_bookings(email=valid_guest.email)
    assert len(bookings) >= 1
    assert bookings[0].guest_info.email == valid_guest.email

    audit_logs = test_repo.get_audit_logs(bookings[0].booking_reference)
    assert len(audit_logs) >= 1
    assert "BOOKING_INITIATED" in audit_logs[0]["event"]


def test_room_occupancy_validation_rejection(booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]  # max_occupancy is 2
    # 1 room for 4 adults should be rejected
    ok, record, msg = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=4,
        num_children=0,
    )
    assert ok is False
    assert record is None
    assert "Occupancy exceeded" in msg


def test_booking_date_validation_rejection(booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]
    # Check-out before check-in
    ok, record, msg = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-25",
        check_out="2026-10-20",
        num_rooms=1,
        num_adults=2,
    )
    assert ok is False
    assert "strictly after" in msg


def test_simulated_payment_success_state_transitions_and_idempotency(booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]
    ok, record, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )
    assert ok is True

    # Process simulated payment (success)
    p_ok, paid_record, msg = booking_service.process_simulated_payment(
        booking_reference=record.booking_reference,
        scenario="success"
    )
    assert p_ok is True
    assert paid_record.booking_status == BookingStatus.CONFIRMED_DEMO
    assert paid_record.payment_status == PaymentStatus.SIMULATED_SUCCESS
    assert paid_record.supplier_booking_reference is not None

    # Duplicate submission prevention / Idempotency
    p_ok2, record2, msg2 = booking_service.process_simulated_payment(
        booking_reference=record.booking_reference,
        scenario="success"
    )
    assert p_ok2 is True
    assert record2.booking_status == BookingStatus.CONFIRMED_DEMO
    assert "already been confirmed" in msg2.lower() or "idempotent" in msg2.lower()


def test_simulated_payment_declined_state_transition(booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]
    ok, record, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )
    assert ok is True

    p_ok, failed_record, msg = booking_service.process_simulated_payment(
        booking_reference=record.booking_reference,
        scenario="declined"
    )
    assert p_ok is False
    assert failed_record.booking_status == BookingStatus.PAYMENT_FAILED
    assert failed_record.payment_status == PaymentStatus.SIMULATED_FAILED


def test_simulated_payment_pending_and_timeout_scenarios(booking_service, sample_offer, valid_guest):
    selected_room = sample_offer.rooms[0]
    # Pending scenario
    ok, rec_pending, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )
    assert ok is True
    p_ok1, rec1, _ = booking_service.process_simulated_payment(rec_pending.booking_reference, scenario="pending")
    assert p_ok1 is False
    assert rec1.payment_status == PaymentStatus.SIMULATED_PENDING
    assert rec1.booking_status == BookingStatus.PAYMENT_PENDING

    # Timeout scenario
    ok2, rec_timeout, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )
    assert ok2 is True
    p_ok2, rec2, _ = booking_service.process_simulated_payment(rec_timeout.booking_reference, scenario="timeout")
    assert p_ok2 is False
    assert rec2.payment_status == PaymentStatus.SIMULATED_TIMEOUT
    assert rec2.booking_status == BookingStatus.PAYMENT_PENDING


def test_inventory_reduction_and_cancellation_restoration(booking_service, sample_offer, valid_guest):
    from travel_agency.hotel_service import get_hotel_service

    hotel_service = get_hotel_service()
    selected_room = sample_offer.rooms[0]
    room_id = selected_room.room_id

    # Check initial inventory
    _, _, initial_count = hotel_service.check_mock_availability(sample_offer.hotel_id, room_id, 1)

    # Book 1 room successfully
    ok, record, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=selected_room,
        guest_info=valid_guest,
        check_in="2026-10-20",
        check_out="2026-10-22",
        num_rooms=1,
        num_adults=2,
    )
    assert ok is True

    p_ok, paid_record, _ = booking_service.process_simulated_payment(record.booking_reference, scenario="success")
    assert p_ok is True

    # Inventory should have decremented by 1
    _, _, after_booking_count = hotel_service.check_mock_availability(sample_offer.hotel_id, room_id, 1)
    assert after_booking_count == initial_count - 1

    # Cancel booking
    c_ok, c_msg = booking_service.cancel_booking(record.booking_reference)
    assert c_ok is True
    assert "successfully cancelled" in c_msg.lower()

    # Inventory should be restored back
    _, _, after_cancel_count = hotel_service.check_mock_availability(sample_offer.hotel_id, room_id, 1)
    assert after_cancel_count == initial_count

    # Check status
    updated = booking_service.repo.get_booking_by_reference(record.booking_reference)
    assert updated.booking_status == BookingStatus.CANCELLED_DEMO

