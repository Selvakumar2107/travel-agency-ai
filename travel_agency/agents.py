"""Specialized AI Agents for SK Holidays Travel Agency powered by Google Gemini API & Google ADK architecture.

Features 5 collaborative agents:
1. Travel Planning Agent (Main coordinator, preference analyst & master itinerary architect)
2. Hotel Recommendation Agent (Lodging specialist, GST calculator & capacity auditor)
3. Transport Planning Agent (Mobility strategist & group transit estimator)
4. Food Planning Agent (Culinary advisor, dietary compliance & allergen consultant)
5. Budget Optimization Agent (Deterministic numerical auditor & multi-pass feedback optimizer)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

from travel_agency.models import (
    TripRequest,
    StructuredTripBrief,
    CostBreakdown,
    OptimizationPass,
    AgentOutput,
    DayItinerary,
    HotelTier,
    FoodTier,
    TransportTier,
    ActivityTier,
)
from travel_agency.data import (
    get_destination_by_id,
    get_hotels_for_destination,
    get_activities_for_destination,
    get_food_tier,
    get_transport_tier,
)
from travel_agency.scoring import (
    score_destination_match,
    evaluate_hotel_recommendation,
    evaluate_transport_tier,
    evaluate_food_tier,
)
from travel_agency.logging_utils import AgentExecutionLogger, log_fallback_event

logger = logging.getLogger(__name__)

# Check Google GenAI availability
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class BaseAgent:
    """Base class for specialized AI agents providing Google Gemini integration, prompt management, and safety wrappers."""

    def __init__(self, name: str, role: str, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        self.name = name
        self.role = role
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.client = None

        if HAS_GENAI and self.api_key and self.api_key.strip() and not self.api_key.startswith("your_"):
            try:
                self.client = genai.Client(api_key=self.api_key.strip())
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI Client for {self.name}: {e}")
                self.client = None

    def call_gemini(self, prompt: str, system_instruction: str) -> Optional[str]:
        """Safely invokes Google Gemini API with error handling for timeouts and rate limits."""
        if not self.client:
            return None

        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=1500,
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                return response.text.strip()
            return None
        except Exception as e:
            logger.error(f"Gemini API invocation error in {self.name}: {e}")
            return None


class TravelPlanningAgent(BaseAgent):
    """Agent 1: Destination Matching, Traveler Preference Analyst & Master Itinerary Architect."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        super().__init__(
            name="Travel Planning Agent",
            role="Trip Coordinator & Master Itinerary Architect",
            api_key=api_key,
            model_name=model_name,
        )

    def create_structured_trip_brief(
        self,
        request: TripRequest,
        destination: Dict[str, Any],
        final_costs: CostBreakdown,
        final_tiers: Dict[str, str],
    ) -> StructuredTripBrief:
        """Establishes the central normalized trip brief used across all collaborating agents."""
        dest_name = destination.get("name", "Curated Destination")
        budget_per_person = round(request.total_budget / max(1, request.num_travelers), 2)
        return StructuredTripBrief(
            origin=request.starting_location,
            destination_id=destination["id"],
            destination_name=dest_name,
            num_travelers=request.num_travelers,
            trip_duration_days=request.trip_duration_days,
            num_nights=final_costs.num_nights,
            num_rooms=final_costs.num_rooms,
            total_budget=request.total_budget,
            budget_per_person=budget_per_person,
            travel_style=request.travel_style,
            preferred_pace=request.preferred_pace,
            dietary_preference=request.dietary_preference,
            allergies=request.allergies,
            accessibility_requirements=request.accessibility_requirements,
            interests=request.interests,
            target_tiers=final_tiers,
        )

    def run(
        self,
        request: TripRequest,
        destination: Dict[str, Any],
        final_tiers: Dict[str, str],
        final_costs: CostBreakdown,
        trip_brief: Optional[StructuredTripBrief] = None,
    ) -> Tuple[AgentOutput, List[DayItinerary]]:
        """Generates destination rationale, pacing considerations, logical sequencing, and day-by-day itinerary."""
        with AgentExecutionLogger(self.name, "itinerary_generation") as tracker:
            dest_name = destination.get("name", "Destination")
            dest_type = destination.get("type", "Getaway")
            tagline = destination.get("tagline", "")
            interests_str = ", ".join(request.interests) if request.interests else "General Sightseeing"
            activities = get_activities_for_destination(destination["id"], final_tiers.get("activity_tier"))

            # Calculate destination recommendation score
            dest_score, score_breakdown, match_highlights = score_destination_match(
                destination=destination,
                interests=request.interests,
                travel_style=request.travel_style,
                total_budget=request.total_budget,
            )

            system_instruction = (
                "You are the Travel Planning Agent in an Agentic AI Travel Agency. "
                "Your role is the master trip coordinator and preference analyst. "
                "CRITICAL RULES: Use only provided destination catalog facts. "
                "Never invent live weather, real-time ticket availability, or live prices. "
                "Respect the traveler's stated travel style, preferred pace, and dietary preferences."
            )

            user_prompt = (
                f"Trip Brief: Destination {dest_name} ({dest_type}) - '{tagline}'\n"
                f"Origin: {request.starting_location} | Travelers: {request.num_travelers} | Duration: {request.trip_duration_days} days\n"
                f"Budget: INR {request.total_budget:,.2f} (INR {round(request.total_budget / request.num_travelers, 2):,.2f} per person)\n"
                f"Travel Style: {request.travel_style.title()} | Preferred Pace: {request.preferred_pace.title()}\n"
                f"Interests: {interests_str} | Dietary Preference: {request.dietary_preference}\n"
                f"Accessibility: {', '.join(request.accessibility_requirements) if request.accessibility_requirements else 'None'}\n"
                f"Activity Tier: {final_tiers.get('activity_tier')}\n"
                f"Catalog Highlights: {[a.get('name') for a in activities[:4]]}\n\n"
                "Synthesize a cohesive trip strategy explaining destination fit, daily pacing, and sightseeing logic."
            )

            gemini_text = self.call_gemini(user_prompt, system_instruction)
            used_gemini = gemini_text is not None

            if not used_gemini:
                log_fallback_event(self.name, "Google Gemini API key not provided or offline; using deterministic template")

            # Determine transit time estimate and activity slots by preferred pace
            pace = request.preferred_pace
            if pace == "relaxed":
                transit_note = "Relaxed pacing: ~15-25 mins transit between sights; ample rest time"
            elif pace == "fast_paced":
                transit_note = "Fast-paced schedule: ~35-50 mins transfer window between multiple attractions"
            else:
                transit_note = "Balanced pacing: ~20-30 mins scenic transfer between morning and afternoon stops"

            # Determine diet note for dining highlight
            diet = request.dietary_preference.lower()
            if "jain" in diet:
                diet_note = "Sattvic vegetarian dining without root vegetables, onion, or garlic"
            elif "vegan" in diet:
                diet_note = "100% plant-based meal, free from dairy, ghee, and animal derivatives"
            elif "vegetarian" in diet:
                diet_note = "Pure lacto-vegetarian regional cuisine (paneer, lentils, fresh veggies)"
            elif "halal" in diet:
                diet_note = "Halal-certified regional dining or pure vegetarian specialties"
            else:
                diet_note = "Regional culinary highlights (seafood/poultry or local vegetarian thali)"

            # Build day-by-day itinerary
            itinerary_days: List[DayItinerary] = []
            catalog_acts = destination.get("suggested_activities", [])
            acts_count = len(catalog_acts)

            daily_act_cost = round(final_costs.activities / max(1, request.trip_duration_days), 2)
            daily_food_cost = round(final_costs.food / max(1, request.trip_duration_days), 2)
            estimated_day_cost = round(daily_act_cost + daily_food_cost, 2)

            for day_num in range(1, request.trip_duration_days + 1):
                act1 = catalog_acts[(day_num * 2 - 2) % acts_count] if acts_count else "Scenic heritage exploration"
                act2 = catalog_acts[(day_num * 2 - 1) % acts_count] if acts_count else "Nature walk and viewpoint"

                if day_num == 1:
                    title = f"Day 1: Arrival & Welcome to {dest_name}"
                    morning = f"Morning arrival from {request.starting_location}, private/express transfer to hotel, check-in and refresh."
                    afternoon = f"Gentle orientation walk and relaxed discovery at {act1}."
                    evening = "Golden-hour promenade through local cultural markets; welcome orientation."
                    dining = f"Traditional welcome dinner featuring {diet_note}."
                    tips = "Acclimatize to local weather, carry light layers, and keep booking reference handy."
                elif day_num == request.trip_duration_days:
                    title = f"Day {day_num}: Final Sightseeing & Departure"
                    morning = f"Early morning excursion to {act1} for sunrise views and artisan shopping."
                    afternoon = "Hotel check-out, luggage assistance, and leisurely lunch before transit."
                    evening = f"Comfortable return transit to {request.starting_location} with cherished memories."
                    dining = f"Farewell regional lunch ({diet_note}) at a reputable heritage cafe."
                    tips = "Review hotel check-out inventory and confirm departure transfer times."
                else:
                    title = f"Day {day_num}: Immersive Discovery in {dest_name}"
                    morning = f"Morning guided visit to {act1} during the freshest hours of the day."
                    afternoon = f"Afternoon curated visit to {act2} with scenic photo opportunities."
                    evening = "Sunset vantage point stroll followed by leisure time at local cafes."
                    dining = f"Selected dinner at a recommended dining spot ({diet_note})."
                    tips = "Wear comfortable walking shoes and stay hydrated."

                itinerary_days.append(
                    DayItinerary(
                        day=day_num,
                        title=title,
                        morning=morning,
                        afternoon=afternoon,
                        evening=evening,
                        dining_highlight=dining,
                        tips=tips,
                        estimated_transit_time=transit_note,
                        dietary_alignment_note=f"Aligned with {request.dietary_preference}",
                        estimated_day_cost=estimated_day_cost,
                    )
                )

            summary = gemini_text if used_gemini else (
                f"**{dest_name}** ({dest_type}) is our curated recommendation for your {request.travel_style.title()} journey! "
                f"Tagline: *'{tagline}'*. Tailored for {request.num_travelers} traveler(s) over {request.trip_duration_days} days "
                f"with a {request.preferred_pace.title()} pace and {request.dietary_preference} dining focus. "
                f"Destination Compatibility Score: **{dest_score}/100**."
            )

            recommendations = [
                f"Destination Score: {dest_score}/100 (Preference Match: {score_breakdown['preference_match']}%, Affordability: {score_breakdown['affordability']}%)",
                f"Pacing: Designed with {request.preferred_pace.title()} scheduling to eliminate transit fatigue.",
                f"Dietary: All daily dining highlights tailored to {request.dietary_preference}.",
            ] + match_highlights[:2]

            source_ids = [destination["id"]] + [a.get("name", "") for a in activities[:3]]

            agent_output = AgentOutput(
                agent_name=self.name,
                agent_role=self.role,
                summary=summary,
                recommendations=recommendations,
                key_metrics={
                    "destination": dest_name,
                    "region": destination.get("state"),
                    "duration_days": request.trip_duration_days,
                    "travelers": request.num_travelers,
                    "travel_style": request.travel_style,
                    "preferred_pace": request.preferred_pace,
                    "dietary_preference": request.dietary_preference,
                    "destination_score": dest_score,
                },
                used_gemini=used_gemini,
                raw_response=gemini_text,
                source_data_ids=source_ids,
                trade_offs=[
                    f"Selected {dest_name} over farther domestic hubs to optimize transit time from {request.starting_location}",
                    f"Paced across {request.trip_duration_days} days to balance sightseeing highlights with downtime",
                ],
                pros=["High preference alignment", "Reliable domestic road/rail connectivity", "Curated regional dining"],
                cons=["Peak season may experience afternoon tourist footfall at viewpoints"],
                scoring_breakdown=score_breakdown,
                is_fallback=not used_gemini,
                execution_time_ms=tracker.duration_ms,
            )

            return agent_output, itinerary_days


class HotelRecommendationAgent(BaseAgent):
    """Agent 2: Hotel & Accommodation Advisor, Capacity Auditor & 12% GST Lodging Evaluator."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        super().__init__(
            name="Hotel Recommendation Agent",
            role="Accommodation Specialist & Lodging Evaluator",
            api_key=api_key,
            model_name=model_name,
        )

    def run(
        self,
        request: TripRequest,
        destination: Dict[str, Any],
        hotel: Dict[str, Any],
        final_costs: CostBreakdown,
        was_optimized: bool = False,
        trip_brief: Optional[StructuredTripBrief] = None,
    ) -> AgentOutput:
        """Evaluates accommodation options, room occupancy, GST calculations, and budget trade-offs."""
        with AgentExecutionLogger(self.name, "hotel_evaluation") as tracker:
            hotel_name = hotel.get("name", "Recommended Hotel")
            hotel_tier = hotel.get("tier", "standard").capitalize()
            price_per_night = float(hotel.get("price_per_night", 2500))
            amenities_str = ", ".join(hotel.get("amenities", []))

            # Base room math
            subtotal_rooms = round(price_per_night * final_costs.num_rooms * final_costs.num_nights, 2)
            gst_amount = round(subtotal_rooms * 0.12, 2)
            final_hotel_cost = round(subtotal_rooms + gst_amount, 2)

            # Evaluate scoring and pros/cons
            score, score_breakdown, pros, cons = evaluate_hotel_recommendation(
                hotel=hotel,
                travel_style=request.travel_style,
                total_budget=request.total_budget,
                num_rooms=final_costs.num_rooms,
                num_nights=final_costs.num_nights,
                accessibility_requirements=request.accessibility_requirements,
            )

            system_instruction = (
                "You are the Hotel Recommendation Agent in an Agentic AI Travel Agency. "
                "Analyze lodging fit, capacity rules, 12% GST taxes, and cost tradeoffs. "
                "CRITICAL RULES: Only recommend hotels loaded from dataset. "
                "Never invent hotel names or claim real-time live booking availability."
            )

            user_prompt = (
                f"Hotel: {hotel_name} ({hotel_tier} Tier)\n"
                f"Destination: {destination.get('name')}\n"
                f"Base Rate: INR {price_per_night}/night | Rooms: {final_costs.num_rooms} | Nights: {final_costs.num_nights}\n"
                f"Room Subtotal: INR {subtotal_rooms} + Estimated 12% GST: INR {gst_amount} = Total: INR {final_hotel_cost}\n"
                f"Travel Style: {request.travel_style.title()} | Total Budget: INR {request.total_budget}\n"
                f"Amenities: {amenities_str}\n"
                f"Adjusted by Budget Feedback: {was_optimized}\n\n"
                "Explain why this property suits the traveler, evaluate trade-offs, and state accommodation math."
            )

            gemini_text = self.call_gemini(user_prompt, system_instruction)
            used_gemini = gemini_text is not None

            if not used_gemini:
                log_fallback_event(self.name, "Gemini offline; using deterministic lodging analysis")

            opt_note = " (Adjusted via budget feedback to preserve feasibility)" if was_optimized else ""
            summary = gemini_text if used_gemini else (
                f"Recommended Property: **{hotel_name}** ({hotel_tier} Tier){opt_note}. "
                f"Located in {destination.get('name')}, rated ★ {hotel.get('rating', 4.2)}/5.0. "
                f"Configured for {final_costs.num_rooms} double-occupancy room(s) over {final_costs.num_nights} night(s). "
                f"Base lodging: INR ₹{subtotal_rooms:,.2f} + 12% GST (INR ₹{gst_amount:,.2f}) = Final Stay Total: **INR ₹{final_hotel_cost:,.2f}**."
            )

            budget_share = round((final_hotel_cost / request.total_budget) * 100, 1)
            trade_offs = [
                f"Accommodation consumes {budget_share}% of total trip budget (healthy target is 35-45%)",
                f"Double occupancy room capacity: {final_costs.num_rooms} room(s) for {request.num_travelers} guest(s)",
            ]
            if budget_share > 45.0:
                trade_offs.append("Lodging consumes over 45% of budget; consider exploring budget tier to free up activity funds.")

            recommendations = [
                f"Hotel Rating: ★ {hotel.get('rating', 4.2)} / 5.0 (Score: {score}/100)",
                f"Total Lodging: INR ₹{final_hotel_cost:,.2f} (Base ₹{subtotal_rooms:,.2f} + 12% GST ₹{gst_amount:,.2f})",
                f"Allocation: {final_costs.num_rooms} room(s) × {final_costs.num_nights} night(s)",
                f"Key Amenities: {amenities_str}",
                "Notice: Fictional dataset hotel for planning estimates. No real-time reservation created.",
            ]

            return AgentOutput(
                agent_name=self.name,
                agent_role=self.role,
                summary=summary,
                recommendations=recommendations,
                key_metrics={
                    "hotel_name": hotel_name,
                    "tier": hotel_tier,
                    "price_per_night_inr": price_per_night,
                    "rooms_required": final_costs.num_rooms,
                    "nights": final_costs.num_nights,
                    "subtotal_inr": subtotal_rooms,
                    "gst_12_percent_inr": gst_amount,
                    "total_stay_inr": final_hotel_cost,
                    "rating": hotel.get("rating", 4.2),
                    "budget_share_percent": budget_share,
                    "hotel_score": score,
                },
                used_gemini=used_gemini,
                raw_response=gemini_text,
                source_data_ids=[hotel.get("id", "hotel-default")],
                trade_offs=trade_offs,
                pros=pros,
                cons=cons,
                scoring_breakdown=score_breakdown,
                is_fallback=not used_gemini,
                execution_time_ms=tracker.duration_ms,
            )


class TransportPlanningAgent(BaseAgent):
    """Agent 3: Transit & Intercity/Local Mobility Advisor."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        super().__init__(
            name="Transport Planning Agent",
            role="Mobility & Logistics Strategist",
            api_key=api_key,
            model_name=model_name,
        )

    def run(
        self,
        request: TripRequest,
        destination: Dict[str, Any],
        transport_tier: TransportTier,
        final_costs: CostBreakdown,
        was_optimized: bool = False,
        trip_brief: Optional[StructuredTripBrief] = None,
    ) -> AgentOutput:
        """Analyzes intercity transit and local in-city mobility estimates."""
        with AgentExecutionLogger(self.name, "transport_evaluation") as tracker:
            tier_info = get_transport_tier(transport_tier)
            dest_name = destination.get("name", "Destination")
            total_transport = round(final_costs.intercity_transport + final_costs.local_transport, 2)

            score, pros, cons = evaluate_transport_tier(
                transport_tier=transport_tier,
                num_travelers=request.num_travelers,
                total_budget=request.total_budget,
                travel_style=request.travel_style,
            )

            system_instruction = (
                "You are the Transport Planning Agent in an Agentic AI Travel Agency. "
                "Analyze intercity and local transport estimates based strictly on provided dummy datasets. "
                "Never invent flight schedules, seat numbers, or live booking confirmations."
            )

            user_prompt = (
                f"Origin: {request.starting_location} -> Destination: {dest_name}\n"
                f"Transport Tier: {tier_info.get('name')} ({transport_tier})\n"
                f"Travelers: {request.num_travelers} | Trip Duration: {request.trip_duration_days} days\n"
                f"Intercity Round-Trip Group Cost: INR {final_costs.intercity_transport}\n"
                f"Local City Mobility ({request.trip_duration_days} days): INR {final_costs.local_transport}\n"
                f"Total Transport Cost: INR {total_transport}\n"
                f"Adjusted by Budget Feedback: {was_optimized}\n\n"
                "Explain the transit trade-offs, group vehicle allocation, and cost practicality."
            )

            gemini_text = self.call_gemini(user_prompt, system_instruction)
            used_gemini = gemini_text is not None

            if not used_gemini:
                log_fallback_event(self.name, "Gemini offline; using deterministic mobility estimates")

            opt_note = " (Optimized to stay within target budget)" if was_optimized else ""
            summary = gemini_text if used_gemini else (
                f"Selected Mobility Plan: **{tier_info.get('name')}**{opt_note}. "
                f"{tier_info.get('description')} "
                f"Round-trip intercity connection: INR ₹{final_costs.intercity_transport:,.2f} for {request.num_travelers} traveler(s). "
                f"Daily local commuting over {request.trip_duration_days} days: INR ₹{final_costs.local_transport:,.2f}. "
                f"Combined Transit Total: **INR ₹{total_transport:,.2f}**."
            )

            recommendations = [
                f"Intercity Route: {request.starting_location} ↔ {dest_name} (₹{final_costs.intercity_transport:,.2f})",
                f"Local Commute: ₹{final_costs.local_transport:,.2f} across {request.trip_duration_days} day(s)",
                "Mobility Advice: Pre-book transfers during peak arrival windows to avoid surge rates.",
                "Notice: Illustrative estimates from dummy transport dataset. No tickets booked.",
            ]

            return AgentOutput(
                agent_name=self.name,
                agent_role=self.role,
                summary=summary,
                recommendations=recommendations,
                key_metrics={
                    "transport_tier": transport_tier,
                    "intercity_cost_inr": final_costs.intercity_transport,
                    "local_cost_inr": final_costs.local_transport,
                    "total_transport_cost_inr": total_transport,
                    "transit_score": score,
                },
                used_gemini=used_gemini,
                raw_response=gemini_text,
                source_data_ids=[f"transport-{transport_tier}"],
                trade_offs=[
                    f"Selected {transport_tier} tier balances group comfort with overall budget allocation",
                    f"Local mobility allocated across full {request.trip_duration_days}-day duration",
                ],
                pros=pros,
                cons=cons,
                is_fallback=not used_gemini,
                execution_time_ms=tracker.duration_ms,
            )


class FoodPlanningAgent(BaseAgent):
    """Agent 4: Culinary & Meal Expense Strategist, Dietary Compliance & Allergen Consultant."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        super().__init__(
            name="Food Planning Agent",
            role="Culinary Advisor & Dietary Consultant",
            api_key=api_key,
            model_name=model_name,
        )

    def run(
        self,
        request: TripRequest,
        destination: Dict[str, Any],
        food_tier: FoodTier,
        final_costs: CostBreakdown,
        was_optimized: bool = False,
        trip_brief: Optional[StructuredTripBrief] = None,
    ) -> AgentOutput:
        """Estimates food expenses per person per day, tailors menus to dietary restrictions, and provides allergen notices."""
        with AgentExecutionLogger(self.name, "food_evaluation") as tracker:
            tier_info = get_food_tier(food_tier)
            dest_name = destination.get("name", "Destination")
            daily_rate = float(tier_info.get("cost_per_person_per_day", 1200))
            diet = request.dietary_preference

            score, pros, cons = evaluate_food_tier(
                food_tier=food_tier,
                dietary_preference=request.dietary_preference,
                allergies=request.allergies,
            )

            # Tailor sample meals according to dietary preference
            diet_lower = diet.lower()
            if "jain" in diet_lower:
                sample_breakfast = "Jain poha, steamed idli, banana pancake, herbal chai"
                sample_lunch = "Pure Jain thali with dal, paneer curry (no onion/garlic), phulkas, rice"
                sample_dinner = "Jain khichdi, kadhi, dry fruit biryani (no potato/root veggies)"
            elif "vegan" in diet_lower:
                sample_breakfast = "Steamed idlis with coconut chutney, fresh fruit platter, black coffee"
                sample_lunch = "Plant-based regional vegetable stew with appam, sambar rice (dairy-free)"
                sample_dinner = "Tofu/vegetable curry with roti, yellow dal tadka, tender coconut dessert"
            elif "vegetarian" in diet_lower:
                sample_breakfast = "South Indian masala dosa, vada, filter coffee or parathas with curd"
                sample_lunch = "Unlimited vegetarian regional thali with paneer, dal, rasam, curd"
                sample_dinner = "Paneer butter masala, naan, jeera rice, gulab jamun"
            else:
                sample_breakfast = tier_info.get("sample_meals", {}).get("breakfast", "Traditional breakfast platter")
                sample_lunch = tier_info.get("sample_meals", {}).get("lunch", "Multi-cuisine or regional thali")
                sample_dinner = tier_info.get("sample_meals", {}).get("dinner", "Regional culinary specialty dinner")

            system_instruction = (
                "You are the Food Planning Agent in an Agentic AI Travel Agency. "
                "Provide dining guidance and meal expense estimation using dummy food datasets. "
                "CRITICAL RULES: Respect stated dietary restrictions (Jain, Vegan, Vegetarian). "
                "Never guarantee allergy cross-contamination controls based on AI assumptions."
            )

            user_prompt = (
                f"Destination: {dest_name} | Food Plan: {tier_info.get('name')} ({food_tier})\n"
                f"Daily Rate per Person: INR {daily_rate} | Travelers: {request.num_travelers} | Days: {request.trip_duration_days}\n"
                f"Total Food Cost: INR {final_costs.food}\n"
                f"Dietary Preference: {diet}\n"
                f"Known Allergies: {', '.join(request.allergies) if request.allergies else 'None'}\n"
                f"Sample Meals: Breakfast: {sample_breakfast} | Lunch: {sample_lunch} | Dinner: {sample_dinner}\n"
                f"Adjusted by Budget Feedback: {was_optimized}\n\n"
                "Summarize meal plan, dietary compatibility, and practical savings tips."
            )

            gemini_text = self.call_gemini(user_prompt, system_instruction)
            used_gemini = gemini_text is not None

            if not used_gemini:
                log_fallback_event(self.name, "Gemini offline; using deterministic culinary plan")

            opt_note = " (Adjusted to meet budget targets)" if was_optimized else ""
            summary = gemini_text if used_gemini else (
                f"Selected Dining Strategy: **{tier_info.get('name')}** ({diet}){opt_note}. "
                f"{tier_info.get('description')} "
                f"Calculated at INR ₹{daily_rate:,.2f} per person per day across {request.num_travelers} traveler(s) for "
                f"{request.trip_duration_days} days, amounting to a total meal budget of **INR ₹{final_costs.food:,.2f}**."
            )

            allergy_warning = (
                "⚠️ Allergen Notice: Menu estimates are derived from dummy datasets. Restaurants cannot be guaranteed "
                "to accommodate severe allergies without direct customer verification with kitchen staff."
            )

            recommendations = [
                f"Daily Dining Allowance: INR ₹{daily_rate:,.2f} per traveler per day",
                f"Dietary Compliance: 100% curated for {diet} preferences",
                f"Sample Breakfast: {sample_breakfast}",
                f"Sample Lunch: {sample_lunch}",
                f"Sample Dinner: {sample_dinner}",
                allergy_warning,
            ] + [f"Savings Tip: {tip}" for tip in tier_info.get("saving_tips", [])[:2]]

            return AgentOutput(
                agent_name=self.name,
                agent_role=self.role,
                summary=summary,
                recommendations=recommendations,
                key_metrics={
                    "food_tier": food_tier,
                    "daily_cost_per_person_inr": daily_rate,
                    "total_food_cost_inr": final_costs.food,
                    "dietary_preference": diet,
                    "food_score": score,
                },
                used_gemini=used_gemini,
                raw_response=gemini_text,
                source_data_ids=[f"food-{food_tier}"],
                trade_offs=[
                    f"Selected {food_tier} dining maintains balanced culinary discovery within INR ₹{daily_rate:,.0f}/day",
                    f"All recommendations strictly respect {diet} requirements",
                ],
                pros=pros,
                cons=cons,
                is_fallback=not used_gemini,
                execution_time_ms=tracker.duration_ms,
            )


class BudgetOptimizationAgent(BaseAgent):
    """Agent 5: Financial Auditor & Deterministic Budget Optimization Specialist."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        super().__init__(
            name="Budget Optimization Agent",
            role="Financial Auditor & Budget Optimization Specialist",
            api_key=api_key,
            model_name=model_name,
        )

    def run(
        self,
        request: TripRequest,
        initial_costs: CostBreakdown,
        final_costs: CostBreakdown,
        passes: List[OptimizationPass],
        budget_status: str,
        balance_or_shortfall: float,
        is_shortfall: bool,
        trip_brief: Optional[StructuredTripBrief] = None,
    ) -> AgentOutput:
        """Audits deterministic trip costs vs budget, explains substitutions, and enforces rules."""
        with AgentExecutionLogger(self.name, "budget_audit") as tracker:
            user_budget = request.total_budget
            initial_total = initial_costs.total_estimated_cost
            final_total = final_costs.total_estimated_cost
            savings = round(initial_total - final_total, 2)

            system_instruction = (
                "You are the Budget Optimization Agent in an Agentic AI Travel Agency. "
                "Audit financial totals calculated by deterministic Python functions. "
                "CRITICAL RULES: Authoritative calculations come exclusively from Python. "
                "Never fabricate discounts, prices, or savings. Respect minimum ₹3,000 budget."
            )

            actions_taken = [p.action_taken for p in passes]
            user_prompt = (
                f"User Target Budget: INR {user_budget}\n"
                f"Initial Estimated Cost: INR {initial_total}\n"
                f"Final Estimated Cost: INR {final_total}\n"
                f"Total Savings Achieved: INR {savings}\n"
                f"Optimization Passes: {len(passes)} (Max allowed: 3)\n"
                f"Actions Applied: {actions_taken}\n"
                f"Final Budget Status: {budget_status}\n"
                f"Surplus/Shortfall: INR {balance_or_shortfall} (Is shortfall: {is_shortfall})\n"
                f"Cost Components: Accommodation={final_costs.hotel_accommodation}, "
                f"Transport={final_costs.intercity_transport + final_costs.local_transport}, "
                f"Food={final_costs.food}, Activities={final_costs.activities}, "
                f"Contingency Reserve (10%)={final_costs.contingency_reserve}\n\n"
                "Provide an honest financial audit, highlighting highest expense categories and substitution rationale."
            )

            gemini_text = self.call_gemini(user_prompt, system_instruction)
            used_gemini = gemini_text is not None

            if not used_gemini:
                log_fallback_event(self.name, "Gemini offline; using deterministic financial summary")

            if budget_status == "within_budget":
                status_text = (
                    f"Your preferred travel choices fit within your INR ₹{user_budget:,.2f} budget without requiring "
                    f"any automatic tier downgrades. Remaining surplus: INR ₹{balance_or_shortfall:,.2f}."
                )
            elif budget_status == "optimized_within_budget":
                status_text = (
                    f"The initial estimate of INR ₹{initial_total:,.2f} exceeded your budget (INR ₹{user_budget:,.2f}). "
                    f"Through {len(passes)} deterministic optimization pass(es), we achieved INR ₹{savings:,.2f} in verified savings, "
                    f"bringing the final estimate to INR ₹{final_total:,.2f} (Under budget with INR ₹{balance_or_shortfall:,.2f} surplus)."
                )
            else:
                status_text = (
                    f"Despite applying all {len(passes)} optimization pass(es) to achieve maximum savings of INR ₹{savings:,.2f}, "
                    f"the lowest feasible estimate is INR ₹{final_total:,.2f}. This leaves an unresolvable shortfall of INR ₹{balance_or_shortfall:,.2f}. "
                    f"To make this trip viable, consider choosing a nearby destination or increasing your budget to at least INR ₹{final_total:,.2f}."
                )

            summary = gemini_text if used_gemini else (
                f"Financial Audit Complete. **Status: {budget_status.replace('_', ' ').title()}**. {status_text}"
            )

            recommendations = [
                f"Target Budget: INR ₹{user_budget:,.2f} | Final Cost: INR ₹{final_total:,.2f}",
                f"Contingency Reserve: INR ₹{final_costs.contingency_reserve:,.2f} (10% emergency buffer included)",
                f"Cost per Traveler: INR ₹{final_costs.cost_per_person:,.2f} for {request.num_travelers} guest(s)",
            ]

            if passes:
                for p in passes:
                    recommendations.append(f"Pass {p.pass_number}: {p.action_taken} (Saved ₹{p.savings:,.2f})")
            if is_shortfall:
                recommendations.append(
                    f"⚠️ Budget Shortfall: INR ₹{balance_or_shortfall:,.2f}. Trip duration and party size were strictly preserved."
                )

            trade_offs = [
                f"Deterministic Math Guarantee: All prices computed by pure Python arithmetic with zero LLM guesswork",
                f"10% contingency reserve (₹{final_costs.contingency_reserve:,.2f}) shields travelers from unexpected on-trip fees",
            ]

            return AgentOutput(
                agent_name=self.name,
                agent_role=self.role,
                summary=summary,
                recommendations=recommendations,
                key_metrics={
                    "user_budget_inr": user_budget,
                    "initial_cost_inr": initial_total,
                    "final_cost_inr": final_total,
                    "savings_achieved_inr": savings,
                    "optimization_passes_count": len(passes),
                    "budget_status": budget_status,
                    "contingency_reserve_inr": final_costs.contingency_reserve,
                    "is_shortfall": is_shortfall,
                    "remaining_balance_or_shortfall_inr": balance_or_shortfall,
                },
                used_gemini=used_gemini,
                raw_response=gemini_text,
                source_data_ids=[f"pass-{p.pass_number}" for p in passes] if passes else ["pass-0-direct"],
                trade_offs=trade_offs,
                pros=["100% deterministic arithmetic", "Essential preferences preserved", "Transparent itemized costs"],
                cons=["Budget shortfall requires traveler compromise if initial budget was very tight"] if is_shortfall else [],
                substitutions_suggested=actions_taken,
                is_fallback=not used_gemini,
                execution_time_ms=tracker.duration_ms,
            )
