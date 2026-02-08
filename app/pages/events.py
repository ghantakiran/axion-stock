"""Event-Driven Analytics Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="Event Analytics", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Event-Driven Analytics")

# --- Sidebar ---
st.sidebar.header("Event Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Earnings", "M&A / Risk Arb", "Corporate Actions", "Event Signals",
    "Earnings Scoring", "M&A Probability", "Corporate Impact", "Event Calendar",
])

# --- Tab 1: Earnings ---
with tab1:
    st.subheader("Earnings Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Beat Rate", "75%")
    col2.metric("Avg Surprise", "+5.2%")
    col3.metric("Streak", "+3 beats")
    col4.metric("Avg PEAD", "+1.8%")

    st.markdown("#### Recent Earnings")
    earn_data = pd.DataFrame([
        {"Quarter": "Q3 2025", "EPS Est": "$1.50", "EPS Act": "$1.62",
         "Surprise": "+8.0%", "Result": "Beat", "Post Drift": "+2.3%"},
        {"Quarter": "Q2 2025", "EPS Est": "$1.45", "EPS Act": "$1.52",
         "Surprise": "+4.8%", "Result": "Beat", "Post Drift": "+1.5%"},
        {"Quarter": "Q1 2025", "EPS Est": "$1.40", "EPS Act": "$1.43",
         "Surprise": "+2.1%", "Result": "Beat", "Post Drift": "+0.8%"},
        {"Quarter": "Q4 2024", "EPS Est": "$1.38", "EPS Act": "$1.35",
         "Surprise": "-2.2%", "Result": "Miss", "Post Drift": "-1.5%"},
    ])
    st.dataframe(earn_data, use_container_width=True, hide_index=True)

# --- Tab 2: M&A / Risk Arb ---
with tab2:
    st.subheader("M&A Deal Monitor")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Deals", "8")
    col2.metric("Avg Spread", "5.2%")
    col3.metric("Avg Probability", "78%")
    col4.metric("Strong Buys", "2")

    st.markdown("#### Active Deals")
    deal_data = pd.DataFrame([
        {"Target": "VMW", "Acquirer": "AVGO", "Spread": "3.2%",
         "Ann. Spread": "8.5%", "Probability": "92%", "Signal": "Strong Buy"},
        {"Target": "ATVI", "Acquirer": "MSFT", "Spread": "1.8%",
         "Ann. Spread": "12.1%", "Probability": "88%", "Signal": "Buy"},
        {"Target": "SGEN", "Acquirer": "PFE", "Spread": "5.5%",
         "Ann. Spread": "9.2%", "Probability": "72%", "Signal": "Buy"},
        {"Target": "SAVE", "Acquirer": "JBLU", "Spread": "18.5%",
         "Ann. Spread": "25.0%", "Probability": "45%", "Signal": "Avoid"},
    ])
    st.dataframe(deal_data, use_container_width=True, hide_index=True)

# --- Tab 3: Corporate Actions ---
with tab3:
    st.subheader("Corporate Actions")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Upcoming", "5")
    col2.metric("Div Yield", "0.55%")
    col3.metric("Buyback", "$90B")
    col4.metric("Div Growth", "+4.2%")

    st.markdown("#### Upcoming Events")
    corp_data = pd.DataFrame([
        {"Symbol": "AAPL", "Type": "Dividend", "Effective": "2025-08-10",
         "Amount": "$0.25", "Days Until": "8"},
        {"Symbol": "NVDA", "Type": "Split", "Effective": "2025-08-15",
         "Amount": "10:1", "Days Until": "13"},
        {"Symbol": "MSFT", "Type": "Dividend", "Effective": "2025-08-20",
         "Amount": "$0.75", "Days Until": "18"},
        {"Symbol": "GOOGL", "Type": "Buyback", "Effective": "2025-09-01",
         "Amount": "$70B", "Days Until": "30"},
    ])
    st.dataframe(corp_data, use_container_width=True, hide_index=True)

# --- Tab 4: Event Signals ---
with tab4:
    st.subheader("Composite Event Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite", "+0.65")
    col2.metric("Direction", "Bullish")
    col3.metric("Strength", "Strong")
    col4.metric("Signals", "3")

    st.markdown("#### Top Event Signals")
    sig_data = pd.DataFrame([
        {"Symbol": "AAPL", "Composite": "+0.72", "Earnings": "+0.85",
         "M&A": "—", "Corporate": "+0.40", "Direction": "Bullish"},
        {"Symbol": "VMW", "Composite": "+0.68", "Earnings": "+0.30",
         "M&A": "+0.90", "Corporate": "—", "Direction": "Bullish"},
        {"Symbol": "NVDA", "Composite": "+0.55", "Earnings": "+0.65",
         "M&A": "—", "Corporate": "+0.20", "Direction": "Bullish"},
        {"Symbol": "BA", "Composite": "-0.45", "Earnings": "-0.60",
         "M&A": "—", "Corporate": "+0.10", "Direction": "Bearish"},
    ])
    st.dataframe(sig_data, use_container_width=True, hide_index=True)

# --- Tab 5: Earnings Scoring ---
with tab5:
    st.subheader("Earnings Quality Scoring")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Score", "+0.72")
    col2.metric("Grade", "A")
    col3.metric("Surprise Score", "+0.85")
    col4.metric("Consistency", "+0.60")

    st.markdown("#### Earnings Scorecard")
    score_data = pd.DataFrame([
        {"Quarter": "Q3 2025", "Overall": "+0.72", "Surprise": "+0.85",
         "Consistency": "+0.60", "Revenue": "+0.55", "Guidance": "+0.80",
         "Breadth": "+0.65", "Grade": "A"},
        {"Quarter": "Q2 2025", "Overall": "+0.58", "Surprise": "+0.65",
         "Consistency": "+0.55", "Revenue": "+0.40", "Guidance": "+0.50",
         "Breadth": "+0.70", "Grade": "B+"},
        {"Quarter": "Q1 2025", "Overall": "+0.35", "Surprise": "+0.30",
         "Consistency": "+0.45", "Revenue": "+0.25", "Guidance": "+0.40",
         "Breadth": "+0.35", "Grade": "B"},
        {"Quarter": "Q4 2024", "Overall": "-0.15", "Surprise": "-0.20",
         "Consistency": "+0.10", "Revenue": "-0.10", "Guidance": "-0.30",
         "Breadth": "+0.05", "Grade": "C"},
    ])
    st.dataframe(score_data, use_container_width=True, hide_index=True)

    st.markdown("#### Guidance Revisions")
    guide_data = pd.DataFrame([
        {"Quarter": "Q3 2025", "Prior Low": "$1.50", "Prior High": "$1.65",
         "New Low": "$1.60", "New High": "$1.70", "Revision": "+5.7%",
         "Type": "Raise"},
        {"Quarter": "Q2 2025", "Prior Low": "$1.40", "Prior High": "$1.55",
         "New Low": "$1.42", "New High": "$1.52", "Revision": "+0.7%",
         "Type": "Narrowed"},
    ])
    st.dataframe(guide_data, use_container_width=True, hide_index=True)

# --- Tab 6: M&A Probability ---
with tab6:
    st.subheader("Deal Completion Probability")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Base Probability", "85%")
    col2.metric("Adjusted", "78%")
    col3.metric("Regulatory Risk", "Medium")
    col4.metric("Est. Days to Close", "120")

    st.markdown("#### Risk Factor Decomposition")
    risk_data = pd.DataFrame([
        {"Factor": "Regulatory", "Weight": "30%", "Risk Score": "0.35",
         "Impact": "-5.3%"},
        {"Factor": "Financing", "Weight": "25%", "Risk Score": "0.15",
         "Impact": "-1.9%"},
        {"Factor": "Antitrust", "Weight": "25%", "Risk Score": "0.45",
         "Impact": "-5.6%"},
        {"Factor": "Shareholder", "Weight": "10%", "Risk Score": "0.10",
         "Impact": "-0.5%"},
        {"Factor": "Market", "Weight": "10%", "Risk Score": "0.20",
         "Impact": "-1.0%"},
    ])
    st.dataframe(risk_data, use_container_width=True, hide_index=True)

    st.markdown("#### Deal Comparison")
    deal_comp = pd.DataFrame([
        {"Deal": "AVGO/VMW", "Base Prob": "88%", "Adjusted": "82%",
         "Risk Level": "low", "Spread": "3.2%", "Risk-Adj Return": "2.6%"},
        {"Deal": "MSFT/ATVI", "Base Prob": "85%", "Adjusted": "75%",
         "Risk Level": "medium", "Spread": "1.8%", "Risk-Adj Return": "1.4%"},
        {"Deal": "JBLU/SAVE", "Base Prob": "55%", "Adjusted": "42%",
         "Risk Level": "high", "Spread": "18.5%", "Risk-Adj Return": "7.8%"},
    ])
    st.dataframe(deal_comp, use_container_width=True, hide_index=True)

# --- Tab 7: Corporate Impact ---
with tab7:
    st.subheader("Corporate Action Impact Estimation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dividend Impact", "-0.17%")
    col2.metric("Buyback Accretion", "+1.2%")
    col3.metric("Split Effect", "+2.5%")
    col4.metric("Net Signal", "Positive")

    st.markdown("#### Dividend Impact Analysis")
    div_data = pd.DataFrame([
        {"Symbol": "AAPL", "Amount": "$0.25", "Ex-Date Adj": "-0.17%",
         "Tax-Adj Impact": "-0.14%", "Ann. Yield": "0.55%", "Signal": "low"},
        {"Symbol": "JNJ", "Amount": "$1.24", "Ex-Date Adj": "-0.75%",
         "Tax-Adj Impact": "-0.64%", "Ann. Yield": "3.0%", "Signal": "neutral"},
        {"Symbol": "T", "Amount": "$0.28", "Ex-Date Adj": "-1.52%",
         "Tax-Adj Impact": "-1.29%", "Ann. Yield": "6.1%", "Signal": "attractive"},
    ])
    st.dataframe(div_data, use_container_width=True, hide_index=True)

    st.markdown("#### Buyback & Split Impact")
    action_data = pd.DataFrame([
        {"Symbol": "AAPL", "Action": "Buyback", "Size": "$90B",
         "EPS Accretion": "+1.2%", "Price Support": "+2.3%",
         "Total Impact": "+3.5%"},
        {"Symbol": "NVDA", "Action": "10:1 Split", "Size": "—",
         "EPS Accretion": "—", "Price Support": "—",
         "Total Impact": "+3.5%"},
        {"Symbol": "GOOGL", "Action": "Buyback", "Size": "$70B",
         "EPS Accretion": "+0.8%", "Price Support": "+1.5%",
         "Total Impact": "+2.3%"},
    ])
    st.dataframe(action_data, use_container_width=True, hide_index=True)

# --- Tab 8: Event Calendar ---
with tab8:
    st.subheader("Event Calendar Analytics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Events This Week", "12")
    col2.metric("Density Score", "2.4")
    col3.metric("High Importance", "4")
    col4.metric("Clusters", "2")

    st.markdown("#### Weekly Event Density")
    density_data = pd.DataFrame([
        {"Week": "Aug 4-8", "Events": "12", "Density": "2.4",
         "High Importance": "4", "Symbols": "8", "Status": "Busy"},
        {"Week": "Aug 11-15", "Events": "8", "Density": "1.6",
         "High Importance": "2", "Symbols": "6", "Status": "Moderate"},
        {"Week": "Aug 18-22", "Events": "3", "Density": "0.6",
         "High Importance": "1", "Symbols": "3", "Status": "Light"},
        {"Week": "Aug 25-29", "Events": "15", "Density": "3.0",
         "High Importance": "6", "Symbols": "10", "Status": "Busy"},
    ])
    st.dataframe(density_data, use_container_width=True, hide_index=True)

    st.markdown("#### Catalyst Timeline")
    catalyst_data = pd.DataFrame([
        {"Symbol": "AAPL", "Next Catalyst": "Earnings",
         "Days Until": "5", "30d Catalysts": "2", "90d Catalysts": "4",
         "Status": "Near-term"},
        {"Symbol": "NVDA", "Next Catalyst": "Split",
         "Days Until": "13", "30d Catalysts": "3", "90d Catalysts": "5",
         "Status": "Near-term"},
        {"Symbol": "MSFT", "Next Catalyst": "Dividend",
         "Days Until": "18", "30d Catalysts": "1", "90d Catalysts": "3",
         "Status": "Upcoming"},
    ])
    st.dataframe(catalyst_data, use_container_width=True, hide_index=True)
