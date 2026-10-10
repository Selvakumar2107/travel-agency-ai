"""Comprehensive automated tests for SK Holidays Advanced Multi-Agent AI Travel Intelligence."""

import pytest
from unittest.mock import MagicMock, patch
from travel_agency.models import (
    TripRequest,
    StructuredTripBrief,
    CostBreakdown,
    OptimizationPass,
    AgentOutput,
    DayItinerary,
    CompleteTripPlan,
)
from travel_agency.data import (
    get_destination_by_id,
    get_hotels_for_destination,
    load_destinations,
)
from travel_agency.costs import (
    compute_trip_costs,
    select_hotel_for_tier,
    calculate_num_rooms,
)
from travel_agency.scoring import (
    score_destination_match,
    evaluate_hotel_recommendation,
    evaluate_transport_tier,
    evaluate_food_tier,
    ScoringWeights,
    DEFAULT_WEIGHTS,
)
from travel_agency.agents import (
    TravelPlanningAgent,
    HotelRecommendationAgent,
    TransportPlanningAgent,
    FoodPlanningAgent,
    BudgetOptimizationAgent,
)
from travel_agency.orchestrator import MultiAgentOrchestrator


# ---------------------------------------------------------------------------
# 1. AGENT INPUT & OUTPUT CONTRACT TESTS
# ---------------------------------------------------------------------------

def test_travel_planning_agent_contract_and_brief():
    """Verify TravelPlanningAgent creates valid StructuredTripBrief and AgentOutput."""
    agent = TravelPlanningAgent(api_key=None)
    destination = get_destination_by_id("mysuru")
    req = TripRequest(
        destination_id="mysuru",
        num_travelers=2,
        trip_duration_days=2,
        total_budget=15000.0,
        travel_style="couple",
        preferred_pace="relaxed",
        dietary_preference="Vegetarian",
        interests=["Heritage", "Culture"],
        starting_location="Bangalore",
    )
    hotel = select_hotel_for_tier("mysuru", "standard")
    costs = compute_trip_costs(
        destination=destination,
        hotel=hotel,
        num_travelers=2,
        trip_duration_days=2,
        transport_tier="standard",
        food_tier="standard",
        activity_tier="standard",
    )
    final_tiers = {
        "hotel_tier": "standard",
        "transport_tier": "standard",
        "food_tier": "standard",
        "activity_tier": "standard",
    }

    # Brief contract
    brief = agent.create_structured_trip_brief(req, destination, costs, final_tiers)
    assert isinstance(brief, StructuredTripBrief)
    assert brief.destination_id == "mysuru"
    assert brief.num_travelers == 2
    assert brief.travel_style == "couple"
    assert brief.budget_per_person == 7500.0
    assert brief.dietary_preference == "Vegetarian"

    # Run contract
    output, itinerary = agent.run(req, destination, final_tiers, costs, trip_brief=brief)
    assert isinstance(output, AgentOutput)
    assert output.agent_name == "Travel Planning Agent"
    assert output.is_fallback is True  # No Gemini key provided
    assert len(itinerary) == 2
    for day in itinerary:
        assert isinstance(day, DayItinerary)
        assert day.day in (1, 2)
        assert day.morning
        assert day.afternoon
        assert day.evening
        assert day.dining_highlight
        assert day.estimated_transit_time is not None
        assert day.dietary_alignment_note is not None
        assert day.estimated_day_cost > 0.0


def test_hotel_recommendation_agent_capacity_and_taxes():
    """Verify HotelRecommendationAgent calculates 12% GST lodging total and checks capacity."""
    agent = HotelRecommendationAgent(api_key=None)
    destination = get_destination_by_id("mysuru")
    hotel = select_hotel_for_tier("mysuru", "standard")
    req = TripRequest(
        destination_id="mysuru",
        num_travelers=3,
        trip_duration_days=2,
        total_budget=20000.0,
        travel_style="family",
    )
    costs = compute_trip_costs(
        destination=destination,
        hotel=hotel,
        num_travelers=3,
        trip_duration_days=2,
        transport_tier="standard",
        food_tier="standard",
        activity_tier="standard",
    )

    output = agent.run(req, destination, hotel, costs, was_optimized=False)
    assert isinstance(output, AgentOutput)
    assert output.agent_name == "Hotel Recommendation Agent"
    assert hotel["id"] in output.source_data_ids
    assert "gst_12_percent_inr" in output.key_metrics

    # Check 12% GST math: price_per_night * rooms * nights * 0.12
    base_subtotal = hotel["price_per_night"] * costs.num_rooms * costs.num_nights
    expected_gst = round(base_subtotal * 0.12, 2)
    assert output.key_metrics["gst_12_percent_inr"] == expected_gst
    assert output.key_metrics["total_stay_inr"] == round(base_subtotal + expected_gst, 2)
    assert len(output.pros) > 0
    assert "hotel_score" in output.key_metrics


def test_transport_planning_agent_group_and_local_costs():
    """Verify TransportPlanningAgent evaluates group intercity and local transit."""
    agent = TransportPlanningAgent(api_key=None)
    destination = get_destination_by_id("ooty")
    req = TripRequest(
        destination_id="ooty",
        num_travelers=4,
        trip_duration_days=3,
        total_budget=30000.0,
        transport_tier="private",
    )
    hotel = select_hotel_for_tier("ooty", "standard")
    costs = compute_trip_costs(
        destination=destination,
        hotel=hotel,
        num_travelers=4,
        trip_duration_days=3,
        transport_tier="private",
        food_tier="standard",
        activity_tier="standard",
    )

    output = agent.run(req, destination, "private", costs, was_optimized=False)
    assert isinstance(output, AgentOutput)
    assert output.agent_name == "Transport Planning Agent"
    assert output.key_metrics["transport_tier"] == "private"
    assert output.key_metrics["intercity_cost_inr"] == costs.intercity_transport
    assert output.key_metrics["local_cost_inr"] == costs.local_transport
    assert output.key_metrics["total_transport_cost_inr"] == round(costs.intercity_transport + costs.local_transport, 2)
    assert "transport-private" in output.source_data_ids


def test_food_planning_agent_dietary_compliance_jain_and_vegan():
    """Verify FoodPlanningAgent strictly tailors menus for Jain and Vegan restrictions."""
    agent = FoodPlanningAgent(api_key=None)
    destination = get_destination_by_id("jaipur")
    hotel = select_hotel_for_tier("jaipur", "standard")

    # 1. Jain diet test
    req_jain = TripRequest(
        destination_id="jaipur",
        num_travelers=2,
        trip_duration_days=2,
        total_budget=20000.0,
        dietary_preference="Jain",
        allergies=["Peanuts"],
    )
    costs_jain = compute_trip_costs(
        destination=destination,
        hotel=hotel,
        num_travelers=2,
        trip_duration_days=2,
        transport_tier="standard",
        food_tier="standard",
        activity_tier="standard",
    )
    out_jain = agent.run(req_jain, destination, "standard", costs_jain)
    assert "Jain" in out_jain.summary or "Jain" in str(out_jain.recommendations)
    # Check allergen disclaimer is included
    has_allergy_warning = any("Allergen Notice" in r for r in out_jain.recommendations)
    assert has_allergy_warning is True

    # 2. Vegan diet test
    req_vegan = TripRequest(
        destination_id="jaipur",
        num_travelers=1,
        trip_duration_days=1,
        total_budget=10000.0,
        dietary_preference="Vegan",
    )
    costs_vegan = compute_trip_costs(
        destination=destination,
        hotel=hotel,
        num_travelers=1,
        trip_duration_days=1,
        transport_tier="standard",
        food_tier="standard",
        activity_tier="standard",
    )
    out_vegan = agent.run(req_vegan, destination, "standard", costs_vegan)
    assert "Vegan" in out_vegan.summary or "Vegan" in str(out_vegan.recommendations)


def test_budget_optimization_agent_contract_and_auditing():
    """Verify BudgetOptimizationAgent audits costs deterministically and reports surplus/shortfall."""
    agent = BudgetOptimizationAgent(api_key=None)
    req = TripRequest(
        destination_id="mysuru",
        num_travelers=2,
        trip_duration_days=2,
        total_budget=15000.0,
    )
    destination = get_destination_by_id("mysuru")
    hotel = select_hotel_for_tier("mysuru", "standard")
    costs = compute_trip_costs(
        destination=destination,
        hotel=hotel,
        num_travelers=2,
        trip_duration_days=2,
        transport_tier="standard",
        food_tier="standard",
        activity_tier="standard",
    )

    out = agent.run(
        request=req,
        initial_costs=costs,
        final_costs=costs,
        passes=[],
        budget_status="within_budget",
        balance_or_shortfall=round(req.total_budget - costs.total_estimated_cost, 2),
        is_shortfall=False,
    )
    assert isinstance(out, AgentOutput)
    assert out.agent_name == "Budget Optimization Agent"
    assert out.key_metrics["user_budget_inr"] == 15000.0
    assert out.key_metrics["contingency_reserve_inr"] == costs.contingency_reserve
    assert out.key_metrics["is_shortfall"] is False


# ---------------------------------------------------------------------------
# 2. DETERMINISTIC SCORING & RANKING TESTS
# ---------------------------------------------------------------------------

def test_preference_based_recommendation_ranking_weights():
    """Verify scoring weights and range boundaries."""
    assert DEFAULT_WEIGHTS.validate_weights() is True
    weights_dict = DEFAULT_WEIGHTS.model_dump()
    assert sum(weights_dict.values()) == pytest.approx(1.0, 0.001)

    dest = get_destination_by_id("goa")
    score_beach, bd_beach, _ = score_destination_match(
        destination=dest,
        interests=["Beach", "Nightlife", "Relaxation"],
        travel_style="friends",
        total_budget=25000.0,
    )
    assert 0.0 <= score_beach <= 100.0
    assert "preference_match" in bd_beach
    assert "affordability" in bd_beach

    # Goa should score higher for beach lovers than for heritage seekers
    score_heritage, _, _ = score_destination_match(
        destination=dest,
        interests=["Heritage", "Palaces", "Monuments"],
        travel_style="friends",
        total_budget=25000.0,
    )
    assert score_beach > score_heritage


def test_hotel_scoring_and_accessibility():
    """Verify hotel evaluation properly checks accessibility requirements."""
    hotel = {
        "id": "h-test",
        "name": "Accessible Resort",
        "price_per_night": 3000,
        "rating": 4.5,
        "amenities": ["WiFi", "Pool", "Wheelchair Accessible", "Elevator"],
        "tier": "standard",
    }
    score, breakdown, pros, cons = evaluate_hotel_recommendation(
        hotel=hotel,
        travel_style="family",
        total_budget=20000.0,
        num_rooms=1,
        num_nights=2,
        accessibility_requirements=["Wheelchair Accessible"],
    )
    assert score >= 70.0
    assert any("Wheelchair" in p for p in pros)


# ---------------------------------------------------------------------------
# 3. PER-PERSON VS GROUP CALCULATIONS & TAX MATH
# ---------------------------------------------------------------------------

def test_per_person_and_room_math():
    """Verify calculate_num_rooms, cost_per_person, and 10% contingency reserve."""
    # 1 guest -> 1 room
    assert calculate_num_rooms(1) == 1
    # 2 guests -> 1 room (double occupancy)
    assert calculate_num_rooms(2) == 1
    # 3 guests -> 2 rooms
    assert calculate_num_rooms(3) == 2
    # 5 guests -> 3 rooms
    assert calculate_num_rooms(5) == 3

    dest = get_destination_by_id("mysuru")
    hotel = select_hotel_for_tier("mysuru", "budget")
    costs = compute_trip_costs(
        destination=dest,
        hotel=hotel,
        num_travelers=3,
        trip_duration_days=2,
        transport_tier="shared",
        food_tier="economy",
        activity_tier="budget",
        contingency_percent=10.0,
    )
    assert costs.num_rooms == 2
    assert costs.num_nights == 1
    assert costs.contingency_reserve == round(costs.subtotal * 0.10, 2)
    assert costs.total_estimated_cost == round(costs.subtotal + costs.contingency_reserve, 2)
    assert costs.cost_per_person == round(costs.total_estimated_cost / 3, 2)


# ---------------------------------------------------------------------------
# 4. BUDGET OPTIMIZATION LOOP & INFEASIBILITY TESTS
# ---------------------------------------------------------------------------

def test_budget_optimization_feasible_no_passes():
    """Verify orchestrator requires 0 optimization passes when budget is ample."""
    orch = MultiAgentOrchestrator(api_key=None)
    req = TripRequest(
        destination_id="mysuru",
        num_travelers=2,
        trip_duration_days=2,
        total_budget=50000.0,  # generous budget
        hotel_tier="standard",
    )
    plan = orch.plan_trip(req)
    assert plan.budget_status == "within_budget"
    assert len(plan.optimization_history) == 0
    assert plan.is_shortfall is False
    assert plan.remaining_balance_or_shortfall > 0


def test_budget_optimization_exceeding_budget_downgrades_tiers():
    """Verify feedback loop executes deterministic tier downgrades to fit budget."""
    orch = MultiAgentOrchestrator(api_key=None)
    # Premium tiers initially exceed ₹8,000 budget for 2 travelers, 2 days
    req = TripRequest(
        destination_id="mysuru",
        num_travelers=2,
        trip_duration_days=2,
        total_budget=10000.0,
        hotel_tier="premium",
        transport_tier="private",
        food_tier="comfort",
        activity_tier="premium",
    )
    plan = orch.plan_trip(req)
    assert len(plan.optimization_history) > 0
    assert len(plan.optimization_history) <= 3
    assert plan.savings_achieved > 0
    # Final cost should be lower than initial cost
    assert plan.final_costs.total_estimated_cost < plan.initial_costs.total_estimated_cost


def test_budget_optimization_maximum_three_passes_enforced():
    """Verify optimizer never exceeds 3 passes even when budget is very tight."""
    orch = MultiAgentOrchestrator(api_key=None)
    # ₹3,000 for 4 people for 4 days in Ooty is impossible
    req = TripRequest(
        destination_id="ooty",
        num_travelers=4,
        trip_duration_days=4,
        total_budget=3000.0,
        hotel_tier="premium",
        transport_tier="private",
        food_tier="comfort",
        activity_tier="premium",
    )
    plan = orch.plan_trip(req)
    assert len(plan.optimization_history) <= 3
    assert plan.budget_status == "exceeded_budget"
    assert plan.is_shortfall is True
    assert plan.remaining_balance_or_shortfall > 0  # Represents shortfall
    # Preserved invariant: duration and travelers are unchanged
    assert plan.request.num_travelers == 4
    assert plan.request.trip_duration_days == 4
    # Cheaper alternatives provided
    assert len(plan.cheaper_alternatives) > 0


# ---------------------------------------------------------------------------
# 5. INPUT VALIDATION & RELIABILITY
# ---------------------------------------------------------------------------

def test_minimum_budget_validation_3000():
    """Verify ValueError is raised if budget is under ₹3,000 INR."""
    with pytest.raises(ValueError, match="3,000"):
        TripRequest(
            destination_id="mysuru",
            num_travelers=1,
            trip_duration_days=1,
            total_budget=2999.0,
        )


def test_invalid_traveler_or_duration_validation():
    """Verify validation on traveler count and duration."""
    with pytest.raises(ValueError):
        TripRequest(
            destination_id="mysuru",
            num_travelers=0,
            trip_duration_days=1,
            total_budget=5000.0,
        )

    with pytest.raises(ValueError):
        TripRequest(
            destination_id="mysuru",
            num_travelers=2,
            trip_duration_days=0,
            total_budget=5000.0,
        )


# ---------------------------------------------------------------------------
# 6. GEMINI INTEGRATION & MOCKED FALLBACK TESTS
# ---------------------------------------------------------------------------

def test_gemini_api_failure_triggers_deterministic_fallback():
    """Verify agent gracefully falls back to deterministic rules if Gemini raises error."""
    agent = TravelPlanningAgent(api_key="mock_key")
    # Mock client generate_content to raise an exception
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("Rate limit / Network timeout")
    agent.client = mock_client

    dest = get_destination_by_id("jaipur")
    req = TripRequest(
        destination_id="jaipur",
        num_travelers=1,
        trip_duration_days=1,
        total_budget=5000.0,
    )
    costs = compute_trip_costs(
        destination=dest,
        hotel=select_hotel_for_tier("jaipur", "budget"),
        num_travelers=1,
        trip_duration_days=1,
        transport_tier="shared",
        food_tier="economy",
        activity_tier="budget",
    )
    final_tiers = {"hotel_tier": "budget", "transport_tier": "shared", "food_tier": "economy", "activity_tier": "budget"}

    output, itinerary = agent.run(req, dest, final_tiers, costs)
    assert output.used_gemini is False
    assert output.is_fallback is True
    assert output.summary is not None
    assert len(itinerary) == 1


def test_gemini_api_mocked_success_enhances_summary():
    """Verify agent integrates Gemini text response when API succeeds."""
    agent = TravelPlanningAgent(api_key="mock_key")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Custom Gemini Curated Itinerary Rationale for Royal Heritage."
    mock_client.models.generate_content.return_value = mock_resp
    agent.client = mock_client

    dest = get_destination_by_id("mysuru")
    req = TripRequest(
        destination_id="mysuru",
        num_travelers=2,
        trip_duration_days=1,
        total_budget=8000.0,
    )
    costs = compute_trip_costs(
        destination=dest,
        hotel=select_hotel_for_tier("mysuru", "standard"),
        num_travelers=2,
        trip_duration_days=1,
        transport_tier="standard",
        food_tier="standard",
        activity_tier="standard",
    )
    final_tiers = {"hotel_tier": "standard", "transport_tier": "standard", "food_tier": "standard", "activity_tier": "standard"}

    output, itinerary = agent.run(req, dest, final_tiers, costs)
    assert output.used_gemini is True
    assert output.is_fallback is False
    assert output.summary == "Custom Gemini Curated Itinerary Rationale for Royal Heritage."


# ---------------------------------------------------------------------------
# 7. END-TO-END ITINERARY GENERATION & FIVE AGENTS COLLABORATION
# ---------------------------------------------------------------------------

def test_end_to_end_orchestration_all_five_agents_participate():
    """Verify CompleteTripPlan contains outputs from all 5 specialized agents."""
    orch = MultiAgentOrchestrator(api_key=None)
    req = TripRequest(
        destination_id="munnar",
        num_travelers=2,
        trip_duration_days=2,
        total_budget=16000.0,
        travel_style="couple",
        preferred_pace="relaxed",
        dietary_preference="Vegetarian",
    )
    plan = orch.plan_trip(req)
    assert isinstance(plan, CompleteTripPlan)
    assert plan.trip_brief is not None
    assert plan.trip_brief.travel_style == "couple"

    # All 5 agents present
    expected_agents = ["travel_planner", "hotel_advisor", "transport_planner", "food_planner", "budget_optimizer"]
    for ag in expected_agents:
        assert ag in plan.agent_reports
        rep = plan.agent_reports[ag]
        assert rep.agent_name
        assert rep.summary
        assert len(rep.trade_offs) > 0 or len(rep.recommendations) > 0

    # Itinerary populated
    assert len(plan.itinerary) == 2
    for day in plan.itinerary:
        assert day.title
        assert day.dining_highlight
        assert day.estimated_transit_time is not None

    # Option comparisons populated
    assert len(plan.option_comparisons) == 3
