"""Pydantic data models and schemas for SK Demo Bank."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DemoBankAccount(BaseModel):
    """Simulated demo bank account schema for testing hotel bookings and payments."""
    account_id: str = "SKDEMO-ACC-100001"
    bank_name: str = "SK Demo Bank"
    account_holder: str = "Demo Traveller"
    account_number: str = "SKDEMO100001"
    account_number_masked: str = "XXXXXX0001"
    account_type: str = "Demo Savings Account"
    balance_paise: int = 10000000  # ₹1,00,000 INR = 10,000,000 paise
    currency: str = "INR"
    account_status: str = "Active (Demo)"
    payment_mode: str = "Simulated only"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @property
    def balance_inr(self) -> float:
        """Returns balance in Rupees rounded to 2 decimal places."""
        return round(self.balance_paise / 100.0, 2)

    @property
    def masked_account_number(self) -> str:
        return self.account_number_masked

    @property
    def status(self) -> str:
        return self.account_status


class DemoBankTransaction(BaseModel):
    """Simulated financial transaction record."""
    transaction_id: str
    account_id: str
    booking_reference: Optional[str] = None
    hotel_name: Optional[str] = None
    transaction_reference: str
    transaction_type: str  # "DEBIT", "CREDIT_REFUND", "RESET"
    amount_paise: int
    balance_before_paise: int
    balance_after_paise: int
    status: str  # "SUCCESS", "FAILED"
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @property
    def amount_inr(self) -> float:
        return round(self.amount_paise / 100.0, 2)

    @property
    def balance_before_inr(self) -> float:
        return round(self.balance_before_paise / 100.0, 2)

    @property
    def balance_after_inr(self) -> float:
        return round(self.balance_after_paise / 100.0, 2)
