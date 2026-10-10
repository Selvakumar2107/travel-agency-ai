"""High-End Streamlit UI Components for Hotel Discovery, Booking, Checkout, Confirmation, and Management.

Rebuilt 100% with native Streamlit components (containers, columns, images,
subheaders, captions, metrics, forms, dividers, and tabs) to guarantee zero raw HTML leakage.
"""

import os
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import streamlit as st

from travel_agency.booking_models import (
    HotelSearchQuery,
    HotelOffer,
    RoomOffer,
    GuestInformation,
    BookingStatus,
    PaymentStatus,
    HotelCategory,
    AccommodationType,
    HotelBookingRecord,
)
from travel_agency.hotel_provider import get_hotel_provider, LiveHotelProviderAdapter
from travel_agency.hotel_recommendations import get_hotel_recommendation_service
from travel_agency.booking_service import get_booking_service
from travel_agency.booking_repository import get_booking_repository
from travel_agency.payment_service import get_payment_provider, DemoPaymentProvider
from travel_agency.data import load_destinations


def render_hotel_discovery_page():
    """Renders the 'Find Hotels' search, AI recommendations, and discovery catalog."""
    hotel_provider = get_hotel_provider()
    recommender = get_hotel_recommendation_service()
    booking_service = get_booking_service()
    destinations = load_destinations()
    dest_names = [d["name"] for d in destinations]

    # Handle active sub-views (details, checkout, confirmation)
    if st.session_state.get("active_booking_view") == "hotel_details" and st.session_state.get("selected_hotel_offer"):
        render_hotel_detail_view(st.session_state.selected_hotel_offer)
        return
    elif st.session_state.get("active_booking_view") == "checkout" and st.session_state.get("checkout_offer"):
        render_checkout_view(st.session_state.checkout_offer, st.session_state.checkout_room)
        return
    elif st.session_state.get("active_booking_view") == "confirmation" and st.session_state.get("confirmed_booking"):
        render_confirmation_view(st.session_state.confirmed_booking)
        return

    # Section Header
    st.title("🏨 Curated Stays & AI Hotel Recommendations")
    st.caption(
        "Luxury Hotel Discovery & Booking • Explore verified hotel inventory across top destinations. "
        "Receive AI-grounded rankings and secure instant simulated bookings."
    )

    # Admin Integration Status & Demo Banner
    if isinstance(hotel_provider, LiveHotelProviderAdapter):
        admin_msg = hotel_provider.get_admin_status_message()
        if admin_msg["status"] == "DEMO_MODE":
            st.info(
                "ℹ️ **Simulated Inventory Active — Prototype Demo:** "
                "Live commercial hotel API credentials are not configured. Properties and room offers "
                "are curated demo data with mock availability."
            )

    # Search Form
    with st.container(border=True):
        st.subheader("🔍 Find Your Perfect Accommodation")

        col1, col2, col3 = st.columns([1.5, 1.2, 1.2])

        with col1:
            selected_city = st.selectbox(
                "Destination or City",
                options=["All Destinations"] + dest_names,
                index=0,
                help="Select your target holiday destination"
            )

        today = date.today()
        default_in = today + timedelta(days=7)
        default_out = today + timedelta(days=10)

        with col2:
            check_in = st.date_input(
                "Check-in Date",
                value=default_in,
                min_value=today,
                help="Check-in must be today or later"
            )

        with col3:
            check_out = st.date_input(
                "Check-out Date",
                value=default_out,
                min_value=check_in + timedelta(days=1),
                help="Check-out must be after check-in"
            )

        # Second row of search fields
        r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

        with r2_col1:
            num_rooms = st.number_input("Number of Rooms", min_value=1, max_value=10, value=1, step=1)
        with r2_col2:
            num_adults = st.number_input("Number of Adults", min_value=1, max_value=20, value=2, step=1)
        with r2_col3:
            num_children = st.number_input("Number of Children", min_value=0, max_value=10, value=0, step=1)
        with r2_col4:
            max_budget_opt = st.number_input(
                "Max Budget / Night (₹)",
                min_value=0,
                max_value=50000,
                value=0,
                step=500,
                help="Optional upper budget limit per night (0 for no limit)"
            )

        # Filters accordion
        with st.expander("⚙️ Advanced Preferences & Filters", expanded=False):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                category_opt = st.selectbox(
                    "Hotel Category",
                    options=["All Categories", "budget", "standard", "premium", "luxury"],
                    index=0
                )
                acc_type_opt = st.selectbox(
                    "Accommodation Type",
                    options=["All Types", "Hotel", "Resort", "Heritage Palace", "Boutique Villa", "Homestay / Eco Lodge"],
                    index=0
                )
            with f_col2:
                min_rating_opt = st.selectbox(
                    "Minimum Guest Rating",
                    options=["Any Rating", "3.5+ ★", "4.0+ ★", "4.5+ ★"],
                    index=0
                )
                travel_style = st.selectbox(
                    "Travel Party Style",
                    options=["Family Retreat", "Couple Getaway", "Solo Journey", "Group / Friends"],
                    index=0
                )
            with f_col3:
                amenities_selected = st.multiselect(
                    "Required Amenities",
                    options=["Free Wi-Fi", "Swimming Pool", "Luxury Spa", "Buffet Breakfast", "Air Conditioning", "Restaurant", "Mountain View", "Valet Parking"],
                    default=[]
                )
                special_reqs = st.text_input("Special Requests (e.g. ground floor, pure veg dining)", "")

        search_btn = st.button("🔎 Search Hotels", key="btn_main_search_hotels", type="primary", use_container_width=True)

    # Date Validation
    if check_out <= check_in:
        st.error("⚠️ Invalid dates: Check-out date must be strictly later than check-in date.")
        return

    # Prepare search query
    dest_id = "all"
    if selected_city != "All Destinations":
        for d in destinations:
            if d["name"] == selected_city:
                dest_id = d["id"]
                break

    category_enum = HotelCategory.ALL
    if category_opt != "All Categories":
        category_enum = HotelCategory(category_opt.lower())

    acc_enum = AccommodationType.ALL
    if acc_type_opt != "All Types":
        acc_enum = AccommodationType(acc_type_opt)

    min_rating_val = 0.0
    if min_rating_opt == "3.5+ ★":
        min_rating_val = 3.5
    elif min_rating_opt == "4.0+ ★":
        min_rating_val = 4.0
    elif min_rating_opt == "4.5+ ★":
        min_rating_val = 4.5

    query = HotelSearchQuery(
        destination_id=dest_id,
        check_in_date=check_in,
        check_out_date=check_out,
        num_rooms=int(num_rooms),
        num_adults=int(num_adults),
        num_children=int(num_children),
        max_budget_per_night=float(max_budget_opt) if max_budget_opt > 0 else None,
        category=category_enum,
        min_rating=min_rating_val,
        required_amenities=amenities_selected,
        accommodation_type=acc_enum,
        travel_style=travel_style.lower(),
        special_requirements=special_reqs if special_reqs else None
    )
    st.session_state.current_hotel_query = query

    # Perform Search
    with st.spinner("Searching hotel inventory and analyzing rates..."):
        results = hotel_provider.search_hotels(query)

    if not results:
        st.warning(
            "🏨 **No Hotels Match Your Exact Filters:** "
            "We could not find properties meeting all your current filter criteria. "
            "Try relaxing amenity constraints or increasing the maximum budget."
        )
        return

    # AI Recommendation Agent Section
    st.subheader("✨ AI Recommended Stays for Your Journey")
    st.caption("Grounded comparative evaluation matching your travel party style, dates, and budget parameters.")

    with st.spinner("AI evaluating best matches..."):
        ai_groups = recommender.recommend(results, query)

    # Render 3 AI Recommendation Cards
    ai_col1, ai_col2, ai_col3 = st.columns(3)

    if ai_groups.best_budget_match:
        with ai_col1:
            render_ai_badge_card(
                badge_title="🟢 Best Budget Match",
                badge_color="#0D8B72",
                offer=ai_groups.best_budget_match,
                rationale=ai_groups.best_budget_rationale,
                key_prefix="ai_budget"
            )

    if ai_groups.best_value:
        with ai_col2:
            render_ai_badge_card(
                badge_title="⭐ Best Value",
                badge_color="#101828",
                offer=ai_groups.best_value,
                rationale=ai_groups.best_value_rationale,
                key_prefix="ai_value"
            )

    if ai_groups.premium_experience:
        with ai_col3:
            render_ai_badge_card(
                badge_title="👑 Premium Experience",
                badge_color="#D6B46A",
                offer=ai_groups.premium_experience,
                rationale=ai_groups.premium_experience_rationale,
                key_prefix="ai_premium"
            )

    st.divider()

    # All Hotel Results
    st.subheader(f"All Available Properties ({len(results)})")
    st.caption(f"Showing verified rates for {query.num_rooms} room(s), {query.num_nights} night(s)")

    # Render Hotel Cards Grid
    grid_cols = st.columns(2)
    for idx, offer in enumerate(results):
        with grid_cols[idx % 2]:
            render_hotel_card(offer, key_prefix=f"res_{idx}")


def render_ai_badge_card(badge_title: str, badge_color: str, offer: HotelOffer, rationale: str, key_prefix: str):
    """Renders a highlighted card for the 3 AI recommendation categories using native widgets."""
    photo = offer.photos[0] if offer.photos else "https://images.unsplash.com/photo-1566073771259-6a8506099945"

    with st.container(border=True):
        c_top1, c_top2 = st.columns([2, 1])
        with c_top1:
            st.caption(f"🏷️ **{badge_title.upper()}**")
        with c_top2:
            st.caption(f"★ **{offer.rating}**")

        st.image(photo, use_container_width=True)
        st.subheader(offer.name)
        st.caption(f"📍 **{offer.city}** • {offer.accommodation_type}")

        st.info(f"🤖 **AI Rationale:** {rationale}")

        st.metric(
            label=f"Total ({offer.num_nights} nights incl. GST)",
            value=f"₹{offer.total_price:,.0f}"
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔍 View Details", key=f"{key_prefix}_det", use_container_width=True, type="secondary"):
                st.session_state.selected_hotel_offer = offer
                st.session_state.active_booking_view = "hotel_details"
                st.rerun()
        with c2:
            if st.button("💳 Reserve Stay", key=f"{key_prefix}_book", type="primary", use_container_width=True):
                st.session_state.checkout_offer = offer
                st.session_state.checkout_room = offer.selected_room or offer.rooms[0]
                st.session_state.active_booking_view = "checkout"
                st.rerun()


def render_hotel_card(offer: HotelOffer, key_prefix: str):
    """Renders a standard premium hotel card with verified facts using native widgets."""
    photo = offer.photos[0] if offer.photos else "https://images.unsplash.com/photo-1566073771259-6a8506099945"
    room = offer.selected_room or (offer.rooms[0] if offer.rooms else None)
    meal = room.meal_inclusion if room else "Room Only"
    cancel = room.cancellation_policy if room else "Standard Cancellation"

    with st.container(border=True):
        c_top1, c_top2 = st.columns([2, 1])
        with c_top1:
            st.caption(f":sparkles: **{offer.accommodation_type.upper()}**")
        with c_top2:
            st.caption(f"★ **{offer.rating}** ({offer.review_count} reviews)")

        st.image(photo, use_container_width=True)
        st.subheader(offer.name)
        st.caption(f"📍 {offer.address}")

        st.markdown(f"*{offer.description[:140]}...*")

        if offer.amenities:
            st.caption(" • ".join(offer.amenities[:4]))

        st.markdown(f"🍽️ **{meal}**  •  🛡️ **{cancel}**")

        st.divider()

        p1, p2 = st.columns(2)
        with p1:
            st.caption("PER NIGHT")
            st.markdown(f"### ₹{offer.price_per_night:,.0f}")
        with p2:
            st.caption(f"TOTAL ({offer.num_nights} NIGHTS INCL. GST)")
            st.markdown(f"### ₹{offer.total_price:,.0f}")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("🔍 View Details", key=f"{key_prefix}_vdet", use_container_width=True, type="secondary"):
                st.session_state.selected_hotel_offer = offer
                st.session_state.active_booking_view = "hotel_details"
                st.rerun()
        with b2:
            if st.button("💳 Reserve Stay", key=f"{key_prefix}_vbook", type="primary", use_container_width=True):
                st.session_state.checkout_offer = offer
                st.session_state.checkout_room = offer.selected_room or offer.rooms[0]
                st.session_state.active_booking_view = "checkout"
                st.rerun()


def render_hotel_detail_view(offer: HotelOffer):
    """Renders the dedicated Hotel Detail and Room Selection View using native widgets."""
    hotel_provider = get_hotel_provider()

    if st.button("← Back to Hotel Search", key="btn_back_to_hotel_search", type="secondary"):
        st.session_state.active_booking_view = None
        st.rerun()

    st.title(offer.name)
    st.caption(f"📍 {offer.address}  •  ★ {offer.rating} ({offer.review_count} verified reviews)  •  🏷️ {offer.accommodation_type}")

    # Photo Gallery
    p_cols = st.columns(3)
    for p_idx, p_url in enumerate(offer.photos[:3]):
        with p_cols[p_idx]:
            st.image(p_url, use_container_width=True)

    det_col1, det_col2 = st.columns([1.8, 1.2])

    with det_col1:
        with st.container(border=True):
            st.subheader("Property Overview")
            st.markdown(offer.description)

            st.subheader("Curated Luxury Amenities")
            for a in offer.amenities:
                st.markdown(f"- ✓ {a}")

            st.subheader("House & Check-in Rules")
            st.info(
                "• Standard Check-in: 14:00 | Standard Check-out: 11:00\n"
                "• Government-issued photo identification required at registration.\n"
                "• Complimentary valet parking and ultra-high-speed Wi-Fi included."
            )

        st.subheader("Select Room & Rate Plan")

        for r_idx, room in enumerate(offer.rooms):
            with st.container(border=True):
                st.subheader(room.room_name)
                st.caption(f"🛏️ {room.bed_type} • Max Occupancy: {room.max_occupancy} Guests")
                st.markdown(f"🍽️ **{room.meal_inclusion}**  •  🛡️ **{room.cancellation_policy}**")
                st.caption(" • ".join(room.features))

                st.metric("Rate Per Night", f"₹{room.base_price_per_night:,.0f}")

                if st.button(f"👉 Select {room.room_name} & Continue", key=f"sel_rm_{r_idx}", type="primary"):
                    with st.spinner("Rechecking live room availability with inventory engine..."):
                        is_avail, live_price, msg = hotel_provider.recheck_availability(offer.hotel_id, room.room_id)

                    if is_avail:
                        st.session_state.checkout_offer = offer
                        st.session_state.checkout_room = room
                        st.session_state.active_booking_view = "checkout"
                        st.rerun()
                    else:
                        st.error(f"⚠️ Room is no longer available: {msg}")

    with det_col2:
        subtotal = round(offer.price_per_night * offer.num_rooms * offer.num_nights, 2)
        taxes = round(subtotal * 0.12, 2)
        total = round(subtotal + taxes, 2)

        with st.container(border=True):
            st.subheader("Stay Price Breakdown")
            st.metric("Total Stay Price", f"₹{total:,.0f} INR")

            st.markdown(f"- **Base Room Rate:** ₹{offer.price_per_night:,.0f} / night")
            st.markdown(f"- **Duration & Rooms:** {offer.num_nights} nights × {offer.num_rooms} room(s)")
            st.markdown(f"- **Room Subtotal:** ₹{subtotal:,.2f}")
            st.markdown(f"- **Estimated Taxes (12% GST):** ₹{taxes:,.2f}")

            st.divider()
            st.caption("🛡️ **SK Holidays Guarantee:** Transparent luxury rates with no hidden resort fees.")


def render_checkout_view(offer: HotelOffer, room: RoomOffer):
    """Renders the secure Checkout view with server-side validation and payment launching."""
    booking_service = get_booking_service()
    payment_gateway = get_payment_gateway_instance()

    if st.button("← Back to Hotel Details", key="btn_back_to_hotel_details", type="secondary"):
        st.session_state.active_booking_view = "hotel_details"
        st.rerun()

    st.title("Confirm & Pay Reservation")
    st.caption("🔒 Luxury Concierge Checkout • Complete lead guest details and proceed to secure online demo payment authorization.")

    subtotal = round(room.base_price_per_night * offer.num_rooms * offer.num_nights, 2)
    taxes = round(subtotal * 0.12, 2)
    total_payable = round(subtotal + taxes, 2)

    with st.form("checkout_guest_form", clear_on_submit=False):
        c_left, c_right = st.columns([1.7, 1.3])

        with c_left:
            st.subheader("Lead Traveler Information")
            st.caption("Please ensure guest credentials match government-issued identification.")

            lead_name = st.text_input(
                "Full Name (as on Government ID)*",
                value=st.session_state.get("chk_lead_name", st.session_state.get("lead_name", "")),
                key="chk_lead_name",
                placeholder="e.g. Selvakumar S",
                help="Name of the primary guest who will check into the hotel"
            )
            em_col, ph_col = st.columns(2)
            with em_col:
                lead_email = st.text_input(
                    "Email Address*",
                    value=st.session_state.get("chk_lead_email", st.session_state.get("lead_email", "")),
                    key="chk_lead_email",
                    placeholder="e.g. selvakumar2113sk@gmail.com",
                    help="Official booking voucher and confirmation will be sent here"
                )
            with ph_col:
                lead_phone = st.text_input(
                    "Contact Phone Number*",
                    value=st.session_state.get("chk_lead_phone", st.session_state.get("lead_phone", "+91 ")),
                    key="chk_lead_phone",
                    placeholder="e.g. +91 9655331391",
                    help="Hotel front desk contact for arrival coordination"
                )

            special_req = st.text_area(
                "Special Requests (Optional)",
                value=st.session_state.get("chk_special_req", ""),
                key="chk_special_req",
                placeholder="e.g. Quiet high floor room, early check-in, vegetarian breakfast preference",
                help="Sent directly to hotel front desk."
            )
            accepted_terms = st.checkbox(
                f"I agree to the Booking Policies, {room.cancellation_policy}, and SK Holidays Terms of Service.",
                value=st.session_state.get("chk_accepted_terms", True),
                key="chk_accepted_terms"
            )

        with c_right:
            with st.container(border=True):
                st.subheader("Booking Summary")
                st.markdown(f"**{offer.name}**  •  📍 {offer.city}")
                st.caption(f"Room: {room.room_name}  •  🍽️ {room.meal_inclusion}")

                st.markdown(f"- **Duration:** {offer.num_nights} nights ({offer.num_rooms} room)")
                st.markdown(f"- **Base Room Subtotal:** ₹{subtotal:,.2f}")
                st.markdown(f"- **Taxes & Fees (12% GST):** ₹{taxes:,.2f}")

                st.divider()
                st.metric("Final Amount", f"₹{total_payable:,.2f}")
                st.caption(f"🛡️ **Cancellation:** {room.cancellation_policy}")

            gateway_is_live = payment_gateway.is_live_mode()
            badge_text = "Razorpay Live Mode" if gateway_is_live else "Razorpay Sandbox / Test Mode"
            st.caption(f"Payment Gateway: **{badge_text}** (Currency: INR)")

            submit_checkout = st.form_submit_button("💳 Proceed to Online Payment", type="primary", use_container_width=True)

        if submit_checkout:
            name_val = (lead_name or st.session_state.get("chk_lead_name", "")).strip()
            email_val = (lead_email or st.session_state.get("chk_lead_email", "")).strip()
            phone_val = (lead_phone or st.session_state.get("chk_lead_phone", "")).strip()

            if not email_val and "@" in name_val:
                email_val = name_val
                name_val = name_val.split("@")[0].replace(".", " ").title()
            elif not name_val and "@" not in email_val and len(email_val) >= 2:
                name_val = email_val

            st.session_state["lead_name"] = name_val
            st.session_state["lead_email"] = email_val
            st.session_state["lead_phone"] = phone_val

            validation_errors = []
            if len(name_val) < 2:
                validation_errors.append("Please enter Full Name (at least 2 characters) for the lead traveler.")
            if not email_val or "@" not in email_val or "." not in email_val.split("@")[-1]:
                validation_errors.append("Please enter a valid Email Address (e.g., selvakumar2113sk@gmail.com).")
            digits_only = "".join(c for c in phone_val if c.isdigit())
            if len(digits_only) < 8:
                validation_errors.append("Please enter a valid Contact Phone Number with at least 8 digits.")
            if not accepted_terms:
                validation_errors.append("You must agree to the Booking Policies and Terms of Service to proceed.")

            if validation_errors:
                for err in validation_errors:
                    st.error(f"⚠️ {err}")
                return

            try:
                guest_info = GuestInformation(
                    lead_guest_name=name_val,
                    email=email_val,
                    phone=phone_val,
                    special_requests=special_req,
                    accepted_terms=accepted_terms,
                )
            except Exception as e:
                st.error(f"⚠️ Validation error: {e}")
                return

            with st.spinner("Initializing booking and creating payment order..."):
                curr_q = st.session_state.get("current_hotel_query")
                today = date.today()
                check_in_str = (
                    curr_q.check_in_date.isoformat()
                    if (curr_q and hasattr(curr_q, "check_in_date"))
                    else (today + timedelta(days=7)).isoformat()
                )
                check_out_str = (
                    curr_q.check_out_date.isoformat()
                    if (curr_q and hasattr(curr_q, "check_out_date"))
                    else (today + timedelta(days=10)).isoformat()
                )
                rooms_to_book = curr_q.num_rooms if curr_q else offer.num_rooms
                adults_to_book = curr_q.num_adults if curr_q else 2
                children_to_book = curr_q.num_children if curr_q else 0

                init_ok, booking_record, init_msg = booking_service.initiate_booking(
                    offer=offer,
                    selected_room=room,
                    guest_info=guest_info,
                    check_in=check_in_str,
                    check_out=check_out_str,
                    num_rooms=rooms_to_book,
                    num_adults=adults_to_book,
                    num_children=children_to_book,
                )

                if not init_ok or not booking_record:
                    st.error(f"⚠️ Booking failed: {init_msg}")
                    return

                ord_ok, pay_order, ord_msg = booking_service.create_payment_order_for_booking(
                    booking_record.booking_reference
                )

                if not ord_ok or not pay_order:
                    st.error(f"⚠️ Payment order creation failed: {ord_msg}")
                    return

                st.session_state.active_payment_order = pay_order
                st.session_state.pending_booking_ref = booking_record.booking_reference
                st.rerun()

    # If payment order was created, render payment execution interface
    if st.session_state.get("active_payment_order") and st.session_state.get("pending_booking_ref"):
        render_payment_modal_interface(
            st.session_state.active_payment_order,
            st.session_state.pending_booking_ref
        )


def render_payment_modal_interface(pay_order, booking_ref: str):
    """Renders the payment interface supporting selectable simulation test scenarios using native widgets."""
    booking_service = get_booking_service()

    st.divider()
    st.warning(
        "🛡️ **DEMO CHECKOUT — No real payment will be collected.**\n\n"
        "This is a safe demonstration payment simulator. Select an authorized test scenario below to simulate gateway response."
    )

    with st.container(border=True):
        st.subheader("Simulated Payment Gateway")
        st.caption(f"Demo Order: `{pay_order.order_id}` • Booking Reference: `{booking_ref}`")
        st.metric("Payable Total (SIMULATED)", f"₹{pay_order.amount_inr:,.2f} INR")

    st.subheader("💳 Select Payment Method:")

    tab_bank, tab_scenarios = st.tabs([
        "🏦 Pay using SK Demo Bank (Simulated Account)",
        "⚙️ Existing Simulated Gateway Scenarios"
    ])

    with tab_bank:
        from travel_agency.bank_service import get_demo_bank_service
        bank_service = get_demo_bank_service()
        acc = bank_service.get_account()
        booking = booking_service.repo.get_booking_by_reference(booking_ref)

        with st.container(border=True):
            st.subheader(f"🏦 {acc.bank_name} • {acc.account_holder}")
            st.code(f"Account: {acc.account_number_masked} ({acc.account_type})")
            st.metric("Available Demo Balance", f"₹{acc.balance_inr:,.2f} INR")

            if booking:
                st.markdown(f"- 🏨 **Hotel:** {booking.hotel_name}")
                st.markdown(f"- 🛏️ **Room:** {booking.room_name}")
                st.markdown(f"- 📅 **Dates:** {booking.check_in} to {booking.check_out} ({booking.num_nights} nights)")
                st.markdown(f"- 👥 **Guests:** {booking.num_adults} Adults, {booking.num_rooms} Room(s)")

            st.divider()
            st.markdown(f"**Final Payable Total (Taxes & 12% GST Included):** ₹{pay_order.amount_inr:,.2f}")

        has_funds = acc.balance_inr >= pay_order.amount_inr

        if has_funds:
            st.success(f"✅ Sufficient balance available. Deducting ₹{pay_order.amount_inr:,.2f} will leave ₹{acc.balance_inr - pay_order.amount_inr:,.2f} in your demo account.")
            if st.button(f"👉 Confirm & Pay ₹{pay_order.amount_inr:,.2f} with SK Demo Bank", key="btn_pay_with_demo_bank", type="primary", use_container_width=True):
                with st.spinner("Authorizing demo transaction with SK Demo Bank..."):
                    ok, rec, msg, meta = booking_service.pay_with_demo_bank(booking_ref)
                if ok and rec:
                    st.session_state.confirmed_booking = rec
                    st.session_state.bank_pay_meta = meta
                    st.session_state.active_booking_view = "confirmation"
                    st.session_state.active_payment_order = None
                    st.rerun()
                else:
                    st.error(f"❌ Payment authorization failed: {msg}")
        else:
            shortfall = round(pay_order.amount_inr - acc.balance_inr, 2)
            st.error(f"❌ Insufficient Demo Funds. Available: ₹{acc.balance_inr:,.2f} | Payable: ₹{pay_order.amount_inr:,.2f} | Shortfall: ₹{shortfall:,.2f}.")
            st.info("💡 You can reset your demo balance to ₹1,00,000 on the 'My Demo Bank Account' page or use the simulated gateway scenarios below.")

    with tab_scenarios:
        sc_col1, sc_col2 = st.columns(2)

        with sc_col1:
            if st.button("🟢 1. Simulate Successful Payment", key="btn_sim_success", type="primary", use_container_width=True):
                with st.spinner("Processing simulated payment authorization (DEMO PAID)..."):
                    ok, rec, msg = booking_service.process_simulated_payment(booking_ref, scenario="success")
                if ok and rec:
                    st.session_state.confirmed_booking = rec
                    st.session_state.bank_pay_meta = None
                    st.session_state.active_booking_view = "confirmation"
                    st.session_state.active_payment_order = None
                    st.rerun()
                else:
                    st.error(f"Simulation failed: {msg}")

            if st.button("🟡 3. Simulate Pending Payment", key="btn_sim_pending", type="secondary", use_container_width=True):
                with st.spinner("Recording pending transaction status..."):
                    ok, rec, msg = booking_service.process_simulated_payment(booking_ref, scenario="pending")
                st.warning(f"⏳ {msg} Status updated to SIMULATED_PENDING. You may retry or inspect in My Bookings.")

        with sc_col2:
            if st.button("🔴 2. Simulate Declined Payment", key="btn_sim_declined", type="secondary", use_container_width=True):
                with st.spinner("Simulating bank authorization rejection..."):
                    ok, rec, msg = booking_service.process_simulated_payment(booking_ref, scenario="declined")
                st.error(f"❌ {msg} Booking status: PAYMENT_FAILED. You can retry with another demo scenario.")

            if st.button("⏱️ 4. Simulate Payment Timeout", key="btn_sim_timeout", type="secondary", use_container_width=True):
                with st.spinner("Simulating gateway timeout..."):
                    ok, rec, msg = booking_service.process_simulated_payment(booking_ref, scenario="timeout")
                st.error(f"⏱️ {msg} Status: SIMULATED_TIMEOUT. Gateway timed out before bank response.")


def render_confirmation_view(booking: HotelBookingRecord):
    """Renders the official Booking Confirmation and printable voucher using native widgets."""
    st.title("🎉 Your Stay is Officially Confirmed!")
    st.caption("Booking Confirmed & Guaranteed • An official luxury confirmation receipt and accommodation voucher have been generated.")

    bank_meta = st.session_state.get("bank_pay_meta")
    is_bank_paid = getattr(booking, "payment_gateway", "") == "sk_demo_bank" or (booking.payment_id and booking.payment_id.startswith("SKTXN")) or bank_meta

    if is_bank_paid:
        txn_ref = bank_meta.get("transaction_reference") if bank_meta else booking.payment_id
        from travel_agency.bank_service import get_demo_bank_service
        cur_bal = get_demo_bank_service().get_account().balance_inr
        st.success(f"🏦 Payment Authorized via SK Demo Bank — Transaction Reference: **{txn_ref}** | Remaining Balance: **₹{cur_bal:,.2f} INR**")

    # Branded Voucher Box
    total_amount = booking.pricing.get("total_amount", 0.0)

    with st.container(border=True):
        v_h1, v_h2 = st.columns([2, 1])
        with v_h1:
            st.title("SK HOLIDAYS")
            st.caption("OFFICIAL LUXURY ACCOMMODATION VOUCHER")
        with v_h2:
            st.success(f"STATUS: {booking.booking_status.value}")

        st.divider()

        ref_c1, ref_c2 = st.columns(2)
        with ref_c1:
            st.caption("BOOKING REFERENCE")
            st.code(booking.booking_reference)
        with ref_c2:
            st.caption("SUPPLIER CONFIRMATION")
            st.code(booking.supplier_booking_reference or "CONFIRMED")

        st.divider()

        d_c1, d_c2 = st.columns(2)
        with d_c1:
            st.subheader(booking.hotel_name)
            st.caption(f"📍 {booking.hotel_address}")
        with d_c2:
            st.subheader(booking.room_name)
            st.caption(f"🍽️ {booking.meal_inclusion}")

        st.divider()

        g_c1, g_c2, g_c3 = st.columns(3)
        with g_c1:
            st.caption("LEAD GUEST")
            st.markdown(f"**{booking.guest_info.lead_guest_name}**")
            st.caption(booking.guest_info.email)
        with g_c2:
            st.caption("ROOMS & GUESTS")
            st.markdown(f"**{booking.num_rooms} Room(s)**")
            st.caption(f"{booking.num_adults} Adults, {booking.num_children} Children")
        with g_c3:
            st.caption("PAID TOTAL")
            st.metric("Total", f"₹{total_amount:,.2f}")
            st.caption(f"Payment ID: {booking.payment_id or 'CAPTURED'}")

        st.divider()
        st.info(
            f"🛡️ **Cancellation Policy:** {booking.cancellation_policy}\n\n"
            f"📞 **VIP Concierge:** Contact SK Holidays VIP Concierge at concierge@skholidays.com quoting reference `{booking.booking_reference}`."
        )

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("📖 View All My Bookings", key="btn_confirm_view_all_bookings", type="primary", use_container_width=True):
            st.session_state.current_page = "📖 My Bookings"
            st.session_state.active_booking_view = None
            st.rerun()
    with b_col2:
        if st.button("🔍 Search Another Hotel", key="btn_confirm_search_another", type="secondary", use_container_width=True):
            st.session_state.active_booking_view = None
            st.rerun()


def render_my_bookings_page():
    """Renders the unified 'My Bookings' management section showing both Package Bookings and Hotel Stays."""
    repo = get_booking_repository()
    booking_service = get_booking_service()

    from travel_agency.package_service import PackageService
    pkg_service = PackageService()

    st.title("📖 My Travel Bookings")
    st.caption("Unified Booking History & Management • Review your confirmed package holidays and hotel reservations, inspect official vouchers, and manage policy-backed cancellations.")

    # Search / Filter Bar
    s_col1, s_col2 = st.columns([2, 1])
    with s_col1:
        email_search = st.text_input("🔍 Filter by Guest Email Address", value="", placeholder="Enter your email to find reservations", key="unified_email_search")
    with s_col2:
        ref_search = st.text_input("Filter by Booking Reference", value="", placeholder="e.g. SKPKG-... or SKH-BK-...", key="unified_ref_search")

    email_filter = email_search.strip() if email_search.strip() else None

    # Load both package bookings and hotel bookings
    pkg_bookings = pkg_service.list_package_bookings(email=email_filter)
    hotel_bookings = repo.list_bookings(email=email_filter)

    if ref_search and ref_search.strip():
        search_kw = ref_search.strip().lower()
        pkg_bookings = [b for b in pkg_bookings if search_kw in b.booking_reference.lower()]
        hotel_bookings = [b for b in hotel_bookings if search_kw in b.booking_reference.lower()]

    tab_packages, tab_hotels = st.tabs([
        f"🎒 Travel Package Bookings ({len(pkg_bookings)})",
        f"🏨 Hotel Stays ({len(hotel_bookings)})"
    ])

    # TAB 1: TRAVEL PACKAGE BOOKINGS
    with tab_packages:
        if not pkg_bookings:
            st.info("🎒 **No Package Bookings Found:** You haven't booked any all-inclusive travel packages yet. Explore curated getaways crafted by our 5 AI agents!")
            if st.button("🎒 Discover Travel Packages", key="btn_my_bookings_explore_pkgs", type="primary"):
                st.session_state.current_page = "🎒 Packages"
                st.session_state.package_view_mode = "catalog"
                st.rerun()
        else:
            for pb in pkg_bookings:
                is_confirmed = pb.booking_status in (BookingStatus.CONFIRMED, BookingStatus.CONFIRMED_DEMO, BookingStatus.DEMO_PAID)
                inc_acts_txt = ", ".join(pb.included_activities[:3]) if pb.included_activities else "Standard sightseeing"

                with st.container(border=True):
                    h_c1, h_c2 = st.columns([2, 1])
                    with h_c1:
                        st.caption(f":sparkles: **{pb.category.upper()} PACKAGE**")
                        st.subheader(pb.package_name)
                        st.caption(f"Reference: `{pb.booking_reference}` • 📍 {pb.destination_name}")
                    with h_c2:
                        st.caption("STATUS")
                        st.markdown(f"**{pb.booking_status.value}**")
                        st.metric("Total Paid", f"₹{pb.total_amount_inr:,.2f}")

                    st.divider()

                    g1, g2, g3 = st.columns(3)
                    with g1:
                        st.markdown(f"📅 **Dates:** {pb.departure_date} to {pb.return_date}")
                        st.caption(f"{pb.duration_days} Days / {pb.num_nights} Nights")
                    with g2:
                        st.markdown(f"👥 **Guests:** {pb.num_adults + pb.num_children} Guests ({pb.num_rooms} Room(s))")
                        st.caption(f"Lead: {pb.guest_info.lead_guest_name}")
                    with g3:
                        st.markdown(f"🚌 **Transport:** {pb.transport_mode}")
                        st.caption(f"Hotel: {pb.hotel_name}")

                    st.markdown(f"🍽️ **Meal:** {pb.meal_plan}  •  🎟️ **Highlights:** {inc_acts_txt}  •  🛡️ **Policy:** {pb.cancellation_policy}")

                    col_pkg1, col_pkg2 = st.columns(2)
                    with col_pkg1:
                        if st.button("📄 View Package Voucher", key=f"btn_pkg_vouch_{pb.booking_reference}", use_container_width=True):
                            st.session_state.confirmed_package_booking = pb
                            st.session_state.package_view_mode = "confirmation"
                            st.session_state.current_page = "🎒 Packages"
                            st.rerun()

                    with col_pkg2:
                        if is_confirmed:
                            if st.button("✕ Cancel Package & Refund (Demo)", key=f"btn_pkg_cancel_{pb.booking_reference}", type="secondary", use_container_width=True):
                                with st.spinner("Processing demo package cancellation & balance refund..."):
                                    c_ok, r_ref, c_msg = pkg_service.cancel_package_booking(pb.booking_reference)
                                if c_ok:
                                    st.success(c_msg)
                                    st.rerun()
                                else:
                                    st.error(c_msg)

    # TAB 2: HOTEL RESERVATIONS
    with tab_hotels:
        if not hotel_bookings:
            st.info("🏨 **No Hotel Stays Found:** You don't have any individual hotel bookings matching the search criteria.")
            if st.button("🏨 Explore Hotels Now", key="btn_explore_hotels_empty", type="primary"):
                st.session_state.current_page = "🏨 Find Hotels"
                st.rerun()
        else:
            for b in hotel_bookings:
                total_amount = b.pricing.get("total_amount", 0.0)

                with st.container(border=True):
                    h_c1, h_c2 = st.columns([2, 1])
                    with h_c1:
                        st.subheader(b.hotel_name)
                        st.caption(f"Reference: `{b.booking_reference}` • 📍 {b.destination_name}")
                        st.markdown(f"**{b.room_name}** ({b.num_rooms} room, {b.num_nights} nights) • 🍽️ {b.meal_inclusion}")
                    with h_c2:
                        st.caption("STATUS")
                        st.markdown(f"**{b.booking_status.value}**")
                        st.metric("Total", f"₹{total_amount:,.2f}")

                    st.caption(f"Lead Guest: **{b.guest_info.lead_guest_name}** ({b.guest_info.email}) • Policy: {b.cancellation_policy}")

                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button("📄 View Voucher", key=f"vouch_{b.booking_reference}", use_container_width=True):
                            st.session_state.confirmed_booking = b
                            st.session_state.active_booking_view = "confirmation"
                            st.session_state.current_page = "🏨 Find Hotels"
                            st.rerun()

                    with col_act2:
                        if b.booking_status in (BookingStatus.CONFIRMED, BookingStatus.CONFIRMED_DEMO, BookingStatus.DEMO_PAID):
                            if st.button("✕ Cancel Reservation (Demo)", key=f"cancel_{b.booking_reference}", type="secondary", use_container_width=True):
                                with st.spinner("Processing demo cancellation and restoring inventory..."):
                                    c_ok, c_msg = booking_service.cancel_booking(b.booking_reference)
                                if c_ok:
                                    st.success(c_msg)
                                    st.rerun()
                                else:
                                    st.error(c_msg)


def get_payment_gateway_instance():
    """Helper accessing global payment provider."""
    return get_payment_provider()
