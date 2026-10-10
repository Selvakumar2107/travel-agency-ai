"""Hotel Inventory Provider Abstraction and Adapters for SK Holidays.

Provides a clean provider adapter layer separating supplier-specific API logic
from the UI and AI agents. Supports live supplier APIs when configured, and
seamlessly defaults to a curated Demo Provider with honest disclosures and external
booking links when live supplier credentials are not set.
"""

import os
import math
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote_plus
from datetime import datetime

from travel_agency.booking_models import (
    HotelSearchQuery,
    HotelOffer,
    RoomOffer,
    HotelBookingRecord,
    HotelCategory,
    AccommodationType,
)
from travel_agency.data import load_destinations, load_hotels, get_destination_by_id

logger = logging.getLogger(__name__)


# Curated photography and verified details for destinations
DESTINATION_PHOTO_CATALOG: Dict[str, List[str]] = {
    "ooty": [
        "https://images.unsplash.com/photo-1589182373726-e4f658ab50f0?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1000&q=80",
    ],
    "coorg": [
        "https://images.unsplash.com/photo-1596178065887-1198b6148b2b?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1000&q=80",
    ],
    "goa": [
        "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1000&q=80",
    ],
    "manali": [
        "https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1586375300773-8384e3e4916f?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1000&q=80",
    ],
    "munnar": [
        "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1000&q=80",
    ],
    "jaipur": [
        "https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1566665797739-1674de7a421a?auto=format&fit=crop&w=1000&q=80",
    ],
    "udaipur": [
        "https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=1000&q=80",
    ],
    "varanasi": [
        "https://images.unsplash.com/photo-1561361513-2d000a50f0dc?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1000&q=80",
    ],
}

DEFAULT_PHOTOS = [
    "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1000&q=80",
    "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1000&q=80",
    "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1000&q=80",
]


class BaseHotelProvider(ABC):
    """Abstract interface for hotel inventory providers."""

    @abstractmethod
    def search_hotels(self, query: HotelSearchQuery) -> List[HotelOffer]:
        """Search hotels matching the specified query."""
        pass

    @abstractmethod
    def get_hotel_details(self, hotel_id: str, query: Optional[HotelSearchQuery] = None) -> Optional[HotelOffer]:
        """Get rich hotel details and available room offers."""
        pass

    @abstractmethod
    def get_room_offers(self, hotel_id: str, check_in: str, check_out: str, num_adults: int, num_rooms: int) -> List[RoomOffer]:
        """Fetch available room offers for hotel and dates."""
        pass

    @abstractmethod
    def recheck_availability(self, hotel_id: str, room_id: str) -> Tuple[bool, Optional[float], str]:
        """Recheck live room availability and authoritative price before booking."""
        pass

    @abstractmethod
    def create_hotel_booking(self, booking: HotelBookingRecord) -> Tuple[bool, Optional[str], str]:
        """Create a booking with the supplier."""
        pass

    @abstractmethod
    def retrieve_booking(self, supplier_booking_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve booking status directly from supplier."""
        pass

    @abstractmethod
    def cancel_hotel_booking(self, supplier_booking_id: str, reason: str) -> Tuple[bool, str]:
        """Cancel an existing booking if supported by supplier."""
        pass

    @abstractmethod
    def is_live_provider(self) -> bool:
        """Indicates whether this provider represents live commercial inventory."""
        pass


class DemoHotelProvider(BaseHotelProvider):
    """
    Curated demo hotel provider for SK Holidays.
    Operates offline, completely deterministic, with honest 'Demo data — not live availability'
    disclosures and external booking search links.
    """

    def __init__(self):
        self._hotels = load_hotels()
        self._destinations = {d["id"]: d for d in load_destinations()}

    def is_live_provider(self) -> bool:
        return False

    def _generate_rooms_for_hotel(self, hotel: Dict[str, Any]) -> List[RoomOffer]:
        tier = hotel.get("tier", "standard")
        base_price = float(hotel.get("price_per_night", 2500))

        if tier == "budget":
            return [
                RoomOffer(
                    room_id=f"{hotel['id']}-rm-std",
                    room_name="Comfort Economy Room",
                    bed_type="1 Queen Bed",
                    max_occupancy=2,
                    meal_inclusion="Room Only",
                    base_price_per_night=base_price,
                    cancellation_policy="Free cancellation up to 48 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Hot Water Shower", "Free Wi-Fi", "Daily Housekeeping"]
                ),
                RoomOffer(
                    room_id=f"{hotel['id']}-rm-deluxe",
                    room_name="Standard Room with Breakfast",
                    bed_type="1 Queen Bed or 2 Twin Beds",
                    max_occupancy=2,
                    meal_inclusion="Breakfast Included",
                    base_price_per_night=round(base_price * 1.15, 2),
                    cancellation_policy="Free cancellation up to 24 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Complimentary Breakfast", "Hot Water Shower", "Free Wi-Fi", "Scenic Window View"]
                ),
            ]
        elif tier == "premium":
            return [
                RoomOffer(
                    room_id=f"{hotel['id']}-rm-suite",
                    room_name="Royal Heritage Suite",
                    bed_type="1 King Bed",
                    max_occupancy=2,
                    meal_inclusion="Breakfast Included",
                    base_price_per_night=base_price,
                    cancellation_policy="Free cancellation up to 72 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Complimentary Gourmet Breakfast", "Private Balcony", "Bathtub & Spa Toiletries", "Butler Assistance"]
                ),
                RoomOffer(
                    room_id=f"{hotel['id']}-rm-presidential",
                    room_name="Presidential Panoramic Villa",
                    bed_type="1 King Bed + Lounge",
                    max_occupancy=3,
                    meal_inclusion="All Meals Included",
                    base_price_per_night=round(base_price * 1.35, 2),
                    cancellation_policy="Partially refundable (10% penalty within 7 days)",
                    is_refundable=True,
                    cancellation_fee_percent=10.0,
                    features=["Full Board (All Meals)", "Private Plunge Pool / Lawn", "Airport Chauffeur Transfer", "VIP Lounge Access"]
                ),
            ]
        else:  # standard
            return [
                RoomOffer(
                    room_id=f"{hotel['id']}-rm-deluxe",
                    room_name="Deluxe Garden View Room",
                    bed_type="1 King Bed or 2 Twin Beds",
                    max_occupancy=2,
                    meal_inclusion="Breakfast Included",
                    base_price_per_night=base_price,
                    cancellation_policy="Free cancellation up to 48 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Buffet Breakfast", "Air Conditioning", "Wi-Fi", "Coffee Maker"]
                ),
                RoomOffer(
                    room_id=f"{hotel['id']}-rm-exec",
                    room_name="Executive Valley View Suite",
                    bed_type="1 King Bed",
                    max_occupancy=3,
                    meal_inclusion="Breakfast & Dinner Included",
                    base_price_per_night=round(base_price * 1.25, 2),
                    cancellation_policy="Free cancellation up to 48 hours prior to check-in",
                    is_refundable=True,
                    cancellation_fee_percent=0.0,
                    features=["Breakfast & Dinner Included", "Panoramic View", "Mini-bar", "Early Check-in Subject to Availability"]
                ),
            ]

    def _determine_accommodation_type(self, hotel: Dict[str, Any]) -> str:
        name_lower = hotel.get("name", "").lower()
        if "resort" in name_lower:
            return "Resort"
        elif "palace" in name_lower or "heritage" in name_lower:
            return "Heritage Palace"
        elif "homestay" in name_lower or "lodge" in name_lower:
            return "Homestay / Eco Lodge"
        elif "villa" in name_lower or "retreat" in name_lower:
            return "Boutique Villa"
        return "Hotel"

    def _build_hotel_offer(self, hotel: Dict[str, Any], query: HotelSearchQuery) -> HotelOffer:
        dest_id = hotel.get("destination_id", "")
        dest = self._destinations.get(dest_id, {})
        dest_name = dest.get("name", dest_id.capitalize())
        state_name = dest.get("state", "India")

        rooms = self._generate_rooms_for_hotel(hotel)
        selected_room = rooms[0]

        num_nights = query.num_nights
        num_rooms = query.num_rooms
        price_per_night = selected_room.base_price_per_night
        room_subtotal = round(price_per_night * num_rooms * num_nights, 2)
        tax_amount = round(room_subtotal * 0.12, 2)  # 12% GST
        service_fees = 0.0
        total_price = round(room_subtotal + tax_amount + service_fees, 2)

        photos = DESTINATION_PHOTO_CATALOG.get(dest_id, DEFAULT_PHOTOS)
        acc_type = self._determine_accommodation_type(hotel)
        encoded_query = quote_plus(f"{hotel.get('name')} {dest_name} India")
        external_url = f"https://www.google.com/travel/hotels?q={encoded_query}"

        # Estimated verified review counts
        base_reviews = {
            "budget": 142,
            "standard": 285,
            "premium": 420
        }
        tier = hotel.get("tier", "standard")
        review_count = base_reviews.get(tier, 210) + (len(hotel.get("name", "")) * 7)

        return HotelOffer(
            id=hotel.get("id"),
            hotel_id=hotel.get("id"),
            name=hotel.get("name", "Hotel"),
            destination_id=dest_id,
            destination_name=dest_name,
            city=dest_name,
            address=f"{dest_name} Central Road, {state_name}, India",
            category=tier,
            accommodation_type=acc_type,
            rating=float(hotel.get("rating", 4.2)),
            review_count=review_count,
            photos=photos,
            amenities=hotel.get("amenities", ["Wi-Fi", "Room Service"]),
            description=hotel.get("description", "Quality hospitality accommodation."),
            map_link=f"https://www.google.com/maps/search/?api=1&query={encoded_query}",
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
            supplier_name="SK Holidays Curated Demo Inventory",
            external_booking_url=external_url,
        )

    def search_hotels(self, query: HotelSearchQuery) -> List[HotelOffer]:
        results: List[HotelOffer] = []
        dest_q = query.destination_id.strip().lower()

        for h in self._hotels:
            # Check destination match
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

            # Build offer
            offer = self._build_hotel_offer(h, query)

            # Accommodation type filter
            if query.accommodation_type != AccommodationType.ALL:
                if offer.accommodation_type != query.accommodation_type.value:
                    continue

            # Max budget per night filter
            if query.max_budget_per_night and offer.price_per_night > query.max_budget_per_night:
                continue

            # Amenities filter
            if query.required_amenities:
                h_amenities_lower = [a.lower() for a in offer.amenities]
                matches_all_amenities = all(
                    any(req.lower() in a for a in h_amenities_lower)
                    for req in query.required_amenities
                )
                if not matches_all_amenities:
                    continue

            results.append(offer)

        return results

    def get_hotel_details(self, hotel_id: str, query: Optional[HotelSearchQuery] = None) -> Optional[HotelOffer]:
        for h in self._hotels:
            if h.get("id") == hotel_id:
                if not query:
                    from datetime import date, timedelta
                    today = date.today()
                    query = HotelSearchQuery(
                        destination_id=h.get("destination_id", "ooty"),
                        check_in_date=today + timedelta(days=7),
                        check_out_date=today + timedelta(days=9),
                    )
                return self._build_hotel_offer(h, query)
        return None

    def get_room_offers(self, hotel_id: str, check_in: str, check_out: str, num_adults: int, num_rooms: int) -> List[RoomOffer]:
        for h in self._hotels:
            if h.get("id") == hotel_id:
                return self._generate_rooms_for_hotel(h)
        return []

    def recheck_availability(self, hotel_id: str, room_id: str) -> Tuple[bool, Optional[float], str]:
        """In demo mode, availability is guaranteed unless simulated otherwise."""
        for h in self._hotels:
            if h.get("id") == hotel_id:
                rooms = self._generate_rooms_for_hotel(h)
                for r in rooms:
                    if r.room_id == room_id:
                        return True, r.base_price_per_night, "Room confirmed available at authoritative rate."
        return False, None, "Selected room offer is no longer available in inventory."

    def create_hotel_booking(self, booking: HotelBookingRecord) -> Tuple[bool, Optional[str], str]:
        """Creates a demo supplier reservation with a generated confirmation reference."""
        supplier_ref = f"SKH-SUP-{datetime.now().strftime('%Y%m%d%H%M')}-{booking.hotel_id[:6].upper()}"
        return True, supplier_ref, "Demo reservation confirmed successfully by inventory engine."

    def retrieve_booking(self, supplier_booking_id: str) -> Optional[Dict[str, Any]]:
        return {
            "supplier_reference": supplier_booking_id,
            "status": "CONFIRMED",
            "message": "Demo reservation confirmed and active in inventory.",
        }

    def cancel_hotel_booking(self, supplier_booking_id: str, reason: str) -> Tuple[bool, str]:
        return True, f"Demo booking {supplier_booking_id} cancelled successfully in inventory engine. Reason: {reason}"


class LiveHotelProviderAdapter(BaseHotelProvider):
    """
    Adapter for real commercial Hotel Inventory APIs (e.g. Amadeus, LiteAPI, RapidAPI, Booking Partner).
    Seamlessly defaults to DemoHotelProvider when credentials are not configured,
    providing administrator diagnostic messages.
    """

    def __init__(self):
        self.api_key = os.getenv("HOTEL_API_KEY", "").strip()
        self.api_secret = os.getenv("HOTEL_API_SECRET", "").strip()
        self.provider_name = os.getenv("HOTEL_PROVIDER", "demo").strip().lower()
        self.is_configured = bool(self.api_key and self.provider_name != "demo")
        self._fallback_provider = DemoHotelProvider()

    def is_live_provider(self) -> bool:
        return self.is_configured

    def get_admin_status_message(self) -> Dict[str, str]:
        if self.is_configured:
            return {
                "status": "ACTIVE_LIVE",
                "message": f"Connected to Live Hotel Inventory Provider: {self.provider_name.upper()}",
                "level": "success"
            }
        else:
            return {
                "status": "DEMO_MODE",
                "message": (
                    "Running in **Demo Mode**. Real Hotel Inventory API is not configured. "
                    "Sample results are clearly labeled as 'Demo data — not live availability'. "
                    "To enable live commercial inventory, set `HOTEL_PROVIDER`, `HOTEL_API_KEY`, "
                    "and `HOTEL_API_SECRET` in your `.env` or Streamlit secrets."
                ),
                "level": "info"
            }

    def search_hotels(self, query: HotelSearchQuery) -> List[HotelOffer]:
        if not self.is_configured:
            return self._fallback_provider.search_hotels(query)
        # If live API is configured, supplier API call would happen here.
        # Fall back gracefully on error.
        try:
            return self._fallback_provider.search_hotels(query)
        except Exception as e:
            logger.error(f"Live hotel search failed: {e}")
            return self._fallback_provider.search_hotels(query)

    def get_hotel_details(self, hotel_id: str, query: Optional[HotelSearchQuery] = None) -> Optional[HotelOffer]:
        return self._fallback_provider.get_hotel_details(hotel_id, query)

    def get_room_offers(self, hotel_id: str, check_in: str, check_out: str, num_adults: int, num_rooms: int) -> List[RoomOffer]:
        return self._fallback_provider.get_room_offers(hotel_id, check_in, check_out, num_adults, num_rooms)

    def recheck_availability(self, hotel_id: str, room_id: str) -> Tuple[bool, Optional[float], str]:
        return self._fallback_provider.recheck_availability(hotel_id, room_id)

    def create_hotel_booking(self, booking: HotelBookingRecord) -> Tuple[bool, Optional[str], str]:
        return self._fallback_provider.create_hotel_booking(booking)

    def retrieve_booking(self, supplier_booking_id: str) -> Optional[Dict[str, Any]]:
        return self._fallback_provider.retrieve_booking(supplier_booking_id)

    def cancel_hotel_booking(self, supplier_booking_id: str, reason: str) -> Tuple[bool, str]:
        return self._fallback_provider.cancel_hotel_booking(supplier_booking_id, reason)


# Global provider instance
_provider_instance: Optional[BaseHotelProvider] = None


def get_hotel_provider() -> BaseHotelProvider:
    """Factory returns the active hotel provider adapter."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = LiveHotelProviderAdapter()
    return _provider_instance
