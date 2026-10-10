"""Agent tools providing clean structured data and deterministic calculations.

These tools can be invoked directly by the orchestrator and bound as callable tools
for Google GenAI / Gemini agents.
"""

from typing import Dict, Any, List, Optional
from travel_agency.data import (
    load_destinations,
    get_destination_by_id,
    get_hotels_for_destination,
    get_transport_tier,
    get_food_tier,
    get_activities_tier,
    get_activities_for_destination,
)
from travel_agency.costs import (
    compute_trip_costs,
    select_hotel_for_tier,
    calculate_num_rooms,
    calculate_num_nights,
)
from travel_agency.models import HotelTier, FoodTier, TransportTier, ActivityTier


def search_destinations(interests: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Search and filter destinations matching traveler interests.

    Args:
        interests: List of interest tags (e.g. ['Nature', 'Trekking'])
    Returns:
        List of matching destination dictionaries.
    """
    all_dests = load_destinations()
    if not interests:
        return all_dests

    normalized_interests = {i.lower() for i in interests}
    matched = []
    for d in all_dests:
        dest_interests = {i.lower() for i in d.get("suitable_interests", [])}
        common = normalized_interests.intersection(dest_interests)
        if common:
            matched.append({**d, "matched_interests_count": len(common)})

    if matched:
        matched.sort(key=lambda x: x.get("matched_interests_count", 0), reverse=True)
        return matched
    return all_dests


def search_hotels(destination_id: str, tier: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search hotels for a destination with optional tier filtering.

    Args:
        destination_id: Identifier of the destination.
        tier: Hotel tier ('budget', 'standard', 'premium') or None.
    Returns:
        List of matching hotel options.
    """
    return get_hotels_for_destination(destination_id, tier)


def get_transport_options(destination_id: str, transport_tier: str) -> Dict[str, Any]:
    """Retrieve intercity and local transport estimates for a destination.

    Args:
        destination_id: Identifier of the destination.
        transport_tier: Transport tier ('shared', 'standard', 'private').
    Returns:
        Dictionary containing tier description and destination-specific estimates.
    """
    dest = get_destination_by_id(destination_id)
    tier_info = get_transport_tier(transport_tier)
    intercity = dest.get("sample_intercity_transport_estimate", {}).get(transport_tier)
    local_daily = dest.get("sample_local_transport_estimate_per_day", {}).get(transport_tier)

    return {
        "tier": transport_tier,
        "name": tier_info.get("name"),
        "description": tier_info.get("description"),
        "sample_intercity_per_person": intercity,
        "sample_local_per_day": local_daily,
    }


def get_food_options(food_tier: str, num_travelers: int, trip_duration_days: int) -> Dict[str, Any]:
    """Retrieve food tier details and total expense estimate.

    Args:
        food_tier: Food tier ('economy', 'standard', 'comfort').
        num_travelers: Total count of travelers.
        trip_duration_days: Duration in days.
    Returns:
        Dictionary containing meal details, daily rate, and total group cost.
    """
    tier_info = get_food_tier(food_tier)
    daily_rate = float(tier_info.get("cost_per_person_per_day", 1200))
    total_cost = round(daily_rate * num_travelers * trip_duration_days, 2)

    return {
        "tier": food_tier,
        "name": tier_info.get("name"),
        "cost_per_person_per_day": daily_rate,
        "total_group_cost": total_cost,
        "sample_meals": tier_info.get("sample_meals", {}),
        "saving_tips": tier_info.get("saving_tips", []),
    }


def get_activity_options(destination_id: str, activity_tier: str) -> Dict[str, Any]:
    """Retrieve activities catalog and tier metadata for a destination.

    Args:
        destination_id: Identifier of the destination.
        activity_tier: Activity tier ('budget', 'standard', 'premium').
    Returns:
        Dictionary containing activities list and tier rates.
    """
    tier_info = get_activities_tier(activity_tier)
    activities = get_activities_for_destination(destination_id, activity_tier)

    return {
        "tier": activity_tier,
        "name": tier_info.get("name"),
        "cost_per_person_per_day": tier_info.get("cost_per_person_per_day"),
        "description": tier_info.get("description"),
        "activities": activities,
    }


def calculate_trip_budget_estimate(
    destination_id: str,
    num_travelers: int,
    trip_duration_days: int,
    hotel_tier: HotelTier = "standard",
    food_tier: FoodTier = "standard",
    transport_tier: TransportTier = "standard",
    activity_tier: ActivityTier = "standard",
    contingency_percent: float = 10.0
) -> Dict[str, Any]:
    """Calculate deterministic trip cost breakdown.

    All math is executed deterministically via Python functions.
    """
    dest = get_destination_by_id(destination_id)
    hotel = select_hotel_for_tier(destination_id, hotel_tier)
    costs = compute_trip_costs(
        destination=dest,
        hotel=hotel,
        num_travelers=num_travelers,
        trip_duration_days=trip_duration_days,
        transport_tier=transport_tier,
        food_tier=food_tier,
        activity_tier=activity_tier,
        contingency_percent=contingency_percent
    )
    return costs.model_dump()
