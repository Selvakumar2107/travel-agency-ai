"""Simulated Banking Engine for SK Demo Bank.

Provides persistent demo bank accounts, deterministic integer paise balance calculations,
atomic debit/credit transactions, idempotency safeguards, and refund linking.
"""

import sqlite3
import random
import string
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import datetime

from travel_agency.bank_models import DemoBankAccount, DemoBankTransaction

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bookings.db"
DEFAULT_ACCOUNT_ID = "SKDEMO-ACC-100001"
INITIAL_BALANCE_PAISE = 10000000  # ₹1,00,000 INR = 10,000,000 paise


def inr_to_paise(amount_inr: float) -> int:
    """Converts INR float/decimal to integer paise without floating-point accumulation drift."""
    return int(round(amount_inr * 100))


def paise_to_inr(paise: int) -> float:
    """Converts integer paise to INR float rounded to 2 decimal places."""
    return round(paise / 100.0, 2)


class DemoBankService:
    """Engine managing the fictional SK Demo Bank account and its transactions."""

    _instances: Dict[str, "DemoBankService"] = {}
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[Union[Path, str]] = None):
        self.db_path = Path(db_path).resolve() if db_path else DB_PATH.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Optional[Union[Path, str]] = None) -> "DemoBankService":
        """
        Thread-safe service factory returning a cached instance per database path.
        Avoids global variable fragility and duplicate instances across reruns.
        """
        resolved_path = Path(db_path).resolve() if db_path else DB_PATH.resolve()
        key = str(resolved_path)
        if key not in cls._instances:
            with cls._lock:
                if key not in cls._instances:
                    cls._instances[key] = cls(db_path=resolved_path)
        return cls._instances[key]

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes demo banking tables and seeds the initial ₹1,00,000 account if not exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS demo_bank_accounts (
                    account_id TEXT PRIMARY KEY,
                    bank_name TEXT NOT NULL,
                    account_holder TEXT NOT NULL,
                    account_number TEXT NOT NULL,
                    account_number_masked TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    balance_paise INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'INR',
                    account_status TEXT NOT NULL DEFAULT 'Active (Demo)',
                    payment_mode TEXT NOT NULL DEFAULT 'Simulated only',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS demo_bank_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    booking_reference TEXT,
                    hotel_name TEXT,
                    transaction_reference TEXT UNIQUE NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount_paise INTEGER NOT NULL,
                    balance_before_paise INTEGER NOT NULL,
                    balance_after_paise INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (account_id) REFERENCES demo_bank_accounts(account_id)
                )
            """)
            conn.commit()

            # Seed default demo account ONLY IF IT DOES NOT EXIST YET
            cursor.execute("SELECT account_id FROM demo_bank_accounts WHERE account_id = ?", (DEFAULT_ACCOUNT_ID,))
            row = cursor.fetchone()
            if not row:
                now_iso = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO demo_bank_accounts (
                        account_id, bank_name, account_holder, account_number,
                        account_number_masked, account_type, balance_paise, currency,
                        account_status, payment_mode, created_at, updated_at
                    ) VALUES (
                        ?, 'SK Demo Bank', 'Demo Traveller', 'SKDEMO100001',
                        'XXXXXX0001', 'Demo Savings Account', ?, 'INR',
                        'Active (Demo)', 'Simulated only', ?, ?
                    )
                """, (DEFAULT_ACCOUNT_ID, INITIAL_BALANCE_PAISE, now_iso, now_iso))
                conn.commit()
                logger.info("Initialized default SK Demo Bank account with ₹1,00,000 INR (10,000,000 paise).")

    def get_account(self, account_id: str = DEFAULT_ACCOUNT_ID) -> DemoBankAccount:
        """Retrieves demo bank account details."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM demo_bank_accounts WHERE account_id = ?", (account_id,))
            row = cursor.fetchone()
            if not row:
                # Re-seed if missing
                self._init_db()
                cursor.execute("SELECT * FROM demo_bank_accounts WHERE account_id = ?", (account_id,))
                row = cursor.fetchone()
            return DemoBankAccount(**dict(row))

    def get_transactions(
        self,
        account_id: str = DEFAULT_ACCOUNT_ID,
        status_filter: Optional[str] = None,
        booking_reference: Optional[str] = None,
        limit: int = 50
    ) -> List[DemoBankTransaction]:
        """Retrieves recent demo bank transactions ordered newest first."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM demo_bank_transactions WHERE account_id = ?"
            params = [account_id]

            if booking_reference:
                query += " AND booking_reference = ?"
                params.append(booking_reference)

            if status_filter and status_filter.upper() != "ALL":
                query += " AND (status = ? OR transaction_type = ?)"
                params.extend([status_filter.upper(), status_filter.upper()])

            query += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [DemoBankTransaction(**dict(r)) for r in rows]

    def get_account_summary(self, account_id: str = DEFAULT_ACCOUNT_ID) -> Dict[str, Any]:
        """Calculates total spend, payment count, and current balance."""
        account = self.get_account(account_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Total spent in successful debits
            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_paise), 0) as total_spent,
                       COUNT(*) as payment_count
                FROM demo_bank_transactions
                WHERE account_id = ? AND transaction_type = 'DEBIT' AND status = 'SUCCESS'
                """,
                (account_id,)
            )
            stats = cursor.fetchone()
            total_spent_paise = stats["total_spent"] if stats else 0
            payment_count = stats["payment_count"] if stats else 0

        return {
            "account": account,
            "available_balance_inr": account.balance_inr,
            "total_spent_inr": paise_to_inr(total_spent_paise),
            "payment_count": payment_count,
            "successful_payment_count": payment_count,
            "initial_balance_inr": 100000.0,
        }

    def process_booking_payment(
        self,
        booking_reference: str,
        hotel_name: str,
        amount_inr: float,
        account_id: str = DEFAULT_ACCOUNT_ID,
    ) -> Tuple[bool, Optional[str], Optional[DemoBankTransaction], str]:
        """
        Deducts funds for a booking atomically using integer paise arithmetic.

        Rules:
        - Rejects zero or negative amounts.
        - Checks sufficient balance.
        - Prevents duplicate deductions for the same booking.
        - Deducts funds strictly after validation within an atomic SQLite transaction.
        """
        # 1. Reject invalid amounts
        if amount_inr <= 0:
            return False, None, None, f"Payment amount must be strictly greater than zero (received ₹{amount_inr})."

        amount_paise = inr_to_paise(amount_inr)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 2. Check for duplicate payment for this booking
            cursor.execute(
                """
                SELECT transaction_reference, balance_after_paise FROM demo_bank_transactions
                WHERE booking_reference = ? AND transaction_type = 'DEBIT' AND status = 'SUCCESS'
                """,
                (booking_reference,)
            )
            existing_txn = cursor.fetchone()
            if existing_txn:
                return (
                    False,
                    existing_txn["transaction_reference"],
                    None,
                    f"Booking {booking_reference} has already been paid using SK Demo Bank (duplicate payment prevented)."
                )

            # 3. Atomic Transaction: Check balance & debit
            try:
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute("SELECT balance_paise FROM demo_bank_accounts WHERE account_id = ?", (account_id,))
                acc_row = cursor.fetchone()
                if not acc_row:
                    conn.rollback()
                    return False, None, None, f"Demo account '{account_id}' not found."

                current_balance_paise = acc_row["balance_paise"]

                # 4. Sufficient funds check
                if current_balance_paise < amount_paise:
                    shortfall_paise = amount_paise - current_balance_paise
                    conn.rollback()
                    avail_inr = paise_to_inr(current_balance_paise)
                    req_inr = paise_to_inr(amount_paise)
                    shortfall_inr = paise_to_inr(shortfall_paise)
                    return (
                        False,
                        None,
                        None,
                        f"Insufficient demo funds. Available: ₹{avail_inr:,.2f}, Required: ₹{req_inr:,.2f}, Shortfall: ₹{shortfall_inr:,.2f}."
                    )

                # 5. Execute debit
                balance_before = current_balance_paise
                balance_after = balance_before - amount_paise
                now_iso = datetime.now().isoformat()
                rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                txn_ref = f"SKTXN-{datetime.now().strftime('%Y%m%d')}-{rand_suffix}"
                txn_id = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{rand_suffix}"

                # Update account balance
                cursor.execute(
                    "UPDATE demo_bank_accounts SET balance_paise = ?, updated_at = ? WHERE account_id = ?",
                    (balance_after, now_iso, account_id)
                )

                # Record transaction
                desc = f"Hotel booking payment for {hotel_name} (Ref: {booking_reference})"
                cursor.execute(
                    """
                    INSERT INTO demo_bank_transactions (
                        transaction_id, account_id, booking_reference, hotel_name,
                        transaction_reference, transaction_type, amount_paise,
                        balance_before_paise, balance_after_paise, status, description, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'DEBIT', ?, ?, ?, 'SUCCESS', ?, ?)
                    """,
                    (
                        txn_id, account_id, booking_reference, hotel_name,
                        txn_ref, amount_paise, balance_before, balance_after,
                        desc, now_iso
                    )
                )

                conn.commit()

                txn_record = DemoBankTransaction(
                    transaction_id=txn_id,
                    account_id=account_id,
                    booking_reference=booking_reference,
                    hotel_name=hotel_name,
                    transaction_reference=txn_ref,
                    transaction_type="DEBIT",
                    amount_paise=amount_paise,
                    balance_before_paise=balance_before,
                    balance_after_paise=balance_after,
                    status="SUCCESS",
                    description=desc,
                    created_at=now_iso,
                )

                logger.info(
                    f"SK Demo Bank: Debited ₹{amount_inr:,.2f} (Txn: {txn_ref}) for booking {booking_reference}. "
                    f"New Balance: ₹{paise_to_inr(balance_after):,.2f}"
                )
                return True, txn_ref, txn_record, f"Payment of ₹{amount_inr:,.2f} successfully authorized by SK Demo Bank."

            except Exception as e:
                conn.rollback()
                logger.error(f"Error processing SK Demo Bank payment for {booking_reference}: {e}")
                return False, None, None, f"Database transaction error during bank debit: {e}"

    def process_cancellation_refund(
        self,
        booking_reference: str,
        hotel_name: str,
        amount_inr: float,
        reason: str = "Customer requested cancellation",
        account_id: str = DEFAULT_ACCOUNT_ID,
    ) -> Tuple[bool, Optional[str], Optional[DemoBankTransaction], str]:
        """
        Credits the refundable amount back to the demo account.

        Rules:
        - Prevents duplicate refunds.
        - Requires an original successful debit.
        - Updates account balance and inserts CREDIT_REFUND transaction atomically.
        """
        if amount_inr <= 0:
            return False, None, None, "Refund amount must be greater than zero."

        amount_paise = inr_to_paise(amount_inr)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Check if refund already completed
            cursor.execute(
                """
                SELECT transaction_reference FROM demo_bank_transactions
                WHERE booking_reference = ? AND transaction_type = 'CREDIT_REFUND' AND status = 'SUCCESS'
                """,
                (booking_reference,)
            )
            existing_ref = cursor.fetchone()
            if existing_ref:
                return (
                    False,
                    existing_ref["transaction_reference"],
                    None,
                    f"Refund has already been credited for booking {booking_reference} (duplicate refund prevented)."
                )

            # 2. Verify original debit exists
            cursor.execute(
                """
                SELECT transaction_reference FROM demo_bank_transactions
                WHERE booking_reference = ? AND transaction_type = 'DEBIT' AND status = 'SUCCESS'
                """,
                (booking_reference,)
            )
            orig_debit = cursor.fetchone()
            if not orig_debit:
                return False, None, None, f"No demo bank payment found for booking {booking_reference} to refund."

            # 3. Atomic Transaction: Credit balance & record transaction
            try:
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute("SELECT balance_paise FROM demo_bank_accounts WHERE account_id = ?", (account_id,))
                acc_row = cursor.fetchone()
                current_balance_paise = acc_row["balance_paise"]

                balance_before = current_balance_paise
                balance_after = balance_before + amount_paise
                now_iso = datetime.now().isoformat()
                rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                txn_ref = f"SKREF-{datetime.now().strftime('%Y%m%d')}-{rand_suffix}"
                txn_id = f"TXN-REF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{rand_suffix}"

                cursor.execute(
                    "UPDATE demo_bank_accounts SET balance_paise = ?, updated_at = ? WHERE account_id = ?",
                    (balance_after, now_iso, account_id)
                )

                desc = f"Cancellation refund for {hotel_name} (Booking Ref: {booking_reference}, Orig Txn: {orig_debit['transaction_reference']}). Reason: {reason}"
                cursor.execute(
                    """
                    INSERT INTO demo_bank_transactions (
                        transaction_id, account_id, booking_reference, hotel_name,
                        transaction_reference, transaction_type, amount_paise,
                        balance_before_paise, balance_after_paise, status, description, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'CREDIT_REFUND', ?, ?, ?, 'SUCCESS', ?, ?)
                    """,
                    (
                        txn_id, account_id, booking_reference, hotel_name,
                        txn_ref, amount_paise, balance_before, balance_after,
                        desc, now_iso
                    )
                )

                conn.commit()

                txn_record = DemoBankTransaction(
                    transaction_id=txn_id,
                    account_id=account_id,
                    booking_reference=booking_reference,
                    hotel_name=hotel_name,
                    transaction_reference=txn_ref,
                    transaction_type="CREDIT_REFUND",
                    amount_paise=amount_paise,
                    balance_before_paise=balance_before,
                    balance_after_paise=balance_after,
                    status="SUCCESS",
                    description=desc,
                    created_at=now_iso,
                )

                logger.info(
                    f"SK Demo Bank: Refunded ₹{amount_inr:,.2f} (Txn: {txn_ref}) for booking {booking_reference}. "
                    f"New Balance: ₹{paise_to_inr(balance_after):,.2f}"
                )
                return True, txn_ref, txn_record, f"Refund of ₹{amount_inr:,.2f} successfully credited to SK Demo Bank."

            except Exception as e:
                conn.rollback()
                logger.error(f"Error processing SK Demo Bank refund for {booking_reference}: {e}")
                return False, None, None, f"Database transaction error during bank refund: {e}"

    def reset_demo_account(
        self,
        account_id: str = DEFAULT_ACCOUNT_ID,
        clear_history: bool = False
    ) -> Tuple[bool, str]:
        """
        Developer-only demo reset utility restoring the demo balance to ₹1,00,000 INR.
        Labeled as a destructive demo operation.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute("SELECT balance_paise FROM demo_bank_accounts WHERE account_id = ?", (account_id,))
                row = cursor.fetchone()
                bal_before = row["balance_paise"] if row else INITIAL_BALANCE_PAISE
                now_iso = datetime.now().isoformat()

                # Reset account balance
                cursor.execute(
                    "UPDATE demo_bank_accounts SET balance_paise = ?, updated_at = ? WHERE account_id = ?",
                    (INITIAL_BALANCE_PAISE, now_iso, account_id)
                )

                if clear_history:
                    cursor.execute("DELETE FROM demo_bank_transactions WHERE account_id = ?", (account_id,))
                else:
                    rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    txn_ref = f"SKRST-{datetime.now().strftime('%Y%m%d')}-{rand_suffix}"
                    txn_id = f"TXN-RST-{datetime.now().strftime('%Y%m%d%H%M%S')}-{rand_suffix}"
                    cursor.execute(
                        """
                        INSERT INTO demo_bank_transactions (
                            transaction_id, account_id, booking_reference, hotel_name,
                            transaction_reference, transaction_type, amount_paise,
                            balance_before_paise, balance_after_paise, status, description, created_at
                        ) VALUES (?, ?, 'ADMIN_RESET', 'Developer Reset', ?, 'RESET', 0, ?, ?, 'SUCCESS', 'Developer reset to initial ₹1,00,000 balance', ?)
                        """,
                        (txn_id, account_id, txn_ref, bal_before, INITIAL_BALANCE_PAISE, now_iso)
                    )

                conn.commit()
                logger.info(f"Developer reset applied: SK Demo Bank account {account_id} restored to ₹1,00,000.")
                return True, "Demo bank account balance successfully restored to ₹1,00,000 INR."
            except Exception as e:
                conn.rollback()
                logger.error(f"Error resetting demo bank account: {e}")
                return False, f"Failed to reset demo bank account: {e}"


# Backward-compatibility alias
_demo_bank_service: Optional[DemoBankService] = None


def get_demo_bank_service(db_path: Optional[Union[Path, str]] = None) -> DemoBankService:
    """
    Factory function returning a cached DemoBankService instance.
    Delegates to DemoBankService.get_instance for robust, thread-safe caching.
    """
    global _demo_bank_service
    service = DemoBankService.get_instance(db_path)
    _demo_bank_service = service
    return service
