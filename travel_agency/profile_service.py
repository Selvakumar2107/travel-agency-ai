"""Profile, Travel Preferences, Saved Destinations, and Settings Service for SK Holidays."""

import sqlite3
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from travel_agency.booking_repository import DB_PATH as BOOKINGS_DB_PATH
from travel_agency.bank_service import DemoBankService

logger = logging.getLogger(__name__)


class UserProfile(BaseModel):
    user_id: str = "demo_user"
    display_name: str = "Demo Traveller"
    email: str = "traveller@skholidays.com"
    phone: str = "+91 98765 43210"
    bio: str = "Passionate explorer of Indian heritage and luxury domestic retreats."
    avatar_initials: str = "DT"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class TravelPreferences(BaseModel):
    user_id: str = "demo_user"
    destination_types: List[str] = Field(default_factory=lambda: ["Heritage & Culture", "Hill Stations & Nature"])
    min_budget: int = 5000
    max_budget: int = 50000
    package_tier: str = "Comfort"
    food_preference: str = "North & South Indian Regional"
    transport_preference: str = "AC Train / Luxury Bus"
    accessibility: str = "Standard Mobility"
    special_requests: str = "Window seat and quiet high-floor room preferred."
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SavedDestination(BaseModel):
    id: Optional[int] = None
    user_id: str = "demo_user"
    destination_id: str
    destination_name: str
    state: str
    saved_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AppSettings(BaseModel):
    user_id: str = "demo_user"
    currency: str = "INR (₹)"
    date_format: str = "DD/MM/YYYY"
    layout_mode: str = "Comfortable"
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ProfileService:
    """Manages local profile, travel preferences, saved destinations, and settings."""

    _instances: Dict[str, "ProfileService"] = {}
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path).resolve() if db_path else BOOKINGS_DB_PATH.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Optional[Path] = None) -> "ProfileService":
        resolved_path = Path(db_path).resolve() if db_path else BOOKINGS_DB_PATH.resolve()
        key = str(resolved_path)
        if key not in cls._instances:
            with cls._lock:
                if key not in cls._instances:
                    cls._instances[key] = cls(db_path=resolved_path)
        return cls._instances[key]

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates profile, preferences, saved destinations, and settings tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT,
                    bio TEXT,
                    avatar_initials TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS travel_preferences (
                    user_id TEXT PRIMARY KEY,
                    destination_types TEXT NOT NULL,
                    min_budget INTEGER NOT NULL,
                    max_budget INTEGER NOT NULL,
                    package_tier TEXT NOT NULL,
                    food_preference TEXT NOT NULL,
                    transport_preference TEXT NOT NULL,
                    accessibility TEXT,
                    special_requests TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_destinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    destination_id TEXT NOT NULL,
                    destination_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    UNIQUE(user_id, destination_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    user_id TEXT PRIMARY KEY,
                    currency TEXT NOT NULL,
                    date_format TEXT NOT NULL,
                    layout_mode TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Seed default profile if not exists
            cursor.execute("SELECT user_id FROM user_profiles WHERE user_id = 'demo_user'")
            if not cursor.fetchone():
                now_str = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO user_profiles (user_id, display_name, email, phone, bio, avatar_initials, created_at, updated_at)
                    VALUES ('demo_user', 'Demo Traveller', 'traveller@skholidays.com', '+91 98765 43210', 'Passionate explorer of Indian heritage and luxury domestic retreats.', 'DT', ?, ?)
                """, (now_str, now_str))

                cursor.execute("""
                    INSERT INTO travel_preferences (user_id, destination_types, min_budget, max_budget, package_tier, food_preference, transport_preference, accessibility, special_requests, updated_at)
                    VALUES ('demo_user', 'Heritage & Culture,Hill Stations & Nature', 5000, 50000, 'Comfort', 'North & South Indian Regional', 'AC Train / Luxury Bus', 'Standard Mobility', 'Window seat and quiet high-floor room preferred.', ?)
                """, (now_str,))

                cursor.execute("""
                    INSERT INTO app_settings (user_id, currency, date_format, layout_mode, updated_at)
                    VALUES ('demo_user', 'INR (₹)', 'DD/MM/YYYY', 'Comfortable', ?)
                """, (now_str,))

                # Seed 2 initial favorites
                cursor.execute("""
                    INSERT OR IGNORE INTO saved_destinations (user_id, destination_id, destination_name, state, saved_at)
                    VALUES ('demo_user', 'ooty', 'Ooty', 'Tamil Nadu', ?)
                """, (now_str,))
                cursor.execute("""
                    INSERT OR IGNORE INTO saved_destinations (user_id, destination_id, destination_name, state, saved_at)
                    VALUES ('demo_user', 'coorg', 'Coorg', 'Karnataka', ?)
                """, (now_str,))

            conn.commit()

    def get_profile(self, user_id: str = "demo_user") -> UserProfile:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return UserProfile(**dict(row))
            return UserProfile()

    def update_profile(self, profile: UserProfile) -> None:
        profile.updated_at = datetime.now().isoformat()
        # Compute initials
        parts = profile.display_name.strip().split()
        if len(parts) >= 2:
            initials = (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1 and parts[0]:
            initials = parts[0][:2].upper()
        else:
            initials = "DT"
        profile.avatar_initials = initials

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_profiles
                (user_id, display_name, email, phone, bio, avatar_initials, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.user_id,
                profile.display_name,
                profile.email,
                profile.phone,
                profile.bio,
                profile.avatar_initials,
                profile.created_at,
                profile.updated_at
            ))
            conn.commit()

    def get_preferences(self, user_id: str = "demo_user") -> TravelPreferences:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM travel_preferences WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["destination_types"] = [t.strip() for t in data["destination_types"].split(",") if t.strip()]
                return TravelPreferences(**data)
            return TravelPreferences()

    def update_preferences(self, prefs: TravelPreferences) -> None:
        prefs.updated_at = datetime.now().isoformat()
        dt_str = ",".join(prefs.destination_types)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO travel_preferences
                (user_id, destination_types, min_budget, max_budget, package_tier, food_preference, transport_preference, accessibility, special_requests, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prefs.user_id,
                dt_str,
                prefs.min_budget,
                prefs.max_budget,
                prefs.package_tier,
                prefs.food_preference,
                prefs.transport_preference,
                prefs.accessibility,
                prefs.special_requests,
                prefs.updated_at
            ))
            conn.commit()

    def get_saved_destinations(self, user_id: str = "demo_user") -> List[SavedDestination]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM saved_destinations WHERE user_id = ? ORDER BY saved_at DESC", (user_id,))
            rows = cursor.fetchall()
            return [SavedDestination(**dict(r)) for r in rows]

    def save_destination(self, destination_id: str, destination_name: str, state: str, user_id: str = "demo_user") -> bool:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO saved_destinations (user_id, destination_id, destination_name, state, saved_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, destination_id, destination_name, state, now_str))
            conn.commit()
            return cursor.rowcount > 0

    def remove_saved_destination(self, destination_id: str, user_id: str = "demo_user") -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM saved_destinations WHERE user_id = ? AND destination_id = ?", (user_id, destination_id))
            conn.commit()
            return cursor.rowcount > 0

    def is_destination_saved(self, destination_id: str, user_id: str = "demo_user") -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM saved_destinations WHERE user_id = ? AND destination_id = ?", (user_id, destination_id))
            return cursor.fetchone() is not None

    def get_app_settings(self, user_id: str = "demo_user") -> AppSettings:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM app_settings WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return AppSettings(**dict(row))
            return AppSettings()

    def update_app_settings(self, settings: AppSettings) -> None:
        settings.updated_at = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO app_settings (user_id, currency, date_format, layout_mode, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (settings.user_id, settings.currency, settings.date_format, settings.layout_mode, settings.updated_at))
            conn.commit()

    def get_real_notifications(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Retrieves real notification events from actual bookings and bank transactions.
        Does not invent fictional notifications for events that did not happen.
        """
        notifications = []
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Hotel Bookings
            try:
                cursor.execute("""
                    SELECT booking_reference, hotel_name, destination_name, booking_status, payment_status, created_at, pricing_json
                    FROM bookings
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,))
                for row in cursor.fetchall():
                    status_icon = "✅" if row["booking_status"] == "CONFIRMED" else ("❌" if row["booking_status"] == "CANCELLED" else "⏳")
                    notifications.append({
                        "id": f"hotel_{row['booking_reference']}",
                        "title": f"{status_icon} Hotel Booking: {row['hotel_name']}",
                        "message": f"Status: {row['booking_status']} • Destination: {row['destination_name']} • Ref: {row['booking_reference']}",
                        "category": "Hotel Booking",
                        "status": row["booking_status"],
                        "timestamp": row["created_at"],
                    })
            except Exception:
                pass

            # 2. Package Bookings (if table exists)
            try:
                cursor.execute("""
                    SELECT booking_reference, package_name, destination_name, booking_status, payment_status, total_amount_inr, created_at
                    FROM package_bookings
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,))
                for row in cursor.fetchall():
                    status_icon = "🎒" if row["booking_status"] == "CONFIRMED" else ("❌" if row["booking_status"] == "CANCELLED" else "⏳")
                    notifications.append({
                        "id": f"pkg_{row['booking_reference']}",
                        "title": f"{status_icon} Package Booking: {row['package_name']}",
                        "message": f"Status: {row['booking_status']} • ₹{row['total_amount_inr']:,.2f} • Ref: {row['booking_reference']}",
                        "category": "Travel Package",
                        "status": row["booking_status"],
                        "timestamp": row["created_at"],
                    })
            except Exception:
                pass

            # 3. Bank Transactions
            try:
                cursor.execute("""
                    SELECT transaction_id, transaction_type, amount_paise, status, description, created_at, booking_reference
                    FROM demo_bank_transactions
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,))
                for row in cursor.fetchall():
                    amt_inr = row["amount_paise"] / 100.0
                    t_icon = "💳" if row["transaction_type"] == "DEBIT" else ("🔄" if row["transaction_type"] == "REFUND" else "💰")
                    notifications.append({
                        "id": f"bank_{row['transaction_id']}",
                        "title": f"{t_icon} Bank {row['transaction_type']}: ₹{amt_inr:,.2f}",
                        "message": f"{row['description']} (Ref: {row['booking_reference'] or row['transaction_id']}) • Status: {row['status']}",
                        "category": "Bank Payment",
                        "status": row["status"],
                        "timestamp": row["created_at"],
                    })
            except Exception:
                pass

        # Sort combined notifications by timestamp descending
        notifications.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
        return notifications[:limit]


def get_profile_service(db_path: Optional[Path] = None) -> ProfileService:
    return ProfileService.get_instance(db_path=db_path)
