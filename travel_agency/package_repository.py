"""Persistent Package Booking Repository for SK Holidays.

Persists package bookings, guest information, itemized price breakdowns,
atomic payment references, and audit events in the shared data/bookings.db SQLite database.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from travel_agency.package_models import (
    PackageBookingRecord,
    PackageCostBreakdown,
)
from travel_agency.booking_models import (
    BookingStatus,
    PaymentStatus,
    GuestInformation,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bookings.db"


class PackageRepository:
    """Manages persistence for travel package bookings, status transitions, and audit logs."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates the package_bookings table and indexes if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS package_bookings (
                    booking_reference TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    package_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    destination_id TEXT NOT NULL,
                    destination_name TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    num_nights INTEGER NOT NULL,
                    duration_days INTEGER NOT NULL,
                    num_adults INTEGER NOT NULL,
                    num_children INTEGER DEFAULT 0,
                    num_rooms INTEGER NOT NULL,
                    room_occupancy_per_room INTEGER DEFAULT 2,
                    hotel_id TEXT NOT NULL,
                    hotel_name TEXT NOT NULL,
                    room_type TEXT NOT NULL,
                    transport_mode TEXT NOT NULL,
                    meal_plan TEXT NOT NULL,
                    included_activities_json TEXT,
                    selected_optional_activities_json TEXT,
                    lead_guest_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    additional_guests_json TEXT,
                    special_requests TEXT,
                    cost_breakdown_json TEXT NOT NULL,
                    total_amount_inr REAL NOT NULL,
                    total_amount_paise INTEGER NOT NULL,
                    booking_status TEXT NOT NULL,
                    payment_status TEXT NOT NULL,
                    payment_order_id TEXT,
                    payment_id TEXT,
                    payment_gateway TEXT DEFAULT 'sk_demo_bank',
                    demo_transaction_reference TEXT,
                    demo_balance_after_inr REAL,
                    cancellation_policy TEXT,
                    is_refundable INTEGER DEFAULT 1,
                    is_demo INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    audit_log_json TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pkg_email ON package_bookings(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pkg_status ON package_bookings(booking_status)")
            conn.commit()

    def save_package_booking(self, record: PackageBookingRecord) -> bool:
        """Inserts or updates a package booking atomically."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO package_bookings (
                    booking_reference, package_id, package_name, category, destination_id, destination_name,
                    departure_date, return_date, num_nights, duration_days, num_adults, num_children,
                    num_rooms, room_occupancy_per_room, hotel_id, hotel_name, room_type, transport_mode,
                    meal_plan, included_activities_json, selected_optional_activities_json,
                    lead_guest_name, email, phone, additional_guests_json, special_requests,
                    cost_breakdown_json, total_amount_inr, total_amount_paise,
                    booking_status, payment_status, payment_order_id, payment_id,
                    payment_gateway, demo_transaction_reference, demo_balance_after_inr,
                    cancellation_policy, is_refundable, is_demo, created_at, updated_at, audit_log_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
            """, (
                record.booking_reference,
                record.package_id,
                record.package_name,
                record.category,
                record.destination_id,
                record.destination_name,
                record.departure_date,
                record.return_date,
                record.num_nights,
                record.duration_days,
                record.num_adults,
                record.num_children,
                record.num_rooms,
                record.room_occupancy_per_room,
                record.hotel_id,
                record.hotel_name,
                record.room_type,
                record.transport_mode,
                record.meal_plan,
                json.dumps(record.included_activities),
                json.dumps(record.selected_optional_activities),
                record.guest_info.lead_guest_name,
                record.guest_info.email,
                record.guest_info.phone,
                json.dumps(record.guest_info.additional_guests),
                record.guest_info.special_requests,
                json.dumps(record.cost_breakdown.model_dump()),
                record.total_amount_inr,
                record.total_amount_paise,
                record.booking_status.value if hasattr(record.booking_status, "value") else str(record.booking_status),
                record.payment_status.value if hasattr(record.payment_status, "value") else str(record.payment_status),
                record.payment_order_id,
                record.payment_id,
                record.payment_gateway,
                record.demo_transaction_reference,
                record.demo_balance_after_inr,
                record.cancellation_policy,
                1 if record.is_refundable else 0,
                1 if record.is_demo else 0,
                record.created_at,
                now_iso,
                json.dumps(record.audit_log),
            ))
            conn.commit()
            return True

    def _row_to_record(self, row: sqlite3.Row) -> PackageBookingRecord:
        """Converts an SQLite row into a validated PackageBookingRecord instance."""
        guest_info = GuestInformation(
            lead_guest_name=row["lead_guest_name"],
            email=row["email"],
            phone=row["phone"],
            additional_guests=json.loads(row["additional_guests_json"] or "[]"),
            special_requests=row["special_requests"],
            accepted_terms=True,
        )

        cost_dict = json.loads(row["cost_breakdown_json"])
        cost_breakdown = PackageCostBreakdown(**cost_dict)

        audit_log = json.loads(row["audit_log_json"] or "[]")

        return PackageBookingRecord(
            booking_reference=row["booking_reference"],
            package_id=row["package_id"],
            package_name=row["package_name"],
            category=row["category"],
            destination_id=row["destination_id"],
            destination_name=row["destination_name"],
            departure_date=row["departure_date"],
            return_date=row["return_date"],
            num_nights=row["num_nights"],
            duration_days=row["duration_days"],
            num_adults=row["num_adults"],
            num_children=row["num_children"] or 0,
            num_rooms=row["num_rooms"],
            room_occupancy_per_room=row["room_occupancy_per_room"] or 2,
            hotel_id=row["hotel_id"],
            hotel_name=row["hotel_name"],
            room_type=row["room_type"],
            transport_mode=row["transport_mode"],
            meal_plan=row["meal_plan"],
            included_activities=json.loads(row["included_activities_json"] or "[]"),
            selected_optional_activities=json.loads(row["selected_optional_activities_json"] or "[]"),
            guest_info=guest_info,
            cost_breakdown=cost_breakdown,
            total_amount_inr=row["total_amount_inr"],
            total_amount_paise=row["total_amount_paise"],
            booking_status=BookingStatus(row["booking_status"]),
            payment_status=PaymentStatus(row["payment_status"]),
            payment_order_id=row["payment_order_id"],
            payment_id=row["payment_id"],
            payment_gateway=row["payment_gateway"] or "sk_demo_bank",
            demo_transaction_reference=row["demo_transaction_reference"],
            demo_balance_after_inr=row["demo_balance_after_inr"],
            cancellation_policy=row["cancellation_policy"] or "Free demo cancellation up to 48 hours prior to check-in.",
            is_refundable=bool(row["is_refundable"]),
            is_demo=bool(row["is_demo"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            audit_log=audit_log,
        )

    def get_package_booking(self, booking_reference: str) -> Optional[PackageBookingRecord]:
        """Retrieves a single package booking by its reference code."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM package_bookings WHERE booking_reference = ?", (booking_reference,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_package_bookings(self, limit: int = 50, email: Optional[str] = None) -> List[PackageBookingRecord]:
        """Lists recent package bookings, optionally filtered by user email."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if email:
                cursor.execute(
                    "SELECT * FROM package_bookings WHERE LOWER(email) = LOWER(?) ORDER BY created_at DESC LIMIT ?",
                    (email.strip(), limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM package_bookings ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [self._row_to_record(r) for r in rows]

    def update_package_booking_status(
        self,
        booking_reference: str,
        booking_status: BookingStatus,
        payment_status: PaymentStatus,
        demo_txn_ref: Optional[str] = None,
        demo_balance_after: Optional[float] = None,
        audit_note: Optional[str] = None,
    ) -> bool:
        """Updates booking status and appends an audit event."""
        booking = self.get_package_booking(booking_reference)
        if not booking:
            return False

        booking.booking_status = booking_status
        booking.payment_status = payment_status
        if demo_txn_ref:
            booking.demo_transaction_reference = demo_txn_ref
        if demo_balance_after is not None:
            booking.demo_balance_after_inr = demo_balance_after

        if audit_note:
            booking.audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "note": audit_note,
                "booking_status": booking_status.value,
                "payment_status": payment_status.value,
            })

        return self.save_package_booking(booking)
