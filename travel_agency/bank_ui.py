"""Streamlit UI component for SK Demo Bank Account Dashboard.

Rebuilt 100% with native Streamlit components (containers, columns, metrics,
markdown tables, callouts, and buttons) to ensure zero raw HTML leakage.
"""

import streamlit as st
from datetime import datetime

from travel_agency.bank_service import get_demo_bank_service


def render_demo_bank_page():
    """Renders the 'My Demo Bank Account' dashboard in Luxury Black & Gold styling."""
    bank_service = get_demo_bank_service()
    summary = bank_service.get_account_summary()
    account = summary["account"]

    # Header section
    st.title("🏦 My Demo Bank Account")
    st.caption(
        "Simulated Financial Testing Engine • Manage and monitor your simulated "
        "SK Demo Bank balance, review hotel booking debits, and inspect refund logs."
    )

    # Prominent Demo Disclaimer
    st.warning(
        "⚠️ **DEMO ACCOUNT — NO REAL MONEY**\n\n"
        "This is a simulated bank account for testing SK Holidays. "
        "No real funds, UPI services, bank credentials, or actual banking transactions are involved."
    )

    # 4 Metric Cards Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            label="Available Demo Balance",
            value=f"₹{account.balance_inr:,.2f}",
            delta="Simulated Funds",
            delta_color="normal"
        )
    with m2:
        st.metric(
            label="Initial Account Balance",
            value=f"₹{summary['initial_balance_inr']:,.2f}",
            help="Starting baseline for testing"
        )
    with m3:
        st.metric(
            label="Total Spent in Bookings",
            value=f"₹{summary['total_spent_inr']:,.2f}",
            delta=f"{summary['payment_count']} Payments" if summary['payment_count'] > 0 else "No spend yet",
            delta_color="off"
        )
    with m4:
        st.metric(
            label="Successful Demo Payments",
            value=str(summary['payment_count']),
            help="Number of completed reservations paid via SK Demo Bank"
        )

    st.divider()

    # Account Profile Card & Credentials
    st.subheader("💳 Account Credentials & Status")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("FINANCIAL INSTITUTION")
            st.markdown(f"🏦 **{account.bank_name}**")
            st.caption("ACCOUNT HOLDER")
            st.markdown(f"👤 **{account.account_holder}**")
        with c2:
            st.caption("ACCOUNT NUMBER")
            st.code(account.account_number_masked)
            st.caption("ACCOUNT TYPE")
            st.markdown(f"📑 **{account.account_type}**")
        with c3:
            st.caption("CURRENCY & STATUS")
            st.markdown(f"🇮🇳 **{account.currency} • {account.account_status}**")
            st.caption("PAYMENT AUTHORIZATION")
            st.markdown(f"⚡ **{account.payment_mode}**")

    st.divider()

    # Transaction History Section
    st.subheader("📜 Simulated Transaction History")
    st.caption("Ordered newest first. Displays debits for reservations, refunds, and balance resets.")

    f_col1, f_col2 = st.columns([2, 3])
    with f_col1:
        txn_filter = st.selectbox(
            "Filter Transactions by Type",
            options=["ALL", "DEBIT", "CREDIT_REFUND", "SUCCESS"],
            index=0,
            help="Filter transactions by debit or refund"
        )

    txns = bank_service.get_transactions(status_filter=txn_filter)

    if not txns:
        st.info(
            "💳 **No transactions recorded yet.** Pay for a hotel reservation or travel package "
            "using SK Demo Bank to see transactions appear here."
        )
    else:
        # Markdown table of transactions (safe, native, zero raw HTML)
        table_lines = [
            "| Txn Reference | Booking Ref | Date & Time | Details | Type | Amount | Balance After | Status |",
            "| :--- | :--- | :--- | :--- | :--- | ---: | ---: | :---: |"
        ]
        for t in txns:
            is_credit = t.transaction_type in ("CREDIT_REFUND", "RESET")
            sign = "+" if is_credit else "-"
            type_badge = "🟢 REFUND" if t.transaction_type == "CREDIT_REFUND" else ("🔵 DEBIT" if t.transaction_type == "DEBIT" else "🔄 RESET")
            date_str = t.created_at[:19].replace('T', ' ')
            hotel_detail = t.hotel_name or "Reservation"
            table_lines.append(
                f"| `{t.transaction_reference}` | `{t.booking_reference or 'N/A'}` | {date_str} | {hotel_detail} | {type_badge} | **{sign}₹{t.amount_inr:,.2f}** | ₹{t.balance_after_inr:,.2f} | **{t.status}** |"
            )

        st.markdown("\n".join(table_lines))

    # Developer-Only Demo Reset Utility
    st.divider()
    with st.expander("🛠️ Developer Utility: Reset Demo Account Balance", expanded=False):
        st.error(
            "⚠️ **DESTRUCTIVE DEMO OPERATION**\n\n"
            "This resets the fictional account balance back to **₹1,00,000 INR**.\n"
            "Ordinary users cannot modify balances through the UI. Use this utility only for testing booking workflows."
        )

        confirm_reset = st.checkbox("I understand this is a testing operation and wish to reset the demo account balance.", key="chk_confirm_reset_bank")
        clear_hist = st.checkbox("Also clear transaction history logs", key="chk_clear_hist_bank")

        if st.button("🔄 Execute Balance Reset to ₹1,00,000", key="btn_exec_reset_bank", type="secondary"):
            if not confirm_reset:
                st.error("Please confirm the checkbox above before executing the reset.")
            else:
                ok, msg = bank_service.reset_demo_account(clear_history=clear_hist)
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ Reset failed: {msg}")
