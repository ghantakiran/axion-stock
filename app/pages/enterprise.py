"""Enterprise Dashboard Streamlit Page.

Comprehensive enterprise interface with:
- User profile and settings
- Multi-account management
- Team workspaces
- Reports
- Audit logs
"""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
from datetime import datetime, date, timedelta

# Page config
try:
    st.set_page_config(
        page_title="Axion Enterprise",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()


# Import enterprise module
try:
    from src.enterprise import (
        AuthService, AccountManager, WorkspaceManager,
        ReportGenerator, AuditLogger, ComplianceManager,
        UserRole, SubscriptionTier, AccountType, TaxStatus,
        SUBSCRIPTION_LIMITS, ReportData, PerformanceMetrics,
    )
    ENTERPRISE_AVAILABLE = True
except ImportError as e:
    ENTERPRISE_AVAILABLE = False
    st.error(f"Enterprise module not available: {e}")


def init_session_state():
    """Initialize session state."""
    if "auth_service" not in st.session_state:
        st.session_state.auth_service = AuthService()
    if "account_manager" not in st.session_state:
        st.session_state.account_manager = AccountManager()
    if "workspace_manager" not in st.session_state:
        st.session_state.workspace_manager = WorkspaceManager()
    if "audit_logger" not in st.session_state:
        st.session_state.audit_logger = AuditLogger()
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False


def render_login():
    """Render login/register form."""
    st.title("🔐 Authentication")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary")

            if submitted and email and password:
                auth = st.session_state.auth_service
                session, error = auth.login(email, password)

                if session:
                    user, _ = auth.verify_token(session.access_token)
                    st.session_state.current_user = user
                    st.session_state.is_logged_in = True
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error(error or "Login failed")

    with tab2:
        with st.form("register_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_pass")
            confirm = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Register", type="primary")

            if submitted:
                if password != confirm:
                    st.error("Passwords do not match")
                elif email and password:
                    auth = st.session_state.auth_service
                    user, error = auth.register(email, password, name)

                    if user:
                        st.success("Registration successful! Please login.")
                    else:
                        st.error(error or "Registration failed")


def render_profile():
    """Render user profile section."""
    user = st.session_state.current_user

    st.header("👤 Profile")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"**Email:** {user.email}")
        st.markdown(f"**Name:** {user.name}")
        st.markdown(f"**Role:** {user.role.value.title()}")

        # Subscription badge
        sub = user.subscription
        if sub == SubscriptionTier.FREE:
            st.markdown("**Plan:** 🆓 Free")
        elif sub == SubscriptionTier.PRO:
            st.markdown("**Plan:** ⭐ Pro")
        else:
            st.markdown("**Plan:** 🏢 Enterprise")

    with col2:
        st.markdown("**Member Since:**")
        st.markdown(user.created_at.strftime("%B %d, %Y"))

        if user.last_login_at:
            st.markdown("**Last Login:**")
            st.markdown(user.last_login_at.strftime("%Y-%m-%d %H:%M"))

    # Subscription features
    st.subheader("📋 Plan Features")

    limits = SUBSCRIPTION_LIMITS.get(user.subscription, {})

    features = [
        ("Live Trading", "live_trading", "✅" if limits.get("live_trading") else "❌"),
        ("Max Accounts", "max_accounts", str(limits.get("max_accounts", 1))),
        ("Max Strategies", "max_strategies", str(limits.get("max_strategies", 2))),
        ("Backtest Years", "backtest_years", str(limits.get("backtest_years", 1))),
        ("ML Predictions", "ml_predictions", "✅" if limits.get("ml_predictions") else "❌"),
        ("Team Workspace", "team_workspace", "✅" if limits.get("team_workspace") else "❌"),
        ("API Access", "api_requests_daily", f"{limits.get('api_requests_daily', 0):,} req/day"),
    ]

    feature_df = pd.DataFrame(features, columns=["Feature", "Key", "Value"])
    st.dataframe(feature_df[["Feature", "Value"]], use_container_width=True, hide_index=True)

    if user.subscription == SubscriptionTier.FREE:
        st.button("⬆️ Upgrade to Pro", type="primary")


def render_accounts():
    """Render multi-account management."""
    user = st.session_state.current_user
    manager = st.session_state.account_manager

    st.header("💼 My Accounts")

    # Household summary
    summary = manager.get_household_summary(user.id)
    accounts = manager.get_user_accounts(user.id)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Value",
            f"${summary.total_value:,.0f}",
            delta=f"{summary.day_pnl_pct*100:+.1f}% today" if summary.day_pnl != 0 else None,
        )
    with col2:
        st.metric("Total Cash", f"${summary.total_cash:,.0f}")
    with col3:
        st.metric("YTD Return", f"{summary.ytd_return*100:+.1f}%")
    with col4:
        st.metric("Accounts", len(accounts))

    st.divider()

    # Account list
    if accounts:
        for account in accounts:
            acc_summary = manager.get_account_summary(account.id)
            if acc_summary:
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])

                    with col1:
                        badge = "📄" if account.account_type == AccountType.PAPER else "💰"
                        st.markdown(f"**{badge} {account.name}**")
                        st.caption(f"{account.account_type.value} | {account.tax_status.value}")

                    with col2:
                        st.metric("Value", f"${acc_summary.total_value:,.0f}")

                    with col3:
                        st.metric("YTD", f"{acc_summary.ytd_return*100:+.1f}%")

                    with col4:
                        st.metric("Strategy", acc_summary.strategy_name or "None")

                    with col5:
                        st.button("⚙️", key=f"edit_{account.id}")

                    st.divider()
    else:
        st.info("No accounts yet. Create your first account below.")

    # Create account form
    with st.expander("➕ Create New Account"):
        with st.form("create_account"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Account Name")
                account_type = st.selectbox(
                    "Account Type",
                    options=[t.value for t in AccountType],
                    format_func=lambda x: x.replace("_", " ").title(),
                )

            with col2:
                initial_value = st.number_input("Initial Value", min_value=0, value=100000)
                benchmark = st.selectbox("Benchmark", ["SPY", "QQQ", "IWM", "DIA"])

            submitted = st.form_submit_button("Create Account", type="primary")

            if submitted and name:
                account, error = manager.create_account(
                    user=user,
                    name=name,
                    account_type=AccountType(account_type),
                    initial_value=initial_value,
                    benchmark=benchmark,
                )

                if account:
                    st.success(f"Account '{name}' created!")
                    st.rerun()
                else:
                    st.error(error or "Failed to create account")

    # Asset location suggestions
    if len(accounts) > 1:
        with st.expander("💡 Tax-Efficient Asset Location"):
            suggestions = manager.suggest_asset_location(user.id)

            for status, data in suggestions.items():
                if data["accounts"]:
                    st.markdown(f"**{status.replace('_', ' ').title()}**")
                    st.markdown(f"*Accounts: {', '.join(data['accounts'])}*")
                    st.markdown("Recommended assets:")
                    for asset in data["recommended_assets"]:
                        st.markdown(f"  - {asset}")
                    st.divider()


def render_workspaces():
    """Render team workspaces."""
    user = st.session_state.current_user
    manager = st.session_state.workspace_manager

    st.header("👥 Team Workspaces")

    # Check subscription
    if user.subscription != SubscriptionTier.ENTERPRISE:
        st.warning("Team workspaces are available on the Enterprise plan.")
        st.button("⬆️ Upgrade to Enterprise", type="primary")
        return

    workspaces = manager.get_user_workspaces(user.id)

    if workspaces:
        for workspace in workspaces:
            stats = manager.get_workspace_stats(workspace.id)

            with st.container():
                st.subheader(f"🏢 {workspace.name}")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Members", stats.member_count if stats else 0)
                with col2:
                    st.metric("Strategies", stats.strategy_count if stats else 0)
                with col3:
                    st.metric("Total AUM", f"${workspace.total_aum:,.0f}")
                with col4:
                    st.metric("Active Today", stats.active_today if stats else 0)

                # Activity feed
                activities = manager.get_activity_feed(workspace.id, limit=5)
                if activities:
                    st.markdown("**Recent Activity**")
                    for activity in activities:
                        time_ago = datetime.utcnow() - activity.timestamp
                        hours = time_ago.total_seconds() / 3600
                        time_str = f"{int(hours)}h ago" if hours < 24 else f"{int(hours/24)}d ago"

                        st.markdown(
                            f"├── {activity.user_name} {activity.action.replace('_', ' ')} "
                            f"\"{activity.resource_name}\" ({time_str})"
                        )

                # Leaderboard
                leaderboard = manager.get_leaderboard(workspace.id, limit=5)
                if leaderboard:
                    st.markdown("**Strategy Leaderboard (YTD)**")
                    for entry in leaderboard:
                        st.markdown(
                            f"{entry.rank}. {entry.strategy_name} "
                            f"  {entry.ytd_return*100:+.1f}%  Sharpe: {entry.sharpe_ratio:.2f}"
                        )

                st.divider()
    else:
        st.info("You're not a member of any workspace yet.")

    # Create workspace
    with st.expander("➕ Create New Workspace"):
        with st.form("create_workspace"):
            name = st.text_input("Workspace Name")
            description = st.text_area("Description")

            if st.form_submit_button("Create Workspace", type="primary"):
                if name:
                    workspace, error = manager.create_workspace(user, name, description)
                    if workspace:
                        st.success(f"Workspace '{name}' created!")
                        st.rerun()
                    else:
                        st.error(error or "Failed to create workspace")


def render_reports():
    """Render reporting section."""
    user = st.session_state.current_user
    account_manager = st.session_state.account_manager
    generator = ReportGenerator()

    st.header("📊 Reports")

    accounts = account_manager.get_user_accounts(user.id)

    if not accounts:
        st.info("Create an account first to generate reports.")
        return

    col1, col2 = st.columns(2)

    with col1:
        selected_account = st.selectbox(
            "Select Account",
            options=[a.name for a in accounts],
        )

        report_type = st.selectbox(
            "Report Type",
            ["Quarterly Performance", "Annual Summary", "Trade Activity"],
        )

    with col2:
        period_start = st.date_input("Start Date", date.today() - timedelta(days=90))
        period_end = st.date_input("End Date", date.today())

        format_type = st.selectbox("Format", ["PDF", "Excel", "HTML"])

    if st.button("📄 Generate Report", type="primary"):
        # Create sample report data
        data = ReportData(
            report_title=f"{report_type} Report",
            client_name=user.name,
            account_name=selected_account,
            period_start=period_start,
            period_end=period_end,
            metrics=PerformanceMetrics(
                period_return=0.082,
                benchmark_return=0.065,
                alpha=0.017,
                sharpe_ratio=1.45,
                max_drawdown=-0.052,
                total_trades=47,
                win_rate=0.58,
            ),
            holdings=[
                {"symbol": "AAPL", "weight": 0.12, "return": 0.15, "pnl": 1800},
                {"symbol": "MSFT", "weight": 0.10, "return": 0.08, "pnl": 960},
                {"symbol": "GOOGL", "weight": 0.08, "return": 0.12, "pnl": 1152},
            ],
        )

        report = generator.generate_quarterly_report(
            data, format_type.lower()
        )

        # Download button
        ext = {"PDF": "txt", "Excel": "csv", "HTML": "html"}[format_type]
        mime = {"PDF": "text/plain", "Excel": "text/csv", "HTML": "text/html"}[format_type]

        st.download_button(
            label=f"📥 Download {format_type}",
            data=report,
            file_name=f"report_{period_end}.{ext}",
            mime=mime,
        )

        # Preview
        if format_type == "HTML":
            st.components.v1.html(report.decode(), height=600, scrolling=True)
        else:
            st.code(report.decode()[:2000])


def render_audit():
    """Render audit log viewer."""
    user = st.session_state.current_user
    logger = st.session_state.audit_logger

    st.header("📋 Audit Log")

    # Check admin permission
    if user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        st.warning("Audit logs are only accessible to managers and admins.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        action_filter = st.selectbox(
            "Action",
            ["All", "Login", "Order", "Strategy", "Account"],
        )
    with col2:
        days = st.selectbox("Time Period", [7, 30, 90], format_func=lambda x: f"Last {x} days")
    with col3:
        status_filter = st.selectbox("Status", ["All", "Success", "Failure"])

    # Get logs
    logs = logger.get_user_activity(user.id, days=days)

    if logs:
        log_data = [
            {
                "Time": log.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Action": log.action.value,
                "Resource": f"{log.resource_type}/{log.resource_id or ''}",
                "Status": log.status,
                "IP": log.ip_address or "",
            }
            for log in logs
        ]

        df = pd.DataFrame(log_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No audit logs found for the selected period.")

    # Security events
    st.subheader("🔒 Security Events")
    security_logs = logger.get_security_events(days=7)

    if security_logs:
        for log in security_logs[:10]:
            icon = "🟢" if log.status == "success" else "🔴"
            st.markdown(
                f"{icon} **{log.action.value}** | "
                f"{log.user_email or 'Unknown'} | "
                f"{log.timestamp.strftime('%Y-%m-%d %H:%M')} | "
                f"{log.ip_address or ''}"
            )
    else:
        st.info("No security events in the last 7 days.")


def main():
    """Main application."""
    st.title("🏢 Enterprise Platform")

    if not ENTERPRISE_AVAILABLE:
        st.error("Enterprise module not available. Please check installation.")
        return

    init_session_state()

    # Check login
    if not st.session_state.is_logged_in:
        render_login()
        return

    user = st.session_state.current_user

    # Sidebar navigation
    with st.sidebar:
        st.markdown(f"**Logged in as:** {user.name}")
        st.caption(user.email)

        if st.button("🚪 Logout"):
            st.session_state.is_logged_in = False
            st.session_state.current_user = None
            st.rerun()

        st.divider()

        page = st.radio(
            "Navigation",
            options=[
                "👤 Profile",
                "💼 Accounts",
                "👥 Workspaces",
                "📊 Reports",
                "📋 Audit Log",
            ],
        )

    # Render selected page
    if page == "👤 Profile":
        render_profile()
    elif page == "💼 Accounts":
        render_accounts()
    elif page == "👥 Workspaces":
        render_workspaces()
    elif page == "📊 Reports":
        render_reports()
    elif page == "📋 Audit Log":
        render_audit()



main()
