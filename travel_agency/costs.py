"""Deterministic travel cost calculation and validation engine.

All financial arithmetic is computed via pure, deterministic Python functions.
No LLM hallucinations or approximate arithmetic are permitted in cost results.
"""

import math
from typing import Dict, Any, Tuple
from travel_agency.models import TripRequest, CostBreakdown, HotelTier, FoodTier, TransportTier, ActivityTier
from travel_agency.data import (
    get_destination_by_id,
    get_hotels_for_destination,
    get_transport_tier,
    get_food_tier,
    get_activities_tier,
)


def calculate_num_rooms(num_travelers: int) -> int:
    """Calculate the required number of hotel rooms (standard double occupancy)."""
    if num_travelers <= 0:
        raise ValueError("Number of travelers must be greater than 0.")
    return math.ceil(num_travelers / 2.0)


def calculate_num_nights(trip_duration_days: int) -> int:
    """Calculate the number of hotel nights for a trip duration in days."""
    if trip_duration_days <= 0:
        raise ValueError("Trip duration in days must be greater than 0.")
    return max(1, trip_duration_days - 1 if trip_duration_days > 1 else 1)


def calculate_intercity_transport(
    destination: Dict[str, Any],
    transport_tier: TransportTier,
    num_travelers: int
) -> float:
    """Calculate intercity travel cost based on destination sample rates or tier defaults."""
    dest_estimates = destination.get("sample_intercity_transport_estimate", {})
    if transport_tier in dest_estimates:
        per_person = float(dest_estimates[transport_tier])
    else:
        tier_data = get_transport_tier(transport_tier)
        per_person = float(tier_data.get("intercity_default_per_person", 2000))
    return round(per_person * num_travelers, 2)


def calculate_local_transport(
    destination: Dict[str, Any],
    transport_tier: TransportTier,
    num_travelers: int,
    trip_duration_days: int
) -> float:
    """Calculate local in-city transportation cost."""
    dest_estimates = destination.get("sample_local_transport_estimate_per_day", {})
    if transport_tier in dest_estimates:
        base_daily = float(dest_estimates[transport_tier])
    else:
        tier_data = get_transport_tier(transport_tier)
        base_daily = float(tier_data.get("local_default_per_person_per_day", 1000))

    if transport_tier == "shared":
        # Shared transit is charged per traveler per day
        total_local = base_daily * num_travelers * trip_duration_days
    else:
        # Standard or private vehicle capacity: 1 cab per up to 4 travelers
        num_vehicles = math.ceil(num_travelers / 4.0)
        total_local = base_daily * num_vehicles * trip_duration_days

    return round(total_local, 2)


def calculate_accommodation_cost(
    hotel: Dict[str, Any],
    num_rooms: int,
    num_nights: int
) -> float:
    """Calculate total hotel accommodation expense, supporting supplier totals and taxes/fees."""
    if "total_price" in hotel and hotel.get("num_rooms") == num_rooms and hotel.get("num_nights") == num_nights:
        return round(float(hotel["total_price"]), 2)
    price_per_night = float(hotel.get("price_per_night", 2500))
    taxes_and_fees = float(hotel.get("taxes_and_fees", 0.0))
    return round((price_per_night * num_rooms * num_nights) + taxes_and_fees, 2)


def calculate_food_cost(
    food_tier: FoodTier,
    num_travelers: int,
    trip_duration_days: int
) -> float:
    """Calculate total meal expenses across all travelers."""
    tier_info = get_food_tier(food_tier)
    daily_per_person = float(tier_info.get("cost_per_person_per_day", 1200))
    return round(daily_per_person * num_travelers * trip_duration_days, 2)


def calculate_activities_cost(
    activity_tier: ActivityTier,
    num_travelers: int,
    trip_duration_days: int
) -> float:
    """Calculate total sightseeing and activities expenses."""
    tier_info = get_activities_tier(activity_tier)
    daily_per_person = float(tier_info.get("cost_per_person_per_day", 1000))
    return round(daily_per_person * num_travelers * trip_duration_days, 2)


def calculate_contingency(subtotal: float, contingency_percent: float = 10.0) -> float:
    """Calculate contingency reserve (default 10%)."""
    if contingency_percent < 0:
        raise ValueError("Contingency percent cannot be negative.")
    return round(subtotal * (contingency_percent / 100.0), 2)


def compute_trip_costs(
    destination: Dict[str, Any],
    hotel: Dict[str, Any],
    num_travelers: int,
    trip_duration_days: int,
    transport_tier: TransportTier,
    food_tier: FoodTier,
    activity_tier: ActivityTier,
    contingency_percent: float = 10.0
) -> CostBreakdown:
    """
    Compute comprehensive, deterministic itemized trip costs.
    Returns an authoritative CostBreakdown model instance.
    """
    if num_travelers < 1:
        raise ValueError("Number of travelers must be at least 1.")
    if trip_duration_days < 1:
        raise ValueError("Trip duration must be at least 1 day.")

    num_rooms = calculate_num_rooms(num_travelers)
    num_nights = calculate_num_nights(trip_duration_days)

    intercity_transport = calculate_intercity_transport(destination, transport_tier, num_travelers)
    local_transport = calculate_local_transport(destination, transport_tier, num_travelers, trip_duration_days)
    hotel_cost = calculate_accommodation_cost(hotel, num_rooms, num_nights)
    food_cost = calculate_food_cost(food_tier, num_travelers, trip_duration_days)
    activity_cost = calculate_activities_cost(activity_tier, num_travelers, trip_duration_days)

    subtotal = round(intercity_transport + local_transport + hotel_cost + food_cost + activity_cost, 2)
    contingency = calculate_contingency(subtotal, contingency_percent)
    grand_total = round(subtotal + contingency, 2)
    per_person = round(grand_total / num_travelers, 2)

    return CostBreakdown(
        intercity_transport=intercity_transport,
        local_transport=local_transport,
        hotel_accommodation=hotel_cost,
        food=food_cost,
        activities=activity_cost,
        subtotal=subtotal,
        contingency_reserve=contingency,
        total_estimated_cost=grand_total,
        cost_per_person=per_person,
        num_rooms=num_rooms,
        num_nights=num_nights
    )


def select_hotel_for_tier(destination_id: str, tier: HotelTier) -> Dict[str, Any]:
    """Select the first matching dummy hotel for a given tier in the destination."""
    hotels = get_hotels_for_destination(destination_id, tier)
    if not hotels:
        # Fallback to any hotel in destination
        all_hotels = get_hotels_for_destination(destination_id)
        if not all_hotels:
            raise ValueError(f"No hotels found in destination '{destination_id}'")
        return all_hotels[0]
    return hotels[0]
