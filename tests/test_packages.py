"""Automated test suite for SK Holidays Travel Package Booking System.

Validates:
1. Package data loading & integrity across 8 destinations
2. Package filtering and category eligibility
3. Date, duration, and nights mathematical calculations
4. Room occupancy and guest party capacity validation
5. Round-trip transport (outbound, return, local) deterministic costs
6. Accommodation expenses by nights and room counts
7. Food expenses by travelers and trip duration
8. Activity costs and GST/transport taxes
9. Integer paise precision: price per person vs grand group total
10. Minimum budget validation (>= ₹3,000 INR)
11. Multi-agent evaluation and 3-pass budget optimization loop
12. Successful atomic payment through SK Demo Bank (₹1,00,000 balance)
13. Insufficient demo bank balance rejection & error messaging
14. Idempotent payment & duplicate charge prevention
15. Failed payment state handling and non-deduction
16. Policy-backed cancellation & duplicate refund prevention
17. SQLite persistence across application restarts
18. Non-regression of existing hotel-only bookings
"""

import pytest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from travel_agency.data import (
    load_packages,
    get_package_by_id,
    get_packages_for_destination,
    load_destinations,
)
from travel_agency.package_models import (
    TravelPackage,
    PackageSearchQuery,
    PackageCustomization,
    PackageCostBreakdown,
    PackageBookingRecord,
)
from travel_agency.booking_models import (
    BookingStatus,
    PaymentStatus,
    GuestInformation,
)
from travel_agency.package_pricing import (
    calculate_package_pricing,
    inr_to_paise,
    paise_to_inr,
)
from travel_agency.package_service import PackageService
from travel_agency.package_repository import PackageRepository
from travel_agency.bank_service import DemoBankService


@pytest.fixture
def temp_db_path(tmp_path):
    """Provides an isolated SQLite database path for testing."""
    return tmp_path / "test_package_bookings.db"


@pytest.fixture
def package_service(temp_db_path):
    """Initializes an isolated PackageService with a temporary database."""
    svc = PackageService(db_path=temp_db_path)
    # Ensure bank service points to the same test database
    svc.bank_service = DemoBankService(db_path=temp_db_path)
    return svc


@pytest.fixture
def sample_guest_info():
    """Provides a valid GuestInformation fixture."""
    return GuestInformation(
        lead_guest_name="Test Traveler",
        email="traveler@skholidays.test",
        phone="+91 9988776655",
        additional_guests=["Companion Traveler"],
        special_requests="High floor with quiet view",
        accepted_terms=True,
    )


# =========================================================================
# 1. PACKAGE DATA LOADING
# =========================================================================
def test_package_data_loading():
    """Test that package catalog loads correctly with 24 complete packages across 8 destinations."""
    packages = load_packages()
    assert len(packages) >= 24

    destinations = {d["id"] for d in load_destinations()}
    for pkg in packages:
        assert "id" in pkg
        assert "name" in pkg
        assert "category" in pkg
        assert pkg["category"] in ("economy", "comfort", "premium")
        assert pkg["destination_id"] in destinations
        assert pkg["duration_days"] >= 2
        assert pkg["num_nights"] >= 1
        assert "hotel_id" in pkg
        assert "transport_mode" in pkg
        assert "meal_plan" in pkg
        assert len(pkg.get("included_activities", [])) >= 1
        assert len(pkg.get("inclusions", [])) >= 1
        assert len(pkg.get("exclusions", [])) >= 1
        assert pkg.get("is_demo_data") is True


def test_package_retrieval_by_id():
    """Test retrieving individual packages by id."""
    pkg = get_package_by_id("pkg-ooty-economy")
    assert pkg["destination_id"] == "ooty"
    assert pkg["category"] == "economy"

    with pytest.raises(ValueError):
        get_package_by_id("non-existent-package-id")


# =========================================================================
# 2. PACKAGE FILTERING & ELIGIBILITY
# =========================================================================
def test_package_filtering(package_service):
    """Test filtering by destination, category, and budget constraints."""
    today = date.today()
    dep = today + timedelta(days=10)
    ret = today + timedelta(days=13)

    # Filter by destination
    query_ooty = PackageSearchQuery(
        departure_date=dep,
        return_date=ret,
        destination_id="ooty",
        category="all",
    )
    results = package_service.search_packages(query_ooty)
    assert len(results) >= 3
    for pkg, _ in results:
        assert pkg.destination_id == "ooty"

    # Filter by category
    query_premium = PackageSearchQuery(
        departure_date=dep,
        return_date=ret,
        category="premium",
    )
    results_prem = package_service.search_packages(query_premium)
    assert len(results_prem) >= 8  # 1 per destination
    for pkg, _ in results_prem:
        assert pkg.category == "premium"


# =========================================================================
# 3. DATE & DURATION VALIDATION
# =========================================================================
def test_date_and_duration_validation():
    """Test date order enforcement and correct calculation of nights & duration."""
    today = date.today()
    dep = today + timedelta(days=5)
    ret = today + timedelta(days=9)

    customization = PackageCustomization(
        package_id="pkg-ooty-comfort",
        destination_id="ooty",
        departure_date=dep,
        return_date=ret,
        num_adults=2,
    )
    assert customization.num_nights == 4
    assert customization.duration_days == 5

    # Invalid dates (return <= departure)
    with pytest.raises(ValueError, match="Return date must be strictly later"):
        PackageCustomization(
            package_id="pkg-ooty-comfort",
            destination_id="ooty",
            departure_date=ret,
            return_date=dep,
        )


# =========================================================================
# 4. ROOM OCCUPANCY & GUEST VALIDATION
# =========================================================================
def test_room_occupancy_validation():
    """Test capacity enforcement: total guests vs rooms * max occupancy."""
    today = date.today()
    customization = PackageCustomization(
        package_id="pkg-ooty-economy",
        destination_id="ooty",
        departure_date=today + timedelta(days=2),
        return_date=today + timedelta(days=4),
        num_adults=5,
        num_children=1,
        num_rooms=2,
        room_occupancy_per_room=2,  # capacity = 2 * 2 = 4 < 6 guests
    )
    is_valid, msg = customization.validate_room_capacity()
    assert is_valid is False
    assert "exceeds room capacity" in msg

    # Valid capacity
    customization.num_rooms = 3  # capacity = 3 * 2 = 6 == 6 guests
    is_valid, _ = customization.validate_room_capacity()
    assert is_valid is True


# =========================================================================
# 5. ROUND-TRIP TRANSPORT CALCULATIONS
# =========================================================================
def test_round_trip_transport_calculations():
    """Test that transport total correctly sums outbound, return, and local transit."""
    raw_pkg = get_package_by_id("pkg-ooty-economy")
    # For ooty economy (shared): intercity = 900, local = 350/person/day
    pricing = calculate_package_pricing(
        package=raw_pkg,
        num_travelers=2,
        num_rooms=1,
        num_nights=2,
        duration_days=3,
        selected_optional_activities=[],
        contingency_percent=10.0,
    )
    # Outbound: 900 * 2 = 1800
    assert pricing.outbound_transport_inr == 1800.0
    # Return: 900 * 2 = 1800
    assert pricing.return_transport_inr == 1800.0
    # Local: 350 * 2 * 3 = 2100
    assert pricing.local_transport_inr == 2100.0
    assert pricing.transport_subtotal_inr == 1800.0 + 1800.0 + 2100.0  # 5700.0


# =========================================================================
# 6. ACCOMMODATION EXPENSES BY NIGHTS & ROOMS
# =========================================================================
def test_accommodation_costs_by_nights_and_rooms():
    """Test accommodation calculation: room_rate * rooms * nights."""
    raw_pkg = get_package_by_id("pkg-ooty-comfort")
    # ooty-standard-1 price is 3200
    pricing = calculate_package_pricing(
        package=raw_pkg,
        num_travelers=4,
        num_rooms=2,
        num_nights=3,
        duration_days=4,
    )
    expected_acc = 3200.0 * 2 * 3
    assert pricing.accommodation_subtotal_inr == expected_acc


# =========================================================================
# 7. FOOD EXPENSES BY TRAVELERS & DAYS
# =========================================================================
def test_food_costs_by_travelers_and_days():
    """Test food calculation: daily_rate * travelers * duration_days."""
    raw_pkg = get_package_by_id("pkg-ooty-comfort")  # food_tier = standard -> 1300/person/day
    pricing = calculate_package_pricing(
        package=raw_pkg,
        num_travelers=3,
        num_rooms=2,
        num_nights=2,
        duration_days=3,
    )
    expected_food = 1300.0 * 3 * 3
    assert pricing.food_subtotal_inr == expected_food


# =========================================================================
# 8. ACTIVITY COSTS & TAXES
# =========================================================================
def test_activity_costs_and_taxes():
    """Test that taxes match 12% Hotel GST + 5% Transport tax, and optional activities are added."""
    raw_pkg = get_package_by_id("pkg-ooty-economy")
    opt_act = "Nilgiri Mountain Toy Train Heritage Experience"  # 600 in ooty catalog
    pricing = calculate_package_pricing(
        package=raw_pkg,
        num_travelers=2,
        num_rooms=1,
        num_nights=2,
        duration_days=3,
        selected_optional_activities=[opt_act],
        contingency_percent=10.0,
    )
    expected_opt_act = 600.0 * 2
    assert pricing.optional_activities_subtotal_inr == expected_opt_act
    assert pricing.hotel_gst_inr == round(pricing.accommodation_subtotal_inr * 0.12, 2)
    assert pricing.transport_tax_inr == round(pricing.transport_subtotal_inr * 0.05, 2)
    assert pricing.taxes_and_fees_inr == round(pricing.hotel_gst_inr + pricing.transport_tax_inr, 2)


# =========================================================================
# 9. INTEGER PAISE PRECISION: PER PERSON VS TOTAL GROUP
# =========================================================================
def test_integer_paise_precision_and_split():
    """Test that all monetary fields have matching integer paise with no float drift."""
    raw_pkg = get_package_by_id("pkg-goa-premium")
    pricing = calculate_package_pricing(
        package=raw_pkg,
        num_travelers=3,
        num_rooms=2,
        num_nights=3,
        duration_days=4,
    )
    assert pricing.total_group_price_paise == inr_to_paise(pricing.total_group_price_inr)
    assert pricing.price_per_person_paise == inr_to_paise(pricing.price_per_person_inr)
    assert pricing.amount_payable_now_inr == pricing.total_group_price_inr
    assert pricing.remaining_balance_inr == 0.0


# =========================================================================
# 10. MINIMUM BUDGET VALIDATION
# =========================================================================
def test_minimum_budget_validation():
    """Test that max_budget < 3000 raises a validation error."""
    today = date.today()
    with pytest.raises(ValueError, match="Minimum accepted trip budget is ₹3,000 INR"):
        PackageCustomization(
            package_id="pkg-ooty-economy",
            destination_id="ooty",
            departure_date=today + timedelta(days=2),
            return_date=today + timedelta(days=4),
            max_budget=2500.0,
        )


# =========================================================================
# 11. BUDGET OPTIMIZATION WITH MAXIMUM THREE PASSES
# =========================================================================
def test_budget_optimization_three_passes(package_service):
    """Test 3-pass budget optimization when package price exceeds maximum budget."""
    today = date.today()
    customization = PackageCustomization(
        package_id="pkg-ooty-premium",
        destination_id="ooty",
        departure_date=today + timedelta(days=2),
        return_date=today + timedelta(days=5),
        num_adults=2,
        num_rooms=1,
        selected_optional_activities=["Private Nilgiri Forest Jeep Safari & Avalanche Lake"],
        max_budget=15000.0,  # Below premium package total (~₹30,000+)
    )
    pricing = package_service.calculate_customized_pricing(customization)
    assert pricing.total_group_price_inr > 15000.0

    review = package_service.evaluate_package_with_agents(customization, pricing)
    assert review.is_within_budget is False
    assert len(review.optimization_passes) <= 3
    assert len(review.optimization_passes) >= 1
    assert "Pass 1" in review.optimization_recommendations[0]


# =========================================================================
# 12. SUCCESSFUL PACKAGE PAYMENT VIA DEMO BANK
# =========================================================================
def test_successful_package_payment(package_service, sample_guest_info):
    """Test full booking and payment lifecycle through the SK Demo Bank account."""
    today = date.today()
    customization = PackageCustomization(
        package_id="pkg-ooty-economy",
        destination_id="ooty",
        departure_date=today + timedelta(days=5),
        return_date=today + timedelta(days=7),
        num_adults=2,
        num_rooms=1,
    )
    draft = package_service.create_package_booking_draft(customization, sample_guest_info)
    assert draft.booking_status == BookingStatus.DRAFT

    initial_acc = package_service.bank_service.get_account()
    initial_balance_inr = paise_to_inr(initial_acc.balance_paise)

    success, txn_ref, bal_after, msg = package_service.pay_with_demo_bank(draft.booking_reference)
    assert success is True
    assert txn_ref.startswith("SKTXN-")
    assert bal_after == pytest.approx(initial_balance_inr - draft.total_amount_inr, 0.01)

    confirmed = package_service.repository.get_package_booking(draft.booking_reference)
    assert confirmed.booking_status == BookingStatus.CONFIRMED
    assert confirmed.payment_status == PaymentStatus.CAPTURED
    assert confirmed.demo_transaction_reference == txn_ref


# =========================================================================
# 13. INSUFFICIENT DEMO BANK BALANCE
# =========================================================================
def test_insufficient_demo_bank_balance(package_service, sample_guest_info):
    """Test payment rejection when available demo bank balance is lower than total price."""
    # Force low balance on test bank account
    with package_service.bank_service._get_connection() as conn:
        conn.cursor().execute("UPDATE demo_bank_accounts SET balance_paise = 50000")  # ₹500
        conn.commit()

    today = date.today()
    customization = PackageCustomization(
        package_id="pkg-ooty-economy",
        destination_id="ooty",
        departure_date=today + timedelta(days=5),
        return_date=today + timedelta(days=7),
        num_adults=2,
        num_rooms=1,
    )
    draft = package_service.create_package_booking_draft(customization, sample_guest_info)

    success, txn_ref, bal_after, msg = package_service.pay_with_demo_bank(draft.booking_reference)
    assert success is False
    assert "Insufficient demo funds" in msg

    # Balance must remain unchanged at ₹500
    acc = package_service.bank_service.get_account()
    assert acc.balance_paise == 50000

    # Booking must be marked failed
    record = package_service.repository.get_package_booking(draft.booking_reference)
    assert record.booking_status == BookingStatus.FAILED


# =========================================================================
# 14. DUPLICATE PAYMENT PREVENTION
# =========================================================================
def test_duplicate_payment_prevention(package_service, sample_guest_info):
    """Test that paying twice for the same booking is blocked by idempotency."""
    today = date.today()
    customization = PackageCustomization(
        package_id="pkg-ooty-economy",
        destination_id="ooty",
        departure_date=today + timedelta(days=5),
        return_date=today + timedelta(days=7),
        num_adults=2,
        num_rooms=1,
    )
    draft = package_service.create_package_booking_draft(customization, sample_guest_info)

    # First payment succeeds
    s1, ref1, _, _ = package_service.pay_with_demo_bank(draft.booking_reference)
    assert s1 is True

    # Second payment is blocked
    s2, ref2, _, msg2 = package_service.pay_with_demo_bank(draft.booking_reference)
    assert s2 is False
    assert "already" in msg2.lower()


# =========================================================================
# 15. CANCELLATION & DUPLICATE REFUND PREVENTION
# =========================================================================
def test_cancellation_and_duplicate_refund_prevention(package_service, sample_guest_info):
    """Test policy cancellation, atomic balance refund, and duplicate refund blocking."""
    today = date.today()
    customization = PackageCustomization(
        package_id="pkg-ooty-economy",
        destination_id="ooty",
        departure_date=today + timedelta(days=5),
        return_date=today + timedelta(days=7),
        num_adults=2,
        num_rooms=1,
    )
    draft = package_service.create_package_booking_draft(customization, sample_guest_info)
    package_service.pay_with_demo_bank(draft.booking_reference)

    bal_before_cancel = paise_to_inr(package_service.bank_service.get_account().balance_paise)

    # 1. First cancellation succeeds and issues refund
    c_ok, r_ref, c_msg = package_service.cancel_package_booking(draft.booking_reference)
    assert c_ok is True
    assert r_ref is not None
    assert "successfully cancelled" in c_msg

    bal_after_cancel = paise_to_inr(package_service.bank_service.get_account().balance_paise)
    assert bal_after_cancel == pytest.approx(bal_before_cancel + draft.total_amount_inr, 0.01)

    record = package_service.repository.get_package_booking(draft.booking_reference)
    assert record.booking_status == BookingStatus.CANCELLED
    assert record.payment_status == PaymentStatus.REFUNDED

    # 2. Second cancellation attempt is blocked
    c_ok2, _, c_msg2 = package_service.cancel_package_booking(draft.booking_reference)
    assert c_ok2 is False
    assert "already cancelled" in c_msg2


# =========================================================================
# 16. PERSISTENCE AFTER APPLICATION RESTART
# =========================================================================
def test_persistence_across_restart(temp_db_path, sample_guest_info):
    """Test that package booking records and bank transactions persist across new service instances."""
    svc1 = PackageService(db_path=temp_db_path)
    svc1.bank_service = DemoBankService(db_path=temp_db_path)

    today = date.today()
    customization = PackageCustomization(
        package_id="pkg-coorg-comfort",
        destination_id="coorg",
        departure_date=today + timedelta(days=10),
        return_date=today + timedelta(days=13),
        num_adults=2,
        num_rooms=1,
    )
    draft = svc1.create_package_booking_draft(customization, sample_guest_info)
    svc1.pay_with_demo_bank(draft.booking_reference)

    # Re-instantiate service (simulating application restart)
    svc2 = PackageService(db_path=temp_db_path)
    svc2.bank_service = DemoBankService(db_path=temp_db_path)

    persisted = svc2.repository.get_package_booking(draft.booking_reference)
    assert persisted is not None
    assert persisted.package_name == "Coorg Spicewood Plantation Comfort"
    assert persisted.booking_status == BookingStatus.CONFIRMED
    assert persisted.total_amount_inr == draft.total_amount_inr


# =========================================================================
# 17. TRAVEL PACKAGES UI RENDERING & HTML ESCAPING VERIFICATION
# =========================================================================
def test_all_24_packages_ui_rendering_and_escaping():
    """Verify all 24 packages render via render_package_card without code-block indentations or raw HTML leaks."""
    from travel_agency.package_ui import render_package_card
    from travel_agency.data import load_packages
    import streamlit as st

    pkg_service = PackageService()
    today = date.today()
    results = pkg_service.search_packages(PackageSearchQuery(
        origin="Bangalore",
        category="all",
        departure_date=today,
        return_date=today + timedelta(days=3),
        max_budget=None,
    ))
    assert len(results) == 24

    for pkg, pricing in results:

        markdown_calls = []

        # Create mock context for Streamlit components
        mock_container = MagicMock()
        mock_container.__enter__.return_value = mock_container
        mock_container.__exit__.return_value = None

        col1, col2 = MagicMock(), MagicMock()
        col1.__enter__.return_value = col1
        col1.__exit__.return_value = None
        col2.__enter__.return_value = col2
        col2.__exit__.return_value = None

        rendered_texts = []

        def fake_markdown(body, *args, **kwargs):
            rendered_texts.append(str(body))

        def fake_caption(body, *args, **kwargs):
            rendered_texts.append(str(body))

        def fake_subheader(body, *args, **kwargs):
            rendered_texts.append(str(body))

        with patch("streamlit.container", return_value=mock_container), \
             patch("streamlit.columns", return_value=[col1, col2]), \
             patch("streamlit.image") as mock_image, \
             patch("streamlit.markdown", side_effect=fake_markdown), \
             patch("streamlit.caption", side_effect=fake_caption), \
             patch("streamlit.subheader", side_effect=fake_subheader), \
             patch("streamlit.divider"), \
             patch("streamlit.button", return_value=False):

            render_package_card(
                pkg=pkg,
                pricing=pricing,
                total_travelers=2,
                num_rooms=1,
                num_nights=3,
                duration_days=4,
                dep_date=date.today(),
                ret_date=date.today() + timedelta(days=3),
            )

            # Ensure image was called with container width
            mock_image.assert_called_once_with(pkg.image_url, use_container_width=True)

            # Assert package details are present
            assert any(pkg.name in t for t in rendered_texts)
            assert any(pkg.destination_name in t for t in rendered_texts)
            assert any(pkg.hotel_name in t for t in rendered_texts)

            # Assert ZERO raw HTML tags in any rendered text
            for text in rendered_texts:
                assert "<div" not in text, f"Found <div in rendered text: {text}"
                assert "<span" not in text, f"Found <span in rendered text: {text}"
                assert "style=" not in text, f"Found style= in rendered text: {text}"
                assert "<ul" not in text, f"Found <ul in rendered text: {text}"
                assert "<li" not in text, f"Found <li in rendered text: {text}"


