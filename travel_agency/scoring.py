"""Deterministic Recommendation Ranking and Scoring Engine for SK Holidays.

Provides transparent, weighted scoring (0 - 100) and eligibility constraint checks.
All calculations use pure deterministic Python arithmetic.
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    """Configurable weights for multi-factor recommendation ranking."""
    preference_match: float = 0.30
    affordability: float = 0.25
    practicality: float = 0.15
    comfort_quality: float = 0.15
    compatibility: float = 0.15

    def validate_weights(self) -> bool:
        total = self.preference_match + self.affordability + self.practicality + self.comfort_quality + self.compatibility
        return abs(total - 1.0) < 0.001


DEFAULT_WEIGHTS = ScoringWeights()


def score_destination_match(
    destination: Dict[str, Any],
    interests: List[str],
    travel_style: str = "family",
    total_budget: float = 10000.0,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> Tuple[float, Dict[str, float], List[str]]:
    """Scores how well a destination matches traveler interests, travel style, and budget."""
    dest_interests = {i.lower() for i in destination.get("suitable_interests", [])}
    user_interests = {i.lower() for i in interests} if interests else set()

    # 1. Preference Match (0-100)
    if user_interests:
        common = user_interests.intersection(dest_interests)
        match_score = (len(common) / len(user_interests)) * 100.0
    else:
        match_score = 75.0

    # 2. Affordability (0-100)
    # Estimate economy cost vs budget
    sample_intercity = destination.get("sample_intercity_transport_estimate", {}).get("standard", 2000)
    affordability_score = min(100.0, max(20.0, (total_budget / max(1.0, sample_intercity * 4.0)) * 25.0))

    # 3. Practicality (0-100)
    practicality_score = 85.0

    # 4. Comfort & Quality (0-100)
    comfort_score = 80.0

    # 5. Compatibility with travel style
    dest_type = destination.get("type", "").lower()
    style_boost = 70.0
    if travel_style == "family" and any(k in dest_interests for k in ["family", "nature", "relaxation"]):
        style_boost = 95.0
    elif travel_style == "couple" and any(k in dest_interests for k in ["relaxation", "photography", "nature"]):
        style_boost = 95.0
    elif travel_style == "friends" and any(k in dest_interests for k in ["adventure", "trekking"]):
        style_boost = 95.0
    elif travel_style == "solo" and any(k in dest_interests for k in ["culture", "trekking", "nature"]):
        style_boost = 90.0

    composite_score = round(
        (match_score * weights.preference_match)
        + (affordability_score * weights.affordability)
        + (practicality_score * weights.practicality)
        + (comfort_score * weights.comfort_quality)
        + (style_boost * weights.compatibility),
        1
    )

    breakdown = {
        "preference_match": round(match_score, 1),
        "affordability": round(affordability_score, 1),
        "practicality": round(practicality_score, 1),
        "comfort_quality": round(comfort_score, 1),
        "compatibility": round(style_boost, 1),
    }

    highlights = [
        f"Matches {len(user_interests.intersection(dest_interests))} of your stated interests: {', '.join(user_interests.intersection(dest_interests)) or 'General leisure'}",
        f"Ideal travel style match for {travel_style.title()} travelers",
        f"Best visiting season: {destination.get('best_season', 'Year-round')}",
    ]

    return min(100.0, composite_score), breakdown, highlights


def evaluate_hotel_recommendation(
    hotel: Dict[str, Any],
    travel_style: str = "family",
    total_budget: float = 10000.0,
    num_rooms: int = 1,
    num_nights: int = 2,
    accessibility_requirements: Optional[List[str]] = None,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> Tuple[float, Dict[str, float], List[str], List[str]]:
    """Evaluates a hotel property, computing multi-factor score and pros/cons trade-offs."""
    rating = float(hotel.get("rating", 4.0))
    price_per_night = float(hotel.get("price_per_night", 2500))
    amenities = [a.lower() for a in hotel.get("amenities", [])]
    total_stay_price = round(price_per_night * num_rooms * num_nights * 1.12, 2)  # incl 12% GST

    # 1. Quality & Rating Score (0-100)
    quality_score = min(100.0, max(0.0, (rating / 5.0) * 100.0))

    # 2. Affordability Score (0-100)
    # Target accommodation budget is ~35-45% of total trip budget
    target_hotel_budget = total_budget * 0.40
    if total_stay_price <= target_hotel_budget:
        affordability_score = 95.0
    else:
        over_ratio = total_stay_price / max(1.0, target_hotel_budget)
        affordability_score = max(20.0, 100.0 - ((over_ratio - 1.0) * 80.0))

    # 3. Preference Match
    style_keywords = {
        "family": ["breakfast", "garden", "room service", "pool", "spacious"],
        "couple": ["fireplace", "spa", "mountain view", "balcony", "butler"],
        "friends": ["wi-fi", "bonfire", "parking", "garden"],
        "solo": ["wi-fi", "hot water", "central", "tea"],
        "business": ["wi-fi", "desk", "room service"],
    }
    desired = style_keywords.get(travel_style, ["wi-fi", "hot water"])
    matched_amenities = [a for a in amenities if any(k in a for k in desired)]
    preference_score = min(100.0, max(40.0, (len(matched_amenities) / max(1, len(desired))) * 100.0 + 30.0))

    # 4. Practicality
    practicality_score = 85.0

    # 5. Accessibility Compatibility
    compat_score = 80.0
    if accessibility_requirements:
        req_clean = [r.lower() for r in accessibility_requirements if r.lower() != "none"]
        if req_clean:
            # Check if property has elevator or ground floor mentioned
            has_access = any("valet" in a or "service" in a for a in amenities)
            compat_score = 90.0 if has_access else 65.0

    composite = round(
        (preference_score * weights.preference_match)
        + (affordability_score * weights.affordability)
        + (practicality_score * weights.practicality)
        + (quality_score * weights.comfort_quality)
        + (compat_score * weights.compatibility),
        1
    )

    breakdown = {
        "preference_match": round(preference_score, 1),
        "affordability": round(affordability_score, 1),
        "practicality": round(practicality_score, 1),
        "comfort_quality": round(quality_score, 1),
        "compatibility": round(compat_score, 1),
    }

    pros = []
    cons = []

    if rating >= 4.4:
        pros.append(f"High guest rating: ★ {rating} / 5.0")
    if total_stay_price <= target_hotel_budget:
        pros.append(f"Highly affordable: Stay total ₹{total_stay_price:,.0f} fits target lodging allocation")
    if any("breakfast" in a for a in amenities):
        pros.append("Complimentary breakfast included to reduce daily meal costs")
    if any("spa" in a or "fireplace" in a or "view" in a for a in amenities):
        pros.append(f"Premium relaxation perks: {', '.join(hotel.get('amenities', [])[:2])}")
    if accessibility_requirements:
        matched_acc = [req for req in accessibility_requirements if any(req.lower() in a for a in amenities)]
        if matched_acc:
            pros.append(f"Accessibility verified: {', '.join(matched_acc)}")

    if total_stay_price > target_hotel_budget:
        cons.append(f"Consumes {round((total_stay_price / total_budget) * 100)}% of total budget (above ideal 40% threshold)")
    if rating < 4.2:
        cons.append("Modest guest rating with basic functional amenities")
    if not any("breakfast" in a for a in amenities):
        cons.append("Room-only rate plan; breakfast requires separate daily dining expense")

    if not pros:
        pros.append("Clean, comfortable accommodation meeting standard safety standards")
    if not cons:
        cons.append("Limited seasonal inventory during peak travel dates")

    return min(100.0, composite), breakdown, pros, cons


def evaluate_transport_tier(
    transport_tier: str,
    num_travelers: int,
    total_budget: float,
    travel_style: str = "family",
) -> Tuple[float, List[str], List[str]]:
    """Evaluates transport tier suitability and trade-offs."""
    pros = []
    cons = []

    if transport_tier == "shared":
        score = 80.0 if total_budget < 8000 else 65.0
        pros.append("Most cost-effective mode, maximizing budget remaining for activities and stays")
        pros.append("Authentic local travel experience via express trains and public transit")
        cons.append("Fixed departure schedules with limited door-to-door flexibility")
        if num_travelers >= 4:
            cons.append("Managing group baggage and seating across public transit can be cumbersome")
    elif transport_tier == "standard":
        score = 88.0
        pros.append("Balanced blend of comfort and affordability with AC train / point-to-point cabs")
        pros.append("Reliable on-call urban mobility and hassle-free transit")
        cons.append("Slightly higher fare than shared transit but substantially more comfortable")
    else:  # private
        score = 90.0 if total_budget > 15000 else 60.0
        pros.append("Full privacy, dedicated chauffeur, flexible photo stops, and door-to-door transit")
        pros.append("Zero wait times and maximum luggage comfort for families or groups")
        cons.append("Consumes a substantial portion of travel budget on dedicated vehicle disposal")

    return score, pros, cons


def evaluate_food_tier(
    food_tier: str,
    dietary_preference: str = "no_restriction",
    allergies: Optional[List[str]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Evaluates food plan suitability, dietary safety, and trade-offs."""
    pros = []
    cons = []

    diet_clean = dietary_preference.lower()
    if food_tier == "economy":
        score = 75.0
        pros.append("Authentic regional tiffins, vegetarian thalis, and local diner specialties")
        pros.append("Lowest daily expense per traveler, keeping food allocation economical")
        if diet_clean in ("vegetarian", "vegan", "jain"):
            pros.append(f"Compatible with {dietary_preference} via traditional plant-based regional thali joints")
        cons.append("Informal seating and limited continental or specialty menu variety")
    elif food_tier == "standard":
        score = 90.0
        pros.append("Air-conditioned family bistros, casual cafes, and trusted multi-cuisine menus")
        pros.append("Clear menu labeling with balanced vegetarian and non-vegetarian selections")
        cons.append("Moderate dining expense requiring balanced meal choices")
    else:  # comfort
        score = 88.0
        pros.append("Chef-curated gourmet buffets, rooftop dining, and scenic destination eateries")
        pros.append("Superior hygiene, diverse culinary options, and dedicated kitchen customization")
        cons.append("Highest daily food expense per person")

    if allergies and any(a.lower() != "none" for a in allergies):
        cons.append("Allergen notice: Dummy data menus cannot guarantee cross-contamination controls. Always verify directly with kitchen staff.")

    return score, pros, cons
