"""Hotel Service Layer for Fictional/Demo Hotel Inventory.

Provides search, filtering, room selection, and mock availability/inventory tracking
across 24 demonstration properties stored in data/hotels.json.
All inventory, rates, and ratings are explicitly labeled as DEMO DATA.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime

from travel_agency.booking_models import (
    HotelOffer,
    RoomOffer,
    HotelSearchQuery,
    HotelCategory,
    AccommodationType,
)
from travel_agency.data import load_destinations, load_hotels

logger = logging.getLogger(__name__)

HOTELS_FILE = Path(__file__).resolve().parent.parent / "data" / "hotels.json"

# In-memory mock inventory cache tracking demo room allocations
_mock_inventory_cache: Dict[str, int] = {}


class HotelService:
    """Service layer managing fictional hotel inventory, filtering, and mock availability."""

    def __init__(self):
        self._destinations = {d["id"]: d for d in load_destinations()}
        self._raw_hotels = load_hotels()
        self._init_inventory_cache()

    def _init_inventory_cache(self):
        """Initializes default mock inventory count (5 rooms per room type) if not set."""
        global _mock_inventory_cache
        if not _mock_inventory_cache:
            for h in self._raw_hotels:
                hotel_id = h.get("id")
                _mock_inventory_cache[f"{hotel_id}-rm-std"] = 5
                _mock_inventory_cache[f"{hotel_id}-rm-deluxe"] = 4
                _mock_inventory_cache[f"{hotel_id}-rm-suite"] = 3
                _mock_inventory_cache[f"{hotel_id}-rm-exec"] = 3
                _mock_inventory_cache[f"{hotel_id}-rm-presidential"] = 2

    def get_all_hotels(self) -> List[Dict[str, Any]]:
        return self._raw_hotels

    def get_hotel_by_id(self, hotel_id: str) -> Optional[Dict[str, Any]]:
        for h in self._raw_hotels:
            if h.get("id") == hotel_id:
                return h
        return None

    def get_room_types(self, hotel_id: str) -> List[RoomOffer]:
        hotel = self.get_hotel_by_id(hotel_id)
        if not hotel:
            return []

        tier = hotel.get("tier", "standard")
        base_price = float(hotel.get("price_per_night", 2500))

        if tier == "budget":
            return [
                RoomOffer(
                    room_id=f"{hotel_id}-rm-std",
                    room_name="Comfort Economy Room (Demo)",
                    bed_type="1 Queen Bed",
                    max_occupancy=2,
                    meal_inclusion="Room Only",
                    base_price_per_night=base_price,
                    cancellation_policy="Free demo cancellation up to 24 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Hot Water", "Free Demo Wi-Fi", "Daily Housekeeping"]
                ),
                RoomOffer(
                    room_id=f"{hotel_id}-rm-deluxe",
                    room_name="Standard Room with Breakfast (Demo)",
                    bed_type="1 Queen Bed or 2 Twin Beds",
                    max_occupancy=2,
                    meal_inclusion="Breakfast Included",
                    base_price_per_night=round(base_price * 1.15, 2),
                    cancellation_policy="Free demo cancellation up to 24 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Complimentary Breakfast", "Hot Water", "Free Demo Wi-Fi", "Scenic Window"]
                ),
            ]
        elif tier == "premium":
            return [
                RoomOffer(
                    room_id=f"{hotel_id}-rm-suite",
                    room_name="Royal Heritage Suite (Demo)",
                    bed_type="1 King Bed",
                    max_occupancy=2,
                    meal_inclusion="Breakfast Included",
                    base_price_per_night=base_price,
                    cancellation_policy="Free demo cancellation up to 48 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Gourmet Breakfast", "Private Balcony", "Luxury Spa Amenities", "Butler Service"]
                ),
                RoomOffer(
                    room_id=f"{hotel_id}-rm-presidential",
                    room_name="Presidential Villa (Demo)",
                    bed_type="1 King Bed + Lounge",
                    max_occupancy=4,
                    meal_inclusion="All Meals Included",
                    base_price_per_night=round(base_price * 1.35, 2),
                    cancellation_policy="Partially refundable demo rate",
                    is_refundable=True,
                    cancellation_fee_percent=10.0,
                    features=["All Meals Included", "Private Plunge Pool / Lawn", "Chauffeur Transfer", "VIP Lounge Access"]
                ),
            ]
        else:  # standard
            return [
                RoomOffer(
                    room_id=f"{hotel_id}-rm-deluxe",
                    room_name="Deluxe Garden Room (Demo)",
                    bed_type="1 King Bed or 2 Twin Beds",
                    max_occupancy=2,
                    meal_inclusion="Breakfast Included",
                    base_price_per_night=base_price,
                    cancellation_policy="Free demo cancellation up to 24 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Buffet Breakfast", "Air Conditioning", "Demo Wi-Fi", "Coffee Maker"]
                ),
                RoomOffer(
                    room_id=f"{hotel_id}-rm-exec",
                    room_name="Executive View Suite (Demo)",
                    bed_type="1 King Bed",
                    max_occupancy=3,
                    meal_inclusion="Breakfast & Dinner Included",
                    base_price_per_night=round(base_price * 1.25, 2),
                    cancellation_policy="Free demo cancellation up to 24 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Breakfast & Dinner Included", "Panoramic View", "Mini-bar", "Early Check-in"]
                ),
            ]

    def check_mock_availability(self, hotel_id: str, room_id: str, rooms_needed: int = 1) -> Tuple[bool, str, int]:
        """Checks current demo inventory count for room."""
        global _mock_inventory_cache
        available_count = _mock_inventory_cache.get(room_id, 3)
        if available_count >= rooms_needed:
            return True, f"Room available in demo inventory ({available_count} left).", available_count
        return False, f"Sold out in demo inventory ({available_count} remaining, requested {rooms_needed}).", available_count

    def update_mock_inventory(self, room_id: str, delta: int) -> bool:
        """Increments or decrements demo room count (e.g., -1 on booking, +1 on cancel)."""
        global _mock_inventory_cache
        curr = _mock_inventory_cache.get(room_id, 5)
        new_count = max(0, curr + delta)
        _mock_inventory_cache[room_id] = new_count
        return True

    def set_mock_inventory(self, room_id: str, count: int) -> bool:
        """Sets the exact mock inventory count for a room."""
        global _mock_inventory_cache
        _mock_inventory_cache[room_id] = max(0, count)
        return True

    def search_hotels(
        self,
        query: HotelSearchQuery,
        sort_by: str = "Recommended"
    ) -> List[HotelOffer]:
        """Searches and filters fictional hotels, calculating stay prices and demo metadata."""
        from travel_agency.hotel_provider import DESTINATION_PHOTO_CATALOG, DEFAULT_PHOTOS
        results: List[HotelOffer] = []
        dest_q = query.destination_id.strip().lower()

        for h in self._raw_hotels:
            h_dest = h.get("destination_id", "").lower()
            dest_obj = self._destinations.get(h_dest, {})
            dest_name = dest_obj.get("name", "").lower()

            if dest_q and dest_q != "all":
                if dest_q != h_dest and dest_q not in dest_name and dest_name not in dest_q:
                    continue

            # Category filter
            if query.category != HotelCategory.ALL:
                if h.get("tier", "").lower() != query.category.value.lower():
                    continue

            # Rating filter
            if query.min_rating > 0 and float(h.get("rating", 0.0)) < query.min_rating:
                continue

            rooms = self.get_room_types(h["id"])
            if not rooms:
                continue

            selected_room = rooms[0]
            price_per_night = selected_room.base_price_per_night

            # Max budget filter
            if query.max_budget_per_night and price_per_night > query.max_budget_per_night:
                continue

            # Amenities filter
            if query.required_amenities:
                h_amenities_lower = [a.lower() for a in h.get("amenities", [])]
                matches = all(
                    any(req.lower() in a for a in h_amenities_lower)
                    for req in query.required_amenities
                )
                if not matches:
                    continue

            num_nights = query.num_nights
            num_rooms = query.num_rooms
            room_subtotal = round(price_per_night * num_rooms * num_nights, 2)
            tax_amount = round(room_subtotal * 0.12, 2)
            service_fees = 0.0
            total_price = round(room_subtotal + tax_amount + service_fees, 2)

            # Accommodation type
            name_lower = h.get("name", "").lower()
            if "resort" in name_lower:
                acc_type = "Resort"
            elif "palace" in name_lower or "heritage" in name_lower:
                acc_type = "Heritage Palace"
            elif "homestay" in name_lower or "lodge" in name_lower:
                acc_type = "Homestay / Eco Lodge"
            elif "villa" in name_lower or "retreat" in name_lower:
                acc_type = "Boutique Villa"
            else:
                acc_type = "Hotel"

            if query.accommodation_type != AccommodationType.ALL:
                if acc_type != query.accommodation_type.value:
                    continue

            photos = DESTINATION_PHOTO_CATALOG.get(h_dest, DEFAULT_PHOTOS)
            review_count = 140 + (len(h.get("name", "")) * 9)

            offer = HotelOffer(
                id=h["id"],
                hotel_id=h["id"],
                name=h["name"],
                destination_id=h_dest,
                destination_name=dest_obj.get("name", h_dest.capitalize()),
                city=dest_obj.get("name", h_dest.capitalize()),
                address=f"{dest_obj.get('name', 'Central')}, {dest_obj.get('state', 'India')} (Demo Property)",
                category=h.get("tier", "standard"),
                accommodation_type=acc_type,
                rating=float(h.get("rating", 4.2)),
                review_count=review_count,
                photos=photos,
                amenities=h.get("amenities", []),
                description=h.get("description", "Demonstration hotel property."),
                rooms=rooms,
                selected_room=selected_room,
                num_nights=num_nights,
                num_rooms=num_rooms,
                price_per_night=price_per_night,
                room_subtotal=room_subtotal,
                tax_rate_percent=12.0,
                tax_amount=tax_amount,
                service_fees=service_fees,
                total_price=total_price,
                is_demo_data=True,
                is_available=True,
                supplier_name="SK Holidays Mock Inventory Engine",
            )
            results.append(offer)

        # Sorting
        if sort_by == "Price: Low to High":
            results.sort(key=lambda x: x.total_price)
        elif sort_by == "Price: High to Low":
            results.sort(key=lambda x: x.total_price, reverse=True)
        elif sort_by == "Guest Rating":
            results.sort(key=lambda x: x.rating, reverse=True)
        elif sort_by == "Best Value":
            results.sort(key=lambda x: (x.rating / max(1.0, x.price_per_night)), reverse=True)

        return results


# Global singleton instance
_hotel_service_instance: Optional[HotelService] = None


def get_hotel_service() -> HotelService:
    global _hotel_service_instance
    if _hotel_service_instance is None:
        _hotel_service_instance = HotelService()
    return _hotel_service_instance
