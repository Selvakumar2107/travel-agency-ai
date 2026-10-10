"""Data models and schemas for Hotel Discovery, Booking, and Payment state machine."""

from datetime import date, datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class BookingStatus(str, Enum):
    DRAFT = "DRAFT"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    DEMO_PAID = "DEMO_PAID"
    CONFIRMED_DEMO = "CONFIRMED_DEMO"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CANCELLED_DEMO = "CANCELLED_DEMO"
    # Aliases
    AVAILABILITY_CHECKED = "DRAFT"
    PAYMENT_VERIFIED = "DEMO_PAID"
    BOOKING_PENDING = "PAYMENT_PENDING"
    CONFIRMED = "CONFIRMED_DEMO"
    FAILED = "PAYMENT_FAILED"
    CANCELLATION_PENDING = "CANCELLED_DEMO"
    CANCELLED = "CANCELLED_DEMO"
    REFUND_PENDING = "CANCELLED_DEMO"
    REFUNDED = "CANCELLED_DEMO"
    REQUIRES_SUPPORT = "PAYMENT_FAILED"

    @classmethod
    def _missing_(cls, value):
        val_str = str(value).upper()
        mapping = {
            "CONFIRMED": cls.CONFIRMED_DEMO,
            "CANCELLED": cls.CANCELLED_DEMO,
            "FAILED": cls.PAYMENT_FAILED,
            "REFUNDED": cls.CANCELLED_DEMO,
            "REFUND_PENDING": cls.CANCELLED_DEMO,
            "CANCELLATION_PENDING": cls.CANCELLED_DEMO,
            "BOOKING_PENDING": cls.PAYMENT_PENDING,
            "PAYMENT_VERIFIED": cls.DEMO_PAID,
            "AVAILABILITY_CHECKED": cls.DRAFT,
            "REQUIRES_SUPPORT": cls.PAYMENT_FAILED,
        }
        if val_str in mapping:
            return mapping[val_str]
        for member in cls:
            if member.value.upper() == val_str:
                return member
        return None


class PaymentStatus(str, Enum):
    SIMULATED_PENDING = "SIMULATED_PENDING"
    SIMULATED_SUCCESS = "SIMULATED_SUCCESS"
    SIMULATED_FAILED = "SIMULATED_FAILED"
    SIMULATED_TIMEOUT = "SIMULATED_TIMEOUT"
    # Aliases
    CREATED = "SIMULATED_PENDING"
    PENDING = "SIMULATED_PENDING"
    AUTHORIZED = "SIMULATED_SUCCESS"
    CAPTURED = "SIMULATED_SUCCESS"
    FAILED = "SIMULATED_FAILED"
    REFUND_PENDING = "SIMULATED_FAILED"
    REFUNDED = "SIMULATED_SUCCESS"

    @classmethod
    def _missing_(cls, value):
        val_str = str(value).upper()
        mapping = {
            "CREATED": cls.SIMULATED_PENDING,
            "PENDING": cls.SIMULATED_PENDING,
            "AUTHORIZED": cls.SIMULATED_SUCCESS,
            "CAPTURED": cls.SIMULATED_SUCCESS,
            "FAILED": cls.SIMULATED_FAILED,
            "REFUND_PENDING": cls.SIMULATED_FAILED,
            "REFUNDED": cls.SIMULATED_SUCCESS,
        }
        if val_str in mapping:
            return mapping[val_str]
        for member in cls:
            if member.value.upper() == val_str:
                return member
        return None


class HotelCategory(str, Enum):
    ALL = "all"
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"
    LUXURY = "luxury"


class AccommodationType(str, Enum):
    ALL = "all"
    HOTEL = "Hotel"
    RESORT = "Resort"
    HERITAGE = "Heritage Palace"
    BOUTIQUE = "Boutique Villa"
    HOMESTAY = "Homestay / Eco Lodge"


class HotelSearchQuery(BaseModel):
    """User input search criteria for hotel discovery."""
    destination_id: str = Field(..., description="Destination identifier or city name")
    check_in_date: date = Field(..., description="Check-in date")
    check_out_date: date = Field(..., description="Check-out date")
    num_rooms: int = Field(default=1, ge=1, description="Number of rooms required")
    num_adults: int = Field(default=2, ge=1, description="Number of adults")
    num_children: int = Field(default=0, ge=0, description="Number of children")
    max_budget_per_night: Optional[float] = Field(default=None, ge=500.0, description="Max budget per night in INR")
    category: HotelCategory = Field(default=HotelCategory.ALL, description="Hotel tier category")
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Minimum guest rating out of 5")
    required_amenities: List[str] = Field(default_factory=list, description="Required amenities")
    accommodation_type: AccommodationType = Field(default=AccommodationType.ALL, description="Preferred accommodation type")
    travel_style: Optional[str] = Field(default="family", description="Traveler style: solo, couple, family, group")
    special_requirements: Optional[str] = Field(default=None, description="Dietary, accessibility, or specific preferences")

    @field_validator("check_out_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        check_in = info.data.get("check_in_date")
        if check_in and v <= check_in:
            raise ValueError("Check-out date must be strictly later than check-in date.")
        return v

    @property
    def num_nights(self) -> int:
        return max(1, (self.check_out_date - self.check_in_date).days)


class RoomOffer(BaseModel):
    """Specific room type and rate plan offered by a hotel."""
    room_id: str
    room_name: str
    bed_type: str = "1 King Bed or 2 Twin Beds"
    max_occupancy: int = 2
    meal_inclusion: str = "Room Only"  # e.g., "Breakfast Included", "Room Only", "All Meals Included"
    base_price_per_night: float
    cancellation_policy: str = "Free cancellation up to 48 hours prior to check-in"
    is_refundable: bool = True
    cancellation_fee_percent: float = 0.0
    features: List[str] = Field(default_factory=list)


class HotelOffer(BaseModel):
    """Complete hotel listing with authoritative supplier facts and rate breakdown."""
    id: str
    hotel_id: str
    name: str
    destination_id: str
    destination_name: str
    city: str
    address: str
    category: str  # budget, standard, premium, luxury
    accommodation_type: str
    rating: float = Field(ge=0.0, le=5.0)
    review_count: int = Field(ge=0)
    photos: List[str] = Field(default_factory=list)
    amenities: List[str] = Field(default_factory=list)
    description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    map_link: Optional[str] = None
    rooms: List[RoomOffer] = Field(default_factory=list)
    selected_room: Optional[RoomOffer] = None

    # Pricing calculation for stay
    num_nights: int = 1
    num_rooms: int = 1
    price_per_night: float
    room_subtotal: float
    tax_rate_percent: float = 12.0  # e.g. 12% GST
    tax_amount: float
    service_fees: float = 0.0
    total_price: float

    # Authority & supplier metadata
    is_demo_data: bool = True
    is_available: bool = True
    supplier_name: str = "SK Holidays Inventory Engine"
    external_booking_url: Optional[str] = None
    last_updated: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M UTC"))


class GuestInformation(BaseModel):
    """Guest contact and travel party information."""
    lead_guest_name: str = Field(..., min_length=2, description="Full name of lead guest")
    email: str = Field(..., min_length=5, description="Primary contact email")
    phone: str = Field(..., min_length=7, description="Phone number with country code")
    additional_guests: List[str] = Field(default_factory=list)
    special_requests: Optional[str] = None
    accepted_terms: bool = Field(default=False)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Please provide a valid email address.")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 8:
            raise ValueError("Please provide a valid contact number (at least 8 digits).")
        return v

    @field_validator("accepted_terms")
    @classmethod
    def validate_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the booking and cancellation terms to continue.")
        return v


class PaymentOrder(BaseModel):
    """Payment order representation across gateways (Razorpay / Demo)."""
    order_id: str
    booking_reference: str
    currency: str = "INR"
    amount_inr: float
    amount_in_paise: int
    gateway: str = "razorpay"
    payment_id: Optional[str] = None
    signature: Optional[str] = None
    status: PaymentStatus = PaymentStatus.CREATED
    error_message: Optional[str] = None
    refund_id: Optional[str] = None
    refund_amount_inr: Optional[float] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class HotelBookingRecord(BaseModel):
    """Persistent booking record with authoritative state history."""
    booking_reference: str
    supplier_booking_reference: Optional[str] = None
    hotel_id: str
    hotel_name: str
    hotel_address: str
    room_id: str
    room_name: str
    destination_name: str
    check_in: str
    check_out: str
    num_nights: int
    num_rooms: int
    num_adults: int
    num_children: int = 0
    meal_inclusion: str
    cancellation_policy: str

    guest_info: GuestInformation
    pricing: Dict[str, float]  # base, room_subtotal, taxes, fees, total_amount

    booking_status: BookingStatus = BookingStatus.DRAFT
    payment_status: PaymentStatus = PaymentStatus.PENDING

    payment_order_id: Optional[str] = None
    payment_id: Optional[str] = None
    payment_gateway: str = "razorpay"

    is_demo: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)


class AIHotelRecommendationGroup(BaseModel):
    """Structured output for the AI hotel recommendation agent."""
    best_budget_match: Optional[HotelOffer] = None
    best_budget_rationale: str = ""
    best_value: Optional[HotelOffer] = None
    best_value_rationale: str = ""
    premium_experience: Optional[HotelOffer] = None
    premium_experience_rationale: str = ""
    general_advice: str = ""
    disclaimer: str = "AI-generated recommendations. All prices, taxes, and policies are strictly grounded in authoritative supplier facts."
