"""Tests for multi-agent budget optimization feedback loop, 3-plan comparisons, and orchestrator."""

from unittest.mock import patch, MagicMock
import pytest

from travel_agency.models import TripRequest
from travel_agency.orchestrator import MultiAgentOrchestrator
from travel_agency.data import get_destination_by_id
from travel_agency.costs import compute_trip_costs, select_hotel_for_tier


def test_default_budget_and_minimum_validation():
    """Verify default starting budget is ₹3,000 and budgets below ₹3,000 are rejected."""
    # Test default starting budget
    req_default = TripRequest(
        destination_id="mysuru",
        num_travelers=1,
        trip_duration_days=1,
    )
    assert req_default.total_budget == 3000.0

    # Test exact ₹3,000 budget is accepted
    req_3000 = TripRequest(
        destination_id="mysuru",
        num_travelers=1,
        trip_duration_days=1,
        total_budget=3000.0,
    )
    assert req_3000.total_budget == 3000.0

    # Test budgets below ₹3,000 are rejected
    with pytest.raises(ValueError, match="Minimum allowed budget is ₹3,000 INR"):
        TripRequest(
            destination_id="mysuru",
            num_travelers=1,
            trip_duration_days=1,
            total_budget=2999.0,
        )

    with pytest.raises(ValueError, match="Minimum allowed budget is ₹3,000 INR"):
        TripRequest(
            destination_id="mysuru",
            num_travelers=1,
            trip_duration_days=1,
            total_budget=1500.0,
        )

    with pytest.raises(ValueError, match="Minimum allowed budget is ₹3,000 INR"):
        TripRequest(
            destination_id="mysuru",
            num_travelers=1,
            trip_duration_days=1,
            total_budget=-100.0,
        )


def test_three_travel_option_plans_comparison():
    """Verify orchestrator generates Economy, Balanced, and Premium comparison plans with contingency."""
    orchestrator = MultiAgentOrchestrator(api_key=None)
    request = TripRequest(
        destination_id="mysuru",
        num_travelers=2,
        trip_duration_days=2,
        total_budget=20000.0,
        hotel_tier="standard",
        food_tier="standard",
        transport_tier="standard",
        activity_tier="standard",
    )

    plan = orchestrator.plan_trip(request)

    assert len(plan.option_comparisons) == 3
    plan_names = [p.plan_name for p in plan.option_comparisons]
    assert plan_names == ["Economy Plan", "Balanced Plan", "Premium Plan"]

    # Verify each comparison plan includes all cost categories & 10% contingency
    for opt in plan.option_comparisons:
        assert opt.costs.hotel_accommodation > 0
        assert opt.costs.intercity_transport > 0
        assert opt.costs.food > 0
        assert opt.costs.activities > 0
        assert opt.costs.contingency_reserve == round(opt.costs.subtotal * 0.10, 2)
        assert opt.costs.total_estimated_cost == round(opt.costs.subtotal + opt.costs.contingency_reserve, 2)
        assert opt.budget_status in ["Within Budget", "Over Budget"]

    # Verify at least one plan is labeled as most affordable feasible
    most_affordable = [p for p in plan.option_comparisons if p.is_most_affordable_feasible]
    assert len(most_affordable) == 1


def test_starting_budget_3000_shortfall_and_alternatives():
    """Verify that a ₹3,000 budget for a multi-day group trip reports shortfall and suggests cheaper alternatives."""
    orchestrator = MultiAgentOrchestrator(api_key=None)
    request = TripRequest(
        destination_id="ooty",
        num_travelers=2,
        trip_duration_days=3,
        total_budget=3000.0,
        hotel_tier="budget",
        food_tier="economy",
        transport_tier="shared",
        activity_tier="budget",
    )

    plan = orchestrator.plan_trip(request)

    # Cannot fit 2 people for 3 days in Ooty at ₹3,000
    assert plan.budget_status == "exceeded_budget"
    assert plan.is_shortfall is True
    assert plan.remaining_balance_or_shortfall > 0

    # Check that option comparisons correctly label plans as Over Budget
    for opt in plan.option_comparisons:
        assert opt.is_over_budget is True
        assert opt.budget_status == "Over Budget"

    # Check that cheaper alternatives are explored
    assert len(plan.cheaper_alternatives) > 0
    # Destination alternatives should have savings and costs computed
    for alt in plan.cheaper_alternatives:
        assert alt.estimated_economy_cost > 0
        assert len(alt.destination_name) > 0


def test_optimization_when_initially_within_budget():
    """Verify that if initial cost is within budget, 0 passes are triggered and status is within_budget."""
    orchestrator = MultiAgentOrchestrator(api_key=None)

    # Budget is generous: INR 100,000 for 2 travelers, 3 days
    request = TripRequest(
        destination_id="ooty",
        num_travelers=2,
        trip_duration_days=3,
        total_budget=100000.0,
        hotel_tier="standard",
        food_tier="standard",
        transport_tier="standard",
        activity_tier="standard",
        interests=["Nature"],
    )

    plan = orchestrator.plan_trip(request)

    assert plan.budget_status == "within_budget"
    assert len(plan.optimization_history) == 0
    assert plan.savings_achieved == 0.0
    assert not plan.is_shortfall
    assert plan.remaining_balance_or_shortfall >= 0
    assert plan.final_costs.total_estimated_cost <= request.total_budget


def test_optimization_when_exceeding_budget_and_can_be_resolved():
    """Verify feedback loop reduces options and resolves within 3 passes."""
    orchestrator = MultiAgentOrchestrator(api_key=None)
    dest = get_destination_by_id("jaipur")
    premium_hotel = select_hotel_for_tier("jaipur", "premium")

    initial_costs = compute_trip_costs(
        destination=dest,
        hotel=premium_hotel,
        num_travelers=2,
        trip_duration_days=4,
        transport_tier="private",
        food_tier="comfort",
        activity_tier="premium",
    )

    # Set budget slightly below initial total so 1 or 2 reductions bring it under budget
    target_budget = initial_costs.total_estimated_cost - 8000.0

    request = TripRequest(
        destination_id="jaipur",
        num_travelers=2,
        trip_duration_days=4,
        total_budget=target_budget,
        hotel_tier="premium",
        food_tier="comfort",
        transport_tier="private",
        activity_tier="premium",
        interests=["Heritage"],
    )

    plan = orchestrator.plan_trip(request)

    assert plan.budget_status == "optimized_within_budget"
    assert 1 <= len(plan.optimization_history) <= 3
    assert plan.savings_achieved > 0
    assert not plan.is_shortfall
    assert plan.final_costs.total_estimated_cost <= request.total_budget
    # Verify invariants: travelers and duration were never modified
    assert plan.request.num_travelers == 2
    assert plan.request.trip_duration_days == 4


def test_maximum_three_passes_enforcement_and_shortfall_reporting():
    """Verify that optimization never exceeds 3 passes and accurately reports shortfall when budget is too low."""
    orchestrator = MultiAgentOrchestrator(api_key=None)

    request = TripRequest(
        destination_id="goa",
        num_travelers=4,
        trip_duration_days=5,
        total_budget=5000.0,
        hotel_tier="premium",
        food_tier="comfort",
        transport_tier="private",
        activity_tier="premium",
        interests=["Beach"],
    )

    plan = orchestrator.plan_trip(request)

    # Must not exceed 3 passes
    assert len(plan.optimization_history) <= 3
    assert plan.budget_status == "exceeded_budget"
    assert plan.is_shortfall is True
    assert plan.remaining_balance_or_shortfall > 0  # this represents shortfall
    # Budget optimizer agent explains the shortfall
    budget_report = plan.agent_reports["budget_optimizer"]
    assert "exceeded" in budget_report.summary.lower() or "shortfall" in budget_report.summary.lower()


def test_orchestrator_runs_without_gemini_key_fallback():
    """Verify complete pipeline runs deterministically without an API key."""
    orchestrator = MultiAgentOrchestrator(api_key=None)
    request = TripRequest(
        destination_id="coorg",
        num_travelers=2,
        trip_duration_days=3,
        total_budget=35000.0,
        hotel_tier="standard",
        food_tier="standard",
        transport_tier="standard",
        activity_tier="standard",
        interests=["Coffee & Food", "Nature"],
    )

    plan = orchestrator.plan_trip(request)

    assert plan is not None
    assert len(plan.itinerary) == 3
    # Check all 5 agents reported
    expected_agents = {"travel_planner", "hotel_advisor", "transport_planner", "food_planner", "budget_optimizer"}
    assert expected_agents.issubset(set(plan.agent_reports.keys()))

    for key, report in plan.agent_reports.items():
        assert report.used_gemini is False
        assert len(report.summary) > 0
        assert len(report.recommendations) > 0


def test_gemini_integration_mocked():
    """Verify that when Gemini client returns a response, agents incorporate it and set used_gemini=True."""
    with patch("travel_agency.agents.BaseAgent.call_gemini", return_value="Curated AI Recommendation from Gemini."):
        orchestrator = MultiAgentOrchestrator(api_key="mock_valid_key")
        request = TripRequest(
            destination_id="mysuru",
            num_travelers=2,
            trip_duration_days=2,
            total_budget=40000.0,
            hotel_tier="standard",
            food_tier="standard",
            transport_tier="standard",
            activity_tier="standard",
            interests=["Heritage"],
        )

        plan = orchestrator.plan_trip(request)
        for key, report in plan.agent_reports.items():
            assert report.used_gemini is True
            assert "Gemini" in report.summary or "Curated" in report.summary
