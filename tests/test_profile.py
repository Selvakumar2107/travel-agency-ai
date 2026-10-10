"""Automated unit tests for ProfileService, Preferences, Saved Destinations, and Notifications."""

import pytest
from pathlib import Path
from travel_agency.profile_service import ProfileService, UserProfile, TravelPreferences, AppSettings


@pytest.fixture
def temp_profile_svc(tmp_path):
    db_file = tmp_path / "test_profile.db"
    return ProfileService(db_path=db_file)


def test_default_profile_initialization(temp_profile_svc):
    profile = temp_profile_svc.get_profile()
    assert profile.user_id == "demo_user"
    assert profile.display_name == "Demo Traveller"
    assert profile.email == "traveller@skholidays.com"
    assert profile.avatar_initials == "DT"


def test_update_profile_and_initials_computation(temp_profile_svc):
    profile = temp_profile_svc.get_profile()
    profile.display_name = "Rajesh Sharma"
    profile.email = "rajesh.sharma@example.com"
    profile.phone = "+91 91234 56789"
    profile.bio = "Heritage lover"
    temp_profile_svc.update_profile(profile)

    updated = temp_profile_svc.get_profile()
    assert updated.display_name == "Rajesh Sharma"
    assert updated.email == "rajesh.sharma@example.com"
    assert updated.avatar_initials == "RS"
    assert updated.phone == "+91 91234 56789"
    assert updated.bio == "Heritage lover"


def test_travel_preferences_crud(temp_profile_svc):
    prefs = temp_profile_svc.get_preferences()
    assert prefs.min_budget >= 3000
    assert prefs.package_tier in ["Economy", "Comfort", "Luxury"]

    prefs.min_budget = 10000
    prefs.max_budget = 75000
    prefs.package_tier = "Luxury"
    prefs.food_preference = "Jain Dietary Guidelines"
    prefs.transport_preference = "Private Cab / Chauffeur"
    prefs.destination_types = ["Hill Stations & Nature", "Wildlife & Adventure"]
    temp_profile_svc.update_preferences(prefs)

    reloaded = temp_profile_svc.get_preferences()
    assert reloaded.min_budget == 10000
    assert reloaded.max_budget == 75000
    assert reloaded.package_tier == "Luxury"
    assert reloaded.food_preference == "Jain Dietary Guidelines"
    assert "Wildlife & Adventure" in reloaded.destination_types


def test_saved_destinations_lifecycle(temp_profile_svc):
    # Initially 2 seeded
    initial = temp_profile_svc.get_saved_destinations()
    assert len(initial) >= 2

    # Save a new destination
    added = temp_profile_svc.save_destination(
        destination_id="munnar",
        destination_name="Munnar",
        state="Kerala"
    )
    assert added is True
    assert temp_profile_svc.is_destination_saved("munnar") is True

    # Duplicate save returns False (or no error due to IGNORE)
    dup = temp_profile_svc.save_destination(
        destination_id="munnar",
        destination_name="Munnar",
        state="Kerala"
    )
    assert dup is False

    # Remove destination
    removed = temp_profile_svc.remove_saved_destination("munnar")
    assert removed is True
    assert temp_profile_svc.is_destination_saved("munnar") is False


def test_app_settings_persistence(temp_profile_svc):
    settings = temp_profile_svc.get_app_settings()
    assert settings.currency == "INR (₹)"

    settings.date_format = "YYYY-MM-DD"
    settings.layout_mode = "Compact"
    temp_profile_svc.update_app_settings(settings)

    reloaded = temp_profile_svc.get_app_settings()
    assert reloaded.date_format == "YYYY-MM-DD"
    assert reloaded.layout_mode == "Compact"


def test_real_notifications_retrieval(temp_profile_svc):
    # On a fresh DB with no bookings or transactions, notifications list is empty
    notifs = temp_profile_svc.get_real_notifications()
    assert isinstance(notifs, list)
