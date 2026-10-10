"""Central Multi-Agent Orchestrator and Deterministic Budget Optimization Feedback Loop."""

import math
from typing import Dict, Any, List, Optional, Tuple
from travel_agency.models import (
    TripRequest,
    StructuredTripBrief,
    CostBreakdown,
    OptimizationPass,
    CompleteTripPlan,
    TravelOptionPlan,
    DestinationAlternative,
    AgentOutput,
    DayItinerary,
    HotelTier,
    FoodTier,
    TransportTier,
    ActivityTier,
)
from travel_agency.data import (
    load_destinations,
    get_destination_by_id,
    get_hotels_for_destination,
    get_activities_for_destination,
)
from travel_agency.costs import (
    compute_trip_costs,
    select_hotel_for_tier,
)
from travel_agency.agents import (
    TravelPlanningAgent,
    HotelRecommendationAgent,
    TransportPlanningAgent,
    FoodPlanningAgent,
    BudgetOptimizationAgent,
)
from travel_agency.logging_utils import AgentExecutionLogger, log_optimization_event


class MultiAgentOrchestrator:
    """Coordinates the 5 specialized AI agents and executes the deterministic budget optimization feedback loop."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key
        self.model_name = model_name
        self.travel_agent = TravelPlanningAgent(api_key=api_key, model_name=model_name)
        self.hotel_agent = HotelRecommendationAgent(api_key=api_key, model_name=model_name)
        self.transport_agent = TransportPlanningAgent(api_key=api_key, model_name=model_name)
        self.food_agent = FoodPlanningAgent(api_key=api_key, model_name=model_name)
        self.budget_agent = BudgetOptimizationAgent(api_key=api_key, model_name=model_name)

    def generate_option_comparisons(
        self,
        request: TripRequest,
        destination: Dict[str, Any]
    ) -> List[TravelOptionPlan]:
        """
        Generates three standard travel plans for comparison:
        1. Economy Plan (Budget tiers, shared transit, economy food)
        2. Balanced Plan (Standard tiers across board)
        3. Premium Plan (Premium tiers, private transport, comfort food)
        """
        tier_specs = [
            ("Economy Plan", "budget", "shared", "economy", "budget"),
            ("Balanced Plan", "standard", "standard", "standard", "standard"),
            ("Premium Plan", "premium", "private", "comfort", "premium"),
        ]

        plans: List[TravelOptionPlan] = []
        user_budget = request.total_budget

        for name, h_tier, t_tier, f_tier, a_tier in tier_specs:
            hotel = select_hotel_for_tier(destination["id"], h_tier)  # type: ignore
            costs = compute_trip_costs(
                destination=destination,
                hotel=hotel,
                num_travelers=request.num_travelers,
                trip_duration_days=request.trip_duration_days,
                transport_tier=t_tier,  # type: ignore
                food_tier=f_tier,  # type: ignore
                activity_tier=a_tier,  # type: ignore
                contingency_percent=request.contingency_percent,
            )

            diff = round(user_budget - costs.total_estimated_cost, 2)
            is_over = costs.total_estimated_cost > user_budget
            status = "Over Budget" if is_over else "Within Budget"

            plans.append(
                TravelOptionPlan(
                    plan_name=name,
                    hotel_tier=h_tier,  # type: ignore
                    transport_tier=t_tier,  # type: ignore
                    food_tier=f_tier,  # type: ignore
                    activity_tier=a_tier,  # type: ignore
                    hotel_name=hotel.get("name", "Hotel"),
                    costs=costs,
                    budget_status=status,
                    difference=abs(diff),
                    is_over_budget=is_over,
                    is_most_affordable_feasible=False,
                )
            )

        # Mark the most affordable feasible option
        feasible_plans = [p for p in plans if not p.is_over_budget]
        if feasible_plans:
            # Sort by total cost ascending
            feasible_plans.sort(key=lambda p: p.costs.total_estimated_cost)
            feasible_plans[0].is_most_affordable_feasible = True
        else:
            # If none fit, mark the lowest cost option (Economy) as the most affordable overall
            plans[0].is_most_affordable_feasible = True

        return plans

    def find_cheaper_alternatives(
        self,
        request: TripRequest,
        current_destination: Dict[str, Any]
    ) -> List[DestinationAlternative]:
        """
        Explores cheaper sample destinations when budget is tight or exceeded,
        comparing economy rates across destinations.
        """
        all_dests = load_destinations()
        alternatives: List[DestinationAlternative] = []

        curr_hotel = select_hotel_for_tier(current_destination["id"], "budget")
        curr_economy_costs = compute_trip_costs(
            destination=current_destination,
            hotel=curr_hotel,
            num_travelers=request.num_travelers,
            trip_duration_days=request.trip_duration_days,
            transport_tier="shared",
            food_tier="economy",
            activity_tier="budget",
            contingency_percent=request.contingency_percent,
        )
        curr_total = curr_economy_costs.total_estimated_cost

        for d in all_dests:
            if d["id"].lower() == current_destination["id"].lower():
                continue

            hotel = select_hotel_for_tier(d["id"], "budget")
            costs = compute_trip_costs(
                destination=d,
                hotel=hotel,
                num_travelers=request.num_travelers,
                trip_duration_days=request.trip_duration_days,
                transport_tier="shared",
                food_tier="economy",
                activity_tier="budget",
                contingency_percent=request.contingency_percent,
            )

            alt_total = costs.total_estimated_cost
            savings = round(curr_total - alt_total, 2)
            is_feasible = alt_total <= request.total_budget

            if alt_total < curr_total or is_feasible:
                note = (
                    f"Fits within budget ₹{request.total_budget:,.2f}"
                    if is_feasible else
                    f"Saves ₹{savings:,.2f} compared to {current_destination['name']}"
                )
                alternatives.append(
                    DestinationAlternative(
                        destination_id=d["id"],
                        destination_name=d["name"],
                        state=d.get("state", ""),
                        estimated_economy_cost=alt_total,
                        feasible=is_feasible,
                        savings_vs_selected=savings,
                        note=note,
                    )
                )

        # Sort by cost ascending
        alternatives.sort(key=lambda a: a.estimated_economy_cost)
        return alternatives[:4]

    def optimize_budget(
        self,
        request: TripRequest,
        destination: Dict[str, Any],
        initial_costs: CostBreakdown,
        max_passes: int = 3
    ) -> Tuple[CostBreakdown, Dict[str, str], List[OptimizationPass], str, float, bool]:
        """
        Executes deterministic feedback loop to adjust options when trip exceeds budget.

        Reduction priority order:
        1. Reduce premium accommodation to standard accommodation.
        2. Reduce standard accommodation to budget accommodation.
        3. Reduce premium activities to standard activities.
        4. Reduce standard activities to budget activities.
        5. Reduce comfort food spending to standard food spending.
        6. Reduce standard food spending to economy food spending.
        7. Reduce private transport to standard transport.
        8. Reduce standard transport to shared/public transport.

        Returns:
            (final_costs, final_tiers, optimization_history, budget_status, balance_or_shortfall, is_shortfall)
        """
        current_hotel_tier: HotelTier = request.hotel_tier
        current_activity_tier: ActivityTier = request.activity_tier
        current_food_tier: FoodTier = request.food_tier
        current_transport_tier: TransportTier = request.transport_tier

        current_hotel = select_hotel_for_tier(destination["id"], current_hotel_tier)
        current_costs = initial_costs
        user_budget = request.total_budget
        passes: List[OptimizationPass] = []

        # Check if already within budget
        if current_costs.total_estimated_cost <= user_budget:
            remaining_balance = round(user_budget - current_costs.total_estimated_cost, 2)
            return (
                current_costs,
                {
                    "hotel_tier": current_hotel_tier,
                    "activity_tier": current_activity_tier,
                    "food_tier": current_food_tier,
                    "transport_tier": current_transport_tier,
                },
                [],
                "within_budget",
                remaining_balance,
                False
            )

        # Optimization reduction rules definition (ordered)
        reduction_rules = [
            ("hotel", "premium", "standard", "Downgraded accommodation from Premium to Standard tier"),
            ("hotel", "standard", "budget", "Downgraded accommodation from Standard to Budget tier"),
            ("activity", "premium", "standard", "Downgraded sightseeing activities from Premium to Standard tier"),
            ("activity", "standard", "budget", "Downgraded sightseeing activities from Standard to Budget tier"),
            ("food", "comfort", "standard", "Reduced dining budget from Comfort to Standard plan"),
            ("food", "standard", "economy", "Reduced dining budget from Standard to Economy plan"),
            ("transport", "private", "standard", "Shifted transport from Private dedicated vehicle to Standard transport"),
            ("transport", "standard", "shared", "Shifted transport from Standard transport to Shared & Public transit"),
        ]

        rule_index = 0
        total_rules = len(reduction_rules)

        for pass_num in range(1, max_passes + 1):
            if current_costs.total_estimated_cost <= user_budget:
                break

            action_applied = None
            # Find next applicable reduction rule
            while rule_index < total_rules:
                cat, from_val, to_val, desc = reduction_rules[rule_index]
                rule_index += 1

                if cat == "hotel" and current_hotel_tier == from_val:
                    current_hotel_tier = to_val  # type: ignore
                    current_hotel = select_hotel_for_tier(destination["id"], current_hotel_tier)
                    action_applied = desc
                    break
                elif cat == "activity" and current_activity_tier == from_val:
                    current_activity_tier = to_val  # type: ignore
                    action_applied = desc
                    break
                elif cat == "food" and current_food_tier == from_val:
                    current_food_tier = to_val  # type: ignore
                    action_applied = desc
                    break
                elif cat == "transport" and current_transport_tier == from_val:
                    current_transport_tier = to_val  # type: ignore
                    action_applied = desc
                    break

            if not action_applied:
                # No further reductions possible
                break

            # Recalculate costs with updated tiers
            new_costs = compute_trip_costs(
                destination=destination,
                hotel=current_hotel,
                num_travelers=request.num_travelers,
                trip_duration_days=request.trip_duration_days,
                transport_tier=current_transport_tier,
                food_tier=current_food_tier,
                activity_tier=current_activity_tier,
                contingency_percent=request.contingency_percent,
            )

            savings = round(current_costs.total_estimated_cost - new_costs.total_estimated_cost, 2)
            opt_pass = OptimizationPass(
                pass_number=pass_num,
                action_taken=action_applied,
                previous_cost=current_costs.total_estimated_cost,
                new_cost=new_costs.total_estimated_cost,
                savings=savings,
                hotel_tier=current_hotel_tier,
                activity_tier=current_activity_tier,
                food_tier=current_food_tier,
                transport_tier=current_transport_tier,
            )
            passes.append(opt_pass)
            log_optimization_event(
                pass_number=pass_num,
                action=action_applied,
                previous_cost=current_costs.total_estimated_cost,
                new_cost=new_costs.total_estimated_cost,
                savings=savings,
            )
            current_costs = new_costs

            if current_costs.total_estimated_cost <= user_budget:
                break

        # Final evaluation
        final_tiers = {
            "hotel_tier": current_hotel_tier,
            "activity_tier": current_activity_tier,
            "food_tier": current_food_tier,
            "transport_tier": current_transport_tier,
        }

        if current_costs.total_estimated_cost <= user_budget:
            status = "optimized_within_budget" if len(passes) > 0 else "within_budget"
            remaining = round(user_budget - current_costs.total_estimated_cost, 2)
            is_shortfall = False
        else:
            status = "exceeded_budget"
            shortfall = round(current_costs.total_estimated_cost - user_budget, 2)
            remaining = shortfall
            is_shortfall = True

        return current_costs, final_tiers, passes, status, remaining, is_shortfall

    def plan_trip(self, request: TripRequest) -> CompleteTripPlan:
        """
        Orchestrates full 5-agent pipeline, option comparisons, and budget feedback loop.
        Workflow:
        1. Validate the user's trip request (dates, count, budget >= 3000).
        2. Lookup destination and baseline inventory.
        3. Deterministically compute initial costs.
        4. Generate comparison options (Economy, Balanced, Premium).
        5. Execute deterministic budget feedback loop (maximum 3 passes).
        6. Create StructuredTripBrief and pass to all five collaborating agents.
        7. Travel Planning Agent builds itinerary and logical day-by-day pacing.
        8. Hotel Recommendation Agent audits lodging, 12% GST, and capacity.
        9. Transport Planning Agent estimates intercity and local transit.
        10. Food Planning Agent ensures strict dietary compliance and allergen notice.
        11. Budget Optimization Agent performs final deterministic audit.
        """
        # 1. Validation
        if request.total_budget < 3000:
            raise ValueError(f"Trip budget of ₹{request.total_budget:,.2f} is below the minimum required budget of ₹3,000 INR.")
        if request.num_travelers < 1:
            raise ValueError(f"Number of travelers must be at least 1 (got {request.num_travelers}).")
        if request.trip_duration_days < 1:
            raise ValueError(f"Trip duration must be at least 1 day (got {request.trip_duration_days}).")

        # 2. Lookup Destination
        destination = get_destination_by_id(request.destination_id)

        # 3. Select initial hotel & compute initial deterministic costs
        hotel = select_hotel_for_tier(destination["id"], request.hotel_tier)
        initial_costs = compute_trip_costs(
            destination=destination,
            hotel=hotel,
            num_travelers=request.num_travelers,
            trip_duration_days=request.trip_duration_days,
            transport_tier=request.transport_tier,
            food_tier=request.food_tier,
            activity_tier=request.activity_tier,
            contingency_percent=request.contingency_percent,
        )

        # 4. Generate Three Standard Comparison Plans (Economy, Balanced, Premium)
        option_comparisons = self.generate_option_comparisons(request, destination)

        # 5. Run deterministic budget feedback loop (up to 3 passes)
        final_costs, final_tiers, passes, budget_status, balance_or_shortfall, is_shortfall = self.optimize_budget(
            request=request,
            destination=destination,
            initial_costs=initial_costs,
            max_passes=3
        )

        final_hotel = select_hotel_for_tier(destination["id"], final_tiers["hotel_tier"])  # type: ignore
        savings_achieved = round(initial_costs.total_estimated_cost - final_costs.total_estimated_cost, 2)
        initial_diff = round(initial_costs.total_estimated_cost - request.total_budget, 2)

        # 6. Explore cheaper alternatives if budget is tight or exceeded
        cheaper_alternatives = self.find_cheaper_alternatives(request, destination)

        # 7. Create StructuredTripBrief for seamless agent-to-agent collaboration
        trip_brief = self.travel_agent.create_structured_trip_brief(
            request=request,
            destination=destination,
            final_costs=final_costs,
            final_tiers=final_tiers,
        )

        # 8. Invoke Agent 1: Travel Planning Agent
        travel_output, itinerary_days = self.travel_agent.run(
            request=request,
            destination=destination,
            final_tiers=final_tiers,
            final_costs=final_costs,
            trip_brief=trip_brief,
        )

        # 9. Invoke Agent 2: Hotel Recommendation Agent
        hotel_output = self.hotel_agent.run(
            request=request,
            destination=destination,
            hotel=final_hotel,
            final_costs=final_costs,
            was_optimized=(final_tiers["hotel_tier"] != request.hotel_tier),
            trip_brief=trip_brief,
        )

        # 10. Invoke Agent 3: Transport Planning Agent
        transport_output = self.transport_agent.run(
            request=request,
            destination=destination,
            transport_tier=final_tiers["transport_tier"],  # type: ignore
            final_costs=final_costs,
            was_optimized=(final_tiers["transport_tier"] != request.transport_tier),
            trip_brief=trip_brief,
        )

        # 11. Invoke Agent 4: Food Planning Agent
        food_output = self.food_agent.run(
            request=request,
            destination=destination,
            food_tier=final_tiers["food_tier"],  # type: ignore
            final_costs=final_costs,
            was_optimized=(final_tiers["food_tier"] != request.food_tier),
            trip_brief=trip_brief,
        )

        # 12. Invoke Agent 5: Budget Optimization Agent
        budget_output = self.budget_agent.run(
            request=request,
            initial_costs=initial_costs,
            final_costs=final_costs,
            passes=passes,
            budget_status=budget_status,
            balance_or_shortfall=balance_or_shortfall,
            is_shortfall=is_shortfall,
            trip_brief=trip_brief,
        )

        # Add shortfall context or alternatives note to budget agent recommendations if shortfall exists
        if is_shortfall and cheaper_alternatives:
            top_alt = cheaper_alternatives[0]
            budget_output.recommendations.append(
                f"Alternative Suggestion: {top_alt.destination_name} has an Economy estimate of "
                f"INR ₹{top_alt.estimated_economy_cost:,.2f} ({top_alt.note})."
            )

        agent_reports = {
            "travel_planner": travel_output,
            "hotel_advisor": hotel_output,
            "transport_planner": transport_output,
            "food_planner": food_output,
            "budget_optimizer": budget_output,
        }

        return CompleteTripPlan(
            request=request,
            trip_brief=trip_brief,
            destination=destination,
            selected_hotel=final_hotel,
            initial_costs=initial_costs,
            final_costs=final_costs,
            selected_tiers=final_tiers,
            optimization_history=passes,
            budget_status=budget_status,  # type: ignore
            initial_difference=initial_diff,
            savings_achieved=savings_achieved,
            remaining_balance_or_shortfall=balance_or_shortfall,
            is_shortfall=is_shortfall,
            itinerary=itinerary_days,
            agent_reports=agent_reports,
            option_comparisons=option_comparisons,
            cheaper_alternatives=cheaper_alternatives,
        )
