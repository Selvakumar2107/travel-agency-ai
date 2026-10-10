"""Automated tests for SK Demo Bank Account, Integer Paise Arithmetic, Idempotency, and Hotel Checkout Integration."""

import pytest
from datetime import date, timedelta
from pathlib import Path

from unittest.mock import patch, MagicMock
from travel_agency.bank_models import DemoBankAccount, DemoBankTransaction
from travel_agency.bank_service import DemoBankService, get_demo_bank_service, inr_to_paise, paise_to_inr
from travel_agency.booking_models import (
    GuestInformation,
    BookingStatus,
    PaymentStatus,
    HotelSearchQuery,
    HotelBookingRecord,
)
from travel_agency.hotel_provider import DemoHotelProvider
from travel_agency.booking_repository import BookingRepository
from travel_agency.booking_service import BookingService
from travel_agency.payment_service import DemoPaymentProvider
from travel_agency.orchestrator import MultiAgentOrchestrator
from travel_agency.models import TripRequest, HotelTier, FoodTier, TransportTier, ActivityTier


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_bank.db"


@pytest.fixture
def bank_service(temp_db_path):
    return DemoBankService(db_path=temp_db_path)


@pytest.fixture
def test_repo(temp_db_path):
    return BookingRepository(db_path=temp_db_path)


@pytest.fixture
def hotel_provider():
    return DemoHotelProvider()


@pytest.fixture
def payment_gateway():
    return DemoPaymentProvider()


@pytest.fixture
def booking_service(test_repo, hotel_provider, payment_gateway, bank_service):
    return BookingService(
        repository=test_repo,
        hotel_provider=hotel_provider,
        payment_gateway=payment_gateway,
        bank_service=bank_service,
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
        lead_guest_name="Demo Traveller",
        email="demo.traveller@skholidays.com",
        phone="+91 98765 43210",
        special_requests="Simulated testing booking"
    )


# =========================================================================
# TEST 1: New demo account starts with ₹1,00,000
# =========================================================================
def test_1_new_demo_account_starts_with_one_lakh(bank_service):
    account = bank_service.get_account()
    assert account is not None
    assert account.bank_name == "SK Demo Bank"
    assert account.account_holder == "Demo Traveller"
    assert account.account_number == "SKDEMO100001"
    assert account.masked_account_number == "XXXXXX0001"
    assert account.account_type == "Demo Savings Account"
    assert account.currency == "INR"
    assert account.status == "Active (Demo)"
    # Strict integer paise check: 10,000,000 paise = ₹1,00,000.00
    assert account.balance_paise == 10000000
    assert account.balance_inr == 100000.00

    summary = bank_service.get_account_summary()
    assert summary["available_balance_inr"] == 100000.00
    assert summary["total_spent_inr"] == 0.00
    assert summary["successful_payment_count"] == 0


# =========================================================================
# TEST 2: A successful ₹3,696 booking payment leaves ₹96,304
# =========================================================================
def test_2_successful_booking_payment_leaves_correct_balance(bank_service):
    booking_ref = "SKH-TEST-BK-001"
    hotel_name = "Savoy - IHCL SeleQtions"
    amount = 3696.0

    ok, txn_ref, txn, msg = bank_service.process_booking_payment(
        booking_reference=booking_ref,
        hotel_name=hotel_name,
        amount_inr=amount
    )

    assert ok is True
    assert txn_ref.startswith("SKTXN-")
    assert txn is not None
    assert txn.status == "SUCCESS"
    assert txn.transaction_type == "DEBIT"
    assert txn.amount_paise == 369600
    assert txn.amount_inr == 3696.0
    assert txn.balance_before_paise == 10000000
    assert txn.balance_after_paise == 9630400
    assert txn.balance_after_inr == 96304.00

    account = bank_service.get_account()
    assert account.balance_paise == 9630400
    assert account.balance_inr == 96304.00

    summary = bank_service.get_account_summary()
    assert summary["total_spent_inr"] == 3696.00
    assert summary["successful_payment_count"] == 1


# =========================================================================
# TEST 3: A second successful payment deducts the correct amount
# =========================================================================
def test_3_second_successful_payment_deducts_correctly(bank_service):
    # Payment 1: ₹3,696.00 -> balance ₹96,304.00
    bank_service.process_booking_payment(
        booking_reference="SKH-TEST-BK-001",
        hotel_name="Savoy IHCL",
        amount_inr=3696.0
    )

    # Payment 2: ₹5,000.00 -> balance ₹91,304.00
    ok, txn_ref, txn, msg = bank_service.process_booking_payment(
        booking_reference="SKH-TEST-BK-002",
        hotel_name="Fortune Resort",
        amount_inr=5000.0
    )

    assert ok is True
    assert txn.balance_before_paise == 9630400
    assert txn.balance_after_paise == 9130400
    assert txn.balance_after_inr == 91304.00

    account = bank_service.get_account()
    assert account.balance_paise == 9130400
    assert account.balance_inr == 91304.00

    summary = bank_service.get_account_summary()
    assert summary["total_spent_inr"] == 8696.00
    assert summary["successful_payment_count"] == 2


# =========================================================================
# TEST 4: An insufficient-balance payment is rejected
# =========================================================================
def test_4_insufficient_balance_payment_rejected(bank_service):
    excessive_amount = 150000.0  # ₹1,50,000 > ₹1,00,000 available

    ok, txn_ref, txn, msg = bank_service.process_booking_payment(
        booking_reference="SKH-TEST-BK-OVERDRAFT",
        hotel_name="Taj Lake Palace",
        amount_inr=excessive_amount
    )

    assert ok is False
    assert txn_ref is None
    assert "Insufficient demo funds" in msg
    assert "Shortfall: ₹50,000.00" in msg

    # Balance remains completely untouched
    account = bank_service.get_account()
    assert account.balance_paise == 10000000
    assert account.balance_inr == 100000.00


# =========================================================================
# TEST 5: Invalid amounts (zero or negative) are rejected
# =========================================================================
def test_5_invalid_zero_and_negative_amounts_rejected(bank_service):
    # Test zero
    ok_zero, _, _, msg_zero = bank_service.process_booking_payment(
        booking_reference="SKH-TEST-BK-ZERO",
        hotel_name="Zero Hotel",
        amount_inr=0.0
    )
    assert ok_zero is False
    assert "greater than zero" in msg_zero

    # Test negative
    ok_neg, _, _, msg_neg = bank_service.process_booking_payment(
        booking_reference="SKH-TEST-BK-NEG",
        hotel_name="Negative Hotel",
        amount_inr=-500.0
    )
    assert ok_neg is False
    assert "greater than zero" in msg_neg

    # Balance remains unchanged
    account = bank_service.get_account()
    assert account.balance_paise == 10000000


# =========================================================================
# TEST 6: Repeated requests do not deduct twice (Idempotency)
# =========================================================================
def test_6_repeated_requests_idempotent_no_double_deduction(bank_service):
    booking_ref = "SKH-TEST-BK-IDEMPOTENT"
    amount = 4500.0

    # First attempt
    ok1, txn_ref1, txn1, _ = bank_service.process_booking_payment(
        booking_reference=booking_ref,
        hotel_name="Idempotent Inn",
        amount_inr=amount
    )
    assert ok1 is True
    initial_bal_after = txn1.balance_after_paise

    # Second attempt with same booking reference directly on bank_service
    ok2, txn_ref2, txn2, msg2 = bank_service.process_booking_payment(
        booking_reference=booking_ref,
        hotel_name="Idempotent Inn",
        amount_inr=amount
    )
    assert ok2 is False
    assert txn_ref1 == txn_ref2
    assert "duplicate payment prevented" in msg2

    # Balance was deducted only once
    account = bank_service.get_account()
    assert account.balance_paise == initial_bal_after
    assert account.balance_paise == 10000000 - 450000

    # Only one debit transaction recorded in DB
    txns = bank_service.get_transactions(booking_reference=booking_ref)
    assert len(txns) == 1


# =========================================================================
# TEST 7: Database or booking failures do not leave an incorrect deduction
# =========================================================================
def test_7_booking_inventory_failure_does_not_deduct_funds(booking_service, sample_offer, valid_guest, bank_service):
    today = date.today()
    ok_init, booking, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=sample_offer.rooms[0],
        guest_info=valid_guest,
        check_in=(today + timedelta(days=7)).isoformat(),
        check_out=(today + timedelta(days=10)).isoformat(),
        num_rooms=1,
        num_adults=2,
    )
    assert ok_init is True

    # Artificially deplete mock inventory
    from travel_agency.hotel_service import get_hotel_service
    hotel_service = get_hotel_service()
    hotel_service.set_mock_inventory(booking.room_id, 0)

    # Attempt payment using SK Demo Bank
    ok_pay, updated_booking, pay_msg, _ = booking_service.pay_with_demo_bank(booking.booking_reference)
    assert ok_pay is False
    assert "Room availability check failed" in pay_msg

    # Verify no deduction occurred
    account = bank_service.get_account()
    assert account.balance_paise == 10000000
    assert account.balance_inr == 100000.00


# =========================================================================
# TEST 8: Successful cancellations produce at most one eligible refund
# =========================================================================
def test_8_successful_cancellation_credits_at_most_one_refund(booking_service, sample_offer, valid_guest, bank_service):
    today = date.today()
    # Reset mock inventory to ample availability
    from travel_agency.hotel_service import get_hotel_service
    get_hotel_service().set_mock_inventory(sample_offer.rooms[0].room_id, 5)

    ok_init, booking, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=sample_offer.rooms[0],
        guest_info=valid_guest,
        check_in=(today + timedelta(days=7)).isoformat(),
        check_out=(today + timedelta(days=10)).isoformat(),
        num_rooms=1,
        num_adults=2,
    )
    assert ok_init is True

    total_amount = booking.pricing["total_amount"]

    # Pay via SK Demo Bank
    ok_pay, paid_booking, _, _ = booking_service.pay_with_demo_bank(booking.booking_reference)
    assert ok_pay is True
    assert paid_booking.booking_status == BookingStatus.CONFIRMED_DEMO

    # Balance debited
    expected_debited_bal = 100000.00 - total_amount
    account_after_pay = bank_service.get_account()
    assert account_after_pay.balance_inr == expected_debited_bal

    # Cancel booking (refundable policy)
    ok_cancel, cancel_msg = booking_service.cancel_booking(booking.booking_reference, reason="Change of travel plans")
    assert ok_cancel is True
    assert "credited back to SK Demo Bank" in cancel_msg

    # Balance refunded back to ₹1,00,000
    account_after_cancel = bank_service.get_account()
    assert account_after_cancel.balance_paise == 10000000
    assert account_after_cancel.balance_inr == 100000.00

    # Attempt duplicate cancellation / refund
    ok_cancel_again, cancel_again_msg = booking_service.cancel_booking(booking.booking_reference)
    assert ok_cancel_again is False
    assert "already been cancelled" in cancel_again_msg

    # Balance still exactly ₹1,00,000 (no double refund)
    account_final = bank_service.get_account()
    assert account_final.balance_paise == 10000000


# =========================================================================
# TEST 9: Non-refundable cancellations do not credit the account
# =========================================================================
def test_9_non_refundable_cancellations_do_not_credit_account(sample_offer, valid_guest, bank_service, booking_service, test_repo):
    today = date.today()
    ok_init, booking, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=sample_offer.rooms[0],
        guest_info=valid_guest,
        check_in=(today + timedelta(days=7)).isoformat(),
        check_out=(today + timedelta(days=9)).isoformat(),
        num_rooms=1,
        num_adults=2,
    )
    assert ok_init is True

    # Set cancellation policy to non-refundable
    booking.cancellation_policy = "Strict Non-Refundable Policy. No refunds allowed upon cancellation."
    test_repo.save_booking(booking)

    # Pay via SK Demo Bank
    ok_pay, paid_booking, _, _ = booking_service.pay_with_demo_bank(booking.booking_reference)
    assert ok_pay is True
    total_amount = paid_booking.pricing["total_amount"]
    expected_debited_bal = 100000.00 - total_amount

    # Cancel non-refundable booking
    ok_cancel, cancel_msg = booking_service.cancel_booking(booking.booking_reference, reason="User cancelled")
    assert ok_cancel is True
    assert "Non-refundable rate as per policy" in cancel_msg

    # Verify balance was NOT credited
    account = bank_service.get_account()
    assert account.balance_inr == expected_debited_bal


# =========================================================================
# TEST 10: Balances and transaction history persist after application restart
# =========================================================================
def test_10_balance_and_transactions_persist_across_restarts(temp_db_path):
    # Session 1: Create bank service and make a payment
    service1 = DemoBankService(db_path=temp_db_path)
    ok1, txn_ref, _, _ = service1.process_booking_payment(
        booking_reference="SKH-PERSIST-001",
        hotel_name="Persistent Haveli",
        amount_inr=6200.0
    )
    assert ok1 is True
    bal1 = service1.get_account().balance_paise
    assert bal1 == 10000000 - 620000

    # Simulate application restart: instantiate a new service instance
    service2 = DemoBankService(db_path=temp_db_path)
    acc2 = service2.get_account()
    assert acc2.balance_paise == bal1
    assert acc2.balance_inr == 93800.00

    txns = service2.get_transactions()
    assert len(txns) == 1
    assert txns[0].transaction_reference == txn_ref
    assert txns[0].amount_inr == 6200.0


# =========================================================================
# TEST 11: The existing simulated payment method still works
# =========================================================================
def test_11_existing_simulated_payment_method_works(booking_service, sample_offer, valid_guest):
    today = date.today()
    from travel_agency.hotel_service import get_hotel_service
    get_hotel_service().set_mock_inventory(sample_offer.rooms[0].room_id, 5)

    # 1. Success scenario
    ok_init, booking, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=sample_offer.rooms[0],
        guest_info=valid_guest,
        check_in=(today + timedelta(days=7)).isoformat(),
        check_out=(today + timedelta(days=10)).isoformat(),
        num_rooms=1,
        num_adults=2,
    )
    assert ok_init is True

    ok_pay, confirmed_booking, msg = booking_service.process_simulated_payment(
        booking_reference=booking.booking_reference,
        scenario="success"
    )
    assert ok_pay is True
    assert confirmed_booking.booking_status == BookingStatus.CONFIRMED_DEMO

    # 2. Declined scenario
    ok_init2, booking2, _ = booking_service.initiate_booking(
        offer=sample_offer,
        selected_room=sample_offer.rooms[0],
        guest_info=valid_guest,
        check_in=(today + timedelta(days=7)).isoformat(),
        check_out=(today + timedelta(days=10)).isoformat(),
        num_rooms=1,
        num_adults=2,
    )
    assert ok_init2 is True

    ok_pay2, failed_booking, msg2 = booking_service.process_simulated_payment(
        booking_reference=booking2.booking_reference,
        scenario="declined"
    )
    assert ok_pay2 is False
    assert failed_booking.booking_status == BookingStatus.PAYMENT_FAILED


# =========================================================================
# TEST 12: Existing AI travel planning, hotel recommendations, and budget optimization continue working
# =========================================================================
def test_12_existing_ai_intelligence_and_optimization_continue_working():
    orchestrator = MultiAgentOrchestrator(api_key=None)

    # Request baseline trip: budget ₹3,000 for 1 day
    req = TripRequest(
        destination_id="mysuru",
        trip_duration_days=1,
        num_travelers=1,
        total_budget=3000.0,
        hotel_tier="budget",
        food_tier="economy",
        transport_tier="shared",
        activity_tier="budget",
        interests=["heritage", "palace"]
    )

    plan = orchestrator.plan_trip(req)

    # Verify plan invariants
    assert plan is not None
    assert plan.destination["id"] == "mysuru"
    assert len(plan.itinerary) == 1
    assert plan.final_costs.total_estimated_cost > 0
    assert plan.final_costs.subtotal > 0
    assert plan.final_costs.contingency_reserve > 0
    assert plan.budget_status in ("within_budget", "optimized_within_budget", "exceeded_budget")
    assert len(plan.agent_reports) == 5
    assert hasattr(plan, "option_comparisons")
    assert len(plan.option_comparisons) == 3  # Economy, Balanced, Premium


# =========================================================================
# TEST 13: First-time service initialization creates tables and default account
# =========================================================================
def test_13_first_time_service_initialization(tmp_path):
    custom_db = tmp_path / "fresh_init.db"
    assert not custom_db.exists()

    service = get_demo_bank_service(custom_db)
    assert custom_db.exists()
    assert service is not None

    account = service.get_account()
    assert account.balance_paise == 10000000
    assert account.balance_inr == 100000.00
    assert account.bank_name == "SK Demo Bank"
    assert account.account_number == "SKDEMO100001"


# =========================================================================
# TEST 14: Repeated calls return the cached singleton instance
# =========================================================================
def test_14_repeated_calls_return_cached_singleton(tmp_path):
    custom_db = tmp_path / "singleton_test.db"

    service1 = get_demo_bank_service(custom_db)
    service2 = get_demo_bank_service(custom_db)
    assert service1 is service2

    # Default path call also returns a stable singleton
    default1 = get_demo_bank_service()
    default2 = get_demo_bank_service()
    assert default1 is default2


# =========================================================================
# TEST 15: Database persistence across reloads and no reset on rerun
# =========================================================================
def test_15_database_persistence_no_reset_on_rerun(tmp_path):
    custom_db = tmp_path / "rerun_persistence.db"
    service = get_demo_bank_service(custom_db)

    # Debit funds for a test booking
    ok, txn_ref, txn, _ = service.process_booking_payment(
        booking_reference="SKH-RERUN-001",
        hotel_name="Persistence Palace",
        amount_inr=15000.0
    )
    assert ok is True
    assert txn.balance_after_inr == 85000.00

    # Simulate a Streamlit page reload / rerun by obtaining service again
    reloaded_service = get_demo_bank_service(custom_db)
    summary = reloaded_service.get_account_summary()

    # Balance must remain ₹85,000 and not reset to ₹1,00,000
    assert summary["available_balance_inr"] == 85000.00
    assert summary["total_spent_inr"] == 15000.00
    assert summary["successful_payment_count"] == 1


# =========================================================================
# TEST 16: Demo Bank page opens without NameError or exceptions
# =========================================================================
def test_16_demo_bank_page_opens_without_name_error():
    from travel_agency.bank_ui import render_demo_bank_page

    with patch("travel_agency.bank_ui.st") as mock_st:
        mock_st.columns.side_effect = lambda spec: [MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))]
        mock_st.expander.return_value.__enter__.return_value = MagicMock()
        mock_st.selectbox.return_value = "All"
        mock_st.checkbox.return_value = False
        mock_st.button.return_value = False

        # Calling render_demo_bank_page must execute cleanly without NameError
        try:
            render_demo_bank_page()
            executed_cleanly = True
        except NameError as ne:
            executed_cleanly = False
            pytest.fail(f"NameError occurred: {ne}")
        except Exception as e:
            # Any non-NameError unexpected exception
            pytest.fail(f"Unexpected exception during render_demo_bank_page: {e}")

        assert executed_cleanly is True
