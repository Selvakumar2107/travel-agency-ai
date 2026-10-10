"""Data models and type schemas for the Agentic AI Travel Agency."""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator


HotelTier = Literal["budget", "standard", "premium"]
FoodTier = Literal["economy", "standard", "comfort"]
TransportTier = Literal["shared", "standard", "private"]
ActivityTier = Literal["budget", "standard", "premium"]
TravelStyle = Literal["family", "couple", "solo", "friends", "business"]
PacePreference = Literal["relaxed", "balanced", "fast_paced"]


class TripRequest(BaseModel):
    """User input preferences for the trip."""
    destination_id: str = Field(..., description="Selected destination identifier")
    num_travelers: int = Field(..., ge=1, description="Total number of travelers (must be >= 1)")
    trip_duration_days: int = Field(..., ge=1, description="Total trip duration in days (must be >= 1)")
    total_budget: float = Field(default=3000.0, ge=3000.0, description="Total budget in INR (minimum ₹3,000)")
    hotel_tier: HotelTier = Field(default="standard", description="Preferred hotel tier")
    food_tier: FoodTier = Field(default="standard", description="Preferred food tier")
    transport_tier: TransportTier = Field(default="standard", description="Preferred transport tier")
    activity_tier: ActivityTier = Field(default="standard", description="Preferred activity tier")
    interests: List[str] = Field(default_factory=list, description="User travel interests")
    starting_location: str = Field(default="Bangalore", description="Starting departure city")
    contingency_percent: float = Field(default=10.0, ge=0.0, description="Contingency reserve percentage")
    travel_style: TravelStyle = Field(default="family", description="Travel party style (family, couple, solo, friends, business)")
    dietary_preference: str = Field(default="No Dietary Restriction", description="Dietary preference (Vegetarian, Vegan, Jain, etc.)")
    allergies: List[str] = Field(default_factory=list, description="Known allergies or dietary restrictions")
    accessibility_requirements: List[str] = Field(default_factory=list, description="Mobility or physical accessibility needs")
    preferred_pace: PacePreference = Field(default="balanced", description="Preferred trip pace (relaxed, balanced, fast_paced)")

    @field_validator("num_travelers")
    @classmethod
    def validate_travelers(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Number of travelers must be at least 1")
        return v

    @field_validator("trip_duration_days")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Trip duration must be at least 1 day")
        return v

    @field_validator("total_budget", mode="before")
    @classmethod
    def validate_budget(cls, v: Any) -> float:
        val = float(v)
        if val < 3000.0:
            raise ValueError("Minimum allowed budget is ₹3,000 INR")
        return val


class StructuredTripBrief(BaseModel):
    """Normalized multi-agent trip brief established by the Travel Planning Agent."""
    origin: str
    destination_id: str
    destination_name: str
    num_travelers: int
    trip_duration_days: int
    num_nights: int
    num_rooms: int
    total_budget: float
    budget_per_person: float
    travel_style: str
    preferred_pace: str
    dietary_preference: str
    allergies: List[str] = Field(default_factory=list)
    accessibility_requirements: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    target_tiers: Dict[str, str] = Field(default_factory=dict)


class CostBreakdown(BaseModel):
    """Itemized deterministic trip cost calculations."""
    intercity_transport: float = Field(..., description="Estimated intercity transportation cost")
    local_transport: float = Field(..., description="Estimated local transportation cost")
    hotel_accommodation: float = Field(..., description="Total hotel accommodation cost")
    food: float = Field(..., description="Total food and dining expense")
    activities: float = Field(..., description="Total sightseeing and activity expense")
    subtotal: float = Field(..., description="Sum of all direct travel expenses")
    contingency_reserve: float = Field(..., description="Configured contingency reserve (default 10%)")
    total_estimated_cost: float = Field(..., description="Authoritative grand total cost")
    cost_per_person: float = Field(..., description="Cost per traveler")
    num_rooms: int = Field(..., description="Number of hotel rooms required")
    num_nights: int = Field(..., description="Number of hotel nights")


class OptimizationPass(BaseModel):
    """Record of a single budget optimization iteration."""
    pass_number: int
    action_taken: str
    previous_cost: float
    new_cost: float
    savings: float
    hotel_tier: HotelTier
    activity_tier: ActivityTier
    food_tier: FoodTier
    transport_tier: TransportTier


class TravelOptionPlan(BaseModel):
    """Pre-calculated comparison plan for tier bundles (Economy, Balanced, Premium)."""
    plan_name: str
    hotel_tier: HotelTier
    transport_tier: TransportTier
    food_tier: FoodTier
    activity_tier: ActivityTier
    hotel_name: str
    costs: CostBreakdown
    budget_status: Literal["Within Budget", "Over Budget"]
    difference: float
    is_over_budget: bool
    is_most_affordable_feasible: bool = False


class DestinationAlternative(BaseModel):
    """Alternative destination exploration when budget is tight or exceeded."""
    destination_id: str
    destination_name: str
    state: str
    estimated_economy_cost: float
    feasible: bool
    savings_vs_selected: float
    note: str


class AgentOutput(BaseModel):
    """Standardized response container for each specialized AI agent."""
    agent_name: str
    agent_role: str
    summary: str
    recommendations: List[str] = Field(default_factory=list)
    key_metrics: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = "Illustrative AI estimate based on dummy datasets. No live availability."
    used_gemini: bool = False
    raw_response: Optional[str] = None
    source_data_ids: List[str] = Field(default_factory=list)
    trade_offs: List[str] = Field(default_factory=list)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    scoring_breakdown: Dict[str, float] = Field(default_factory=dict)
    is_fallback: bool = False
    execution_time_ms: float = 0.0
    substitutions_suggested: List[str] = Field(default_factory=list)


class DayItinerary(BaseModel):
    """Itinerary details for a single day."""
    day: int
    title: str
    morning: str
    afternoon: str
    evening: str
    dining_highlight: str
    tips: Optional[str] = None
    estimated_transit_time: Optional[str] = None
    dietary_alignment_note: Optional[str] = None
    estimated_day_cost: float = 0.0


class CompleteTripPlan(BaseModel):
    """Final trip plan generated by the multi-agent orchestrator."""
    request: TripRequest
    trip_brief: Optional[StructuredTripBrief] = None
    destination: Dict[str, Any]
    selected_hotel: Dict[str, Any]
    initial_costs: CostBreakdown
    final_costs: CostBreakdown
    selected_tiers: Dict[str, str]
    optimization_history: List[OptimizationPass]
    budget_status: Literal["within_budget", "optimized_within_budget", "exceeded_budget"]
    initial_difference: float
    savings_achieved: float
    remaining_balance_or_shortfall: float
    is_shortfall: bool
    itinerary: List[DayItinerary]
    agent_reports: Dict[str, AgentOutput]
    option_comparisons: List[TravelOptionPlan] = Field(default_factory=list)
    cheaper_alternatives: List[DestinationAlternative] = Field(default_factory=list)

