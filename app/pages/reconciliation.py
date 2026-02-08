"""PRD-126: Trade Reconciliation & Settlement — Dashboard."""

import streamlit as st

st.set_page_config(page_title="Trade Reconciliation", layout="wide")
st.title("Trade Reconciliation & Settlement Engine")

tab1, tab2, tab3, tab4 = st.tabs([
    "Reconciliation Overview", "Trade Matching", "Settlement Tracking", "Break Management"
])

# --------------- Tab 1: Reconciliation Overview ---------------
with tab1:
    st.header("Reconciliation Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Match Rate", "99.2%", "+0.3%")
    col2.metric("Open Breaks", "7", "-3")
    col3.metric("Pending Settlements", "42")
    col4.metric("Trades Reconciled", "2,847")

    st.subheader("Daily Match Rates")
    st.line_chart({
        "Mon": 99.1,
        "Tue": 99.3,
        "Wed": 98.9,
        "Thu": 99.5,
        "Fri": 99.2,
    })

    st.subheader("Break Type Distribution")
    st.bar_chart({
        "Price Mismatch": 3,
        "Quantity Mismatch": 2,
        "Missing Broker": 1,
        "Timing": 1,
    })

# --------------- Tab 2: Trade Matching ---------------
with tab2:
    st.header("Trade Matching")

    st.subheader("Recent Matches")
    st.dataframe({
        "Match ID": ["m-001", "m-002", "m-003", "m-004", "m-005"],
        "Symbol": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"],
        "Side": ["buy", "sell", "buy", "buy", "sell"],
        "Internal Qty": [100, 200, 50, 150, 75],
        "Broker Qty": [100, 200, 50, 150, 75],
        "Internal Price": [175.50, 380.20, 140.75, 245.00, 178.30],
        "Broker Price": [175.50, 380.20, 140.75, 245.00, 178.30],
        "Status": ["matched", "matched", "matched", "matched", "matched"],
        "Confidence": ["100%", "100%", "100%", "100%", "100%"],
    })

    st.subheader("Unmatched Internal Trades")
    st.dataframe({
        "Trade ID": ["t-891"],
        "Symbol": ["NVDA"],
        "Side": ["buy"],
        "Quantity": [200],
        "Price": [450.00],
        "Status": ["missing_broker"],
    })

    st.subheader("Unmatched Broker Trades")
    st.dataframe({
        "Trade ID": ["b-342"],
        "Symbol": ["META"],
        "Side": ["sell"],
        "Quantity": [100],
        "Price": [320.50],
        "Status": ["missing_internal"],
    })

# --------------- Tab 3: Settlement Tracking ---------------
with tab3:
    st.header("Settlement Tracking")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pending", "42")
    col2.metric("In Progress", "18")
    col3.metric("Settled Today", "127")
    col4.metric("Overdue", "2")

    st.subheader("Pending Settlements")
    st.dataframe({
        "Trade ID": ["t-001", "t-002", "t-003", "t-004"],
        "Symbol": ["AAPL", "MSFT", "GOOGL", "TSLA"],
        "Amount": ["$17,550", "$76,040", "$7,037", "$36,750"],
        "Expected Date": ["2025-01-15", "2025-01-15", "2025-01-16", "2025-01-16"],
        "Status": ["pending", "in_progress", "pending", "pending"],
        "Counterparty": ["Alpaca", "IBKR", "Alpaca", "Alpaca"],
    })

    st.subheader("Settlement Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Settlement Rate", "98.5%")
    col2.metric("Avg Settlement Time", "1.8 days")
    col3.metric("Failed Settlements", "3")

# --------------- Tab 4: Break Management ---------------
with tab4:
    st.header("Break Management")

    st.subheader("Open Breaks")
    st.dataframe({
        "Break ID": ["b-001", "b-002", "b-003"],
        "Type": ["price_mismatch", "quantity_mismatch", "missing_broker"],
        "Severity": ["medium", "low", "high"],
        "Symbol": ["AAPL", "TSLA", "NVDA"],
        "Assigned To": ["ops_team", "ops_team", "unassigned"],
        "Age": ["2 hours", "1 day", "30 min"],
    })

    st.subheader("Break Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Breaks", "47")
    col2.metric("Open", "7")
    col3.metric("Resolved", "38")
    col4.metric("Resolution Rate", "85.1%")

    st.subheader("Aging Report")
    st.bar_chart({
        "0-1 days": 4,
        "1-3 days": 2,
        "3-7 days": 1,
        "7-14 days": 0,
        "14+ days": 0,
    })
