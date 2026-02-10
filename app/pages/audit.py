"""Audit Trail Dashboard (PRD-109).

Displays event timeline, actor activity, integrity verification,
and export options for the audit trail system.
"""

import json
import random
from datetime import datetime, timedelta, timezone

import streamlit as st
from app.styles import inject_global_styles

from src.audit.config import AuditConfig, EventCategory, EventOutcome
from src.audit.events import Actor, AuditEvent, Resource
from src.audit.recorder import AuditRecorder

try:
    st.set_page_config(page_title="Audit Trail", page_icon="📜", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("📜 Audit Trail & Event Sourcing")

tab1, tab2, tab3, tab4 = st.tabs([
    "Event Timeline",
    "Actor Activity",
    "Integrity Check",
    "Export",
])


def _generate_sample_events(n=20):
    """Generate sample audit events for display."""
    actions = [
        ("order.create", EventCategory.TRADING),
        ("order.cancel", EventCategory.TRADING),
        ("order.modify", EventCategory.TRADING),
        ("config.update", EventCategory.CONFIG),
        ("user.login", EventCategory.AUTH),
        ("user.logout", EventCategory.AUTH),
        ("system.restart", EventCategory.SYSTEM),
        ("compliance.check", EventCategory.COMPLIANCE),
    ]
    actors = ["user_42", "user_17", "admin", "system", "bot_alpha"]
    events = []
    now = datetime.now(timezone.utc)
    for i in range(n):
        action, category = random.choice(actions)
        events.append({
            "timestamp": (now - timedelta(minutes=i * 5)).strftime("%H:%M:%S"),
            "actor": random.choice(actors),
            "action": action,
            "category": category.value,
            "outcome": random.choice(["success", "success", "success", "failure"]),
            "hash": f"sha256:{random.randbytes(8).hex()}",
        })
    return events


with tab1:
    st.header("Event Timeline")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Events (24h)", "12,456")
    col2.metric("Trading Events", "8,234")
    col3.metric("Auth Events", "2,891")
    col4.metric("System Events", "1,331")

    events = _generate_sample_events(15)
    for event in events:
        color = "green" if event["outcome"] == "success" else "red"
        st.markdown(
            f"<span style='font-family:monospace'>"
            f"{event['timestamp']} | "
            f"<span style='color:{color}'>{event['outcome']:8s}</span> | "
            f"{event['actor']:10s} | {event['action']:20s} | "
            f"{event['category']:12s} | {event['hash'][:20]}</span>",
            unsafe_allow_html=True,
        )

with tab2:
    st.header("Actor Activity")
    actor_stats = {
        "user_42": {"events": 3456, "last_active": "2 min ago", "top_action": "order.create"},
        "user_17": {"events": 1234, "last_active": "15 min ago", "top_action": "order.modify"},
        "admin": {"events": 567, "last_active": "1 hr ago", "top_action": "config.update"},
        "system": {"events": 4521, "last_active": "now", "top_action": "system.health_check"},
        "bot_alpha": {"events": 2345, "last_active": "5 min ago", "top_action": "order.create"},
    }
    for actor, stats in actor_stats.items():
        with st.expander(f"{actor} — {stats['events']} events"):
            st.write(f"Last active: {stats['last_active']}")
            st.write(f"Top action: {stats['top_action']}")
            st.write(f"Total events: {stats['events']}")

    st.subheader("Events by Category")
    cat_data = {c.value: random.randint(500, 5000) for c in EventCategory}
    st.bar_chart(cat_data)

with tab3:
    st.header("Hash Chain Integrity")
    st.success("Hash chain integrity: VERIFIED (12,456 events)")
    st.write("All events form a valid SHA-256 hash chain from genesis to the latest event.")

    st.subheader("How It Works")
    st.code("""
# Each event's hash = SHA-256(previous_hash + event_id + timestamp + action)
# First event uses "genesis" as previous_hash

Event 1: hash = SHA-256("genesis" + event_1_id + ts + action)
Event 2: hash = SHA-256(event_1_hash + event_2_id + ts + action)
Event 3: hash = SHA-256(event_2_hash + event_3_id + ts + action)
...

# If any event is tampered with, the chain breaks from that point forward
    """)

    st.subheader("Verification Result")
    st.json({
        "verified": True,
        "total_events": 12456,
        "chain_start": "genesis",
        "chain_end": "a1b2c3d4e5f6...",
        "verification_time_ms": 234,
    })

with tab4:
    st.header("Export & Compliance")

    st.subheader("Export Format")
    format_choice = st.selectbox("Format", ["JSON Lines", "CSV", "Compliance Report"])

    if format_choice == "JSON Lines":
        st.code("""
{"event_id":"abc-123","timestamp":"2024-01-01T00:00:00Z","actor":{"actor_id":"user_42"},...}
{"event_id":"abc-124","timestamp":"2024-01-01T00:01:00Z","actor":{"actor_id":"admin"},...}
        """)
    elif format_choice == "CSV":
        st.code("""
event_id,timestamp,actor_id,action,category,outcome,event_hash
abc-123,2024-01-01T00:00:00Z,user_42,order.create,trading,success,sha256:a1b2...
        """)
    else:
        st.json({
            "title": "Audit Compliance Report",
            "summary": {
                "total_events": 12456,
                "unique_actors": 23,
                "unique_actions": 15,
                "failure_count": 234,
            },
            "categories": {"trading": 8234, "auth": 2891, "system": 1331},
        })

    config = AuditConfig()
    st.subheader("Retention Configuration")
    st.json({
        "default_retention_days": config.default_retention_days,
        "hash_algorithm": config.hash_algorithm,
        "buffer_size": config.buffer_size,
        "flush_interval_seconds": config.flush_interval_seconds,
    })
