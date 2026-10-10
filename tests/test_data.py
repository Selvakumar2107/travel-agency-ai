"""Tests for dataset loading, querying, and validation."""

import pytest
from travel_agency.data import (
    load_destinations,
    get_destination_by_id,
    load_hotels,
    get_hotels_for_destination,
    get_hotel_by_id,
    load_transport,
    get_transport_tier,
    load_food,
    get_food_tier,
    load_activities,
    get_activities_tier,
    get_activities_for_destination,
)


def test_load_destinations():
    """Verify destinations dataset loads and has at least 8 destinations."""
    destinations = load_destinations()
    assert isinstance(destinations, list)
    assert len(destinations) >= 8

    # Check for expected sample destinations
    expected_ids = {"ooty", "coorg", "mysuru", "pondicherry", "munnar", "jaipur", "goa", "rishikesh"}
    actual_ids = {d["id"].lower() for d in destinations}
    assert expected_ids.issubset(actual_ids)


def test_get_destination_by_id():
    """Verify destination lookup by valid and invalid ID."""
    dest = get_destination_by_id("ooty")
    assert dest["name"] == "Ooty"
    assert "suitable_interests" in dest
    assert "sample_intercity_transport_estimate" in dest

    with pytest.raises(ValueError, match="not found in dataset"):
        get_destination_by_id("non_existent_destination")


def test_load_hotels_and_tiers():
    """Verify hotels dataset loads with all tiers for each destination."""
    hotels = load_hotels()
    assert len(hotels) > 0

    destinations = load_destinations()
    for d in destinations:
        dest_hotels = get_hotels_for_destination(d["id"])
        assert len(dest_hotels) >= 3, f"Destination {d['id']} should have multiple hotels"
        tiers = {h["tier"] for h in dest_hotels}
        assert "budget" in tiers
        assert "standard" in tiers
        assert "premium" in tiers


def test_get_hotels_for_destination_filter():
    """Verify hotel filtering by tier."""
    budget_hotels = get_hotels_for_destination("goa", tier="budget")
    assert len(budget_hotels) > 0
    assert all(h["tier"] == "budget" for h in budget_hotels)


def test_load_transport_tiers():
    """Verify transport dataset contains shared, standard, and private tiers."""
    transport = load_transport()
    assert "tiers" in transport
    for tier in ["shared", "standard", "private"]:
        tier_data = get_transport_tier(tier)
        assert "name" in tier_data
        assert "intercity_default_per_person" in tier_data

    with pytest.raises(ValueError):
        get_transport_tier("invalid_tier")


def test_load_food_tiers():
    """Verify food dataset contains economy, standard, and comfort tiers."""
    food = load_food()
    assert "tiers" in food
    for tier in ["economy", "standard", "comfort"]:
        tier_data = get_food_tier(tier)
        assert "cost_per_person_per_day" in tier_data
        assert tier_data["cost_per_person_per_day"] > 0

    with pytest.raises(ValueError):
        get_food_tier("invalid_food_tier")


def test_load_activities():
    """Verify activities dataset contains tiers and destination catalog."""
    activities_data = load_activities()
    assert "tiers" in activities_data
    assert "destination_catalog" in activities_data

    for tier in ["budget", "standard", "premium"]:
        tier_data = get_activities_tier(tier)
        assert "cost_per_person_per_day" in tier_data

    ooty_acts = get_activities_for_destination("ooty")
    assert len(ooty_acts) > 0
