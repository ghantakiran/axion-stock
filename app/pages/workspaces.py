"""Team Workspaces Dashboard - PRD-69.

Collaborative workspace features:
- Workspace list and creation
- Member management
- Shared strategy library with leaderboard
- Activity feed
- Research notes sharing
- Shared watchlists
"""

import sys
import os
from datetime import datetime, timedelta
import random
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

try:
    st.set_page_config(page_title="Workspaces", page_icon="👥", layout="wide")
except st.errors.StreamlitAPIException:
    pass


# Try to import enterprise modules
try:
    from src.enterprise.workspaces import WorkspaceManager
    from src.enterprise.config import SubscriptionTier
    WORKSPACES_AVAILABLE = True
except ImportError:
    WORKSPACES_AVAILABLE = False


def init_session_state():
    """Initialize session state."""
    if "demo_workspaces" not in st.session_state:
        st.session_state.demo_workspaces = generate_demo_workspaces()
    if "selected_workspace_id" not in st.session_state:
        st.session_state.selected_workspace_id = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = {
            "id": "user-001",
            "name": "John Smith",
            "email": "john@example.com",
            "role": "owner",
        }


def generate_demo_workspaces():
    """Generate demo workspace data."""
    workspaces = [
        {
            "id": "ws-001",
            "name": "Alpha Capital Research",
            "description": "Quantitative research team focused on factor-based strategies",
            "owner_id": "user-001",
            "owner_name": "John Smith",
            "member_count": 5,
            "strategy_count": 12,
            "total_aum": 2400000,
            "created_at": datetime(2024, 6, 15),
            "members": [
                {"id": "user-001", "name": "John Smith", "role": "owner", "email": "john@example.com", "joined": datetime(2024, 6, 15)},
                {"id": "user-002", "name": "Sarah Chen", "role": "admin", "email": "sarah@example.com", "joined": datetime(2024, 6, 20)},
                {"id": "user-003", "name": "Mike Johnson", "role": "member", "email": "mike@example.com", "joined": datetime(2024, 7, 1)},
                {"id": "user-004", "name": "Lisa Park", "role": "member", "email": "lisa@example.com", "joined": datetime(2024, 7, 15)},
                {"id": "user-005", "name": "David Lee", "role": "viewer", "email": "david@example.com", "joined": datetime(2024, 8, 1)},
            ],
            "strategies": [
                {"id": "strat-001", "name": "Quality Growth v3", "creator": "Sarah Chen", "ytd_return": 0.142, "sharpe": 1.82, "use_count": 8, "created": datetime(2024, 8, 15)},
                {"id": "strat-002", "name": "Earnings Momentum", "creator": "John Smith", "ytd_return": 0.118, "sharpe": 1.45, "use_count": 5, "created": datetime(2024, 7, 20)},
                {"id": "strat-003", "name": "Tech Alpha", "creator": "Mike Johnson", "ytd_return": 0.104, "sharpe": 1.21, "use_count": 3, "created": datetime(2024, 9, 1)},
                {"id": "strat-004", "name": "Deep Value", "creator": "Lisa Park", "ytd_return": 0.091, "sharpe": 1.08, "use_count": 4, "created": datetime(2024, 8, 1)},
                {"id": "strat-005", "name": "Dividend Aristocrats", "creator": "John Smith", "ytd_return": 0.067, "sharpe": 1.35, "use_count": 6, "created": datetime(2024, 6, 25)},
            ],
            "activities": generate_demo_activities("ws-001"),
            "watchlists": [
                {"id": "wl-001", "name": "Tech Leaders", "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"], "creator": "Mike Johnson"},
                {"id": "wl-002", "name": "Dividend Champions", "symbols": ["JNJ", "PG", "KO", "PEP", "MCD"], "creator": "Lisa Park"},
            ],
            "research_notes": [
                {"id": "rn-001", "title": "NVDA Earnings Analysis Q4", "author": "Mike Johnson", "symbols": ["NVDA"], "tags": ["earnings", "semiconductors"], "created": datetime(2024, 11, 20), "is_pinned": True},
                {"id": "rn-002", "title": "Fed Rate Decision Impact", "author": "Sarah Chen", "symbols": [], "tags": ["macro", "rates"], "created": datetime(2024, 11, 15), "is_pinned": False},
                {"id": "rn-003", "title": "Quality Factor Deep Dive", "author": "John Smith", "symbols": [], "tags": ["factors", "research"], "created": datetime(2024, 10, 28), "is_pinned": False},
            ],
        },
        {
            "id": "ws-002",
            "name": "Options Trading Club",
            "description": "Options strategies and volatility trading ideas",
            "owner_id": "user-002",
            "owner_name": "Sarah Chen",
            "member_count": 3,
            "strategy_count": 6,
            "total_aum": 850000,
            "created_at": datetime(2024, 9, 1),
            "members": [
                {"id": "user-002", "name": "Sarah Chen", "role": "owner", "email": "sarah@example.com", "joined": datetime(2024, 9, 1)},
                {"id": "user-001", "name": "John Smith", "role": "member", "email": "john@example.com", "joined": datetime(2024, 9, 5)},
                {"id": "user-006", "name": "Tom Wilson", "role": "member", "email": "tom@example.com", "joined": datetime(2024, 9, 10)},
            ],
            "strategies": [
                {"id": "strat-006", "name": "Iron Condor Weekly", "creator": "Sarah Chen", "ytd_return": 0.085, "sharpe": 1.95, "use_count": 12, "created": datetime(2024, 9, 15)},
                {"id": "strat-007", "name": "Vol Selling", "creator": "Tom Wilson", "ytd_return": 0.072, "sharpe": 1.65, "use_count": 8, "created": datetime(2024, 10, 1)},
            ],
            "activities": generate_demo_activities("ws-002"),
            "watchlists": [],
            "research_notes": [],
        },
    ]
    return workspaces


def generate_demo_activities(workspace_id: str):
    """Generate demo activity feed."""
    actions = [
        ("created_strategy", "strategy", "Created strategy '{}'"),
        ("updated_strategy", "strategy", "Updated strategy '{}'"),
        ("executed_trade", "trade", "Executed trade in {}"),
        ("shared_research", "research", "Shared research note: {}"),
        ("rebalanced", "account", "Rebalanced portfolio"),
        ("joined_workspace", "user", "Joined the workspace"),
        ("hit_new_high", "strategy", "{} hit new high watermark"),
    ]

    names = ["John Smith", "Sarah Chen", "Mike Johnson", "Lisa Park", "David Lee"]
    resources = ["Quality Growth v3", "Earnings Momentum", "Tech Alpha", "NVDA analysis", "AAPL", "MSFT"]

    activities = []
    base_time = datetime.now()

    for i in range(15):
        action, resource_type, template = random.choice(actions)
        user_name = random.choice(names)
        resource = random.choice(resources)

        activities.append({
            "id": f"act-{i:03d}",
            "user_name": user_name,
            "action": action,
            "resource_type": resource_type,
            "resource_name": resource,
            "message": template.format(resource),
            "timestamp": base_time - timedelta(hours=i * 2 + random.randint(0, 3)),
        })

    return sorted(activities, key=lambda x: x["timestamp"], reverse=True)


def render_workspace_list():
    """Render list of workspaces."""
    st.subheader("My Workspaces")

    workspaces = st.session_state.demo_workspaces

    if not workspaces:
        st.info("You are not a member of any workspaces yet. Create one to get started!")
        return

    for ws in workspaces:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

            with col1:
                if st.button(f"**{ws['name']}**", key=f"ws_{ws['id']}", use_container_width=True):
                    st.session_state.selected_workspace_id = ws['id']
                    st.rerun()
                st.caption(ws['description'][:60] + "..." if len(ws['description']) > 60 else ws['description'])

            with col2:
                st.metric("Members", ws['member_count'])

            with col3:
                st.metric("Strategies", ws['strategy_count'])

            with col4:
                st.metric("AUM", f"${ws['total_aum']/1000000:.1f}M")

            st.divider()


def render_create_workspace():
    """Render workspace creation form."""
    st.subheader("Create New Workspace")

    with st.form("create_workspace"):
        name = st.text_input("Workspace Name", placeholder="e.g., Alpha Research Team")
        description = st.text_area("Description", placeholder="Describe the purpose of this workspace...")

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Create Workspace", type="primary", use_container_width=True)
        with col2:
            st.form_submit_button("Cancel", use_container_width=True)

        if submitted and name:
            new_workspace = {
                "id": f"ws-{uuid.uuid4().hex[:8]}",
                "name": name,
                "description": description,
                "owner_id": st.session_state.current_user["id"],
                "owner_name": st.session_state.current_user["name"],
                "member_count": 1,
                "strategy_count": 0,
                "total_aum": 0,
                "created_at": datetime.now(),
                "members": [
                    {
                        "id": st.session_state.current_user["id"],
                        "name": st.session_state.current_user["name"],
                        "role": "owner",
                        "email": st.session_state.current_user["email"],
                        "joined": datetime.now(),
                    }
                ],
                "strategies": [],
                "activities": [],
                "watchlists": [],
                "research_notes": [],
            }
            st.session_state.demo_workspaces.append(new_workspace)
            st.success(f"Workspace '{name}' created successfully!")
            st.rerun()


def render_workspace_detail(workspace: dict):
    """Render detailed workspace view."""
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title(f"👥 {workspace['name']}")
        st.caption(workspace['description'])
    with col2:
        if st.button("Back to List", use_container_width=True):
            st.session_state.selected_workspace_id = None
            st.rerun()

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Members", workspace['member_count'])
    with col2:
        st.metric("Strategies", workspace['strategy_count'])
    with col3:
        st.metric("Total AUM", f"${workspace['total_aum']/1000000:.1f}M")
    with col4:
        top_strat = workspace['strategies'][0] if workspace['strategies'] else None
        top_return = f"{top_strat['ytd_return']*100:.1f}%" if top_strat else "N/A"
        st.metric("Top YTD", top_return)
    with col5:
        st.metric("Created", workspace['created_at'].strftime("%b %Y"))

    st.divider()

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Activity Feed",
        "Strategy Leaderboard",
        "Members",
        "Watchlists",
        "Research Notes",
    ])

    with tab1:
        render_activity_feed(workspace)

    with tab2:
        render_strategy_leaderboard(workspace)

    with tab3:
        render_members(workspace)

    with tab4:
        render_watchlists(workspace)

    with tab5:
        render_research_notes(workspace)


def render_activity_feed(workspace: dict):
    """Render activity feed."""
    st.subheader("Recent Activity")

    activities = workspace.get("activities", [])

    if not activities:
        st.info("No recent activity in this workspace.")
        return

    for activity in activities[:10]:
        col1, col2 = st.columns([5, 1])

        with col1:
            # Icon based on action
            icons = {
                "created_strategy": "🎯",
                "updated_strategy": "📝",
                "executed_trade": "💹",
                "shared_research": "📊",
                "rebalanced": "⚖️",
                "joined_workspace": "👋",
                "hit_new_high": "🏆",
            }
            icon = icons.get(activity['action'], "📌")

            st.markdown(f"{icon} **{activity['user_name']}** {activity['message']}")

        with col2:
            time_ago = datetime.now() - activity['timestamp']
            if time_ago.days > 0:
                st.caption(f"{time_ago.days}d ago")
            elif time_ago.seconds > 3600:
                st.caption(f"{time_ago.seconds // 3600}h ago")
            else:
                st.caption(f"{time_ago.seconds // 60}m ago")


def render_strategy_leaderboard(workspace: dict):
    """Render strategy leaderboard."""
    st.subheader("Strategy Leaderboard")

    strategies = workspace.get("strategies", [])

    if not strategies:
        st.info("No strategies shared in this workspace yet.")
        return

    # Sort by YTD return
    sorted_strategies = sorted(strategies, key=lambda x: x['ytd_return'], reverse=True)

    # Leaderboard table
    df = pd.DataFrame([
        {
            "Rank": i + 1,
            "Strategy": s['name'],
            "Creator": s['creator'],
            "YTD Return": f"{s['ytd_return']*100:.1f}%",
            "Sharpe": f"{s['sharpe']:.2f}",
            "Users": s['use_count'],
        }
        for i, s in enumerate(sorted_strategies)
    ])

    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Rank": st.column_config.NumberColumn("🏆", width="small"),
            "YTD Return": st.column_config.TextColumn("YTD Return"),
            "Sharpe": st.column_config.TextColumn("Sharpe"),
        }
    )

    # Performance chart
    st.subheader("Performance Comparison")

    fig = go.Figure()

    colors = px.colors.qualitative.Set2
    for i, strat in enumerate(sorted_strategies[:5]):
        # Generate mock equity curve
        dates = pd.date_range(start='2024-01-01', periods=250, freq='B')
        base_return = strat['ytd_return']
        daily_return = (1 + base_return) ** (1/250) - 1

        values = [100]
        for _ in range(249):
            change = daily_return + random.gauss(0, 0.01)
            values.append(values[-1] * (1 + change))

        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
            name=strat['name'],
            line=dict(color=colors[i % len(colors)]),
        ))

    fig.update_layout(
        title="Strategy Performance (Indexed to 100)",
        xaxis_title="Date",
        yaxis_title="Value",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Share strategy form
    with st.expander("Share New Strategy"):
        with st.form("share_strategy"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Strategy Name")
                ytd_return = st.number_input("YTD Return (%)", value=0.0, step=0.1)
            with col2:
                description = st.text_input("Description")
                sharpe = st.number_input("Sharpe Ratio", value=0.0, step=0.01)

            if st.form_submit_button("Share Strategy", type="primary"):
                if name:
                    new_strategy = {
                        "id": f"strat-{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "creator": st.session_state.current_user["name"],
                        "ytd_return": ytd_return / 100,
                        "sharpe": sharpe,
                        "use_count": 0,
                        "created": datetime.now(),
                    }
                    workspace['strategies'].append(new_strategy)
                    workspace['strategy_count'] = len(workspace['strategies'])
                    st.success(f"Strategy '{name}' shared!")
                    st.rerun()


def render_members(workspace: dict):
    """Render members management."""
    st.subheader("Team Members")

    members = workspace.get("members", [])
    current_user_role = "viewer"
    for m in members:
        if m['id'] == st.session_state.current_user['id']:
            current_user_role = m['role']
            break

    # Member list
    for member in members:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

        with col1:
            role_badges = {
                "owner": "👑",
                "admin": "⚡",
                "member": "👤",
                "viewer": "👁️",
            }
            badge = role_badges.get(member['role'], "👤")
            st.markdown(f"{badge} **{member['name']}**")
            st.caption(member['email'])

        with col2:
            st.text(member['role'].title())

        with col3:
            st.text(f"Joined {member['joined'].strftime('%b %d, %Y')}")

        with col4:
            if current_user_role in ["owner", "admin"] and member['role'] != "owner":
                if st.button("Remove", key=f"remove_{member['id']}", type="secondary"):
                    st.warning(f"Remove {member['name']}?")

    st.divider()

    # Invite member
    if current_user_role in ["owner", "admin"]:
        st.subheader("Invite Member")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            email = st.text_input("Email Address", placeholder="colleague@example.com", label_visibility="collapsed")
        with col2:
            role = st.selectbox("Role", ["member", "admin", "viewer"], label_visibility="collapsed")
        with col3:
            if st.button("Send Invite", type="primary", use_container_width=True):
                if email:
                    st.success(f"Invitation sent to {email}!")


def render_watchlists(workspace: dict):
    """Render shared watchlists."""
    st.subheader("Shared Watchlists")

    watchlists = workspace.get("watchlists", [])

    if not watchlists:
        st.info("No shared watchlists yet. Create one to get started!")
    else:
        for wl in watchlists:
            with st.expander(f"📋 {wl['name']} ({len(wl['symbols'])} symbols)"):
                st.caption(f"Created by {wl['creator']}")

                # Display symbols as chips
                symbols_str = " | ".join([f"`{s}`" for s in wl['symbols']])
                st.markdown(symbols_str)

                # Mini performance table
                if wl['symbols']:
                    perf_data = []
                    for sym in wl['symbols']:
                        perf_data.append({
                            "Symbol": sym,
                            "Price": f"${random.uniform(50, 500):.2f}",
                            "Day": f"{random.uniform(-3, 5):.1f}%",
                            "Week": f"{random.uniform(-5, 8):.1f}%",
                        })
                    st.dataframe(pd.DataFrame(perf_data), hide_index=True, use_container_width=True)

    # Create watchlist
    with st.expander("Create New Watchlist"):
        with st.form("create_watchlist"):
            name = st.text_input("Watchlist Name")
            symbols = st.text_input("Symbols (comma-separated)", placeholder="AAPL, MSFT, NVDA")

            if st.form_submit_button("Create Watchlist", type="primary"):
                if name and symbols:
                    symbol_list = [s.strip().upper() for s in symbols.split(",")]
                    new_watchlist = {
                        "id": f"wl-{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "symbols": symbol_list,
                        "creator": st.session_state.current_user["name"],
                    }
                    workspace['watchlists'].append(new_watchlist)
                    st.success(f"Watchlist '{name}' created!")
                    st.rerun()


def render_research_notes(workspace: dict):
    """Render research notes."""
    st.subheader("Research Notes")

    notes = workspace.get("research_notes", [])

    # Pinned notes first
    pinned = [n for n in notes if n.get('is_pinned')]
    unpinned = [n for n in notes if not n.get('is_pinned')]

    if pinned:
        st.markdown("**📌 Pinned**")
        for note in pinned:
            render_research_note_card(note)

    if unpinned:
        st.markdown("**Recent**")
        for note in unpinned:
            render_research_note_card(note)

    if not notes:
        st.info("No research notes shared yet.")

    # Create note
    with st.expander("Share Research Note"):
        with st.form("create_note"):
            title = st.text_input("Title")
            content = st.text_area("Content", height=200)
            col1, col2 = st.columns(2)
            with col1:
                symbols = st.text_input("Related Symbols (comma-separated)")
            with col2:
                tags = st.text_input("Tags (comma-separated)")

            if st.form_submit_button("Share Note", type="primary"):
                if title:
                    new_note = {
                        "id": f"rn-{uuid.uuid4().hex[:8]}",
                        "title": title,
                        "author": st.session_state.current_user["name"],
                        "symbols": [s.strip().upper() for s in symbols.split(",")] if symbols else [],
                        "tags": [t.strip() for t in tags.split(",")] if tags else [],
                        "created": datetime.now(),
                        "is_pinned": False,
                    }
                    workspace['research_notes'].insert(0, new_note)
                    st.success(f"Research note '{title}' shared!")
                    st.rerun()


def render_research_note_card(note: dict):
    """Render a research note card."""
    with st.container():
        col1, col2 = st.columns([5, 1])

        with col1:
            st.markdown(f"**{note['title']}**")
            st.caption(f"By {note['author']} on {note['created'].strftime('%b %d, %Y')}")

            # Tags
            if note.get('tags'):
                tags_str = " ".join([f"`{t}`" for t in note['tags']])
                st.markdown(tags_str)

            # Symbols
            if note.get('symbols'):
                symbols_str = " ".join([f"${s}" for s in note['symbols']])
                st.markdown(symbols_str)

        with col2:
            st.button("View", key=f"view_{note['id']}")

        st.divider()


def main():
    """Main application."""
    init_session_state()

    st.title("👥 Team Workspaces")
    st.caption("Collaborate with your team on strategies, research, and trading ideas")

    # Check if enterprise features available
    if not WORKSPACES_AVAILABLE:
        st.warning("Team Workspaces require Enterprise subscription. Using demo mode.")

    # Check if viewing specific workspace
    selected_id = st.session_state.selected_workspace_id

    if selected_id:
        workspace = next((w for w in st.session_state.demo_workspaces if w['id'] == selected_id), None)
        if workspace:
            render_workspace_detail(workspace)
        else:
            st.error("Workspace not found")
            st.session_state.selected_workspace_id = None
    else:
        # Main workspace list view
        tab1, tab2 = st.tabs(["My Workspaces", "Create New"])

        with tab1:
            render_workspace_list()

        with tab2:
            render_create_workspace()

    # Sidebar stats
    with st.sidebar:
        st.subheader("Workspace Stats")

        total_workspaces = len(st.session_state.demo_workspaces)
        total_strategies = sum(ws['strategy_count'] for ws in st.session_state.demo_workspaces)
        total_aum = sum(ws['total_aum'] for ws in st.session_state.demo_workspaces)

        st.metric("Your Workspaces", total_workspaces)
        st.metric("Shared Strategies", total_strategies)
        st.metric("Combined AUM", f"${total_aum/1000000:.1f}M")

        st.divider()

        st.subheader("Quick Actions")
        if st.button("Create Workspace", use_container_width=True):
            st.session_state.selected_workspace_id = None
            st.rerun()

        if st.button("Invite Colleague", use_container_width=True):
            st.info("Select a workspace first to invite members")



main()
