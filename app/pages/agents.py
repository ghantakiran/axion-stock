"""Agent Hub Dashboard — Browse, chat with, and manage AI agents."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import datetime, timezone

try:
    st.set_page_config(page_title="Agent Hub", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Agent Hub")

# ── Imports ───────────────────────────────────────────────────────────

from src.agents.config import AgentCategory, AgentType
from src.agents.registry import (
    AGENT_CONFIGS,
    get_agent,
    get_agents_by_category,
    get_default_agent,
    list_agents,
)
from src.agents.router import AgentRouter
from src.agents.memory import AgentMemory

# ── Session State Init ────────────────────────────────────────────────

if "agent_memory" not in st.session_state:
    st.session_state["agent_memory"] = AgentMemory()

if "active_agent_type" not in st.session_state:
    st.session_state["active_agent_type"] = None

if "agent_chat_messages" not in st.session_state:
    st.session_state["agent_chat_messages"] = []

if "agent_api_messages" not in st.session_state:
    st.session_state["agent_api_messages"] = []

if "agent_session_id" not in st.session_state:
    st.session_state["agent_session_id"] = None

router = AgentRouter()
memory: AgentMemory = st.session_state["agent_memory"]

# ── Sidebar ───────────────────────────────────────────────────────────

st.sidebar.header("Agent Hub")
st.sidebar.caption("Choose a specialized AI agent that matches your investment style.")

# Quick agent selector in sidebar
agent_names = {a.name: a.agent_type for a in list_agents()}
selected_name = st.sidebar.selectbox(
    "Active Agent",
    options=list(agent_names.keys()),
    index=0,
    key="sidebar_agent_select",
)
if selected_name:
    selected_type = agent_names[selected_name]
    agent_cfg = get_agent(selected_type)
    st.sidebar.markdown(f"{agent_cfg.avatar} **{agent_cfg.name}**")
    st.sidebar.caption(agent_cfg.description)

st.sidebar.markdown("---")

# API key
api_key = st.sidebar.text_input(
    "Anthropic API Key",
    type="password",
    placeholder="sk-ant-...",
    key="agent_api_key",
    label_visibility="collapsed",
)
if not api_key:
    # Try to auto-load from environment or secrets
    try:
        from app.chat import get_api_key
        api_key = get_api_key() or ""
    except Exception:
        pass

# ── Main Tabs ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "Agent Gallery",
    "Active Sessions",
    "Agent Chat",
    "Settings",
])

# ── Tab 1: Agent Gallery ──────────────────────────────────────────────

with tab1:
    st.subheader("Choose Your Agent")
    st.caption("Each agent has a unique personality, tool preferences, and analysis style.")

    # Investment Style Agents
    st.markdown("### Investment Style Agents")
    style_agents = get_agents_by_category(AgentCategory.INVESTMENT_STYLE)

    cols = st.columns(3)
    for i, agent in enumerate(style_agents):
        with cols[i % 3]:
            with st.container():
                st.markdown(f"#### {agent.avatar} {agent.name}")
                st.caption(agent.description)

                # Example queries
                with st.expander("Example queries"):
                    for q in agent.example_queries:
                        st.markdown(f"- *{q}*")

                if st.button(
                    f"Start Chat with {agent.name}",
                    key=f"start_{agent.agent_type.value}",
                    use_container_width=True,
                ):
                    st.session_state["active_agent_type"] = agent.agent_type
                    st.session_state["agent_chat_messages"] = []
                    st.session_state["agent_api_messages"] = []
                    session = memory.create_session(
                        user_id="default",
                        agent_type=agent.agent_type.value,
                        title=f"Chat with {agent.name}",
                    )
                    st.session_state["agent_session_id"] = session.session_id
                    st.rerun()

    st.markdown("---")

    # Functional Role Agents
    st.markdown("### Functional Role Agents")
    role_agents = get_agents_by_category(AgentCategory.FUNCTIONAL_ROLE)

    cols2 = st.columns(2)
    for i, agent in enumerate(role_agents):
        with cols2[i % 2]:
            with st.container():
                st.markdown(f"#### {agent.avatar} {agent.name}")
                st.caption(agent.description)

                with st.expander("Example queries"):
                    for q in agent.example_queries:
                        st.markdown(f"- *{q}*")

                if st.button(
                    f"Start Chat with {agent.name}",
                    key=f"start_{agent.agent_type.value}",
                    use_container_width=True,
                ):
                    st.session_state["active_agent_type"] = agent.agent_type
                    st.session_state["agent_chat_messages"] = []
                    st.session_state["agent_api_messages"] = []
                    session = memory.create_session(
                        user_id="default",
                        agent_type=agent.agent_type.value,
                        title=f"Chat with {agent.name}",
                    )
                    st.session_state["agent_session_id"] = session.session_id
                    st.rerun()


# ── Tab 2: Active Sessions ───────────────────────────────────────────

with tab2:
    st.subheader("Active Sessions")

    sessions = memory.get_user_sessions("default", active_only=False)

    if not sessions:
        st.info("No active sessions. Start a chat from the Agent Gallery!")
    else:
        for session in sessions:
            agent_cfg = AGENT_CONFIGS.get(AgentType(session.agent_type))
            avatar = agent_cfg.avatar if agent_cfg else "🤖"
            name = agent_cfg.name if agent_cfg else session.agent_type

            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.markdown(f"**{avatar} {name}** — {session.title}")
            with col2:
                st.caption(f"{session.message_count} msgs")
            with col3:
                if st.button("Resume", key=f"resume_{session.session_id}"):
                    st.session_state["active_agent_type"] = AgentType(session.agent_type)
                    # Restore messages from memory
                    msgs = memory.load_messages(session.session_id)
                    st.session_state["agent_chat_messages"] = [
                        {"role": m["role"], "content": m["content"]}
                        for m in msgs
                    ]
                    st.session_state["agent_api_messages"] = [
                        {"role": m["role"], "content": m["content"]}
                        for m in msgs
                    ]
                    st.session_state["agent_session_id"] = session.session_id
                    st.rerun()
            with col4:
                if st.button("Delete", key=f"delete_{session.session_id}"):
                    memory.delete_session(session.session_id)
                    st.rerun()

    # Stats
    st.markdown("---")
    stats = memory.get_session_stats("default")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Sessions", stats["total_sessions"])
    col_b.metric("Total Messages", stats["total_messages"])
    col_c.metric("Agents Used", len(stats["agents_used"]))


# ── Tab 3: Agent Chat ────────────────────────────────────────────────

with tab3:
    active_type = st.session_state.get("active_agent_type")

    if not active_type:
        st.info("Select an agent from the Gallery or Active Sessions to start chatting.")
    else:
        agent_cfg = get_agent(active_type)
        st.markdown(f"### {agent_cfg.avatar} {agent_cfg.name}")
        st.caption(agent_cfg.description)

        # Show welcome message if no messages yet
        if not st.session_state["agent_chat_messages"]:
            st.info(agent_cfg.welcome_message)

        # Agent switch suggestion
        if st.session_state["agent_chat_messages"]:
            last_user_msg = None
            for m in reversed(st.session_state["agent_chat_messages"]):
                if m["role"] == "user":
                    last_user_msg = m["content"]
                    break
            if last_user_msg:
                suggestion = router.should_suggest_switch(last_user_msg, active_type)
                if suggestion:
                    suggested_cfg = get_agent(suggestion.agent_type)
                    st.info(
                        f"💡 Try **{suggested_cfg.avatar} {suggested_cfg.name}** "
                        f"for this type of query ({suggestion.reason})"
                    )

        # Display chat history
        for msg in st.session_state["agent_chat_messages"]:
            avatar = agent_cfg.avatar if msg["role"] == "assistant" else None
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

        # Chat input
        if prompt := st.chat_input(f"Ask {agent_cfg.name}...", key="agent_chat_input"):
            # Add user message
            st.session_state["agent_chat_messages"].append(
                {"role": "user", "content": prompt}
            )
            st.session_state["agent_api_messages"].append(
                {"role": "user", "content": prompt}
            )

            # Save to memory
            session_id = st.session_state.get("agent_session_id")
            if session_id:
                memory.save_message(session_id, "user", prompt)

            with st.chat_message("user"):
                st.markdown(prompt)

            if not api_key:
                with st.chat_message("assistant", avatar=agent_cfg.avatar):
                    st.error("Enter your Anthropic API key in the sidebar to chat with agents.")
            else:
                with st.chat_message("assistant", avatar=agent_cfg.avatar):
                    with st.spinner(f"{agent_cfg.name} is thinking..."):
                        try:
                            from src.agents.engine import AgentEngine

                            engine = AgentEngine()
                            response_text, updated_messages, tool_calls = engine.get_response(
                                st.session_state["agent_api_messages"],
                                api_key,
                                agent_cfg,
                            )

                            st.session_state["agent_api_messages"] = updated_messages
                            st.session_state["agent_api_messages"].append(
                                {"role": "assistant", "content": response_text}
                            )
                            st.session_state["agent_chat_messages"].append(
                                {"role": "assistant", "content": response_text}
                            )

                            # Save to memory
                            if session_id:
                                memory.save_message(
                                    session_id,
                                    "assistant",
                                    response_text,
                                )

                            st.markdown(response_text)

                        except Exception as e:
                            try:
                                from app.chat import format_api_error
                                st.error(format_api_error(e))
                            except Exception:
                                st.error(f"Error: {e}")

        # New chat button
        st.markdown("---")
        if st.button("New Chat", key="new_agent_chat"):
            st.session_state["agent_chat_messages"] = []
            st.session_state["agent_api_messages"] = []
            session = memory.create_session(
                user_id="default",
                agent_type=active_type.value,
                title=f"Chat with {agent_cfg.name}",
            )
            st.session_state["agent_session_id"] = session.session_id
            st.rerun()


# ── Tab 4: Settings ──────────────────────────────────────────────────

with tab4:
    st.subheader("Agent Preferences")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Default Agent")
        default_names = [a.name for a in list_agents()]
        current_pref = memory.load_preference("default", "default_agent")
        default_idx = 0
        if current_pref:
            try:
                default_idx = default_names.index(current_pref)
            except ValueError:
                pass

        chosen_default = st.selectbox(
            "Default agent for new chats",
            options=default_names,
            index=default_idx,
            key="pref_default_agent",
        )

        st.markdown("### Response Verbosity")
        verbosity = st.select_slider(
            "Detail Level",
            options=["Concise", "Balanced", "Detailed"],
            value="Balanced",
            key="pref_verbosity",
        )

    with col2:
        st.markdown("### Agent Overview")

        for agent in list_agents():
            priority = agent.priority_tools[:3]
            tools_str = ", ".join(priority) if priority else "All tools equally"
            st.markdown(
                f"**{agent.avatar} {agent.name}** — "
                f"Top tools: {tools_str}"
            )

    st.markdown("---")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("Save Preferences", type="primary"):
            memory.save_preference("default", "default_agent", chosen_default)
            memory.save_preference("default", "verbosity", verbosity)
            st.success("Preferences saved!")
    with col_s2:
        if st.button("Reset to Defaults"):
            memory.save_preference("default", "default_agent", "Alpha Strategist")
            memory.save_preference("default", "verbosity", "Balanced")
            st.info("Preferences reset to defaults.")
