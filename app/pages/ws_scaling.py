"""PRD-119: WebSocket Scaling & Real-time Infrastructure Dashboard."""

import random
import streamlit as st
from datetime import datetime, timedelta

from src.ws_scaling import (
    ConnectionRegistry,
    MessageRouter,
    BackpressureHandler,
    ReconnectionManager,
    WSScalingConfig,
    MessagePriority,
    ConnectionState,
    Message,
)


def render():
    try:
        st.set_page_config(page_title="WebSocket Scaling", page_icon="\U0001f50c")
    except st.errors.StreamlitAPIException:
        pass
    st.title("\U0001f50c WebSocket Scaling & Real-time Infrastructure")

    tabs = st.tabs(["Connections", "Message Throughput", "Backpressure", "Health"])

    # ── Generate sample data ─────────────────────────────────────────
    config = WSScalingConfig()
    registry = ConnectionRegistry(config=config)
    router = MessageRouter()
    bp_handler = BackpressureHandler(config=config)
    recon_mgr = ReconnectionManager(config=config)

    # Register sample connections
    sample_users = ["alice", "bob", "charlie", "diana", "eve"]
    sample_instances = ["ws-node-1", "ws-node-2", "ws-node-3"]
    sample_channels = ["prices.AAPL", "prices.GOOGL", "trades", "alerts", "portfolio"]
    connections = []
    for user in sample_users:
        for inst in random.sample(sample_instances, k=random.randint(1, 2)):
            subs = random.sample(sample_channels, k=random.randint(1, 3))
            info = registry.register(user, inst, subscriptions=subs)
            connections.append(info)
            for ch in subs:
                router.subscribe(info.connection_id, ch)

    # Generate sample messages
    for ch in sample_channels:
        for _ in range(random.randint(5, 20)):
            prio = random.choice(list(MessagePriority))
            router.broadcast(ch, {"value": round(random.uniform(100, 500), 2)}, priority=prio)

    # Generate sample backpressure
    for conn in connections[:3]:
        for _ in range(random.randint(50, 200)):
            bp_handler.enqueue(
                conn.connection_id,
                Message(channel="prices.AAPL", payload={"tick": random.random()}),
            )

    # Generate sample reconnection sessions
    for conn in connections[3:5]:
        session = recon_mgr.start_session(conn.user_id, conn.connection_id)
        for _ in range(random.randint(1, 5)):
            recon_mgr.buffer_message(
                conn.connection_id,
                Message(channel="prices", payload={"missed": True}),
            )
        if random.random() > 0.5:
            recon_mgr.attempt_reconnect(session.session_id, f"new-{conn.connection_id[:8]}")

    # ── Tab 1: Connections ───────────────────────────────────────────
    with tabs[0]:
        st.subheader("Connection Overview")
        stats = registry.get_stats()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Connections", stats["total_connections"])
        col2.metric("Active Users", stats["total_users"])
        col3.metric("Server Instances", stats["total_instances"])
        col4.metric("Global Limit", f"{stats['total_connections']}/{stats['max_global_connections']}")

        st.subheader("Connections by User")
        user_data = []
        for user in sample_users:
            user_conns = registry.get_user_connections(user)
            for c in user_conns:
                user_data.append({
                    "User": c.user_id,
                    "Connection ID": c.connection_id[:12] + "...",
                    "Instance": c.instance_id,
                    "State": c.state.value,
                    "Subscriptions": ", ".join(c.subscriptions),
                    "Connected At": c.connected_at.strftime("%H:%M:%S"),
                })
        st.dataframe(user_data, use_container_width=True)

        st.subheader("Connections per Instance")
        inst_data = []
        for inst in sample_instances:
            inst_conns = registry.get_instance_connections(inst)
            inst_data.append({
                "Instance": inst,
                "Connections": len(inst_conns),
                "Users": len(set(c.user_id for c in inst_conns)),
            })
        st.dataframe(inst_data, use_container_width=True)

    # ── Tab 2: Message Throughput ────────────────────────────────────
    with tabs[1]:
        st.subheader("Channel Statistics")

        channel_stats = router.get_channel_stats()
        msg_log = router.get_message_log()

        col1, col2, col3 = st.columns(3)
        col1.metric("Active Channels", len(channel_stats))
        col2.metric("Total Messages", len(msg_log))
        col3.metric("Avg Subscribers/Channel",
                     f"{sum(channel_stats.values()) / max(len(channel_stats), 1):.1f}")

        st.subheader("Subscribers per Channel")
        ch_data = [{"Channel": ch, "Subscribers": cnt} for ch, cnt in sorted(channel_stats.items())]
        st.dataframe(ch_data, use_container_width=True)

        st.subheader("Recent Messages")
        recent = router.get_message_log(limit=20)
        msg_data = []
        for m in recent[-15:]:
            msg_data.append({
                "ID": m.message_id[:12] + "...",
                "Channel": m.channel,
                "Priority": m.priority.value,
                "Targets": len(m.target_connection_ids) if m.target_connection_ids else 0,
                "Time": m.timestamp.strftime("%H:%M:%S.%f")[:-3],
            })
        st.dataframe(msg_data, use_container_width=True)

        st.subheader("Priority Distribution")
        prio_counts = {}
        for m in msg_log:
            prio_counts[m.priority.value] = prio_counts.get(m.priority.value, 0) + 1
        prio_data = [{"Priority": p, "Count": c} for p, c in sorted(prio_counts.items())]
        st.dataframe(prio_data, use_container_width=True)

    # ── Tab 3: Backpressure ──────────────────────────────────────────
    with tabs[2]:
        st.subheader("Backpressure Monitor")

        total_queued = bp_handler.get_total_queued()
        slow = bp_handler.detect_slow_consumers()
        all_bp_stats = bp_handler.get_all_stats()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Queued Messages", total_queued)
        col2.metric("Slow Consumers", len(slow))
        col3.metric("Tracked Queues", len(all_bp_stats))

        st.subheader("Queue Details")
        q_data = []
        for cid, qs in all_bp_stats.items():
            q_data.append({
                "Connection": cid[:12] + "...",
                "Queue Depth": qs.queue_depth,
                "Oldest Msg Age (ms)": f"{qs.oldest_message_age_ms:.0f}",
                "Messages Dropped": qs.messages_dropped,
                "Slow?": "Yes" if qs.is_slow else "No",
            })
        st.dataframe(q_data, use_container_width=True)

        if slow:
            st.warning(f"{len(slow)} slow consumer(s) detected. Consider applying drop strategies.")

    # ── Tab 4: Health ────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Reconnection Health")

        recon_stats = recon_mgr.get_reconnection_stats()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Sessions", recon_stats["total"])
        col2.metric("Successful", recon_stats["successful"])
        col3.metric("Failed", recon_stats["failed"])
        col4.metric("Avg Attempts", f"{recon_stats['avg_attempts']:.1f}")

        st.subheader("Session Details")
        sessions = recon_mgr.list_sessions()
        sess_data = []
        for s in sessions:
            sess_data.append({
                "Session ID": s.session_id[:12] + "...",
                "User": s.user_id,
                "Original Conn": s.original_connection_id[:12] + "...",
                "State": s.state,
                "Attempts": s.attempt_count,
                "Missed Messages": len(s.missed_messages),
            })
        st.dataframe(sess_data, use_container_width=True)

        st.subheader("Infrastructure Summary")
        summary_data = {
            "Max Connections/User": config.max_connections_per_user,
            "Max Global Connections": config.max_global_connections,
            "Message Buffer Size": config.message_buffer_size,
            "Backpressure Threshold": config.backpressure_threshold,
            "Slow Consumer Threshold (ms)": config.slow_consumer_threshold_ms,
            "Reconnection Window (s)": config.reconnection_window_seconds,
            "Max Reconnection Attempts": config.max_reconnection_attempts,
            "Heartbeat Interval (s)": config.heartbeat_interval_seconds,
        }
        for key, val in summary_data.items():
            st.text(f"{key}: {val}")



render()
