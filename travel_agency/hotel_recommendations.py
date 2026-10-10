"""AI Hotel Recommendation Engine powered by Google Gemini API & Deterministic Grounding.

Ranks supplier-verified hotel inventory into three structured groups:
1. Best Budget Match
2. Best Value
3. Premium Experience

Grounded strictly in supplier facts; AI explains and ranks rather than fabricating prices.
"""

import os
import json
import logging
from typing import List, Optional, Tuple, Dict, Any

from travel_agency.booking_models import (
    HotelOffer,
    HotelSearchQuery,
    AIHotelRecommendationGroup,
)

logger = logging.getLogger(__name__)

# Check Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class AIHotelRecommendationService:
    """Specialized AI recommender ranking live or demo hotel inventory."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "").strip()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.client = None

        if HAS_GENAI and self.api_key and not self.api_key.startswith("your_"):
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not init GenAI client for hotel recommendations: {e}")
                self.client = None

    def call_gemini(self, prompt: str, system_instruction: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
                max_output_tokens=1500,
            )
            res = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            if res and res.text:
                return res.text.strip()
            return None
        except Exception as e:
            logger.error(f"Gemini hotel recommendation prompt error: {e}")
            return None

    def recommend(
        self,
        hotels: List[HotelOffer],
        query: HotelSearchQuery
    ) -> AIHotelRecommendationGroup:
        """
        Ranks and analyzes hotel offers into the 3 specified groups.
        Deterministic ranking serves as the solid ground truth, with Gemini providing
        personalized travel rationale.
        """
        if not hotels:
            return AIHotelRecommendationGroup(
                general_advice="No hotels matched your selected criteria. Try adjusting your filters or expanding your budget."
            )

        # 1. Deterministic Grounded Selection
        # Best Budget Match: lowest price meeting criteria
        sorted_by_price = sorted(hotels, key=lambda h: h.total_price)
        best_budget = sorted_by_price[0]

        # Best Value Match: composite score = rating / (price index) + amenity bonus
        def value_score(h: HotelOffer) -> float:
            score = (h.rating * 1000.0) / max(h.price_per_night, 1000.0)
            if "Breakfast Included" in (h.selected_room.meal_inclusion if h.selected_room else ""):
                score *= 1.15
            score += len(h.amenities) * 0.05
            return score

        sorted_by_value = sorted(hotels, key=value_score, reverse=True)
        # Choose a best value that isn't identical to best budget if alternatives exist
        best_value = None
        for h in sorted_by_value:
            if h.id != best_budget.id or len(hotels) == 1:
                best_value = h
                break
        if not best_value:
            best_value = sorted_by_value[0]

        # Premium Experience: highest tier / rating with comfort focus
        sorted_by_premium = sorted(
            hotels,
            key=lambda h: (1 if h.category in ("premium", "luxury") else 0, h.rating, h.price_per_night),
            reverse=True
        )
        premium_match = None
        for h in sorted_by_premium:
            if h.id not in (best_budget.id, best_value.id) or len(hotels) <= 2:
                premium_match = h
                break
        if not premium_match:
            premium_match = sorted_by_premium[0]

        # 2. Craft Grounded Explanations (Gemini with Fallbacks)
        dest_name = query.destination_id.capitalize()
        travel_style = query.travel_style or "family"

        system_instruction = (
            "You are the Hotel Recommendation Specialist for SK Holidays. "
            "Explain why the selected hotels fit three distinct personas: "
            "1. Best Budget Match (lowest price meeting requirements) "
            "2. Best Value (optimal balance of amenities, ratings, and price) "
            "3. Premium Experience (highest comfort, luxury feel, curated services). "
            "CRITICAL INSTRUCTION: Never fabricate prices, ratings, or room features. "
            "Keep all explanations grounded strictly in the provided verified supplier facts. "
            "Return concise, 2-line rationales for each."
        )

        user_prompt = (
            f"Destination: {dest_name}\n"
            f"Dates: {query.check_in_date} to {query.check_out_date} ({query.num_nights} nights)\n"
            f"Rooms: {query.num_rooms}, Adults: {query.num_adults}, Children: {query.num_children}\n"
            f"Travel Style: {travel_style}\n"
            f"Special Requirements: {query.special_requirements or 'None'}\n\n"
            f"1. Best Budget Candidate: {best_budget.name} | Total: INR {best_budget.total_price:,.2f} | Rating: {best_budget.rating} | Amenities: {', '.join(best_budget.amenities[:4])}\n"
            f"2. Best Value Candidate: {best_value.name} | Total: INR {best_value.total_price:,.2f} | Rating: {best_value.rating} | Amenities: {', '.join(best_value.amenities[:4])}\n"
            f"3. Premium Experience Candidate: {premium_match.name} | Total: INR {premium_match.total_price:,.2f} | Rating: {premium_match.rating} | Amenities: {', '.join(premium_match.amenities[:4])}\n\n"
            "Format your reply as JSON with keys: 'best_budget_rationale', 'best_value_rationale', 'premium_rationale', 'general_advice'."
        )

        gemini_response = self.call_gemini(user_prompt, system_instruction)

        b_rat, v_rat, p_rat, g_adv = "", "", "", ""
        if gemini_response:
            try:
                # Strip markdown code fencing if any
                clean_json = gemini_response.strip()
                if clean_json.startswith("```"):
                    clean_json = clean_json.split("\n", 1)[1]
                    if clean_json.endswith("```"):
                        clean_json = clean_json.rsplit("```", 1)[0]
                data = json.loads(clean_json.strip())
                b_rat = data.get("best_budget_rationale", "")
                v_rat = data.get("best_value_rationale", "")
                p_rat = data.get("premium_rationale", "")
                g_adv = data.get("general_advice", "")
            except Exception:
                pass

        # Robust deterministic fallbacks if LLM is unavailable or JSON parsing fails
        if not b_rat:
            b_rat = (
                f"Delivers the most cost-effective stay in {dest_name} at INR {best_budget.total_price:,.2f} total "
                f"while maintaining a trusted {best_budget.rating}★ rating and essential amenities ({', '.join(best_budget.amenities[:3])})."
            )
        if not v_rat:
            v_rat = (
                f"Strikes the sweet spot between comfort and price at INR {best_value.total_price:,.2f} total. "
                f"Boasts a {best_value.rating}★ guest rating with {best_value.review_count} verified reviews and superior location amenities."
            )
        if not p_rat:
            p_rat = (
                f"Elevated comfort and refined hospitality in {dest_name} at INR {premium_match.total_price:,.2f} total. "
                f"Features {premium_match.accommodation_type} accommodations, rated {premium_match.rating}★ with luxury amenities ({', '.join(premium_match.amenities[:3])})."
            )
        if not g_adv:
            g_adv = f"All rates include 12% GST and mandatory fees for {query.num_rooms} room(s) across {query.num_nights} night(s)."

        return AIHotelRecommendationGroup(
            best_budget_match=best_budget,
            best_budget_rationale=b_rat,
            best_value=best_value,
            best_value_rationale=v_rat,
            premium_experience=premium_match,
            premium_experience_rationale=p_rat,
            general_advice=g_adv,
            disclaimer="Recommendations ranked with AI. Prices, taxes, and policies are verified supplier facts."
        )


# Global recommender instance
_recommender_instance: Optional[AIHotelRecommendationService] = None


def get_hotel_recommendation_service() -> AIHotelRecommendationService:
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = AIHotelRecommendationService()
    return _recommender_instance
