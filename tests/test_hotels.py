"""Automated tests for Hotel Discovery, Inventory Provider, and AI Recommendations."""

import pytest
from datetime import date, timedelta
from travel_agency.booking_models import (
    HotelSearchQuery,
    HotelCategory,
    AccommodationType,
)
from travel_agency.hotel_provider import DemoHotelProvider, LiveHotelProviderAdapter
from travel_agency.hotel_recommendations import AIHotelRecommendationService


@pytest.fixture
def hotel_provider():
    return DemoHotelProvider()


@pytest.fixture
def sample_query():
    today = date.today()
    return HotelSearchQuery(
        destination_id="ooty",
        check_in_date=today + timedelta(days=5),
        check_out_date=today + timedelta(days=8),
        num_rooms=1,
        num_adults=2,
        num_children=0,
    )


def test_hotel_search_destination_filter(hotel_provider, sample_query):
    results = hotel_provider.search_hotels(sample_query)
    assert len(results) > 0
    for h in results:
        assert h.destination_id == "ooty"
        assert h.is_demo_data is True
        assert "Demo data" in h.supplier_name or h.is_demo_data


def test_hotel_search_category_filter(hotel_provider, sample_query):
    query_budget = sample_query.model_copy(update={"category": HotelCategory.BUDGET})
    results = hotel_provider.search_hotels(query_budget)
    assert len(results) > 0
    for h in results:
        assert h.category == "budget"


def test_hotel_search_max_budget_filter(hotel_provider, sample_query):
    max_budget = 2000.0
    query_capped = sample_query.model_copy(update={"max_budget_per_night": max_budget})
    results = hotel_provider.search_hotels(query_capped)
    for h in results:
        assert h.price_per_night <= max_budget


def test_hotel_search_amenities_filter(hotel_provider, sample_query):
    query_wifi = sample_query.model_copy(update={"required_amenities": ["Wi-Fi"]})
    results = hotel_provider.search_hotels(query_wifi)
    assert len(results) > 0
    for h in results:
        has_wifi = any("wi-fi" in a.lower() or "wifi" in a.lower() for a in h.amenities)
        assert has_wifi


def test_date_validation_checkout_before_checkin():
    today = date.today()
    with pytest.raises(ValueError, match="strictly later"):
        HotelSearchQuery(
            destination_id="ooty",
            check_in_date=today + timedelta(days=5),
            check_out_date=today + timedelta(days=4),
        )


def test_date_validation_checkout_equals_checkin():
    today = date.today()
    with pytest.raises(ValueError, match="strictly later"):
        HotelSearchQuery(
            destination_id="ooty",
            check_in_date=today + timedelta(days=5),
            check_out_date=today + timedelta(days=5),
        )


def test_guest_count_validation():
    today = date.today()
    with pytest.raises(ValueError):
        HotelSearchQuery(
            destination_id="ooty",
            check_in_date=today + timedelta(days=2),
            check_out_date=today + timedelta(days=4),
            num_adults=0,
        )


def test_recheck_availability_existing_and_invalid(hotel_provider):
    # Valid room recheck
    is_avail, price, msg = hotel_provider.recheck_availability("ooty-budget-1", "ooty-budget-1-rm-std")
    assert is_avail is True
    assert price is not None
    assert price > 0

    # Non-existent room recheck
    is_avail_bad, price_bad, msg_bad = hotel_provider.recheck_availability("ooty-budget-1", "non-existent-room-99")
    assert is_avail_bad is False
    assert price_bad is None


def test_ai_recommendation_ranking_groups(hotel_provider, sample_query):
    hotels = hotel_provider.search_hotels(sample_query)
    recommender = AIHotelRecommendationService()
    groups = recommender.recommend(hotels, sample_query)

    assert groups.best_budget_match is not None
    assert groups.best_value is not None
    assert groups.premium_experience is not None

    # Best budget match should have lowest total price
    assert groups.best_budget_match.total_price <= groups.premium_experience.total_price
    assert len(groups.best_budget_rationale) > 0
    assert len(groups.best_value_rationale) > 0
    assert len(groups.premium_experience_rationale) > 0


def test_live_provider_adapter_fallback_and_admin_status():
    adapter = LiveHotelProviderAdapter()
    admin_status = adapter.get_admin_status_message()
    assert admin_status["status"] in ("DEMO_MODE", "ACTIVE_LIVE")
    assert "status" in admin_status
