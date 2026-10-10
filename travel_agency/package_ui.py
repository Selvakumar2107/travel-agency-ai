"""Luxury Travel Packages UI for SK Holidays.

Provides interactive package discovery, customization, 5-agent AI reviews,
deterministic price breakdown, guest information validation, atomic demo bank payment,
and confirmation voucher under the luxury Black & Gold theme.
Built 100% with native Streamlit components (containers, columns, images, subheaders,
captions, metrics, dividers, buttons) to guarantee zero raw HTML leakage.
"""

from datetime import date, timedelta
from typing import List, Tuple, Optional
import streamlit as st

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
from travel_agency.package_service import PackageService
from travel_agency.bank_service import DemoBankService, paise_to_inr
from travel_agency.data import load_destinations, load_packages


def get_package_service() -> PackageService:
    """Returns singleton-style PackageService instance."""
    if "package_service" not in st.session_state:
        st.session_state.package_service = PackageService()
    return st.session_state.package_service


def render_travel_packages_page():
    """Main entrypoint for the 'Travel Packages' navigation page."""
    pkg_service = get_package_service()

    # Session states for package flow
    if "selected_package_id" not in st.session_state:
        st.session_state.selected_package_id = None
    if "package_view_mode" not in st.session_state:
        st.session_state.package_view_mode = "catalog"  # catalog | detail | checkout | confirmation
    if "confirmed_package_booking" not in st.session_state:
        st.session_state.confirmed_package_booking = None

    # Handle confirmation view
    if st.session_state.package_view_mode == "confirmation" and st.session_state.confirmed_package_booking:
        render_package_confirmation_voucher(st.session_state.confirmed_package_booking)
        return

    # Handle detail/customization/checkout view
    if st.session_state.package_view_mode in ("detail", "checkout") and st.session_state.selected_package_id:
        render_package_customization_and_booking(st.session_state.selected_package_id)
        return

    # Default: Render Package Catalog
    render_package_catalog(pkg_service)


def render_package_catalog(pkg_service: PackageService):
    """Renders the top banner, search/filter bar, and luxury package cards grid using native Streamlit widgets."""
    st.title("🎒 All-Inclusive Holidays Powered by 5 AI Agents")
    st.markdown(
        "**Curated Luxury Travel Packages** — Handcrafted travel packages combining intercity transit, "
        "verified hotels, regional dining plans, and curated sightseeing activities. "
        "Every quote is computed with pure Python deterministic mathematics."
    )
    st.info("🛡️ **Demo Simulation Environment:** All packages, bookings, and payments are simulated. No real cards, bank credentials, or real transactions occur.")

    # Search & Filter Controls
    destinations = load_destinations()
    dest_options = ["All Destinations"] + [d["name"] for d in destinations]
    dest_id_map = {d["name"]: d["id"] for d in destinations}

    with st.container(border=True):
        st.subheader("🔍 Customize & Filter Packages")

        col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.2, 1.2, 1.2])

        with col_f1:
            sel_dest = st.selectbox("Destination", options=dest_options, index=0, key="pkg_filter_dest")
        with col_f2:
            sel_cat = st.selectbox(
                "Package Category",
                options=["All Categories", "Economy", "Comfort", "Premium"],
                index=0,
                key="pkg_filter_cat"
            )
        with col_f3:
            dep_date = st.date_input("Departure Date", value=date.today() + timedelta(days=7), key="pkg_filter_dep")
        with col_f4:
            ret_date = st.date_input("Return Date", value=date.today() + timedelta(days=10), key="pkg_filter_ret")

        col_f5, col_f6, col_f7, col_f8 = st.columns([1, 1, 1, 1.5])

        with col_f5:
            num_adults = st.number_input("Adults (12+)", min_value=1, max_value=10, value=2, step=1, key="pkg_filter_adults")
        with col_f6:
            num_children = st.number_input("Children", min_value=0, max_value=6, value=0, step=1, key="pkg_filter_children")
        with col_f7:
            num_rooms = st.number_input("Hotel Rooms", min_value=1, max_value=5, value=1, step=1, key="pkg_filter_rooms")
        with col_f8:
            max_budget_filter = st.number_input(
                "Max Budget (₹ INR, optional)",
                min_value=0,
                max_value=200000,
                value=0,
                step=1000,
                key="pkg_filter_budget",
                help="Set 0 for unlimited budget. Minimum accepted trip budget is ₹3,000."
            )

    # Date Validation
    if ret_date <= dep_date:
        st.error("⚠️ Return date must be strictly later than departure date.")
        return

    num_nights = max(1, (ret_date - dep_date).days)
    duration_days = num_nights + 1
    total_travelers = num_adults + num_children

    st.info(
        f"📅 **Duration:** {duration_days} Days / {num_nights} Nights  •  "
        f"👥 **Group:** {total_travelers} Guests ({num_adults} Adults{f', {num_children} Children' if num_children > 0 else ''})  •  "
        f"🏨 **Lodging:** {num_rooms} Room(s)"
    )

    # Search Query
    dest_id = dest_id_map.get(sel_dest) if sel_dest != "All Destinations" else None
    cat_query = sel_cat.lower() if sel_cat != "All Categories" else "all"
    budget_val = float(max_budget_filter) if max_budget_filter >= 3000 else None

    query = PackageSearchQuery(
        origin="Bangalore",
        destination_id=dest_id,
        departure_date=dep_date,
        return_date=ret_date,
        category=cat_query,
        num_adults=num_adults,
        num_children=num_children,
        num_rooms=num_rooms,
        max_budget=budget_val,
    )

    results = pkg_service.search_packages(query)

    if not results:
        st.warning("🎒 No Packages Found Matching Criteria. Try adjusting your budget filter or selecting 'All Categories' to view available packages.")
        return

    st.subheader(f"Found {len(results)} Available Package(s):")

    # Render Cards in a 2-Column Responsive Grid using Native Streamlit Containers
    for i in range(0, len(results), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(results):
                pkg, pricing = results[idx]
                with cols[j]:
                    render_package_card(pkg, pricing, total_travelers, num_rooms, num_nights, duration_days, dep_date, ret_date)


def render_package_card(
    pkg: TravelPackage,
    pricing: PackageCostBreakdown,
    total_travelers: int,
    num_rooms: int,
    num_nights: int,
    duration_days: int,
    dep_date: date,
    ret_date: date,
):
    """
    Renders a single luxury Black & Gold package card using 100% native Streamlit
    components (containers, columns, images, subheaders, captions, metrics, buttons).
    Eliminates all raw HTML tags/templates so no raw HTML strings can leak to the UI.
    """
    with st.container(border=True):
        # 1. Top Badges: Category & Duration
        b_c1, b_c2 = st.columns([2, 1])
        with b_c1:
            st.caption(f":sparkles: **{pkg.category.upper()} PACKAGE**")
        with b_c2:
            st.caption(f"⏱️ **{duration_days}D / {num_nights}N**")

        # 2. Destination Photography (Native Streamlit Image Component)
        st.image(pkg.image_url, use_container_width=True)

        # 3. Package Name & Destination Tagline
        st.subheader(pkg.name)
        st.caption(f"📍 **{pkg.destination_name}** • {pkg.tagline}")

        # 4. Stay, Transport, Meal Plan & Status Grid
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown(f"🏨 **Stay:** {pkg.hotel_name}")
            st.caption(f"Room: {pkg.room_type}")
            st.markdown(f"🍽️ **Meal:** {pkg.meal_plan}")
        with col_r:
            st.markdown(f"🚌 **Transport:** {pkg.transport_mode}")
            st.caption(f"Tier: {pkg.transport_tier.title()}")
            st.markdown("⚡ **Status:** Demo Available")

        # 5. Included Sightseeing Highlights
        st.markdown("**Included Highlights:**")
        for act in pkg.included_activities[:3]:
            st.markdown(f"- ✓ {act}")

        st.divider()

        # 6. Pricing Row
        p_c1, p_c2 = st.columns(2)
        with p_c1:
            st.caption("PER PERSON")
            st.markdown(f"### ₹{pricing.price_per_person_inr:,.2f}")
        with p_c2:
            st.caption(f"GROUP TOTAL ({total_travelers} GUESTS)")
            st.markdown(f"### ₹{pricing.total_group_price_inr:,.2f}")

        st.caption(":white_check_mark: Taxes & 10% contingency included")

        # 7. Action Buttons (View Package & Book Package)
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("👁️ View Package", key=f"btn_view_{pkg.id}", use_container_width=True, type="secondary"):
                st.session_state.selected_package_id = pkg.id
                st.session_state.package_view_mode = "detail"
                st.session_state.pkg_dep_date = dep_date
                st.session_state.pkg_ret_date = ret_date
                st.session_state.pkg_adults = total_travelers
                st.session_state.pkg_rooms = num_rooms
                st.rerun()

        with btn_c2:
            if st.button("⚡ Book Package", key=f"btn_book_{pkg.id}", use_container_width=True, type="primary"):
                st.session_state.selected_package_id = pkg.id
                st.session_state.package_view_mode = "checkout"
                st.session_state.pkg_dep_date = dep_date
                st.session_state.pkg_ret_date = ret_date
                st.session_state.pkg_adults = total_travelers
                st.session_state.pkg_rooms = num_rooms
                st.rerun()


def render_package_customization_and_booking(package_id: str):
    """Renders the in-depth customization, 5-agent AI reviews, price breakdown, and checkout flow using native Streamlit widgets."""
    pkg_service = get_package_service()
    pkg = pkg_service.get_package_by_id(package_id)

    # Top return button
    if st.button("← Back to Travel Packages Catalog", key="btn_back_catalog", type="secondary"):
        st.session_state.package_view_mode = "catalog"
        st.session_state.selected_package_id = None
        st.rerun()

    st.caption(f":sparkles: **{pkg.category.upper()} PACKAGE • {pkg.destination_name}**")
    st.title(pkg.name)
    st.markdown(f"*{pkg.tagline}*")

    # Two column layout: Left = Customizer & Itinerary; Right = Dynamic Pricing & AI Agent Review
    left_col, right_col = st.columns([1.1, 0.9])

    with left_col:
        with st.container(border=True):
            st.subheader("Step 2: Customize Dates, Travellers & Preferences")

            c_d1, c_d2 = st.columns(2)
            with c_d1:
                default_dep = getattr(st.session_state, "pkg_dep_date", date.today() + timedelta(days=7))
                cust_dep = st.date_input("Departure Date", value=default_dep, key="cust_dep")
            with c_d2:
                default_ret = getattr(st.session_state, "pkg_ret_date", date.today() + timedelta(days=10))
                cust_ret = st.date_input("Return Date", value=default_ret, key="cust_ret")

            if cust_ret <= cust_dep:
                st.error("⚠️ Return date must be after departure date.")
                return

            cust_nights = max(1, (cust_ret - cust_dep).days)
            cust_days = cust_nights + 1

            c_g1, c_g2, c_g3, c_g4 = st.columns(4)
            with c_g1:
                cust_adults = st.number_input("Adults", min_value=1, max_value=10, value=getattr(st.session_state, "pkg_adults", 2), step=1, key="cust_adults")
            with c_g2:
                cust_children = st.number_input("Children", min_value=0, max_value=6, value=0, step=1, key="cust_children")
            with c_g3:
                cust_rooms = st.number_input("Rooms", min_value=1, max_value=5, value=getattr(st.session_state, "pkg_rooms", 1), step=1, key="cust_rooms")
            with c_g4:
                cust_occ = st.number_input("Max Guests/Room", min_value=1, max_value=4, value=2, step=1, key="cust_occ")

            total_guests = cust_adults + cust_children

            # Validate Room Capacity
            max_room_capacity = cust_rooms * cust_occ
            if total_guests > max_room_capacity:
                st.error(
                    f"⚠️ Room capacity exceeded! {total_guests} guests require more capacity "
                    f"({cust_rooms} rooms × {cust_occ} guests/room = {max_room_capacity} max). "
                    f"Please increase room count."
                )
                return

            c_p1, c_p2 = st.columns(2)
            with c_p1:
                meal_pref = st.selectbox(
                    "Dietary Preference",
                    options=["No Dietary Restriction", "Vegetarian", "Vegan", "Jain", "Halal"],
                    index=0,
                    key="cust_meal_pref"
                )
            with c_p2:
                target_max_budget = st.number_input(
                    "Maximum Trip Budget (₹ INR, optional)",
                    min_value=0,
                    max_value=300000,
                    value=0,
                    step=2000,
                    key="cust_max_budget",
                    help="Set 0 for unconstrained. Minimum accepted trip budget is ₹3,000."
                )

            # Optional Activities
            st.markdown("**Optional Sightseeing Add-Ons:**")
            selected_optional_acts: List[str] = []
            if pkg.optional_activities:
                for opt_act in pkg.optional_activities:
                    checked = st.checkbox(f"➕ {opt_act} (Add-on)", key=f"opt_act_{opt_act}")
                    if checked:
                        selected_optional_acts.append(opt_act)
            else:
                st.caption("All featured sightseeing activities are already included in this package.")

        # Inclusions & Exclusions Accordion
        with st.expander("📋 Detailed Inclusions, Exclusions & Cancellation Rules", expanded=False):
            st.markdown("### ✓ Included in Package:")
            for inc in pkg.inclusions:
                st.markdown(f"- {inc}")
            st.markdown("### ✕ Exclusions:")
            for exc in pkg.exclusions:
                st.markdown(f"- {exc}")
            st.markdown("### 🛡️ Cancellation Policy:")
            st.info(pkg.cancellation_policy)

    # Compute Deterministic Customization Pricing
    budget_arg = float(target_max_budget) if target_max_budget >= 3000 else None

    customization = PackageCustomization(
        package_id=pkg.id,
        origin="Bangalore",
        destination_id=pkg.destination_id,
        departure_date=cust_dep,
        return_date=cust_ret,
        num_adults=cust_adults,
        num_children=cust_children,
        num_rooms=cust_rooms,
        room_occupancy_per_room=cust_occ,
        selected_optional_activities=selected_optional_acts,
        meal_preference=meal_pref,
        contingency_percent=10.0,
        max_budget=budget_arg,
    )

    pricing = pkg_service.calculate_customized_pricing(customization)
    ai_review = pkg_service.evaluate_package_with_agents(customization, pricing)

    with right_col:
        # Transparent Cost Breakdown Card
        with st.container(border=True):
            st.subheader("📊 Deterministic Cost Breakdown")
            st.caption(":lock: INTEGER PAISE ACCURACY")
            st.markdown(f"- 🚌 **Outbound Transport ({pkg.transport_mode}):** ₹{pricing.outbound_transport_inr:,.2f}")
            st.markdown(f"- 🚌 **Return Transport:** ₹{pricing.return_transport_inr:,.2f}")
            st.markdown(f"- 🚗 **Local Sightseeing Transit:** ₹{pricing.local_transport_inr:,.2f}")
            st.markdown(f"**Transport Subtotal:** ₹{pricing.transport_subtotal_inr:,.2f}")
            st.divider()
            st.markdown(f"- 🏨 **Accommodation ({cust_rooms} room × {cust_nights} nights):** ₹{pricing.accommodation_subtotal_inr:,.2f}")
            st.markdown(f"- 🍽️ **Dining Plan ({cust_days} days × {total_guests} guests):** ₹{pricing.food_subtotal_inr:,.2f}")
            st.markdown(f"- 🎟️ **Included Activities:** ₹{pricing.included_activities_subtotal_inr:,.2f}")
            if pricing.optional_activities_subtotal_inr > 0:
                st.markdown(f"- ➕ **Optional Activities:** ₹{pricing.optional_activities_subtotal_inr:,.2f}")
            st.markdown(f"- 🏛️ **Taxes & Fees (12% Hotel GST + 5% Transport):** ₹{pricing.taxes_and_fees_inr:,.2f}")
            st.markdown(f"- 🛡️ **Disclosed Contingency Reserve (10%):** ₹{pricing.contingency_reserve_inr:,.2f}")
            st.divider()
            tot_c1, tot_c2 = st.columns(2)
            with tot_c1:
                st.metric("Total Group Price", f"₹{pricing.total_group_price_inr:,.2f}")
            with tot_c2:
                st.metric("Per Person", f"₹{pricing.price_per_person_inr:,.2f}")
            st.caption(f"✨ Amount Payable Now: **₹{pricing.amount_payable_now_inr:,.2f}**")

        # AI Agent Review Panel
        with st.expander("🤖 5 AI Collaborative Agents Review & Budget Feedback", expanded=True):
            st.markdown(f"🧭 **Travel Planning Agent:**\n\n{ai_review.travel_agent_verdict}")
            st.markdown(f"🏨 **Hotel Recommendation Agent:**\n\n{ai_review.hotel_agent_verdict}")
            st.markdown(f"🚗 **Transport Planning Agent:**\n\n{ai_review.transport_agent_verdict}")
            st.markdown(f"🍽️ **Food Recommendation Agent:**\n\n{ai_review.food_agent_verdict}")
            st.markdown(f"📊 **Budget Optimization Agent:**\n\n{ai_review.budget_agent_verdict}")

            if ai_review.optimization_passes:
                st.markdown("#### 3-Pass Optimization Feedback Loop:")
                for p in ai_review.optimization_passes:
                    st.info(f"**Pass {p['pass']}:** {p['action']} — saves ₹{p['savings']:,.2f} (New Total: ₹{p['new_cost']:,.2f})")

    st.divider()

    # STEP 4: GUEST INFORMATION & CHECKOUT
    with st.container(border=True):
        st.subheader("Step 4: Guest Contact Details & Payment Execution")
        st.caption("Enter lead guest contact information. Information is strictly validated via Pydantic schemas.")

        col_g1, col_g2, col_g3 = st.columns(3)
        with col_g1:
            lead_name = st.text_input("Lead Guest Full Name", value="Demo Traveller", key="lead_name")
        with col_g2:
            lead_email = st.text_input("Email Address", value="demo.traveller@skholidays.com", key="lead_email")
        with col_g3:
            lead_phone = st.text_input("Contact Phone Number", value="+91 9876543210", key="lead_phone")

        special_reqs = st.text_input("Special Requests (optional)", value="Quiet room with scenic view", key="special_reqs")
        agree_terms = st.checkbox("I accept the booking terms and demo cancellation policies.", value=True, key="agree_terms")

    # Validate Guest Information
    guest_info = None
    try:
        guest_info = GuestInformation(
            lead_guest_name=lead_name,
            email=lead_email,
            phone=lead_phone,
            additional_guests=[],
            special_requests=special_reqs,
            accepted_terms=agree_terms,
        )
    except Exception as e:
        st.warning(f"⚠️ Validation notice: {e}")

    # Payment Selection Tabs
    st.subheader("Step 6: Choose Simulated Payment Method")
    tab_bank, tab_gateway = st.tabs(["💳 SK Demo Bank Account (Instant ₹1,00,000)", "⚡ Simulated Payment Gateway"])

    bank_service = DemoBankService.get_instance()
    bank_acc = bank_service.get_account()
    avail_balance = paise_to_inr(bank_acc.balance_paise) if bank_acc else 0.0

    with tab_bank:
        with st.container(border=True):
            b_l, b_r = st.columns([1.5, 1])
            with b_l:
                st.caption("CONNECTED DEMO BANK")
                st.subheader(bank_acc.bank_name if bank_acc else "SK Demo Bank")
                st.code(bank_acc.account_number_masked if bank_acc else "SKDEMO••••100001")
            with b_r:
                st.caption("AVAILABLE DEMO BALANCE")
                st.metric("Balance", f"₹{avail_balance:,.2f}")
            st.caption("✓ 1-Click Atomic Debit • Protected by Idempotency & Duplicate Charge Prevention")

        if avail_balance < pricing.total_group_price_inr:
            st.error(
                f"❌ Insufficient demo funds! Required: ₹{pricing.total_group_price_inr:,.2f}, "
                f"Available: ₹{avail_balance:,.2f}. Please visit the Demo Bank page to adjust balance."
            )

        if st.button(
            f"💳 Confirm & Pay ₹{pricing.total_group_price_inr:,.2f} with SK Demo Bank",
            key="btn_pay_demo_bank",
            type="primary",
            use_container_width=True,
            disabled=(guest_info is None or avail_balance < pricing.total_group_price_inr)
        ):
            with st.spinner("Processing atomic demo bank transaction..."):
                try:
                    # 1. Create booking draft
                    booking_draft = pkg_service.create_package_booking_draft(customization, guest_info)
                    # 2. Pay via demo bank
                    success, txn_ref, bal_after, msg = pkg_service.pay_with_demo_bank(booking_draft.booking_reference)
                    if success:
                        st.success(f"🎉 Payment successful! Ref: {txn_ref}")
                        confirmed = pkg_service.repository.get_package_booking(booking_draft.booking_reference)
                        st.session_state.confirmed_package_booking = confirmed
                        st.session_state.package_view_mode = "confirmation"
                        st.rerun()
                    else:
                        st.error(f"❌ Payment failed: {msg}")
                except Exception as e:
                    st.error(f"❌ Transaction error: {e}")

    with tab_gateway:
        with st.container(border=True):
            st.subheader("Simulated Gateway / Razorpay Test Mode")
            st.caption("Simulates an instant successful payment authorization for testing external gateway workflows.")

        if st.button(
            f"⚡ Authorize Demo Payment of ₹{pricing.total_group_price_inr:,.2f}",
            key="btn_pay_simulated_gateway",
            type="primary",
            use_container_width=True,
            disabled=(guest_info is None)
        ):
            with st.spinner("Simulating gateway authorization..."):
                try:
                    booking_draft = pkg_service.create_package_booking_draft(customization, guest_info)
                    # Complete booking with demo simulated gateway
                    sim_txn = f"SIMPAY-{date.today().strftime('%Y%m%d')}-PKG"
                    pkg_service.repository.update_package_booking_status(
                        booking_reference=booking_draft.booking_reference,
                        booking_status=BookingStatus.CONFIRMED,
                        payment_status=PaymentStatus.CAPTURED,
                        demo_txn_ref=sim_txn,
                        audit_note="Paid via simulated payment gateway test mode.",
                    )
                    confirmed = pkg_service.repository.get_package_booking(booking_draft.booking_reference)
                    st.session_state.confirmed_package_booking = confirmed
                    st.session_state.package_view_mode = "confirmation"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Booking failed: {e}")


def render_package_confirmation_voucher(booking: PackageBookingRecord):
    """Renders the official luxury Black & Gold confirmation voucher cleanly with native Streamlit components."""
    with st.container(border=True):
        v_top1, v_top2 = st.columns([2, 1])
        with v_top1:
            st.title("SK HOLIDAYS")
            st.caption("OFFICIAL PACKAGE CONFIRMATION VOUCHER")
        with v_top2:
            st.success("STATUS: CONFIRMED (DEMO)")

        st.divider()

        ref_c1, ref_c2 = st.columns(2)
        with ref_c1:
            st.caption("BOOKING REFERENCE")
            st.code(booking.booking_reference)
        with ref_c2:
            st.caption("TRANSACTION REFERENCE")
            st.code(booking.demo_transaction_reference or "CONFIRMED")

        st.divider()

        d_c1, d_c2 = st.columns(2)
        with d_c1:
            st.subheader(booking.package_name)
            st.markdown(f"📍 **{booking.destination_name}** • {booking.duration_days} Days / {booking.num_nights} Nights")
            st.caption(f"Dates: {booking.departure_date} to {booking.return_date}")
        with d_c2:
            st.markdown(f"🏨 **Hotel:** {booking.hotel_name}")
            st.caption(f"Room: {booking.room_type} ({booking.num_rooms} room(s))")
            st.markdown(f"🍽️ **Meal Plan:** {booking.meal_plan}")

        st.divider()

        g_c1, g_c2, g_c3 = st.columns(3)
        with g_c1:
            st.caption("LEAD GUEST")
            st.markdown(f"**{booking.guest_info.lead_guest_name}**")
            st.caption(booking.guest_info.email)
        with g_c2:
            st.caption("TRANSPORT MODE")
            st.markdown(f"**{booking.transport_mode}**")
            st.caption("Round-trip + local transfers")
        with g_c3:
            st.caption("TOTAL PAID AMOUNT")
            st.metric("Paid", f"₹{booking.total_amount_inr:,.2f}")
            if booking.demo_balance_after_inr is not None:
                st.caption(f"Remaining balance: ₹{booking.demo_balance_after_inr:,.2f}")

        st.divider()
        st.info(f"🛡️ **Cancellation Rules:** {booking.cancellation_policy}\n\n💼 **VIP Assistance:** Demo concierge support is accessible 24/7 at vip@skholidays.com.")

    c_conf1, c_conf2 = st.columns(2)
    with c_conf1:
        if st.button("📖 View in My Bookings Dashboard", key="btn_conf_view_my_bookings", type="primary", use_container_width=True):
            st.session_state.current_page = "📖 My Bookings"
            st.session_state.package_view_mode = "catalog"
            st.rerun()
    with c_conf2:
        if st.button("🎒 Discover More Packages", key="btn_conf_more_packages", type="secondary", use_container_width=True):
            st.session_state.package_view_mode = "catalog"
            st.session_state.selected_package_id = None
            st.session_state.confirmed_package_booking = None
            st.rerun()
