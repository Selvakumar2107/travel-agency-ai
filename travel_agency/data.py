"""Data loaders and dataset query access for dummy travel datasets."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_json(filename: str) -> Any:
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Required dataset file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_destinations() -> List[Dict[str, Any]]:
    """Load all destination records from destinations.json."""
    return _read_json("destinations.json")


def get_destination_by_id(destination_id: str) -> Dict[str, Any]:
    """Retrieve a single destination record by its ID."""
    destinations = load_destinations()
    for dest in destinations:
        if dest["id"].lower() == destination_id.lower():
            return dest
    raise ValueError(f"Destination with ID '{destination_id}' not found in dataset.")


def load_hotels() -> List[Dict[str, Any]]:
    """Load all hotel records from hotels.json."""
    return _read_json("hotels.json")


def get_hotels_for_destination(destination_id: str, tier: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve hotels for a destination, optionally filtered by tier."""
    all_hotels = load_hotels()
    filtered = [
        h for h in all_hotels
        if h["destination_id"].lower() == destination_id.lower()
    ]
    if tier:
        tier_lower = tier.lower()
        matched = [h for h in filtered if h["tier"].lower() == tier_lower]
        return matched if matched else filtered
    return filtered


def get_hotel_by_id(hotel_id: str) -> Dict[str, Any]:
    """Retrieve a specific hotel by ID."""
    all_hotels = load_hotels()
    for h in all_hotels:
        if h["id"].lower() == hotel_id.lower():
            return h
    raise ValueError(f"Hotel with ID '{hotel_id}' not found in dataset.")


def load_transport() -> Dict[str, Any]:
    """Load transport dataset from transport.json."""
    return _read_json("transport.json")


def get_transport_tier(tier: str) -> Dict[str, Any]:
    """Retrieve transport details for a given tier ('shared', 'standard', 'private')."""
    data = load_transport()
    tiers = data.get("tiers", {})
    tier_lower = tier.lower()
    if tier_lower not in tiers:
        raise ValueError(f"Invalid transport tier '{tier}'. Supported: {list(tiers.keys())}")
    return tiers[tier_lower]


def load_food() -> Dict[str, Any]:
    """Load food meal budget dataset from food.json."""
    return _read_json("food.json")


def get_food_tier(tier: str) -> Dict[str, Any]:
    """Retrieve food details for a given tier ('economy', 'standard', 'comfort')."""
    data = load_food()
    tiers = data.get("tiers", {})
    tier_lower = tier.lower()
    if tier_lower not in tiers:
        raise ValueError(f"Invalid food tier '{tier}'. Supported: {list(tiers.keys())}")
    return tiers[tier_lower]


def load_activities() -> Dict[str, Any]:
    """Load activities dataset from activities.json."""
    return _read_json("activities.json")


def get_activities_tier(tier: str) -> Dict[str, Any]:
    """Retrieve activity metadata for a tier ('budget', 'standard', 'premium')."""
    data = load_activities()
    tiers = data.get("tiers", {})
    tier_lower = tier.lower()
    if tier_lower not in tiers:
        raise ValueError(f"Invalid activity tier '{tier}'. Supported: {list(tiers.keys())}")
    return tiers[tier_lower]


def get_activities_for_destination(destination_id: str, tier: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve curated activities for a destination, optionally filtered by tier."""
    data = load_activities()
    catalog = data.get("destination_catalog", {})
    activities = catalog.get(destination_id.lower(), [])
    if tier:
        tier_lower = tier.lower()
        matched = [a for a in activities if a.get("tier", "").lower() == tier_lower]
        return matched if matched else activities
    return activities


def load_packages() -> List[Dict[str, Any]]:
    """Load curated travel package catalog from packages.json with safe fallback."""
    try:
        packages = _read_json("packages.json")
        if isinstance(packages, list) and len(packages) > 0:
            return packages
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        pass

    # Safe fallback if packages.json is missing or malformed
    destinations = load_destinations()
    fallback_pkgs: List[Dict[str, Any]] = []
    for d in destinations:
        dest_id = d["id"]
        dest_name = d["name"]
        for cat, tier, h_tier, t_mode, m_plan in [
            ("economy", "budget", "budget", "Train / Express Bus", "Economy Food Plan"),
            ("comfort", "standard", "standard", "Fast Express AC Train / Intercity Cab", "Standard Dining Plan (Breakfast Included)"),
            ("premium", "premium", "premium", "Private Chauffeur Car / Flight + Cab", "Comfort & Fine Dining Plan (All Meals)")
        ]:
            fallback_pkgs.append({
                "id": f"pkg-{dest_id}-{cat}",
                "destination_id": dest_id,
                "destination_name": dest_name,
                "name": f"{dest_name} {cat.title()} Experience",
                "category": cat,
                "duration_days": 3,
                "num_nights": 2,
                "tagline": f"Curated {cat} getaway to {dest_name}",
                "image_url": d.get("image_url", "https://images.unsplash.com/photo-1589182373726-e4f658ab50f0?auto=format&fit=crop&w=1000&q=80"),
                "hotel_id": f"{dest_id}-{h_tier}-1",
                "hotel_name": f"{dest_name} {cat.title()} Stay",
                "room_tier": h_tier,
                "room_type": f"{cat.title()} Room (Demo)",
                "transport_mode": t_mode,
                "transport_tier": "shared" if cat == "economy" else ("standard" if cat == "comfort" else "private"),
                "meal_plan": m_plan,
                "food_tier": cat,
                "included_activities": d.get("suggested_activities", ["City Highlights Tour"])[:2],
                "optional_activities": d.get("suggested_activities", ["Special Sightseeing"])[2:3],
                "inclusions": [f"Round-trip {t_mode}", f"2 Nights accommodation", "Daily meals per plan"],
                "exclusions": ["Personal expenses", "Optional activities"],
                "cancellation_policy": "Free demo cancellation up to 48 hours prior to check-in. Fully refundable.",
                "is_refundable": True,
                "is_demo_data": True,
            })
    return fallback_pkgs


def get_package_by_id(package_id: str) -> Dict[str, Any]:
    """Retrieve a specific package record by its ID."""
    packages = load_packages()
    for pkg in packages:
        if pkg["id"].lower() == package_id.lower():
            return pkg
    raise ValueError(f"Travel package with ID '{package_id}' not found in catalog.")


def get_packages_for_destination(destination_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve packages for a destination, optionally filtered by category ('economy', 'comfort', 'premium')."""
    all_packages = load_packages()
    filtered = [
        p for p in all_packages
        if p.get("destination_id", "").lower() == destination_id.lower()
    ]
    if category and category.lower() != "all":
        cat_lower = category.lower()
        filtered = [p for p in filtered if p.get("category", "").lower() == cat_lower]
    return filtered


__all__ = [
    "load_destinations",
    "get_destination_by_id",
    "load_hotels",
    "get_hotels_for_destination",
    "get_hotel_by_id",
    "load_transport",
    "get_transport_tier",
    "load_food",
    "get_food_tier",
    "load_activities",
    "get_activities_tier",
    "get_activities_for_destination",
    "load_packages",
    "get_package_by_id",
    "get_packages_for_destination",
]


