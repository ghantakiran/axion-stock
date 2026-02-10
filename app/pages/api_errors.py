"""API Error Handling Dashboard (PRD-106).

Displays error rates, error distribution, recent errors,
and validation failure analytics.
"""

import json
import random
from datetime import datetime, timedelta, timezone

import streamlit as st
from app.styles import inject_global_styles

from src.api_errors.config import ERROR_STATUS_MAP, ErrorCode, ErrorSeverity

try:
    st.set_page_config(page_title="API Error Handling", page_icon="🛡️", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("🛡️ API Error Handling & Validation")

tab1, tab2, tab3, tab4 = st.tabs([
    "Error Overview",
    "Error Distribution",
    "Recent Errors",
    "Validation Analytics",
])

with tab1:
    st.header("Error Rate Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests (24h)", "284,512")
    col2.metric("Error Rate", "0.42%", "-0.08%")
    col3.metric("4xx Errors", "892", "-45")
    col4.metric("5xx Errors", "312", "+12")

    st.subheader("Error Rate Trend")
    chart_data = {f"{i}:00": random.uniform(0.2, 0.8) for i in range(24)}
    st.line_chart(chart_data)

    st.subheader("Error Response Format")
    st.json({
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid symbol format",
            "details": [{"field": "symbol", "issue": "Must be 1-5 uppercase letters"}],
            "request_id": "a1b2c3d4-e5f6-7890",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    })

with tab2:
    st.header("Error Distribution")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("By Error Code")
        code_counts = {
            "VALIDATION_ERROR": 423,
            "RESOURCE_NOT_FOUND": 198,
            "AUTHENTICATION_REQUIRED": 156,
            "RATE_LIMIT_EXCEEDED": 87,
            "INTERNAL_ERROR": 45,
            "BROKER_ERROR": 23,
        }
        st.bar_chart(code_counts)

    with col2:
        st.subheader("By HTTP Status")
        status_counts = {"400": 520, "401": 156, "403": 34, "404": 198, "429": 87, "500": 68, "503": 12}
        st.bar_chart(status_counts)

    st.subheader("Error Code Reference")
    rows = []
    for code in ErrorCode:
        status = ERROR_STATUS_MAP.get(code, 500)
        rows.append({"Code": code.value, "HTTP Status": status})
    st.dataframe(rows, use_container_width=True)

with tab3:
    st.header("Recent Errors")
    errors = [
        {"time": "14:23:15", "code": "VALIDATION_ERROR", "path": "/api/v1/orders", "message": "Invalid quantity: -5"},
        {"time": "14:22:58", "code": "AUTHENTICATION_REQUIRED", "path": "/api/v1/portfolio", "message": "Missing auth token"},
        {"time": "14:22:41", "code": "RESOURCE_NOT_FOUND", "path": "/api/v1/orders/xyz", "message": "Order not found"},
        {"time": "14:22:30", "code": "RATE_LIMIT_EXCEEDED", "path": "/api/v1/quotes", "message": "Rate limit exceeded"},
        {"time": "14:22:12", "code": "BROKER_ERROR", "path": "/api/v1/orders", "message": "Broker connection timeout"},
    ]
    for err in errors:
        color = "red" if "ERROR" in err["code"] or "BROKER" in err["code"] else "orange"
        st.markdown(
            f"<span style='color:{color};font-family:monospace'>"
            f"{err['time']} [{err['code']}] {err['path']} — {err['message']}</span>",
            unsafe_allow_html=True,
        )

with tab4:
    st.header("Validation Analytics")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Validation Failures")
        failures = {
            "Invalid symbol format": 234,
            "Quantity must be positive": 89,
            "Date range too large": 56,
            "Missing required field": 44,
            "Page size exceeds maximum": 31,
        }
        st.bar_chart(failures)

    with col2:
        st.subheader("Injection Attempts Blocked")
        st.metric("SQL Injection Attempts", "23", "blocked")
        st.metric("XSS Attempts", "15", "blocked")
        st.metric("Total Sanitized Inputs", "1,234")

    st.subheader("Input Sanitization Example")
    st.code("""
from src.api_errors.validators import validate_symbol, validate_quantity
from src.api_errors.middleware import sanitize_string

# Validate trading inputs
symbol = validate_symbol("AAPL")       # Returns "AAPL"
quantity = validate_quantity(100)        # Returns 100.0

# Sanitize user input
safe = sanitize_string("<script>alert(1)</script>")
# Returns "&lt;script&gt;alert(1)&lt;/script&gt;"
    """, language="python")
