"""Persistent Booking Repository using SQLite for SK Holidays.

Provides a clean repository layer for persisting bookings, payment statuses,
idempotency tracking, and audit logs. Designed for SQLite local development
with a clean structure ready for PostgreSQL migration.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from travel_agency.booking_models import (
    HotelBookingRecord,
    BookingStatus,
    PaymentStatus,
    GuestInformation,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bookings.db"


class BookingRepository:
    """Manages SQLite persistence for hotel bookings, payments, and audit logs."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes database tables with migrations support."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Bookings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    booking_reference TEXT PRIMARY KEY,
                    supplier_booking_reference TEXT,
                    hotel_id TEXT NOT NULL,
                    hotel_name TEXT NOT NULL,
                    hotel_address TEXT,
                    room_id TEXT NOT NULL,
                    room_name TEXT NOT NULL,
                    destination_name TEXT NOT NULL,
                    check_in TEXT NOT NULL,
                    check_out TEXT NOT NULL,
                    num_nights INTEGER NOT NULL,
                    num_rooms INTEGER NOT NULL,
                    num_adults INTEGER NOT NULL,
                    num_children INTEGER DEFAULT 0,
                    meal_inclusion TEXT,
                    cancellation_policy TEXT,
                    lead_guest_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    additional_guests_json TEXT,
                    special_requests TEXT,
                    pricing_json TEXT NOT NULL,
                    booking_status TEXT NOT NULL,
                    payment_status TEXT NOT NULL,
                    payment_order_id TEXT,
                    payment_id TEXT,
                    payment_gateway TEXT DEFAULT 'razorpay',
                    is_demo INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Processed payments table for idempotency protection
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_payments (
                    payment_id TEXT PRIMARY KEY,
                    booking_reference TEXT NOT NULL,
                    order_id TEXT,
                    amount REAL,
                    created_at TEXT NOT NULL
                )
            """)

            # Audit logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_reference TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Indexes for fast lookup
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_email ON bookings(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_order ON bookings(payment_order_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_ref ON audit_logs(booking_reference)")
            conn.commit()

    def save_booking(self, booking: HotelBookingRecord) -> bool:
        """Inserts or updates a booking record safely."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO bookings (
                    booking_reference, supplier_booking_reference, hotel_id, hotel_name,
                    hotel_address, room_id, room_name, destination_name, check_in, check_out,
                    num_nights, num_rooms, num_adults, num_children, meal_inclusion,
                    cancellation_policy, lead_guest_name, email, phone, additional_guests_json,
                    special_requests, pricing_json, booking_status, payment_status,
                    payment_order_id, payment_id, payment_gateway, is_demo, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                booking.booking_reference,
                booking.supplier_booking_reference,
                booking.hotel_id,
                booking.hotel_name,
                booking.hotel_address,
                booking.room_id,
                booking.room_name,
                booking.destination_name,
                booking.check_in,
                booking.check_out,
                booking.num_nights,
                booking.num_rooms,
                booking.num_adults,
                booking.num_children,
                booking.meal_inclusion,
                booking.cancellation_policy,
                booking.guest_info.lead_guest_name,
                booking.guest_info.email,
                booking.guest_info.phone,
                json.dumps(booking.guest_info.additional_guests),
                booking.guest_info.special_requests,
                json.dumps(booking.pricing),
                booking.booking_status.value,
                booking.payment_status.value,
                booking.payment_order_id,
                booking.payment_id,
                booking.payment_gateway,
                1 if booking.is_demo else 0,
                booking.created_at,
                now_iso
            ))
            conn.commit()
            return True

    def _row_to_booking(self, row: sqlite3.Row) -> HotelBookingRecord:
        guest_info = GuestInformation(
            lead_guest_name=row["lead_guest_name"],
            email=row["email"],
            phone=row["phone"],
            additional_guests=json.loads(row["additional_guests_json"] or "[]"),
            special_requests=row["special_requests"],
            accepted_terms=True
        )

        audit_logs = self.get_audit_logs(row["booking_reference"])

        return HotelBookingRecord(
            booking_reference=row["booking_reference"],
            supplier_booking_reference=row["supplier_booking_reference"],
            hotel_id=row["hotel_id"],
            hotel_name=row["hotel_name"],
            hotel_address=row["hotel_address"] or "",
            room_id=row["room_id"],
            room_name=row["room_name"],
            destination_name=row["destination_name"],
            check_in=row["check_in"],
            check_out=row["check_out"],
            num_nights=row["num_nights"],
            num_rooms=row["num_rooms"],
            num_adults=row["num_adults"],
            num_children=row["num_children"] or 0,
            meal_inclusion=row["meal_inclusion"] or "Room Only",
            cancellation_policy=row["cancellation_policy"] or "",
            guest_info=guest_info,
            pricing=json.loads(row["pricing_json"]),
            booking_status=BookingStatus(row["booking_status"]),
            payment_status=PaymentStatus(row["payment_status"]),
            payment_order_id=row["payment_order_id"],
            payment_id=row["payment_id"],
            payment_gateway=row["payment_gateway"] or "razorpay",
            is_demo=bool(row["is_demo"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            audit_log=audit_logs
        )

    def get_booking_by_reference(self, reference: str) -> Optional[HotelBookingRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bookings WHERE booking_reference = ?", (reference.strip(),))
            row = cursor.fetchone()
            if row:
                return self._row_to_booking(row)
        return None

    def get_booking_by_order_id(self, order_id: str) -> Optional[HotelBookingRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bookings WHERE payment_order_id = ?", (order_id.strip(),))
            row = cursor.fetchone()
            if row:
                return self._row_to_booking(row)
        return None

    def list_bookings(self, email: Optional[str] = None, limit: int = 50) -> List[HotelBookingRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if email and email.strip():
                cursor.execute(
                    "SELECT * FROM bookings WHERE LOWER(email) = LOWER(?) ORDER BY created_at DESC LIMIT ?",
                    (email.strip(), limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM bookings ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [self._row_to_booking(r) for r in rows]

    def update_booking_status(
        self,
        reference: str,
        booking_status: BookingStatus,
        payment_status: Optional[PaymentStatus] = None,
        supplier_ref: Optional[str] = None,
        payment_id: Optional[str] = None,
        payment_gateway: Optional[str] = None,
        note: str = ""
    ) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()

            updates = ["booking_status = ?", "updated_at = ?"]
            params = [booking_status.value, now_iso]

            if payment_status:
                updates.append("payment_status = ?")
                params.append(payment_status.value)
            if supplier_ref:
                updates.append("supplier_booking_reference = ?")
                params.append(supplier_ref)
            if payment_id:
                updates.append("payment_id = ?")
                params.append(payment_id)
            if payment_gateway:
                updates.append("payment_gateway = ?")
                params.append(payment_gateway)

            params.append(reference)
            query = f"UPDATE bookings SET {', '.join(updates)} WHERE booking_reference = ?"
            cursor.execute(query, tuple(params))
            conn.commit()

        self.add_audit_log(
            reference,
            f"STATUS_TRANSITION: {booking_status.value}",
            {
                "booking_status": booking_status.value,
                "payment_status": payment_status.value if payment_status else None,
                "supplier_ref": supplier_ref,
                "note": note,
            }
        )
        return True

    def add_audit_log(self, reference: str, event: str, details: Dict[str, Any]):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_logs (booking_reference, event, details_json, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    reference,
                    event,
                    json.dumps(details),
                    datetime.now().isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to add audit log: {e}")

    def get_audit_logs(self, reference: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT event, details_json, created_at FROM audit_logs WHERE booking_reference = ? ORDER BY id ASC",
                (reference,)
            )
            rows = cursor.fetchall()
            logs = []
            for r in rows:
                try:
                    details = json.loads(r["details_json"])
                except Exception:
                    details = {}
                logs.append({
                    "event": r["event"],
                    "timestamp": r["created_at"],
                    "details": details
                })
            return logs

    def is_payment_processed(self, payment_id: str) -> bool:
        """Idempotency check to prevent duplicate payment processing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_payments WHERE payment_id = ?", (payment_id.strip(),))
            return cursor.fetchone() is not None

    def mark_payment_processed(self, payment_id: str, booking_reference: str, order_id: str = "", amount: float = 0.0) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO processed_payments (payment_id, booking_reference, order_id, amount, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                payment_id.strip(),
                booking_reference.strip(),
                order_id.strip(),
                amount,
                datetime.now().isoformat()
            ))
            conn.commit()
            return True


# Global repository instance
_repo_instance: Optional[BookingRepository] = None


def get_booking_repository() -> BookingRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = BookingRepository()
    return _repo_instance
