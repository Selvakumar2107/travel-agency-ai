"""SK Holidays — Premium AI-Powered Travel Planning Web Application.

Brand: SK Holidays
Tagline: "Your Journey. Your Budget. Our Intelligence."
Palette:
  Midnight navy: #101828
  Emerald green: #0D8B72
  Warm gold:     #D6B46A
  Ivory bg:      #F8F7F3
  White:         #FFFFFF
  Dark text:     #202938
"""

import os
import json
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from travel_agency.models import TripRequest, HotelTier, FoodTier, TransportTier, ActivityTier
from travel_agency.orchestrator import MultiAgentOrchestrator
from travel_agency.data import load_destinations, get_destination_by_id

# Page configuration
st.set_page_config(
    page_title="SK Holidays | Your Journey. Your Budget. Our Intelligence.",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

from travel_agency.theme import LUXURY_CSS, get_luxury_header_html, get_luxury_footer_html

# Inject Luxury Black & Gold Design System
st.markdown(LUXURY_CSS, unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables for SK Holidays."""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "🏠 Home"
    if "trip_plan" not in st.session_state:
        st.session_state.trip_plan = None
    elif st.session_state.trip_plan is not None:
        if not hasattr(st.session_state.trip_plan, "option_comparisons"):
            st.session_state.trip_plan = None
    if "api_key" not in st.session_state or not st.session_state.api_key:
        st.session_state.api_key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if "model_choice" not in st.session_state:
        st.session_state.model_choice = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if "preselected_destination" not in st.session_state:
        st.session_state.preselected_destination = None


init_session_state()

# Load destinations list
destinations = load_destinations()
dest_map = {d["name"]: d["id"] for d in destinations}
dest_id_to_name = {d["id"]: d["name"] for d in destinations}
dest_names = list(dest_map.keys())


# --- TOP BRAND HEADER COMPONENT ---
st.markdown(get_luxury_header_html(), unsafe_allow_html=True)



# --- NAVIGATION BAR ---
nav_cols = st.columns([0.9, 1.0, 1.1, 1.1, 1.1, 1.1, 1.1, 1.0, 0.9])

with nav_cols[0]:
    if st.button("🏠 Home", key="nav_btn_home", use_container_width=True, type="primary" if st.session_state.current_page == "🏠 Home" else "secondary"):
        st.session_state.current_page = "🏠 Home"
        st.session_state.active_booking_view = None
        st.rerun()

with nav_cols[1]:
    if st.button("✈️ Plan Trip", key="nav_btn_plan", use_container_width=True, type="primary" if st.session_state.current_page == "✈️ Plan a Trip" else "secondary"):
        st.session_state.current_page = "✈️ Plan a Trip"
        st.rerun()

with nav_cols[2]:
    if st.button("🏨 Find Hotels", key="nav_btn_find_hotels", use_container_width=True, type="primary" if st.session_state.current_page == "🏨 Find Hotels" else "secondary"):
        st.session_state.current_page = "🏨 Find Hotels"
        st.session_state.active_booking_view = None
        st.rerun()

with nav_cols[3]:
    if st.button("🎒 Packages", key="nav_btn_packages", use_container_width=True, type="primary" if st.session_state.current_page == "🎒 Packages" else "secondary"):
        st.session_state.current_page = "🎒 Packages"
        st.session_state.package_view_mode = "catalog"
        st.rerun()

with nav_cols[4]:
    if st.button("🗺️ Destinations", key="nav_btn_destinations", use_container_width=True, type="primary" if st.session_state.current_page == "🗺️ Destinations" else "secondary"):
        st.session_state.current_page = "🗺️ Destinations"
        st.rerun()

with nav_cols[5]:
    if st.button("📋 My Itinerary", key="nav_btn_itinerary", use_container_width=True, type="primary" if st.session_state.current_page == "📋 My Itinerary" else "secondary"):
        st.session_state.current_page = "📋 My Itinerary"
        st.rerun()

with nav_cols[6]:
    if st.button("📖 My Bookings", key="nav_btn_my_bookings", use_container_width=True, type="primary" if st.session_state.current_page == "📖 My Bookings" else "secondary"):
        st.session_state.current_page = "📖 My Bookings"
        st.rerun()

with nav_cols[7]:
    if st.button("💳 Demo Bank", key="nav_btn_demo_bank", use_container_width=True, type="primary" if st.session_state.current_page == "💳 Demo Bank" else "secondary"):
        st.session_state.current_page = "💳 Demo Bank"
        st.rerun()

with nav_cols[8]:
    if st.button("ℹ️ About Us", key="nav_btn_about", use_container_width=True, type="primary" if st.session_state.current_page == "ℹ️ About SK Holidays" else "secondary"):
        st.session_state.current_page = "ℹ️ About SK Holidays"
        st.rerun()


st.markdown("<hr style='margin:0.8rem 0 1.5rem 0; border:none; border-top:1px solid #CBD5E1;'>", unsafe_allow_html=True)


# --- SIDEBAR CONFIGURATION ---
model_choice = st.session_state.get("model_choice", "gemini-3.5-flash-lite")

from travel_agency.profile_ui import (
    render_sidebar_profile_panel,
    render_my_profile_page,
    render_saved_destinations_page,
    render_travel_preferences_page,
    render_notifications_page,
    render_app_settings_page,
    render_help_support_page,
)

with st.sidebar:
    render_sidebar_profile_panel()


# =========================================================================
# PAGE 1: HOME PAGE
# =========================================================================
if st.session_state.current_page == "🏠 Home":
    # 1. Cinematic Luxury Hero Section
    with st.container(border=True):
        st.caption("👑 **EXCLUSIVE AI TRAVEL ATELIER — SK HOLIDAYS**")
        st.title("Travel Beyond Ordinary.")
        st.markdown("*“Your Journey. Your Budget. Our Intelligence.”*")
        st.markdown(
            "Experience bespoke journeys curated by 5 specialized AI travel agents. "
            "From ₹3,000 baseline heritage escapes to royal 5-star retreats, every itinerary is "
            "mathematically audited with 10% contingency protection."
        )

        # Hero Action Buttons
        h_btn_col1, h_btn_col2, h_btn_col3 = st.columns([1.5, 1.5, 1.5])
        with h_btn_col1:
            if st.button("✨ Plan My Journey", key="hero_btn_plan_journey", use_container_width=True, type="primary"):
                st.session_state.current_page = "✈️ Plan a Trip"
                st.rerun()
        with h_btn_col2:
            if st.button("🏨 Explore Luxury Stays", key="hero_btn_explore_hotels", use_container_width=True, type="secondary"):
                st.session_state.current_page = "🏨 Find Hotels"
                st.session_state.active_booking_view = None
                st.rerun()
        with h_btn_col3:
            if st.button("🗺️ Discover Destinations", key="hero_btn_explore_destinations", use_container_width=True, type="secondary"):
                st.session_state.current_page = "🗺️ Destinations"
                st.rerun()

    st.divider()

    # 2. Premium Travel Search Panel
    with st.container(border=True):
        st.subheader("🔍 Curate Your Private Escape")
        st.caption("AI-ASSISTED RESERVATION")

        sp_col1, sp_col2, sp_col3, sp_col4, sp_col5 = st.columns([1.5, 1.2, 1.2, 1, 1.2])

        with sp_col1:
            qs_dest = st.selectbox(
                "Target Destination",
                options=dest_names,
                index=0,
                key="qs_dest_select"
            )
        with sp_col2:
            from datetime import date, timedelta
            today = date.today()
            qs_in = st.date_input("Check-in Date", value=today + timedelta(days=7), key="qs_checkin")
        with sp_col3:
            qs_out = st.date_input("Check-out Date", value=today + timedelta(days=10), key="qs_checkout")
        with sp_col4:
            qs_guests = st.number_input("Travelers", min_value=1, max_value=20, value=2, key="qs_guests")
        with sp_col5:
            qs_budget = st.number_input("Target Budget (₹)", min_value=3000, max_value=1000000, value=12000, step=1000, key="qs_budget")

        qs_submit = st.button("✨ Search Luxury Stays & Itineraries", key="hero_btn_search_experiences", type="primary", use_container_width=True)
        if qs_submit:
            st.session_state.preselected_destination = dest_map.get(qs_dest)
            st.session_state.current_page = "🏨 Find Hotels"
            st.session_state.active_booking_view = None
            st.rerun()

    # 3. Trust & Intelligence Indicators Strip
    with st.container(border=True):
        t1, t2, t3 = st.columns(3)
        with t1:
            st.markdown("🎯 **Personalized Itineraries**")
            st.caption("Curated day-by-day blueprints crafted around your travel style.")
        with t2:
            st.markdown("💰 **Deterministic Budgets**")
            st.caption("Audited itemized calculations with ₹3,000 minimum & 10% reserve.")
        with t3:
            st.markdown("🤖 **5 Specialized AI Agents**")
            st.caption("Autonomous multi-agent orchestration for stays, transit, and dining.")

    # 4. Featured Destinations Showcase with Luxury Styling
    st.subheader("🌟 Premier Domestic Retreats")
    st.caption("Handpicked scenic getaways with verified hotel inventory and sample budget bands.")

    feat_cols = st.columns(4)
    for idx, dest in enumerate(destinations[:4]):
        with feat_cols[idx]:
            with st.container(border=True):
                img_url = dest.get("image_url", "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80")
                st.image(img_url, use_container_width=True)
                st.caption(f"{dest['state']} • {dest['type']}")
                st.subheader(dest['name'])
                st.caption(f"{dest['tagline'][:85]}...")
                st.markdown(f"Starts at **{dest.get('indicative_budget_range', '₹3,000+')}**")
                if st.button(f"Plan {dest['name']} Trip", key=f"feat_{dest['id']}", use_container_width=True, type="secondary"):
                    st.session_state.preselected_destination = dest['id']
                    st.session_state.current_page = "✈️ Plan a Trip"
                    st.rerun()

    # 5. Section Showcasing the 5 Specialized AI Travel Agents
    with st.container(border=True):
        st.subheader("The 5 Autonomous AI Travel Agents")
        st.caption("POWERED BY GOOGLE GEMINI & ADK • Every trip is engineered through collaborative agent reasoning.")
        ag_c1, ag_c2, ag_c3, ag_c4, ag_c5 = st.columns(5)
        with ag_c1:
            st.markdown("🧭 **Travel Planning Agent**")
            st.caption("Engineers personalized day-by-day blueprints and pacing tailored to your traveler profile.")
        with ag_c2:
            st.markdown("🏨 **Hotel Advisor Agent**")
            st.caption("Ranks verified properties into Budget Match, Best Value, and Royal Luxury experiences.")
        with ag_c3:
            st.markdown("🚗 **Transport Agent**")
            st.caption("Optimizes intercity and in-city transit across shared, standard, and private chauffeurs.")
        with ag_c4:
            st.markdown("🍽️ **Food Planner Agent**")
            st.caption("Curates regional gastronomic recommendations and itemized daily dining allowances.")
        with ag_c5:
            st.markdown("📊 **Budget Optimizer**")
            st.caption("Enforces 3-pass optimization loops, ₹3,000 baseline, and 10% contingency protection.")

    # 6. Section Featuring 3-Tier Travel Experiences
    st.subheader("👑 Tailored Travel Collections")
    st.caption("Choose the travel style that matches your mood and budget.")

    tier_c1, tier_c2, tier_c3 = st.columns(3)
    with tier_c1:
        with st.container(border=True):
            st.caption("🌱 **BUDGET CONSCIOUS**")
            st.subheader("Smart Scenic Escapes")
            st.markdown("### From ₹3,000 INR")
            st.caption("Value-driven stays in comfortable economy rooms, scenic rail and coach journeys, and authentic local street and cafe dining.")
            st.markdown("- ✓ Clean, verified budget accommodations\n- ✓ Shared or standard regional transit\n- ✓ Priority self-guided sightseeing\n- ✓ 10% Emergency contingency buffer")
            if st.button("Explore Budget Escapes", key="tier_btn_budget", use_container_width=True, type="secondary"):
                st.session_state.current_page = "✈️ Plan a Trip"
                st.rerun()

    with tier_c2:
        with st.container(border=True):
            st.caption("⭐ **POPULAR CHOICE**")
            st.subheader("Balanced Comfort Journeys")
            st.markdown("### From ₹8,000 INR")
            st.caption("The ideal sweet spot of 3 to 4-star boutique hotels, delicious breakfast inclusions, dedicated AC transit, and curated guided entry.")
            st.markdown("- ✓ 3★ & 4★ Boutique hotels with breakfast\n- ✓ Private AC cab or 1st-class train\n- ✓ Curated restaurant dining plans\n- ✓ Priority museum and monument entry")
            if st.button("Explore Balanced Journeys", key="tier_btn_balanced", use_container_width=True, type="primary"):
                st.session_state.current_page = "✈️ Plan a Trip"
                st.rerun()

    with tier_c3:
        with st.container(border=True):
            st.caption("👑 **ROYAL LUXURY**")
            st.subheader("Ultra-Luxury Retreats")
            st.markdown("### From ₹18,000+ INR")
            st.caption("5-star heritage palaces, panoramic executive suites, dedicated luxury chauffeurs, VIP concierge passes, and gourmet dining.")
            st.markdown("- ✓ 5★ Heritage palaces & luxury resorts\n- ✓ Dedicated chauffeur throughout stay\n- ✓ Fine dining tasting menus\n- ✓ Private guided VIP experiences")
            if st.button("Explore Luxury Stays", key="tier_btn_luxury", use_container_width=True, type="secondary"):
                st.session_state.current_page = "🏨 Find Hotels"
                st.rerun()




# =========================================================================
# PAGE 2: PLAN A TRIP
# =========================================================================
elif st.session_state.current_page == "✈️ Plan a Trip":
    st.markdown("## ✈️ Design Your Journey with SK Holidays")
    st.caption("Tell us your parameters. Our 5 specialized AI agents will engineer your complete itinerary and cost breakdown.")

    # Budget Category Band Selection
    st.markdown("#### 1. Select Budget Band")
    budget_category = st.radio(
        "Choose Budget Category Band",
        options=[
            "Low Budget: ₹3,000–₹10,000",
            "Medium Budget: ₹10,001–₹25,000",
            "High Budget: ₹25,001–₹50,000",
            "Premium Budget: ₹50,001+",
            "Custom Budget (₹3,000+)"
        ],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        help="Choose a budget band. Minimum starting budget is ₹3,000."
    )

    preset_defaults = {
        "Low Budget: ₹3,000–₹10,000": 3000.0,
        "Medium Budget: ₹10,001–₹25,000": 15000.0,
        "High Budget: ₹25,001–₹50,000": 35000.0,
        "Premium Budget: ₹50,001+": 60000.0,
        "Custom Budget (₹3,000+)": 3000.0,
    }
    suggested_budget = preset_defaults[budget_category]

    with st.form(key="sk_trip_form"):
        st.markdown("#### 2. Departure, Destination & Travelers")
        col1, col2, col3 = st.columns(3)

        with col1:
            starting_location = st.text_input(
                "Starting Location",
                value="Bangalore / Bengaluru",
                placeholder="e.g. Bangalore, Chennai, Mumbai, Delhi",
                help="Your point of departure."
            )

            # Check if there is a preselected destination from other pages
            default_dest_idx = 2  # Mysuru
            if st.session_state.preselected_destination:
                pre_name = dest_id_to_name.get(st.session_state.preselected_destination)
                if pre_name in dest_names:
                    default_dest_idx = dest_names.index(pre_name)

            selected_dest_name = st.selectbox(
                "Destination",
                options=dest_names,
                index=default_dest_idx,
                help="Select from 8 curated destinations."
            )
            selected_dest_id = dest_map[selected_dest_name]
            dest_record = get_destination_by_id(selected_dest_id)
            st.caption(f"📍 {dest_record.get('state')} • *{dest_record.get('type')}*")

        with col2:
            num_travelers = st.number_input(
                "Number of Travelers",
                min_value=1,
                max_value=30,
                value=1,
                step=1,
                help="Total count of people traveling."
            )

            trip_duration = st.number_input(
                "Trip Duration (Days)",
                min_value=1,
                max_value=30,
                value=1,
                step=1,
                help="Duration of the trip. Never silently altered."
            )

        with col3:
            total_budget = st.number_input(
                "Total Target Budget in INR (₹)",
                min_value=3000.0,
                max_value=10000000.0,
                value=float(suggested_budget),
                step=500.0,
                format="%.2f",
                help="Minimum allowed budget is ₹3,000 INR."
            )
            st.caption("🛡️ *Includes 10% contingency reserve buffer.*")

            all_interests = [
                "Nature", "Heritage", "Adventure", "Beach", "Food & Cafes",
                "Relaxation", "Trekking", "Photography", "Culture", "Spiritual", "Nightlife"
            ]
            default_interests = [i for i in dest_record.get("suitable_interests", []) if i in all_interests][:3]
            selected_interests = st.multiselect(
                "Travel Preferences & Interests",
                options=all_interests,
                default=default_interests,
                help="Interests will guide activity selection."
            )

        st.markdown("---")
        st.markdown("#### 3. Personalization & Traveler Profile")
        pref_c1, pref_c2, pref_c3 = st.columns(3)

        with pref_c1:
            travel_style_choice = st.selectbox(
                "Travel Party Style",
                options=["family", "couple", "solo", "friends", "business"],
                format_func=lambda x: {
                    "family": "👨‍👩‍👧‍👦 Family Vacation",
                    "couple": "💑 Romantic Couple",
                    "solo": "🧳 Solo Explorer",
                    "friends": "🎉 Friends Getaway",
                    "business": "💼 Executive / Business",
                }.get(x, x.title()),
                index=0,
                help="Guides accommodation room setup, activity suggestions, and recommendations."
            )

        with pref_c2:
            preferred_pace_choice = st.selectbox(
                "Preferred Travel Pace",
                options=["relaxed", "balanced", "fast_paced"],
                format_func=lambda x: {
                    "relaxed": "🌿 Relaxed & Leisurely",
                    "balanced": "⚖️ Balanced & Moderate",
                    "fast_paced": "⚡ Fast-Paced & Energetic",
                }.get(x, x.title()),
                index=1,
                help="Determines sightseeing schedule density and daily transit windows."
            )

        with pref_c3:
            dietary_choice = st.selectbox(
                "Dietary Preference",
                options=["No Dietary Restriction", "Vegetarian", "Vegan", "Jain", "Non-Vegetarian", "Halal"],
                index=0,
                help="Hard constraint: strictly tailored dining recommendations."
            )

        spec_c1, spec_c2 = st.columns(2)
        with spec_c1:
            allergies_selected = st.multiselect(
                "Known Allergies / Food Sensitivities",
                options=["Peanuts", "Tree Nuts", "Dairy / Lactose", "Gluten / Wheat", "Eggs", "Shellfish / Seafood", "Soy"],
                default=[],
                help="Flagged in culinary reports and meal notes."
            )
        with spec_c2:
            access_selected = st.multiselect(
                "Accessibility & Special Requirements",
                options=["Wheelchair Accessible", "Elevator Required", "Ground Floor Priority", "Step-Free Access", "Elderly Friendly"],
                default=[],
                help="Factored into hotel matching and activity pacing."
            )

        st.markdown("---")
        st.markdown("#### 4. Baseline Tier Preferences")
        tier_col1, tier_col2, tier_col3 = st.columns(3)

        is_starting_low = (total_budget <= 10000.0)

        with tier_col1:
            hotel_tier = st.selectbox(
                "Accommodation Preference",
                options=["budget", "standard", "premium"],
                index=0 if is_starting_low else 1,
                format_func=lambda x: f"🏨 {x.capitalize()} Tier",
                help="Initial lodging preference."
            )

        with tier_col2:
            transport_tier = st.selectbox(
                "Transport Preference",
                options=["shared", "standard", "private"],
                index=0 if is_starting_low else 1,
                format_func=lambda x: "🚌 Shared / Public Transit" if x == "shared" else ("🚗 Standard AC Cab/Train" if x == "standard" else "🚘 Dedicated Private Chauffeur"),
                help="Transit mode preference."
            )

        with tier_col3:
            food_tier = st.selectbox(
                "Dietary & Dining Preference",
                options=["economy", "standard", "comfort"],
                index=0 if is_starting_low else 1,
                format_func=lambda x: f"🍽️ {x.capitalize()} Dining",
                help="Daily meal allowance tier."
            )

        activity_tier: ActivityTier = "budget" if is_starting_low else "standard"

        generate_submit = st.form_submit_button(
            label="✨ Generate My SK Holidays Itinerary",
            use_container_width=True
        )

    if generate_submit:
        try:
            trip_request = TripRequest(
                destination_id=selected_dest_id,
                num_travelers=int(num_travelers),
                trip_duration_days=int(trip_duration),
                total_budget=float(total_budget),
                hotel_tier=hotel_tier,  # type: ignore
                food_tier=food_tier,    # type: ignore
                transport_tier=transport_tier,  # type: ignore
                activity_tier=activity_tier,
                interests=selected_interests,
                starting_location=starting_location,
                contingency_percent=10.0,
                travel_style=travel_style_choice,
                dietary_preference=dietary_choice,
                allergies=allergies_selected,
                accessibility_requirements=access_selected,
                preferred_pace=preferred_pace_choice,
            )

            with st.spinner("🤖 SK Holidays Agents are designing your journey..."):
                orchestrator = MultiAgentOrchestrator(
                    api_key=st.session_state.api_key,
                    model_name=model_choice
                )
                plan = orchestrator.plan_trip(trip_request)
                st.session_state.trip_plan = plan

            st.session_state.current_page = "📋 My Itinerary"
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error generating itinerary: {e}")


# =========================================================================
# PAGE 3: FIND HOTELS & AI RECOMMENDATIONS
# =========================================================================
elif st.session_state.current_page == "🏨 Find Hotels":
    from travel_agency.booking_ui import render_hotel_discovery_page
    render_hotel_discovery_page()


# =========================================================================
# PAGE 4: DESTINATIONS CATALOG
# =========================================================================
elif st.session_state.current_page == "🗺️ Destinations":
    st.markdown("## 🗺️ Explore SK Holidays Destinations")
    st.caption("Curated collection of premier Indian retreats, categorized by style and budget.")

    dest_filter = st.selectbox(
        "Filter by Travel Style",
        options=["All Destinations", "Hill Stations", "Heritage & Culture", "Beaches & Coastal", "Spiritual & Adventure"],
        index=0
    )

    filtered_dests = destinations
    if dest_filter == "Hill Stations":
        filtered_dests = [d for d in destinations if "Hill" in d.get("type", "") or "Tea" in d.get("type", "")]
    elif dest_filter == "Heritage & Culture":
        filtered_dests = [d for d in destinations if "Heritage" in d.get("type", "") or "Palaces" in d.get("type", "")]
    elif dest_filter == "Beaches & Coastal":
        filtered_dests = [d for d in destinations if "Beach" in d.get("type", "") or "Coastal" in d.get("type", "")]
    elif dest_filter == "Spiritual & Adventure":
        filtered_dests = [d for d in destinations if "Spiritual" in d.get("type", "") or "Adventure" in d.get("type", "")]

    d_cols = st.columns(2)
    for idx, dest in enumerate(filtered_dests):
        with d_cols[idx % 2]:
            with st.container(border=True):
                img_url = dest.get("image_url", "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80")
                st.image(img_url, use_container_width=True)

                c_top1, c_top2 = st.columns([3, 2])
                with c_top1:
                    st.caption(f"📍 {dest['state']} • {dest['type']}")
                with c_top2:
                    st.caption(f"🗓️ Best: {dest.get('best_season', 'Year-round')}")

                st.subheader(dest['name'])
                st.write(f"*{dest['tagline']}*")

                interests = dest.get('suitable_interests', [])[:4]
                if interests:
                    st.caption("🏷️ " + " • ".join(interests))

                st.markdown(f"**Indicative Cost:** `{dest.get('indicative_budget_range', '₹3,000+')}` *(Estimate)*")

                st.divider()
                dest_btn_c1, dest_btn_c2 = st.columns(2)
                with dest_btn_c1:
                    if st.button(f"✨ Plan {dest['name']} Trip", key=f"cat_plan_{dest['id']}", use_container_width=True):
                        st.session_state.preselected_destination = dest['id']
                        st.session_state.current_page = "✈️ Plan a Trip"
                        st.rerun()
                with dest_btn_c2:
                    if st.button(f"🏨 Stays in {dest['name']}", key=f"cat_hotel_{dest['id']}", type="secondary", use_container_width=True):
                        st.session_state.preselected_destination = dest['id']
                        st.session_state.current_page = "🏨 Find Hotels"
                        st.session_state.active_booking_view = None
                        st.rerun()



# =========================================================================
# PAGE 4: MY ITINERARY DASHBOARD
# =========================================================================
elif st.session_state.current_page == "📋 My Itinerary":
    plan = st.session_state.trip_plan

    if plan is None:
        with st.container(border=True):
            st.subheader("🧭 No Itinerary Generated Yet")
            st.write("Your personalized travel blueprint will appear here once generated by our 5 AI agents.")
            btn_c1, btn_c2, btn_c3 = st.columns([1.5, 2, 1.5])
            with btn_c2:
                if st.button("✨ Start Planning Your Journey", key="itin_empty_start_plan_btn", use_container_width=True, type="primary"):
                    st.session_state.current_page = "✈️ Plan a Trip"
                    st.rerun()
    else:
        # Trip Overview Hero
        dest_img = plan.destination.get("image_url", "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1200&q=80")
        start_loc = getattr(plan.request, "starting_location", "Bangalore")

        with st.container(border=True):
            st.image(dest_img, use_container_width=True)
            st.caption("✨ SK HOLIDAYS PERSONALIZED BLUEPRINT")
            st.header(f"🌟 {plan.destination['name']} Private Journey")
            st.write(f"Departing from **{start_loc}** • **{plan.request.num_travelers}** Traveler(s) • **{plan.request.trip_duration_days}** Day(s)")

        # Action Button: Modify Preferences / Regenerate
        replan_c1, replan_c2 = st.columns([7, 3])
        with replan_c1:
            st.write(f"Personalized blueprint for **{plan.request.num_travelers} traveler(s)** • Travel Style: **{plan.request.travel_style.title()}** • Pace: **{plan.request.preferred_pace.title()}**")
        with replan_c2:
            if st.button("🔄 Modify Preferences & Re-Plan", key="itin_btn_replan", use_container_width=True, type="secondary"):
                st.session_state.current_page = "✈️ Plan a Trip"
                st.rerun()

        st.write("")

        # Dynamic Agent Progress Tracker with Timings & Mode
        tr_rep = plan.agent_reports.get("travel_planner")
        ht_rep = plan.agent_reports.get("hotel_advisor")
        tp_rep = plan.agent_reports.get("transport_planner")
        fd_rep = plan.agent_reports.get("food_planner")
        bg_rep = plan.agent_reports.get("budget_optimizer")

        with st.container(border=True):
            st.subheader("🤖 SK Holidays AI Agent Orchestration Status")
            st.caption("✅ All 5 Autonomous Agents Completed Successfully")

            t_cols = st.columns(5)
            agent_items = [
                ("🧭", "Travel Planner", tr_rep),
                ("🏨", "Hotel Advisor", ht_rep),
                ("🚗", "Transport Agent", tp_rep),
                ("🍽️", "Food Planner", fd_rep),
                ("📊", "Budget Optimizer", bg_rep),
            ]
            for col, (icon, name, rep) in zip(t_cols, agent_items):
                with col:
                    with st.container(border=True):
                        st.write(f"**{icon} {name}**")
                        if rep:
                            dur = f"{rep.execution_time_ms:.0f}ms" if rep.execution_time_ms > 0 else "<1ms"
                            engine = "Gemini" if rep.used_gemini else "Deterministic"
                            st.caption(f"⚡ {engine} ({dur})")
                        else:
                            st.caption("⚡ Complete")

        # Key Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric(
                label="Total Trip Estimate",
                value=f"₹{plan.final_costs.total_estimated_cost:,.2f}",
                delta=f"-₹{plan.savings_achieved:,.2f} Saved" if plan.savings_achieved > 0 else None,
                delta_color="inverse"
            )
        with m2:
            st.metric(label="Your Selected Budget", value=f"₹{plan.request.total_budget:,.2f}")
        with m3:
            st.metric(label="Cost Per Traveler", value=f"₹{plan.final_costs.cost_per_person:,.2f}", help=f"Group of {plan.request.num_travelers}")
        with m4:
            if plan.is_shortfall:
                st.metric(label="Budget Shortfall", value=f"₹{plan.remaining_balance_or_shortfall:,.2f}", delta="Exceeds Budget", delta_color="inverse")
            else:
                st.metric(label="Remaining Surplus", value=f"₹{plan.remaining_balance_or_shortfall:,.2f}", delta="Within Budget", delta_color="normal")

        st.markdown("<br>", unsafe_allow_html=True)

        # Before & After Budget Optimization Comparison Card
        if plan.optimization_history or plan.savings_achieved > 0 or plan.is_shortfall:
            st.markdown("### 🔄 Budget Optimization Audit & Before-After Comparison")
            opt_c1, opt_c2 = st.columns([1.5, 1])
            with opt_c1:
                diff_init_str = f"Over by ₹{plan.initial_difference:,.2f}" if plan.initial_difference > 0 else "Under Budget"
                status_final_str = f"Shortfall: ₹{plan.remaining_balance_or_shortfall:,.2f}" if plan.is_shortfall else f"Surplus: +₹{plan.remaining_balance_or_shortfall:,.2f}"
                passes_str = f"{len(plan.optimization_history)} Pass(es) Applied (Max 3)"

                audit_table_md = (
                    "| Audit Metric | Initial State | Optimized State | Variance / Savings |\n"
                    "| :--- | :---: | :---: | :---: |\n"
                    f"| **Estimated Total Cost** | ₹{plan.initial_costs.total_estimated_cost:,.2f} | **₹{plan.final_costs.total_estimated_cost:,.2f}** | **-₹{plan.savings_achieved:,.2f}** |\n"
                    f"| **User Target Budget** | ₹{plan.request.total_budget:,.2f} | ₹{plan.request.total_budget:,.2f} | Strict Baseline Preserved |\n"
                    f"| **Budget Balance / Status** | {diff_init_str} | **{status_final_str}** | {passes_str} |"
                )
                st.markdown(audit_table_md)
            with opt_c2:
                if plan.optimization_history:
                    st.markdown("**Substitutions Applied:**")
                    for p in plan.optimization_history:
                        st.info(f"**Pass {p.pass_number}:** {p.action_taken} *(Saved ₹{p.savings:,.2f})*")
                else:
                    st.success("✅ Direct Fit: No substitutions required to meet budget targets.")

        # Three Comparison Cards (Economy, Balanced, Premium)
        st.markdown("### ⚖️ Three Travel Tier Comparisons")
        st.caption("Standard tier bundles with 10% contingency reserve included. Highlights the most affordable feasible plan.")

        option_comparisons = getattr(plan, "option_comparisons", None)
        if not option_comparisons:
            try:
                orchestrator = MultiAgentOrchestrator(api_key=st.session_state.api_key)
                option_comparisons = orchestrator.generate_option_comparisons(plan.request, plan.destination)
            except Exception:
                option_comparisons = []

        if option_comparisons:
            p_cols = st.columns(3)
            p_styles = ["🌱 Economy & Transit", "⭐ Balanced Standard", "👑 Luxury & Dedicated"]

            for idx, opt in enumerate(option_comparisons):
                subtitle = p_styles[idx % 3]
                is_over = opt.is_over_budget

                with p_cols[idx]:
                    with st.container(border=True):
                        st.subheader(opt.plan_name)
                        st.caption(subtitle)
                        if opt.is_most_affordable_feasible and not is_over:
                            st.success("🏆 MOST AFFORDABLE")
                        elif not is_over:
                            st.info("✅ FITS BUDGET")
                        else:
                            st.error("❌ OVER BUDGET")

                        st.metric(label="Total Estimate", value=f"₹{opt.costs.total_estimated_cost:,.2f}")
                        st.caption(f"₹{opt.costs.cost_per_person:,.2f} per person")
                        st.divider()

                        st.write(f"🏨 **Hotel:** {opt.hotel_tier.capitalize()} ({opt.hotel_name}) — ₹{opt.costs.hotel_accommodation:,.0f}")
                        st.write(f"🚌 **Transit:** {opt.transport_tier.capitalize()} — ₹{opt.costs.intercity_transport + opt.costs.local_transport:,.0f}")
                        st.write(f"🍽️ **Dining:** {opt.food_tier.capitalize()} — ₹{opt.costs.food:,.0f}")
                        st.write(f"🎟️ **Activities:** {opt.activity_tier.capitalize()} — ₹{opt.costs.activities:,.0f}")
                        st.write(f"🛡️ **10% Reserve:** ₹{opt.costs.contingency_reserve:,.0f}")

                        st.divider()
                        if not is_over:
                            st.write(f"**Surplus:** :green[+₹{opt.difference:,.2f}]")
                        else:
                            st.write(f"**Shortfall:** :red[-₹{opt.difference:,.2f}]")

        st.write("")

        # Low Budget Advisory if Shortfall
        cheaper_alts = getattr(plan, "cheaper_alternatives", []) or []
        if plan.is_shortfall or plan.request.total_budget <= 10000.0:
            with st.expander("💡 SK Holidays Low Budget Feasibility Advisory", expanded=plan.is_shortfall):
                st.markdown(f"""
                **Feasibility Audit for ₹{plan.request.total_budget:,.2f} Target:**
                - Destination: **{plan.destination['name']}** for {plan.request.num_travelers} traveler(s) across {plan.request.trip_duration_days} day(s).
                - Status: {'Shortfall of ₹' + f'{plan.remaining_balance_or_shortfall:,.2f}' if plan.is_shortfall else 'Within target budget.'}
                """)
                if plan.request.trip_duration_days > 1:
                    st.info("💡 **Short-Trip Alternative:** A 1-day excursion saves on accommodation and multi-day meal costs while retaining priority sightseeing highlights.")

                if cheaper_alts:
                    st.markdown("##### 📍 More Affordable Destination Alternatives (Same Group & Duration):")
                    alt_data = []
                    for alt in cheaper_alts:
                        alt_data.append({
                            "Destination": f"{alt.destination_name} ({alt.state})",
                            "Economy Estimate": f"₹{alt.estimated_economy_cost:,.2f}",
                            "Feasibility": "✅ Fits Budget" if alt.feasible else "❌ Over Budget",
                            "Savings vs Selected": f"₹{alt.savings_vs_selected:,.2f}",
                            "Note": alt.note
                        })
                    st.table(alt_data)

        # Day-by-Day Itinerary with Transit Times & Dietary Alignments
        st.markdown("### 📅 Curated Day-by-Day Itinerary")
        for day in plan.itinerary:
            with st.expander(f"📍 Day {day.day}: {day.title}", expanded=(day.day == 1)):
                d_c1, d_c2, d_c3 = st.columns(3)
                with d_c1:
                    st.markdown(f"**🌅 Morning Experience**\n\n{day.morning}")
                with d_c2:
                    st.markdown(f"**☀️ Afternoon Highlights**\n\n{day.afternoon}")
                with d_c3:
                    st.markdown(f"**🌆 Evening Relaxation**\n\n{day.evening}")
                st.markdown(f"🍽️ **Dining Highlight:** {day.dining_highlight}")
                if getattr(day, "estimated_transit_time", None):
                    st.markdown(f"🚙 **Estimated Transit Time:** `{day.estimated_transit_time}`")
                if getattr(day, "dietary_alignment_note", None):
                    st.markdown(f"🥗 **Dietary Alignment:** *{day.dietary_alignment_note}*")
                if getattr(day, "estimated_day_cost", 0.0) > 0:
                    st.caption(f"💰 *Estimated Day Cost: ₹{day.estimated_day_cost:,.2f}*")
                if day.tips:
                    st.caption(f"💡 *SK Holidays Insider Tip:* {day.tips}")

        # Itemized Financial Breakdown
        st.markdown("### 📊 Itemized Financial Breakdown")
        bk_c1, bk_c2 = st.columns([3, 2])

        with bk_c1:
            fin_table_md = (
                "| Category | Calculation Details | Amount (INR) |\n"
                "| :--- | :--- | :---: |\n"
                f"| 🏨 **Accommodation** | {plan.final_costs.num_rooms} room(s) × {plan.final_costs.num_nights} night(s) @ ₹{plan.selected_hotel.get('price_per_night', 0):,.0f} | ₹{plan.final_costs.hotel_accommodation:,.2f} |\n"
                f"| 🚂 **Intercity Transit** | {plan.selected_tiers['transport_tier'].capitalize()} mode roundtrip | ₹{plan.final_costs.intercity_transport:,.2f} |\n"
                f"| 🚕 **Local Mobility** | In-city daily transit across {plan.request.trip_duration_days} day(s) | ₹{plan.final_costs.local_transport:,.2f} |\n"
                f"| 🍽️ **Meals & Dining** | {plan.selected_tiers['food_tier'].capitalize()} plan | ₹{plan.final_costs.food:,.2f} |\n"
                f"| 🎟️ **Sightseeing** | Curated {plan.selected_tiers['activity_tier'].capitalize()} passes | ₹{plan.final_costs.activities:,.2f} |\n"
                f"| 🛡️ **Contingency Reserve** | 10% buffer on subtotal | ₹{plan.final_costs.contingency_reserve:,.2f} |\n"
                f"| 🏆 **GRAND TOTAL ESTIMATE** | **Deterministic Total** | **₹{plan.final_costs.total_estimated_cost:,.2f}** |"
            )
            st.markdown(fin_table_md)

        with bk_c2:
            st.markdown("##### 📈 Budget Utilization")
            budget_util = (plan.final_costs.total_estimated_cost / plan.request.total_budget) * 100 if plan.request.total_budget > 0 else 100
            prog = min(1.0, max(0.0, plan.final_costs.total_estimated_cost / plan.request.total_budget)) if plan.request.total_budget > 0 else 1.0
            st.progress(prog)
            st.write(f"**Budget Used:** {budget_util:.1f}%")

            if plan.optimization_history:
                st.markdown("##### 🔄 Optimization Feedback Passes")
                for p in plan.optimization_history:
                    st.info(f"**Pass {p.pass_number}:** {p.action_taken} — *Saved ₹{p.savings:,.2f}*")
            else:
                st.success("✅ Initial options matched target budget without adjustments.")

        # Agent Detailed Reports
        st.markdown("### 🤖 Specialized AI Agent Reports & Explainability")
        agent_tabs = st.tabs([
            "🧭 Travel Planner",
            "🏨 Hotel Advisor",
            "🚗 Transport Agent",
            "🍽️ Food Recommendation",
            "📊 Budget Optimizer"
        ])

        agent_keys = [
            ("travel_planner", agent_tabs[0]),
            ("hotel_advisor", agent_tabs[1]),
            ("transport_planner", agent_tabs[2]),
            ("food_planner", agent_tabs[3]),
            ("budget_optimizer", agent_tabs[4]),
        ]

        for key, tab in agent_keys:
            report = plan.agent_reports.get(key)
            if report:
                with tab:
                    head_c1, head_c2 = st.columns([7, 3])
                    with head_c1:
                        st.markdown(f"#### {report.agent_name}")
                        st.caption(f"**Role:** {report.agent_role} • **Engine:** {'✨ Google Gemini Active' if report.used_gemini else '🛡️ Deterministic Rule Engine'}")
                    with head_c2:
                        dur_str = f"{report.execution_time_ms:.1f}ms" if report.execution_time_ms > 0 else "<1ms"
                        st.caption(f"⏱️ **Execution Time:** {dur_str}")

                    st.markdown(report.summary)

                    # Pros and Cons display
                    if report.pros or report.cons:
                        pc1, pc2 = st.columns(2)
                        with pc1:
                            if report.pros:
                                st.markdown("##### 🟢 Advantages & Suitability")
                                for pro in report.pros:
                                    st.markdown(f"- ✅ {pro}")
                        with pc2:
                            if report.cons:
                                st.markdown("##### 🟡 Trade-Offs & Limitations")
                                for con in report.cons:
                                    st.markdown(f"- ⚠️ {con}")

                    # Trade-offs & Recommendations
                    if report.trade_offs:
                        st.markdown("##### ⚖️ Trade-off Analysis")
                        for to in report.trade_offs:
                            st.markdown(f"- {to}")

                    if report.recommendations:
                        st.markdown("##### 📋 Agent Recommendations & Notes")
                        for rec in report.recommendations:
                            st.markdown(f"- {rec}")

                    if report.scoring_breakdown:
                        with st.expander("🎯 Transparent Scoring Breakdown (Deterministic Model)", expanded=False):
                            for factor, weight in report.scoring_breakdown.items():
                                st.write(f"- **{factor.replace('_', ' ').title()}:** {weight}")

                    if report.key_metrics:
                        with st.expander("🔍 Key Structured Metrics", expanded=False):
                            st.json(report.key_metrics)

                    st.caption(f"🛡️ *Disclaimer:* {report.disclaimer}")

        # Export JSON
        st.markdown("---")
        ex_c1, ex_c2 = st.columns([2, 8])
        with ex_c1:
            plan_json = plan.model_dump_json(indent=2)
            st.download_button(
                label="📥 Download Itinerary (JSON)",
                data=plan_json,
                file_name=f"sk_holidays_itinerary_{plan.destination['id']}.json",
                mime="application/json",
                use_container_width=True
            )
        with ex_c2:
            st.caption("Export full SK Holidays itinerary, 3-plan comparisons, and financial calculations.")


# =========================================================================
# PAGE: TRAVEL PACKAGES PAGE
# =========================================================================
elif st.session_state.current_page == "🎒 Packages":
    from travel_agency.package_ui import render_travel_packages_page
    render_travel_packages_page()


# =========================================================================
# PAGE 6: MY BOOKINGS DASHBOARD
# =========================================================================
elif st.session_state.current_page == "📖 My Bookings":
    from travel_agency.booking_ui import render_my_bookings_page
    render_my_bookings_page()


# =========================================================================
# PAGE 7: MY DEMO BANK ACCOUNT DASHBOARD
# =========================================================================
elif st.session_state.current_page == "💳 Demo Bank":
    from travel_agency.bank_ui import render_demo_bank_page
    render_demo_bank_page()


# =========================================================================
# PAGE 8: ABOUT SK HOLIDAYS
# =========================================================================
elif st.session_state.current_page == "ℹ️ About SK Holidays":
    st.markdown("## ℹ️ About SK Holidays")
    st.markdown("#### *Your Journey. Your Budget. Our Intelligence.*")

    st.markdown("""
    **SK Holidays** is an AI-powered travel curator dedicated to making personalized, premium travel planning effortless, transparent, and accessible across every budget.

    Whether you are planning a **₹3,000 weekend getaway** to a nearby cultural retreat or a luxury heritage vacation, our platform pairs specialized artificial intelligence with deterministic mathematical precision.
    """)

    st.markdown("### 🏛️ The Five Autonomous Travel Agents")
    st.markdown("""
    1. **Travel Planning Agent:** Curates day-by-day itineraries tailored to your unique interests and duration.
    2. **Hotel Recommendation Agent:** Matches quality accommodations across budget, standard, and premium tiers with room allocation math.
    3. **Transport Agent:** Optimizes intercity and local transit across shared, standard, and private modes.
    4. **Food Recommendation Agent:** Designs balanced dining plans with real regional flavor and practical savings tips.
    5. **Budget Optimization Agent:** Audits your trip costs deterministically and runs up to 3 optimization passes if expenses exceed your target budget.
    """)

    st.markdown("### 🛡️ The SK Holidays Transparency Promise")
    st.markdown("""
    - **No Hidden Markups:** 100% deterministic arithmetic calculated directly in Python.
    - **10% Contingency Reserve:** Every single itinerary incorporates an automatic safety buffer for unforeseen expenses.
    - **Invariable Parameters:** We will never shorten your trip or decrease traveler count without your explicit consent.
    """)


# =========================================================================
# PROFILE & SETTINGS PAGES
# =========================================================================
elif st.session_state.current_page == "👤 My Profile":
    render_my_profile_page()

elif st.session_state.current_page == "⭐ Saved Destinations":
    render_saved_destinations_page()

elif st.session_state.current_page == "⚙️ Travel Preferences":
    render_travel_preferences_page()

elif st.session_state.current_page == "🔔 Notifications":
    render_notifications_page()

elif st.session_state.current_page == "🛠️ App Settings":
    render_app_settings_page()

elif st.session_state.current_page == "❓ Help & Support":
    render_help_support_page()


# --- GLOBAL FOOTER ---
st.markdown(get_luxury_footer_html(), unsafe_allow_html=True)

