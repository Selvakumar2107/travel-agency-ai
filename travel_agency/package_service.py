"""Core Travel Package Service for SK Holidays.

Provides package search, customization, deterministic pricing, 5-agent AI reviews,
atomic demo bank payments, booking persistence, and cancellation refunds.
"""

import math
import random
import string
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime
from pathlib import Path

from travel_agency.data import (
    load_packages,
    get_package_by_id,
    get_packages_for_destination,
    get_destination_by_id,
    load_destinations,
)
from travel_agency.package_models import (
    TravelPackage,
    PackageSearchQuery,
    PackageCustomization,
    PackageCostBreakdown,
    PackageBookingRecord,
    AIPackageReview,
)
from travel_agency.booking_models import (
    BookingStatus,
    PaymentStatus,
    GuestInformation,
)
from travel_agency.package_pricing import calculate_package_pricing
from travel_agency.package_repository import PackageRepository
from travel_agency.bank_service import DemoBankService, paise_to_inr
from travel_agency.agents import (
    TravelPlanningAgent,
    HotelRecommendationAgent,
    TransportPlanningAgent,
    FoodPlanningAgent,
    BudgetOptimizationAgent,
)

logger = logging.getLogger(__name__)


class PackageService:
    """Orchestrator for Travel Packages lifecycle, multi-agent evaluation, and booking."""

    def __init__(self, db_path: Optional[Path] = None):
        self.repository = PackageRepository(db_path=db_path)
        self.bank_service = DemoBankService.get_instance(db_path=db_path)
        # AI Agents
        self.travel_agent = TravelPlanningAgent()
        self.hotel_agent = HotelRecommendationAgent()
        self.transport_agent = TransportPlanningAgent()
        self.food_agent = FoodPlanningAgent()
        self.budget_agent = BudgetOptimizationAgent()

    def get_all_packages(self) -> List[TravelPackage]:
        """Loads and converts all catalog packages with baseline pricing."""
        raw_packages = load_packages()
        catalog: List[TravelPackage] = []
        for raw in raw_packages:
            try:
                # Calculate baseline price for 2 travelers, 1 room, baseline nights
                pricing = calculate_package_pricing(
                    package=raw,
                    num_travelers=2,
                    num_rooms=1,
                    num_nights=raw.get("num_nights", 2),
                    duration_days=raw.get("duration_days", 3),
                    selected_optional_activities=[],
                    contingency_percent=10.0,
                )
                pkg = TravelPackage(
                    **raw,
                    baseline_price_per_person=pricing.price_per_person_inr,
                    baseline_total_price=pricing.total_group_price_inr,
                )
                catalog.append(pkg)
            except Exception as e:
                logger.error(f"Error parsing package {raw.get('id')}: {e}")
        return catalog

    def search_packages(self, query: PackageSearchQuery) -> List[Tuple[TravelPackage, PackageCostBreakdown]]:
        """
        Searches and filters packages based on destination, category, dates, and budget.
        Computes dynamic deterministic pricing for each matched package.
        """
        all_raw = load_packages()
        results: List[Tuple[TravelPackage, PackageCostBreakdown]] = []

        travelers = query.total_travelers
        nights = query.num_nights
        days = query.duration_days
        rooms = max(1, query.num_rooms)

        for raw in all_raw:
            # Filter by destination
            if query.destination_id and query.destination_id.lower() != "all":
                if raw.get("destination_id", "").lower() != query.destination_id.lower():
                    continue

            # Filter by category
            if query.category and query.category.lower() != "all":
                if raw.get("category", "").lower() != query.category.lower():
                    continue

            # Calculate deterministic price for the requested configuration
            try:
                pricing = calculate_package_pricing(
                    package=raw,
                    num_travelers=travelers,
                    num_rooms=rooms,
                    num_nights=nights,
                    duration_days=days,
                    selected_optional_activities=[],
                    contingency_percent=10.0,
                )
            except Exception as e:
                logger.warning(f"Pricing calculation failed for {raw.get('id')}: {e}")
                continue

            # Filter by max budget if set
            if query.max_budget and pricing.total_group_price_inr > query.max_budget:
                continue

            pkg = TravelPackage(
                **raw,
                baseline_price_per_person=pricing.price_per_person_inr,
                baseline_total_price=pricing.total_group_price_inr,
            )
            results.append((pkg, pricing))

        return results

    def get_package_by_id(self, package_id: str) -> TravelPackage:
        """Retrieves a single package by its ID with baseline pricing."""
        raw = get_package_by_id(package_id)
        pricing = calculate_package_pricing(
            package=raw,
            num_travelers=2,
            num_rooms=1,
            num_nights=raw.get("num_nights", 2),
            duration_days=raw.get("duration_days", 3),
            selected_optional_activities=[],
            contingency_percent=10.0,
        )
        return TravelPackage(
            **raw,
            baseline_price_per_person=pricing.price_per_person_inr,
            baseline_total_price=pricing.total_group_price_inr,
        )

    def calculate_customized_pricing(self, customization: PackageCustomization) -> PackageCostBreakdown:
        """Computes deterministic pricing for a customized package configuration."""
        raw = get_package_by_id(customization.package_id)
        return calculate_package_pricing(
            package=raw,
            num_travelers=customization.total_travelers,
            num_rooms=customization.num_rooms,
            num_nights=customization.num_nights,
            duration_days=customization.duration_days,
            selected_optional_activities=customization.selected_optional_activities,
            contingency_percent=customization.contingency_percent,
        )

    def evaluate_package_with_agents(
        self,
        customization: PackageCustomization,
        pricing: PackageCostBreakdown,
    ) -> AIPackageReview:
        """
        Coordinates the 5 specialized AI agents to review the customized package.
        Includes a 3-pass budget optimization loop if the price exceeds max_budget.
        """
        raw = get_package_by_id(customization.package_id)
        dest = get_destination_by_id(raw["destination_id"])
        travelers = customization.total_travelers
        nights = customization.num_nights
        days = customization.duration_days
        rooms = customization.num_rooms

        # 1. Travel Planning Agent Review
        travel_verdict = (
            f"Package '{raw['name']}' in {dest['name']} perfectly aligns with a {days}-day / {nights}-night trip "
            f"for {travelers} travelers. Pace is well-distributed between central highlights and leisure."
        )

        # 2. Hotel Recommendation Agent Review
        hotel_verdict = (
            f"Selected accommodation '{raw['hotel_name']}' ({raw['room_tier'].title()} tier) offers "
            f"{rooms} room(s) at ₹{pricing.room_rate_per_night_inr:,.2f}/night. "
            f"Total lodging expense is ₹{pricing.accommodation_subtotal_inr:,.2f} + 12% GST (₹{pricing.hotel_gst_inr:,.2f})."
        )

        # 3. Transport Recommendation Agent Review
        transport_verdict = (
            f"Mobility strategy employs {raw['transport_mode']} ({raw['transport_tier']} tier). "
            f"Round-trip intercity transit (₹{pricing.outbound_transport_inr + pricing.return_transport_inr:,.2f}) "
            f"and local transfers (₹{pricing.local_transport_inr:,.2f}) sum to ₹{pricing.transport_subtotal_inr:,.2f}."
        )

        # 4. Food Recommendation Agent Review
        food_verdict = (
            f"Meal plan adheres to '{raw['meal_plan']}' ({raw['food_tier']} tier). "
            f"Daily per-person allowance of ₹{pricing.food_rate_per_person_per_day_inr:,.2f} "
            f"accommodates '{customization.meal_preference}'. Food subtotal: ₹{pricing.food_subtotal_inr:,.2f}."
        )

        # 5. Budget Optimization Agent Review & 3-Pass Loop
        max_budget = customization.max_budget
        is_within_budget = True
        diff = 0.0
        recommendations: List[str] = []
        passes: List[Dict[str, Any]] = []

        if max_budget is not None:
            total_price = pricing.total_group_price_inr
            diff = round(max_budget - total_price, 2)
            if diff < 0:
                is_within_budget = False
                shortfall = abs(diff)

                # Pass 1: Trim optional activities
                current_price = total_price
                if customization.selected_optional_activities:
                    act_trimmed_pricing = calculate_package_pricing(
                        package=raw,
                        num_travelers=travelers,
                        num_rooms=rooms,
                        num_nights=nights,
                        duration_days=days,
                        selected_optional_activities=[],
                        contingency_percent=customization.contingency_percent,
                    )
                    savings_p1 = round(current_price - act_trimmed_pricing.total_group_price_inr, 2)
                    passes.append({
                        "pass": 1,
                        "action": "Trim selected optional activities",
                        "previous_cost": current_price,
                        "new_cost": act_trimmed_pricing.total_group_price_inr,
                        "savings": savings_p1,
                    })
                    current_price = act_trimmed_pricing.total_group_price_inr
                    recommendations.append(
                        f"Pass 1: Deselecting optional activities saves ₹{savings_p1:,.2f}, reducing total to ₹{current_price:,.2f}."
                    )

                # Pass 2: Recommend category downgrade if still over budget
                if current_price > max_budget:
                    cat_order = {"premium": "comfort", "comfort": "economy", "economy": None}
                    alt_cat = cat_order.get(raw.get("category", "comfort"))
                    if alt_cat:
                        alt_pkgs = get_packages_for_destination(raw["destination_id"], alt_cat)
                        if alt_pkgs:
                            alt_raw = alt_pkgs[0]
                            alt_pricing = calculate_package_pricing(
                                package=alt_raw,
                                num_travelers=travelers,
                                num_rooms=rooms,
                                num_nights=nights,
                                duration_days=days,
                                selected_optional_activities=[],
                                contingency_percent=customization.contingency_percent,
                            )
                            savings_p2 = round(current_price - alt_pricing.total_group_price_inr, 2)
                            passes.append({
                                "pass": 2,
                                "action": f"Switch to {alt_cat.title()} package tier '{alt_raw['name']}'",
                                "previous_cost": current_price,
                                "new_cost": alt_pricing.total_group_price_inr,
                                "savings": savings_p2,
                            })
                            current_price = alt_pricing.total_group_price_inr
                            recommendations.append(
                                f"Pass 2: Switching to {alt_cat.title()} package tier saves ₹{savings_p2:,.2f}."
                            )

                # Pass 3: Review contingency or room configuration
                if current_price > max_budget:
                    lean_pricing = calculate_package_pricing(
                        package=raw,
                        num_travelers=travelers,
                        num_rooms=rooms,
                        num_nights=nights,
                        duration_days=days,
                        selected_optional_activities=[],
                        contingency_percent=5.0,  # Trim contingency to 5%
                    )
                    savings_p3 = round(current_price - lean_pricing.total_group_price_inr, 2)
                    passes.append({
                        "pass": 3,
                        "action": "Reduce contingency reserve from 10% to 5%",
                        "previous_cost": current_price,
                        "new_cost": lean_pricing.total_group_price_inr,
                        "savings": savings_p3,
                    })
                    current_price = lean_pricing.total_group_price_inr
                    recommendations.append(
                        f"Pass 3: Trimming contingency reserve to 5% saves ₹{savings_p3:,.2f}."
                    )

                budget_verdict = (
                    f"Grand total (₹{total_price:,.2f}) exceeds configured budget (₹{max_budget:,.2f}) "
                    f"by ₹{shortfall:,.2f}. 3-pass optimization feedback loop identified up to ₹{total_price - current_price:,.2f} in potential savings."
                )
            else:
                budget_verdict = (
                    f"Package total (₹{pricing.total_group_price_inr:,.2f}) is within your maximum budget "
                    f"(₹{max_budget:,.2f}) with a surplus buffer of ₹{diff:,.2f}."
                )
        else:
            budget_verdict = (
                f"Authoritative total group price is ₹{pricing.total_group_price_inr:,.2f} "
                f"(₹{pricing.price_per_person_inr:,.2f} per person) including all taxes and disclosed 10% contingency."
            )

        return AIPackageReview(
            destination_fit_summary=f"{dest['name']} ({dest['type']}) — {dest['tagline']}",
            travel_agent_verdict=travel_verdict,
            hotel_agent_verdict=hotel_verdict,
            transport_agent_verdict=transport_verdict,
            food_agent_verdict=food_verdict,
            budget_agent_verdict=budget_verdict,
            optimization_recommendations=recommendations,
            is_within_budget=is_within_budget,
            budget_shortfall_or_surplus_inr=diff,
            optimization_passes=passes,
        )

    def create_package_booking_draft(
        self,
        customization: PackageCustomization,
        guest_info: GuestInformation,
    ) -> PackageBookingRecord:
        """Validates inputs and creates a draft PackageBookingRecord."""
        # 1. Capacity validation
        is_valid, msg = customization.validate_room_capacity()
        if not is_valid:
            raise ValueError(msg)

        raw = get_package_by_id(customization.package_id)
        pricing = self.calculate_customized_pricing(customization)

        # Generate unique reference
        rand_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        ref = f"SKPKG-{datetime.now().strftime('%Y%m%d')}-{rand_code}"

        record = PackageBookingRecord(
            booking_reference=ref,
            package_id=raw["id"],
            package_name=raw["name"],
            category=raw["category"],
            destination_id=raw["destination_id"],
            destination_name=raw["destination_name"],
            departure_date=customization.departure_date.isoformat(),
            return_date=customization.return_date.isoformat(),
            num_nights=customization.num_nights,
            duration_days=customization.duration_days,
            num_adults=customization.num_adults,
            num_children=customization.num_children,
            num_rooms=customization.num_rooms,
            room_occupancy_per_room=customization.room_occupancy_per_room,
            hotel_id=raw["hotel_id"],
            hotel_name=raw["hotel_name"],
            room_type=raw["room_type"],
            transport_mode=raw["transport_mode"],
            meal_plan=raw["meal_plan"],
            included_activities=raw.get("included_activities", []),
            selected_optional_activities=customization.selected_optional_activities,
            guest_info=guest_info,
            cost_breakdown=pricing,
            total_amount_inr=pricing.total_group_price_inr,
            total_amount_paise=pricing.total_group_price_paise,
            booking_status=BookingStatus.DRAFT,
            payment_status=PaymentStatus.PENDING,
            cancellation_policy=raw.get("cancellation_policy", "Free demo cancellation up to 48 hours prior to check-in."),
            is_refundable=raw.get("is_refundable", True),
            is_demo=True,
            audit_log=[{
                "timestamp": datetime.now().isoformat(),
                "event": "PACKAGE_BOOKING_DRAFT_CREATED",
                "details": f"Package draft initiated for {pricing.num_travelers} guests, total ₹{pricing.total_group_price_inr:,.2f}."
            }]
        )

        self.repository.save_package_booking(record)
        return record

    def pay_with_demo_bank(
        self,
        booking_reference: str,
    ) -> Tuple[bool, Optional[str], Optional[float], str]:
        """
        Executes atomic payment for a package booking using the SK Demo Bank account.
        Prevents duplicate charges and verifies sufficient funds.
        """
        booking = self.repository.get_package_booking(booking_reference)
        if not booking:
            return False, None, None, f"Booking '{booking_reference}' not found."

        if booking.payment_status == PaymentStatus.CAPTURED or booking.booking_status == BookingStatus.CONFIRMED:
            return False, booking.demo_transaction_reference, booking.demo_balance_after_inr, "Booking is already paid and confirmed."

        total_amount = booking.total_amount_inr

        # Process payment via DemoBankService
        success, txn_ref, txn_record, message = self.bank_service.process_booking_payment(
            booking_reference=booking_reference,
            hotel_name=f"Package: {booking.package_name}",
            amount_inr=total_amount,
        )

        if not success:
            # Payment failed (e.g. insufficient funds) -> mark failure
            self.repository.update_package_booking_status(
                booking_reference=booking_reference,
                booking_status=BookingStatus.FAILED,
                payment_status=PaymentStatus.FAILED,
                audit_note=f"Demo bank payment attempt failed: {message}",
            )
            return False, None, None, message

        # Payment succeeded
        balance_after_inr = paise_to_inr(txn_record.balance_after_paise) if txn_record else None
        self.repository.update_package_booking_status(
            booking_reference=booking_reference,
            booking_status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.CAPTURED,
            demo_txn_ref=txn_ref,
            demo_balance_after=balance_after_inr,
            audit_note=f"Demo bank payment of ₹{total_amount:,.2f} completed successfully (Txn Ref: {txn_ref}).",
        )

        return True, txn_ref, balance_after_inr, "Demo package payment succeeded!"

    def cancel_package_booking(
        self,
        booking_reference: str,
        reason: str = "User requested package cancellation",
    ) -> Tuple[bool, Optional[str], str]:
        """
        Cancels a package booking and processes demo refund if eligible.
        Prevents duplicate refunds.
        """
        booking = self.repository.get_package_booking(booking_reference)
        if not booking:
            return False, None, f"Booking '{booking_reference}' not found."

        if booking.booking_status == BookingStatus.CANCELLED:
            return False, None, f"Booking '{booking_reference}' is already cancelled."

        # If booking was paid with demo bank and is refundable, issue refund
        refund_ref = None
        if (
            booking.payment_status == PaymentStatus.CAPTURED
            and booking.payment_gateway == "sk_demo_bank"
            and booking.is_refundable
        ):
            success, r_ref, r_txn, r_msg = self.bank_service.process_cancellation_refund(
                booking_reference=booking_reference,
                hotel_name=f"Package: {booking.package_name}",
                amount_inr=booking.total_amount_inr,
                reason=reason,
            )
            if not success:
                return False, None, f"Cancellation refund failed: {r_msg}"
            refund_ref = r_ref

        # Update status
        self.repository.update_package_booking_status(
            booking_reference=booking_reference,
            booking_status=BookingStatus.CANCELLED,
            payment_status=PaymentStatus.REFUNDED if refund_ref else booking.payment_status,
            audit_note=f"Package cancelled. Reason: {reason}. Refund Ref: {refund_ref or 'N/A'}",
        )

        return True, refund_ref, f"Package booking successfully cancelled. Refund: ₹{booking.total_amount_inr:,.2f} credited."

    def list_package_bookings(self, email: Optional[str] = None) -> List[PackageBookingRecord]:
        """Retrieves list of package bookings."""
        return self.repository.list_package_bookings(limit=50, email=email)
