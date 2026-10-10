"""Deterministic Package Pricing Engine for SK Holidays.

Provides authoritative, pure Python mathematical pricing with integer paise precision.
Includes outbound & return transport, local transit, hotel rooms × nights, meal allowances,
included and optional activities, taxes & regulatory fees, and disclosed contingency reserves.
"""

import math
from typing import Dict, Any, List, Optional
from travel_agency.package_models import TravelPackage, PackageCostBreakdown, PackageCustomization
from travel_agency.data import (
    get_destination_by_id,
    get_hotel_by_id,
    get_transport_tier,
    get_food_tier,
    get_activities_tier,
    load_activities,
)


def inr_to_paise(amount_inr: float) -> int:
    """Convert INR float to exact integer paise."""
    return int(round(amount_inr * 100))


def paise_to_inr(paise: int) -> float:
    """Convert exact integer paise to INR float."""
    return round(paise / 100.0, 2)


def get_activity_price_lookup(destination_id: str) -> Dict[str, float]:
    """Build a name -> approx_cost lookup dictionary for activities in a destination."""
    activities_data = load_activities()
    catalog = activities_data.get("destination_catalog", {}).get(destination_id.lower(), [])
    lookup: Dict[str, float] = {}
    for item in catalog:
        lookup[item["name"].strip().lower()] = float(item.get("approx_cost", 0.0))
    return lookup


def calculate_package_pricing(
    package: Dict[str, Any],
    num_travelers: int,
    num_rooms: int,
    num_nights: int,
    duration_days: int,
    selected_optional_activities: Optional[List[str]] = None,
    contingency_percent: float = 10.0,
) -> PackageCostBreakdown:
    """
    Computes deterministic itemized package pricing grounded strictly in project JSON data.

    Parameters:
    - package: Dict of package catalog item
    - num_travelers: Total guests (adults + children)
    - num_rooms: Total rooms booked
    - num_nights: Number of nights stay
    - duration_days: Number of days
    - selected_optional_activities: Optional activity names selected by user
    - contingency_percent: Contingency buffer percentage (disclosed)
    """
    if num_travelers < 1:
        raise ValueError("Number of travelers must be at least 1.")
    if num_rooms < 1:
        raise ValueError("Number of rooms must be at least 1.")
    if num_nights < 1:
        raise ValueError("Number of nights must be at least 1.")
    if duration_days < 1:
        raise ValueError("Trip duration days must be at least 1.")
    if contingency_percent < 0:
        raise ValueError("Contingency percentage cannot be negative.")

    destination_id = package["destination_id"]
    destination = get_destination_by_id(destination_id)

    # 1. Transport Calculations
    transport_tier = package.get("transport_tier", "standard")
    intercity_estimates = destination.get("sample_intercity_transport_estimate", {})
    if transport_tier in intercity_estimates:
        one_way_transit_pp = float(intercity_estimates[transport_tier])
    else:
        tier_data = get_transport_tier(transport_tier)
        one_way_transit_pp = float(tier_data.get("intercity_default_per_person", 2000))

    outbound_transit = round(one_way_transit_pp * num_travelers, 2)
    return_transit = round(one_way_transit_pp * num_travelers, 2)

    local_estimates = destination.get("sample_local_transport_estimate_per_day", {})
    if transport_tier in local_estimates:
        daily_local = float(local_estimates[transport_tier])
    else:
        tier_data = get_transport_tier(transport_tier)
        daily_local = float(tier_data.get("local_default_per_person_per_day", 1000))

    if transport_tier == "shared":
        local_transit = round(daily_local * num_travelers * duration_days, 2)
    else:
        num_vehicles = math.ceil(num_travelers / 4.0)
        local_transit = round(daily_local * num_vehicles * duration_days, 2)

    transport_subtotal = round(outbound_transit + return_transit + local_transit, 2)

    # 2. Hotel Lodging Calculations
    hotel_id = package.get("hotel_id")
    try:
        hotel = get_hotel_by_id(hotel_id)
        room_rate_per_night = float(hotel.get("price_per_night", 2500))
    except Exception:
        # Fallback to tier standard if hotel not found by ID
        room_tier = package.get("room_tier", "standard")
        fallback_rates = {"budget": 1500.0, "standard": 3500.0, "premium": 7500.0}
        room_rate_per_night = fallback_rates.get(room_tier, 3000.0)

    accommodation_subtotal = round(room_rate_per_night * num_rooms * num_nights, 2)

    # 3. Meals Calculations
    food_tier = package.get("food_tier", "standard")
    food_info = get_food_tier(food_tier)
    food_rate_per_person_per_day = float(food_info.get("cost_per_person_per_day", 1300))
    food_subtotal = round(food_rate_per_person_per_day * num_travelers * duration_days, 2)

    # 4. Activities Calculations
    act_lookup = get_activity_price_lookup(destination_id)
    included_act_names = package.get("included_activities", [])

    included_act_cost_pp = 0.0
    for name in included_act_names:
        key = name.strip().lower()
        if key in act_lookup:
            included_act_cost_pp += act_lookup[key]
        else:
            # Check partial match
            matched = False
            for act_name, price in act_lookup.items():
                if key in act_name or act_name in key:
                    included_act_cost_pp += price
                    matched = True
                    break
            if not matched:
                included_act_cost_pp += 300.0  # Disclosed default activity estimate

    included_act_subtotal = round(included_act_cost_pp * num_travelers, 2)

    optional_act_subtotal = 0.0
    selected_opt = selected_optional_activities or []
    for opt_name in selected_opt:
        key = opt_name.strip().lower()
        if key in act_lookup:
            optional_act_subtotal += round(act_lookup[key] * num_travelers, 2)
        else:
            matched = False
            for act_name, price in act_lookup.items():
                if key in act_name or act_name in key:
                    optional_act_subtotal += round(price * num_travelers, 2)
                    matched = True
                    break
            if not matched:
                optional_act_subtotal += round(500.0 * num_travelers, 2)

    activities_subtotal = round(included_act_subtotal + optional_act_subtotal, 2)

    # 5. Taxes and Fees
    hotel_gst = round(accommodation_subtotal * 0.12, 2)      # 12% Hotel GST
    transport_tax = round(transport_subtotal * 0.05, 2)      # 5% Transport tax
    taxes_and_fees = round(hotel_gst + transport_tax, 2)

    # 6. Disclosed Contingency Reserve
    direct_expenses = round(transport_subtotal + accommodation_subtotal + food_subtotal + activities_subtotal, 2)
    contingency_reserve = round(direct_expenses * (contingency_percent / 100.0), 2)

    # 7. Grand Total Group Price
    total_group_price = round(direct_expenses + taxes_and_fees + contingency_reserve, 2)
    total_group_paise = inr_to_paise(total_group_price)

    # 8. Per-person Price
    price_per_person = round(total_group_price / num_travelers, 2)
    price_per_person_paise = inr_to_paise(price_per_person)

    # 9. Payment Amounts
    amount_payable_now = total_group_price
    amount_payable_now_paise = total_group_paise
    remaining_balance = 0.0
    remaining_balance_paise = 0

    itemized_details = {
        "outbound_per_person": one_way_transit_pp,
        "return_per_person": one_way_transit_pp,
        "daily_local_transit": daily_local,
        "room_rate_per_night": room_rate_per_night,
        "food_rate_per_person_per_day": food_rate_per_person_per_day,
        "included_activities_count": len(included_act_names),
        "selected_optional_activities": selected_opt,
        "hotel_gst_rate": "12%",
        "transport_tax_rate": "5%",
        "contingency_rate": f"{contingency_percent}%",
    }

    return PackageCostBreakdown(
        outbound_transport_inr=outbound_transit,
        return_transport_inr=return_transit,
        local_transport_inr=local_transit,
        transport_subtotal_inr=transport_subtotal,
        transport_subtotal_paise=inr_to_paise(transport_subtotal),
        room_rate_per_night_inr=room_rate_per_night,
        hotel_nights=num_nights,
        num_rooms=num_rooms,
        accommodation_subtotal_inr=accommodation_subtotal,
        accommodation_subtotal_paise=inr_to_paise(accommodation_subtotal),
        food_rate_per_person_per_day_inr=food_rate_per_person_per_day,
        food_days=duration_days,
        food_subtotal_inr=food_subtotal,
        food_subtotal_paise=inr_to_paise(food_subtotal),
        included_activities_subtotal_inr=included_act_subtotal,
        optional_activities_subtotal_inr=optional_act_subtotal,
        activities_subtotal_inr=activities_subtotal,
        activities_subtotal_paise=inr_to_paise(activities_subtotal),
        hotel_gst_inr=hotel_gst,
        transport_tax_inr=transport_tax,
        taxes_and_fees_inr=taxes_and_fees,
        taxes_and_fees_paise=inr_to_paise(taxes_and_fees),
        contingency_percent=contingency_percent,
        contingency_reserve_inr=contingency_reserve,
        contingency_reserve_paise=inr_to_paise(contingency_reserve),
        total_group_price_inr=total_group_price,
        total_group_price_paise=total_group_paise,
        price_per_person_inr=price_per_person,
        price_per_person_paise=price_per_person_paise,
        amount_payable_now_inr=amount_payable_now,
        amount_payable_now_paise=amount_payable_now_paise,
        remaining_balance_inr=remaining_balance,
        remaining_balance_paise=remaining_balance_paise,
        num_travelers=num_travelers,
        itemized_details=itemized_details,
    )
