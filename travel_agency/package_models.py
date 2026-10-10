"""Pydantic Models and Data Schemas for SK Holidays Travel Packages.

Supports 3 package categories (Economy, Comfort, Premium), deterministic integer-paise
pricing, guest details validation, multi-agent AI reviews, and booking records.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Literal, Tuple
from pydantic import BaseModel, Field, field_validator

from travel_agency.booking_models import (
    BookingStatus,
    PaymentStatus,
    GuestInformation,
)

PackageCategory = Literal["economy", "comfort", "premium"]


class TravelPackage(BaseModel):
    """Authoritative representation of a curated travel package catalog item."""
    id: str
    destination_id: str
    destination_name: str
    name: str
    category: PackageCategory
    duration_days: int = Field(ge=1, description="Number of days")
    num_nights: int = Field(ge=1, description="Number of nights")
    tagline: str
    image_url: str
    hotel_id: str
    hotel_name: str
    room_tier: str  # budget, standard, premium
    room_type: str
    transport_mode: str
    transport_tier: str  # shared, standard, private
    meal_plan: str
    food_tier: str  # economy, standard, comfort
    included_activities: List[str] = Field(default_factory=list)
    optional_activities: List[str] = Field(default_factory=list)
    inclusions: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    cancellation_policy: str = "Free demo cancellation up to 48 hours prior to check-in. Fully refundable."
    is_refundable: bool = True
    is_demo_data: bool = True
    # Baseline pricing estimates (for 1 adult, baseline duration)
    baseline_price_per_person: float = 0.0
    baseline_total_price: float = 0.0


class PackageSearchQuery(BaseModel):
    """User search and filtering parameters for packages."""
    origin: str = Field(default="Bangalore", description="Departure city")
    destination_id: Optional[str] = Field(default=None, description="Optional destination filter")
    departure_date: date = Field(..., description="Trip start date")
    return_date: date = Field(..., description="Trip return date")
    category: Optional[str] = Field(default="all", description="economy, comfort, premium, or all")
    num_adults: int = Field(default=2, ge=1, description="Number of adult travelers")
    num_children: int = Field(default=0, ge=0, description="Number of child travelers")
    num_rooms: int = Field(default=1, ge=1, description="Number of hotel rooms")
    max_budget: Optional[float] = Field(default=None, ge=3000.0, description="Maximum total budget in INR")
    meal_preference: Optional[str] = Field(default=None, description="Dietary preference")
    transport_preference: Optional[str] = Field(default=None, description="Transport preference")

    @field_validator("return_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        departure = info.data.get("departure_date")
        if departure and v <= departure:
            raise ValueError("Return date must be strictly later than departure date.")
        return v

    @property
    def total_travelers(self) -> int:
        return self.num_adults + self.num_children

    @property
    def num_nights(self) -> int:
        return max(1, (self.return_date - self.departure_date).days)

    @property
    def duration_days(self) -> int:
        return self.num_nights + 1


class PackageCustomization(BaseModel):
    """Customization inputs selected by the user for a specific package."""
    package_id: str
    origin: str = "Bangalore"
    destination_id: str
    departure_date: date
    return_date: date
    num_adults: int = Field(default=2, ge=1)
    num_children: int = Field(default=0, ge=0)
    num_rooms: int = Field(default=1, ge=1)
    room_occupancy_per_room: int = Field(default=2, ge=1, le=4)
    selected_optional_activities: List[str] = Field(default_factory=list)
    meal_preference: str = "No Dietary Restriction"
    allergies: List[str] = Field(default_factory=list)
    transport_preference: Optional[str] = None
    contingency_percent: float = Field(default=10.0, ge=0.0)
    max_budget: Optional[float] = Field(default=None, ge=3000.0)

    @field_validator("return_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        departure = info.data.get("departure_date")
        if departure and v <= departure:
            raise ValueError("Return date must be strictly later than departure date.")
        return v

    @field_validator("max_budget", mode="before")
    @classmethod
    def validate_max_budget(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        val = float(v)
        if val < 3000.0:
            raise ValueError("Minimum accepted trip budget is ₹3,000 INR.")
        return val

    @property
    def total_travelers(self) -> int:
        return self.num_adults + self.num_children

    @property
    def num_nights(self) -> int:
        return max(1, (self.return_date - self.departure_date).days)

    @property
    def duration_days(self) -> int:
        return self.num_nights + 1

    def validate_room_capacity(self) -> Tuple[bool, str]:
        """Validate that rooms can comfortably accommodate the party."""
        max_capacity = self.num_rooms * self.room_occupancy_per_room
        if self.total_travelers > max_capacity:
            return False, (
                f"Guest count ({self.total_travelers} guests) exceeds room capacity "
                f"({self.num_rooms} rooms × {self.room_occupancy_per_room} max guests = {max_capacity}). "
                f"Please add more rooms."
            )
        return True, "Room capacity is valid."


class PackageCostBreakdown(BaseModel):
    """
    Itemized deterministic package cost calculation.
    All financial computations use integer paise for zero drift, with INR floats for display.
    """
    # 1. Transport breakdown
    outbound_transport_inr: float = Field(..., description="Outbound bus/transit cost")
    return_transport_inr: float = Field(..., description="Return bus/transit cost")
    local_transport_inr: float = Field(..., description="Local sightseeing transit cost")
    transport_subtotal_inr: float = Field(..., description="Total transportation subtotal")
    transport_subtotal_paise: int

    # 2. Lodging breakdown
    room_rate_per_night_inr: float
    hotel_nights: int
    num_rooms: int
    accommodation_subtotal_inr: float = Field(..., description="Room cost × nights × rooms")
    accommodation_subtotal_paise: int

    # 3. Meals breakdown
    food_rate_per_person_per_day_inr: float
    food_days: int
    food_subtotal_inr: float = Field(..., description="Food cost per person per day × travelers × days")
    food_subtotal_paise: int

    # 4. Activities breakdown
    included_activities_subtotal_inr: float = Field(default=0.0)
    optional_activities_subtotal_inr: float = Field(default=0.0)
    activities_subtotal_inr: float = Field(..., description="Activities subtotal")
    activities_subtotal_paise: int

    # 5. Taxes & Fees
    hotel_gst_inr: float = Field(default=0.0, description="12% Hotel GST")
    transport_tax_inr: float = Field(default=0.0, description="5% Transport tax")
    taxes_and_fees_inr: float = Field(..., description="Total taxes and regulatory fees")
    taxes_and_fees_paise: int

    # 6. Other disclosed costs
    contingency_percent: float = Field(default=10.0)
    contingency_reserve_inr: float = Field(..., description="Disclosed contingency reserve")
    contingency_reserve_paise: int

    # 7. Grand Totals
    total_group_price_inr: float = Field(..., description="Authoritative grand total group price")
    total_group_price_paise: int
    price_per_person_inr: float = Field(..., description="Total group price divided by traveler count")
    price_per_person_paise: int

    # 8. Payment Schedule
    amount_payable_now_inr: float = Field(..., description="Amount payable immediately")
    amount_payable_now_paise: int
    remaining_balance_inr: float = Field(default=0.0, description="Remaining balance if instalments supported")
    remaining_balance_paise: int = Field(default=0)

    # 9. Meta & Itemized specifics
    num_travelers: int
    itemized_details: Dict[str, Any] = Field(default_factory=dict)


class AIPackageReview(BaseModel):
    """Structured collaborative insights from the 5 AI agents on a customized package."""
    destination_fit_summary: str = ""
    travel_agent_verdict: str = ""
    hotel_agent_verdict: str = ""
    transport_agent_verdict: str = ""
    food_agent_verdict: str = ""
    budget_agent_verdict: str = ""
    optimization_recommendations: List[str] = Field(default_factory=list)
    is_within_budget: bool = True
    budget_shortfall_or_surplus_inr: float = 0.0
    optimization_passes: List[Dict[str, Any]] = Field(default_factory=list)


class PackageBookingRecord(BaseModel):
    """Persistent booking record for a travel package."""
    booking_reference: str
    package_id: str
    package_name: str
    category: str
    destination_id: str
    destination_name: str
    departure_date: str
    return_date: str
    num_nights: int
    duration_days: int
    num_adults: int
    num_children: int = 0
    num_rooms: int = 1
    room_occupancy_per_room: int = 2

    # Supplier details
    hotel_id: str
    hotel_name: str
    room_type: str
    transport_mode: str
    meal_plan: str
    included_activities: List[str] = Field(default_factory=list)
    selected_optional_activities: List[str] = Field(default_factory=list)

    # Guest and Cost details
    guest_info: GuestInformation
    cost_breakdown: PackageCostBreakdown
    total_amount_inr: float
    total_amount_paise: int

    # Booking & Payment state
    booking_status: BookingStatus = BookingStatus.DRAFT
    payment_status: PaymentStatus = PaymentStatus.PENDING
    payment_order_id: Optional[str] = None
    payment_id: Optional[str] = None
    payment_gateway: str = "sk_demo_bank"
    demo_transaction_reference: Optional[str] = None
    demo_balance_after_inr: Optional[float] = None

    # Policies & Metadata
    cancellation_policy: str
    is_refundable: bool = True
    is_demo: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)
