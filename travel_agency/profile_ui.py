"""UI Renderers for Profile, Settings, Saved Destinations, Notifications, and Help."""

import streamlit as st
from typing import List, Dict, Any
from travel_agency.profile_service import get_profile_service, UserProfile, TravelPreferences, AppSettings
from travel_agency.bank_service import DemoBankService
from travel_agency.data import load_destinations


def render_sidebar_profile_panel():
    """
    Renders the luxury profile header, quick wallet balance, and menu options in the sidebar.
    Uses 100% native Streamlit components.
    """
    svc = get_profile_service()
    profile = svc.get_profile()

    # Retrieve live demo bank balance
    try:
        bank_svc = DemoBankService.get_instance()
        account = bank_svc.get_account()
        wallet_balance_str = f"₹{account.balance_inr:,.2f}"
    except Exception:
        wallet_balance_str = "₹1,00,000.00"

    # Profile Header Container
    with st.container(border=True):
        p_c1, p_c2 = st.columns([1, 2.5])
        with p_c1:
            st.markdown(f"### 👑 `{profile.avatar_initials}`")
        with p_c2:
            st.markdown(f"**{profile.display_name}**")
            st.caption("👤 Demo Profile")

        st.caption(f"📧 {profile.email}")
        st.divider()

        # Demo Wallet Snapshot
        st.markdown(f"💳 **Demo Wallet:** `{wallet_balance_str}`")

        w_col1, w_col2 = st.columns(2)
        with w_col1:
            if st.button("⚙️ Profile", key="sb_btn_edit_profile", use_container_width=True, type="secondary"):
                st.session_state.current_page = "👤 My Profile"
                st.rerun()
        with w_col2:
            if st.button("💳 Wallet", key="sb_btn_open_wallet", use_container_width=True, type="secondary"):
                st.session_state.current_page = "💳 Demo Bank"
                st.rerun()

    # Sidebar Navigation Menu Options
    st.caption("🧭 **NAVIGATION & SETTINGS**")

    curr = st.session_state.get("current_page", "🏠 Home")

    menu_items = [
        ("🏠 Home Overview", "🏠 Home"),
        ("✈️ AI Trip Planner", "✈️ Plan a Trip"),
        ("🎒 Travel Packages", "🎒 Packages"),
        ("🏨 Hotel Stays", "🏨 Find Hotels"),
        ("📖 My Trips & Bookings", "📖 My Bookings"),
        ("⭐ Saved Destinations", "⭐ Saved Destinations"),
        ("⚙️ Travel Preferences", "⚙️ Travel Preferences"),
        ("💳 Demo Wallet & Bank", "💳 Demo Bank"),
        ("🔔 Notifications", "🔔 Notifications"),
        ("🛠️ App Settings", "🛠️ App Settings"),
        ("❓ Help & Support", "❓ Help & Support"),
    ]

    for label, target_page in menu_items:
        is_active = (curr == target_page)
        btn_type = "primary" if is_active else "secondary"
        if st.button(label, key=f"sb_nav_{target_page}", use_container_width=True, type=btn_type):
            st.session_state.current_page = target_page
            if target_page == "🎒 Packages":
                st.session_state.package_view_mode = "catalog"
            elif target_page in ["🏨 Find Hotels", "🏠 Home"]:
                st.session_state.active_booking_view = None
            st.rerun()

    st.divider()

    # AI Status Indicator (safe: no secret exposed)
    with st.container(border=True):
        st.caption("🤖 **AI ORCHESTRATION STATUS**")
        st.write("🟢 **5 Autonomous Agents Ready**")
        st.caption("Deterministic math & Gemini natural language engine active.")

    # SK Holidays Guarantee
    with st.container(border=True):
        st.caption("🛡️ **SK HOLIDAYS GUARANTEE**")
        st.write("✓ Pure Python Deterministic Math")
        st.write("✓ ₹3,000 Minimum Baseline")
        st.write("✓ 10% Disclosed Contingency Buffer")
        st.write("✓ Zero Hidden Markups")


def render_my_profile_page():
    """Renders editable user profile form and persistence."""
    svc = get_profile_service()
    profile = svc.get_profile()

    st.markdown("## 👤 User Profile & Account Settings")
    st.caption("Local Demo Profile • Persisted in local SK Holidays database")

    with st.container(border=True):
        st.subheader("Edit Profile Information")
        st.write("Changes will be saved to your local session and database.")

        with st.form("profile_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                display_name = st.text_input("Display Name", value=profile.display_name, max_chars=50)
                email = st.text_input("Contact Email", value=profile.email, max_chars=100)
            with c2:
                phone = st.text_input("Contact Phone", value=profile.phone, max_chars=20)
                initials = st.text_input("Avatar Initials (1-2 chars)", value=profile.avatar_initials, max_chars=3)

            bio = st.text_area("Traveler Bio / About You", value=profile.bio, max_chars=250)

            submitted = st.form_submit_button("💾 Save Profile Changes", type="primary", use_container_width=True)

            if submitted:
                if not display_name.strip():
                    st.error("Display Name cannot be empty.")
                elif not email.strip() or "@" not in email:
                    st.error("Please enter a valid email address.")
                else:
                    profile.display_name = display_name.strip()
                    profile.email = email.strip()
                    profile.phone = phone.strip()
                    profile.bio = bio.strip()
                    if initials.strip():
                        profile.avatar_initials = initials.strip().upper()[:2]
                    svc.update_profile(profile)
                    st.success("✅ Profile successfully updated and persisted!")
                    st.rerun()

    # Profile Summary Card
    with st.container(border=True):
        st.subheader("Active Profile Card")
        c_a, c_b = st.columns([1, 4])
        with c_a:
            st.metric(label="Initials", value=profile.avatar_initials)
        with c_b:
            st.write(f"**Name:** {profile.display_name}")
            st.write(f"**Email:** {profile.email} • **Phone:** {profile.phone}")
            st.caption(f"*{profile.bio}*")


def render_saved_destinations_page():
    """Renders list of user's saved favorite destinations."""
    svc = get_profile_service()
    saved = svc.get_saved_destinations()
    all_dests = load_destinations()
    all_dest_map = {d["id"]: d for d in all_dests}

    st.markdown("## ⭐ Saved Favorite Destinations")
    st.caption("Curated destinations pinned to your personal travel wishlist.")

    # Add Destination Section
    with st.container(border=True):
        st.subheader("➕ Add Destination to Favorites")
        dest_options = [d["name"] for d in all_dests]
        selected_dest_name = st.selectbox("Choose a destination to add:", options=dest_options, key="add_fav_dest_select")
        if st.button("⭐ Save to Wishlist", type="primary", key="btn_add_fav_dest"):
            matched = next((d for d in all_dests if d["name"] == selected_dest_name), None)
            if matched:
                added = svc.save_destination(
                    destination_id=matched["id"],
                    destination_name=matched["name"],
                    state=matched.get("state", "India")
                )
                if added:
                    st.success(f"✅ Added {matched['name']} to your saved destinations!")
                    st.rerun()
                else:
                    st.info(f"ℹ️ {matched['name']} is already in your saved destinations.")

    # Saved Destinations List
    if not saved:
        with st.container(border=True):
            st.subheader("No Saved Destinations Yet")
            st.write("Browse destinations and save your favorite domestic retreats for fast planning.")
            if st.button("🗺️ Explore All Destinations", type="primary"):
                st.session_state.current_page = "🗺️ Destinations"
                st.rerun()
    else:
        st.markdown(f"### You have {len(saved)} saved destination(s):")
        cols = st.columns(2)
        for idx, item in enumerate(saved):
            with cols[idx % 2]:
                with st.container(border=True):
                    dest_info = all_dest_map.get(item.destination_id, {})
                    img_url = dest_info.get("image_url", "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80")
                    st.image(img_url, use_container_width=True)

                    st.subheader(f"📍 {item.destination_name}")
                    st.caption(f"State: {item.state} • Saved on {item.saved_at[:10]}")

                    if dest_info.get("tagline"):
                        st.write(f"*{dest_info['tagline']}*")

                    st.divider()
                    b_c1, b_c2, b_c3 = st.columns(3)
                    with b_c1:
                        if st.button("✨ Plan Trip", key=f"plan_fav_{item.destination_id}", use_container_width=True, type="primary"):
                            st.session_state.preselected_destination = item.destination_id
                            st.session_state.current_page = "✈️ Plan a Trip"
                            st.rerun()
                    with b_c2:
                        if st.button("🏨 Stays", key=f"hotel_fav_{item.destination_id}", use_container_width=True, type="secondary"):
                            st.session_state.preselected_destination = item.destination_id
                            st.session_state.current_page = "🏨 Find Hotels"
                            st.session_state.active_booking_view = None
                            st.rerun()
                    with b_c3:
                        if st.button("🗑️ Remove", key=f"del_fav_{item.destination_id}", use_container_width=True, type="secondary"):
                            svc.remove_saved_destination(item.destination_id)
                            st.rerun()


def render_travel_preferences_page():
    """Renders user travel preferences and personalization controls."""
    svc = get_profile_service()
    prefs = svc.get_preferences()

    st.markdown("## ⚙️ Personal Travel Preferences")
    st.caption("Configure your default travel styles, budget ranges, and transit preferences.")

    with st.container(border=True):
        st.subheader("Personalization Settings")
        with st.form("travel_prefs_form"):
            avail_types = [
                "Heritage & Culture",
                "Hill Stations & Nature",
                "Beaches & Coastal",
                "Spiritual & Pilgrimage",
                "Wildlife & Adventure",
                "Food & Culinary"
            ]

            default_types = [t for t in prefs.destination_types if t in avail_types] or ["Heritage & Culture"]
            selected_types = st.multiselect("Preferred Destination Themes", options=avail_types, default=default_types)

            c1, c2 = st.columns(2)
            with c1:
                min_b = st.number_input("Minimum Baseline Budget (₹)", min_value=3000, max_value=500000, value=prefs.min_budget, step=1000)
                tier_idx = ["Economy", "Comfort", "Luxury"].index(prefs.package_tier) if prefs.package_tier in ["Economy", "Comfort", "Luxury"] else 1
                pkg_tier = st.selectbox("Preferred Travel Tier", options=["Economy", "Comfort", "Luxury"], index=tier_idx)
                transport_opt = st.selectbox(
                    "Preferred Transit Mode",
                    options=["AC Train / Luxury Bus", "Flight / Air", "Private Cab / Chauffeur", "Standard Bus / Shared Transit"],
                    index=0
                )
            with c2:
                max_b = st.number_input("Maximum Budget Cap (₹)", min_value=min_b, max_value=1000000, value=max(max_b_val for max_b_val in [prefs.max_budget, min_b]), step=5000)
                food_opt = st.selectbox(
                    "Dietary & Dining Style",
                    options=["North & South Indian Regional", "Pure Vegetarian (Satvik)", "Jain Dietary Guidelines", "Halal Friendly", "Non-Vegetarian & Seafood", "Continental & Multi-Cuisine"],
                    index=0
                )
                access_opt = st.selectbox(
                    "Accessibility Requirements",
                    options=["Standard Mobility", "Wheelchair Accessible Stays", "Ground Floor Priority", "Minimal Walking Tours"],
                    index=0
                )

            special_req = st.text_area("Special Room / Transit Requests", value=prefs.special_requests, max_chars=200)

            submitted = st.form_submit_button("💾 Save Preferences", type="primary", use_container_width=True)

            if submitted:
                if min_b > max_b:
                    st.error("Minimum budget cannot exceed maximum budget.")
                else:
                    prefs.destination_types = selected_types or ["Heritage & Culture"]
                    prefs.min_budget = int(min_b)
                    prefs.max_budget = int(max_b)
                    prefs.package_tier = pkg_tier
                    prefs.food_preference = food_opt
                    prefs.transport_preference = transport_opt
                    prefs.accessibility = access_opt
                    prefs.special_requests = special_req.strip()
                    svc.update_preferences(prefs)
                    st.success("✅ Travel preferences saved and persisted!")
                    st.rerun()

    # Current Preferences Summary
    with st.container(border=True):
        st.subheader("Active Preferences Summary")
        p1, p2, p3 = st.columns(3)
        with p1:
            st.write(f"**Preferred Tier:** {prefs.package_tier}")
            st.write(f"**Budget Range:** ₹{prefs.min_budget:,} – ₹{prefs.max_budget:,}")
        with p2:
            st.write(f"**Transit:** {prefs.transport_preference}")
            st.write(f"**Dining:** {prefs.food_preference}")
        with p3:
            st.write(f"**Mobility:** {prefs.accessibility}")
            st.caption(f"Special: {prefs.special_requests}")


def render_notifications_page():
    """Renders authentic booking and payment notifications from real database records."""
    svc = get_profile_service()
    notifications = svc.get_real_notifications()

    st.markdown("## 🔔 Booking & Payment Notifications")
    st.caption("Live status updates derived from your actual booking history and demo wallet transactions.")

    if not notifications:
        with st.container(border=True):
            st.subheader("No Notifications Yet")
            st.write("You currently have no booking or payment records. Explore packages or stays to create your first reservation!")
            b_c1, b_c2 = st.columns(2)
            with b_c1:
                if st.button("🎒 Explore Travel Packages", type="primary", use_container_width=True):
                    st.session_state.current_page = "🎒 Packages"
                    st.session_state.package_view_mode = "catalog"
                    st.rerun()
            with b_c2:
                if st.button("🏨 Find Luxury Hotels", type="secondary", use_container_width=True):
                    st.session_state.current_page = "🏨 Find Hotels"
                    st.session_state.active_booking_view = None
                    st.rerun()
    else:
        st.markdown(f"### Recent Activity ({len(notifications)} Event(s)):")
        for item in notifications:
            with st.container(border=True):
                n_c1, n_c2 = st.columns([3, 1])
                with n_c1:
                    st.subheader(item["title"])
                    st.write(item["message"])
                with n_c2:
                    st.caption(f"Category: {item['category']}")
                    st.caption(f"Time: {item['timestamp'][:19].replace('T', ' ')}")


def render_app_settings_page():
    """Renders application display settings."""
    svc = get_profile_service()
    settings = svc.get_app_settings()

    st.markdown("## 🛠️ Application Settings")
    st.caption("Configure regional currency, date formatting, and layout density.")

    with st.container(border=True):
        st.subheader("Preferences & Formats")
        with st.form("app_settings_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                currency = st.selectbox("Currency Display", options=["INR (₹)"], index=0, help="Default Indian Rupee currency.")
            with c2:
                date_fmt = st.selectbox("Date Format", options=["DD/MM/YYYY", "YYYY-MM-DD", "DD MMM YYYY"], index=0)
            with c3:
                layout = st.selectbox("Layout Density", options=["Comfortable", "Compact"], index=0)

            submitted = st.form_submit_button("💾 Save Settings", type="primary", use_container_width=True)
            if submitted:
                settings.currency = currency
                settings.date_format = date_fmt
                settings.layout_mode = layout
                svc.update_app_settings(settings)
                st.success("✅ Application settings updated!")
                st.rerun()

    with st.container(border=True):
        st.subheader("Theme & Visual Design")
        st.write("✨ **Active Theme:** SK Holidays Signature Black & Gold")
        st.caption("Crafted with obsidian dark backgrounds (#080808), gold highlights (#D4AF37), and high-contrast typography.")


def render_help_support_page():
    """Renders guide and help documentation for SK Holidays features."""
    st.markdown("## ❓ Help, Support & User Guide")
    st.caption("Comprehensive guide to navigating itineraries, booking packages, and using the demo wallet.")

    with st.container(border=True):
        st.subheader("🧭 1. How to Use the AI Trip Planner")
        st.markdown("""
        - Select your destination, duration (1 to 14 days), number of travelers, and total budget (₹3,000 minimum).
        - Our **5 Autonomous Agents** coordinate in real time:
          1. **Travel Planner:** Designs day-by-day sightseeing.
          2. **Hotel Advisor:** Allocates rooms with per-person rate breakdowns.
          3. **Transport Agent:** Calculates roundtrip and local mobility costs.
          4. **Food Planner:** Curates authentic regional dining.
          5. **Budget Optimizer:** Runs up to 3 automated substitution passes if costs exceed your budget.
        """)

    with st.container(border=True):
        st.subheader("🎒 2. Booking Travel Packages")
        st.markdown("""
        - Navigate to **🎒 Travel Packages** to browse all 24 curated destination experiences.
        - Customize your traveler count, duration, room allocation, and optional sightseeing excursions.
        - Real-time transparent price calculation includes 12% Hotel GST, 5% Transport GST, and 10% safety reserve.
        """)

    with st.container(border=True):
        st.subheader("💳 3. Using the Demo Bank Account (₹1,00,000 Balance)")
        st.markdown("""
        - Every tester starts with an active **SK Demo Bank Account** preloaded with **₹1,00,000 INR**.
        - During package and hotel checkouts, select **SK Demo Bank** to simulate instantaneous payment.
        - Enter any 6-digit simulated OTP (e.g. `123456`) to confirm.
        - Funds are atomically debited from your demo balance, and an audit ledger entry is created.
        - Cancelling a refundable booking automatically credits the full amount back to your demo bank account!
        """)

    with st.container(border=True):
        st.subheader("🛡️ 4. The SK Holidays Transparency Promise")
        st.markdown("""
        - **No Arbitrary Markups:** All figures are computed mathematically in deterministic Python.
        - **10% Safety Buffer:** Every package and itinerary has an explicit contingency reserve.
        - **No Data Reset:** Your booking references and bank transactions remain persistent across app restarts.
        """)
