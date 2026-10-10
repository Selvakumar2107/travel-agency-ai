"""Tests for deterministic cost calculation engine and financial validation."""

import pytest
from travel_agency.costs import (
    calculate_num_rooms,
    calculate_num_nights,
    calculate_intercity_transport,
    calculate_local_transport,
    calculate_accommodation_cost,
    calculate_food_cost,
    calculate_activities_cost,
    calculate_contingency,
    compute_trip_costs,
    select_hotel_for_tier,
)
from travel_agency.data import get_destination_by_id


def test_calculate_num_rooms():
    """Verify double-occupancy room calculation: 1 -> 1, 2 -> 1, 3 -> 2, 4 -> 2, 5 -> 3."""
    assert calculate_num_rooms(1) == 1
    assert calculate_num_rooms(2) == 1
    assert calculate_num_rooms(3) == 2
    assert calculate_num_rooms(4) == 2
    assert calculate_num_rooms(5) == 3

    with pytest.raises(ValueError):
        calculate_num_rooms(0)
    with pytest.raises(ValueError):
        calculate_num_rooms(-2)


def test_calculate_num_nights():
    """Verify nights calculation for trip duration."""
    assert calculate_num_nights(1) == 1
    assert calculate_num_nights(2) == 1
    assert calculate_num_nights(4) == 3
    assert calculate_num_nights(7) == 6

    with pytest.raises(ValueError):
        calculate_num_nights(0)


def test_contingency_calculation():
    """Verify 10% contingency calculation and custom percentage support."""
    assert calculate_contingency(10000.0, 10.0) == 1000.0
    assert calculate_contingency(5550.0, 10.0) == 555.0
    assert calculate_contingency(10000.0, 15.0) == 1500.0

    with pytest.raises(ValueError):
        calculate_contingency(10000.0, -5.0)


def test_compute_trip_costs_structure_and_math():
    """Verify complete trip costs math determinism, subtotal, contingency, and per-person breakdown."""
    dest = get_destination_by_id("ooty")
    hotel = select_hotel_for_tier("ooty", "standard")

    costs = compute_trip_costs(
        destination=dest,
        hotel=hotel,
        num_travelers=2,
        trip_duration_days=3,
        transport_tier="standard",
        food_tier="standard",
        activity_tier="standard",
        contingency_percent=10.0
    )

    # 2 travelers, 3 days => 1 room, 2 nights
    assert costs.num_rooms == 1
    assert costs.num_nights == 2

    # Check accommodation
    expected_hotel = hotel["price_per_night"] * 1 * 2
    assert costs.hotel_accommodation == expected_hotel

    # Check subtotal sum
    expected_subtotal = round(
        costs.intercity_transport +
        costs.local_transport +
        costs.hotel_accommodation +
        costs.food +
        costs.activities,
        2
    )
    assert costs.subtotal == expected_subtotal

    # Check contingency and grand total
    expected_contingency = round(expected_subtotal * 0.10, 2)
    assert costs.contingency_reserve == expected_contingency
    expected_grand_total = round(expected_subtotal + expected_contingency, 2)
    assert costs.total_estimated_cost == expected_grand_total

    # Check per-person
    assert costs.cost_per_person == round(expected_grand_total / 2.0, 2)


def test_compute_trip_costs_invalid_inputs():
    """Verify rejection of invalid duration or traveler count."""
    dest = get_destination_by_id("goa")
    hotel = select_hotel_for_tier("goa", "budget")

    with pytest.raises(ValueError, match="Number of travelers"):
        compute_trip_costs(
            destination=dest,
            hotel=hotel,
            num_travelers=0,
            trip_duration_days=3,
            transport_tier="budget", # type: ignore
            food_tier="economy",
            activity_tier="budget"
        )

    with pytest.raises(ValueError, match="Trip duration"):
        compute_trip_costs(
            destination=dest,
            hotel=hotel,
            num_travelers=2,
            trip_duration_days=0,
            transport_tier="standard",
            food_tier="standard",
            activity_tier="standard"
        )
