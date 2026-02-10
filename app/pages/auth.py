"""Authentication Dashboard - PRD-67.

Comprehensive authentication interface with:
- Login/Registration
- OAuth social login
- Two-factor authentication (2FA)
- Profile management
- API key management
- Session management
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Authentication", page_icon="🔐", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()


# Try to import auth modules
try:
    from src.enterprise.auth import AuthService, PasswordHasher, TOTPManager
    from src.enterprise.config import UserRole, SubscriptionTier, ROLE_PERMISSIONS
    from src.enterprise.models import User, Session, APIKey
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False


def init_session_state():
    """Initialize session state."""
    if "auth_service" not in st.session_state:
        if AUTH_AVAILABLE:
            st.session_state.auth_service = AuthService()
        else:
            st.session_state.auth_service = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False
    if "session" not in st.session_state:
        st.session_state.session = None
    if "totp_setup_secret" not in st.session_state:
        st.session_state.totp_setup_secret = None
    if "demo_users" not in st.session_state:
        st.session_state.demo_users = create_demo_users()
    if "demo_sessions" not in st.session_state:
        st.session_state.demo_sessions = []
    if "demo_api_keys" not in st.session_state:
        st.session_state.demo_api_keys = []


def create_demo_users():
    """Create demo users."""
    return {
        "demo@axion.ai": {
            "id": "user-001",
            "email": "demo@axion.ai",
            "name": "Demo User",
            "password": "Demo123!",  # In real app, this would be hashed
            "role": "trader",
            "subscription": "pro",
            "totp_enabled": False,
            "totp_secret": None,
            "is_verified": True,
            "created_at": datetime(2025, 1, 15),
            "last_login_at": datetime.now() - timedelta(hours=2),
        },
        "admin@axion.ai": {
            "id": "user-002",
            "email": "admin@axion.ai",
            "name": "Admin User",
            "password": "Admin123!",
            "role": "admin",
            "subscription": "enterprise",
            "totp_enabled": True,
            "totp_secret": "JBSWY3DPEHPK3PXP",
            "is_verified": True,
            "created_at": datetime(2024, 6, 1),
            "last_login_at": datetime.now() - timedelta(days=1),
        },
    }


def demo_login(email: str, password: str, totp_code: str = None) -> tuple:
    """Demo login function."""
    user = st.session_state.demo_users.get(email.lower())
    if not user:
        return None, "Invalid email or password"

    if user["password"] != password:
        return None, "Invalid email or password"

    if user["totp_enabled"]:
        if not totp_code:
            return None, "2FA code required"
        # In demo, accept any 6-digit code
        if len(totp_code) != 6 or not totp_code.isdigit():
            return None, "Invalid 2FA code"

    # Create session
    session = {
        "id": f"session-{len(st.session_state.demo_sessions)+1}",
        "user_id": user["id"],
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(days=30),
        "ip_address": "127.0.0.1",
        "user_agent": "Streamlit Demo",
        "is_active": True,
    }
    st.session_state.demo_sessions.append(session)

    user["last_login_at"] = datetime.now()
    return user, None


def demo_register(email: str, password: str, name: str) -> tuple:
    """Demo registration function."""
    if email.lower() in st.session_state.demo_users:
        return None, "Email already registered"

    if len(password) < 8:
        return None, "Password must be at least 8 characters"

    user = {
        "id": f"user-{len(st.session_state.demo_users)+1:03d}",
        "email": email.lower(),
        "name": name,
        "password": password,
        "role": "trader",
        "subscription": "free",
        "totp_enabled": False,
        "totp_secret": None,
        "is_verified": False,
        "created_at": datetime.now(),
        "last_login_at": None,
    }
    st.session_state.demo_users[email.lower()] = user
    return user, None


def render_login_form():
    """Render login form."""
    st.subheader("Sign In")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")

        # Check if user has 2FA enabled
        show_totp = False
        if email.lower() in st.session_state.demo_users:
            if st.session_state.demo_users[email.lower()].get("totp_enabled"):
                show_totp = True

        totp_code = None
        if show_totp:
            totp_code = st.text_input("2FA Code", max_chars=6, placeholder="123456")

        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
        with col2:
            st.form_submit_button("Forgot Password?", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please enter email and password")
            else:
                user, error = demo_login(email, password, totp_code)
                if error:
                    st.error(error)
                else:
                    st.session_state.current_user = user
                    st.session_state.is_logged_in = True
                    st.success(f"Welcome back, {user['name']}!")
                    st.rerun()

    st.markdown("---")
    st.markdown("#### Or sign in with")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔵 Google", use_container_width=True):
            st.info("Google OAuth would redirect here")
    with col2:
        if st.button("⚫ GitHub", use_container_width=True):
            st.info("GitHub OAuth would redirect here")
    with col3:
        if st.button("🍎 Apple", use_container_width=True):
            st.info("Apple Sign In would redirect here")


def render_register_form():
    """Render registration form."""
    st.subheader("Create Account")

    with st.form("register_form"):
        name = st.text_input("Full Name", placeholder="John Doe")
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", help="Min 8 chars, 1 uppercase, 1 number")
        confirm_password = st.text_input("Confirm Password", type="password")

        agree = st.checkbox("I agree to the Terms of Service and Privacy Policy")

        submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)

        if submitted:
            if not name or not email or not password:
                st.error("Please fill all fields")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif not agree:
                st.error("Please agree to the terms")
            else:
                user, error = demo_register(email, password, name)
                if error:
                    st.error(error)
                else:
                    st.success("Account created! Please sign in.")
                    st.balloons()


def render_profile_settings():
    """Render profile settings."""
    user = st.session_state.current_user

    st.subheader("Profile Settings")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### Avatar")
        st.image("https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&s=200", width=150)
        st.button("Change Avatar", use_container_width=True)

    with col2:
        with st.form("profile_form"):
            name = st.text_input("Full Name", value=user.get("name", ""))
            email = st.text_input("Email", value=user.get("email", ""), disabled=True)
            timezone = st.selectbox(
                "Timezone",
                ["UTC", "America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London", "Asia/Tokyo"],
                index=0,
            )

            if st.form_submit_button("Save Changes", type="primary"):
                user["name"] = name
                st.success("Profile updated!")


def render_security_settings():
    """Render security settings."""
    user = st.session_state.current_user

    st.subheader("Security Settings")

    # Password change
    st.markdown("#### Change Password")
    with st.form("password_form"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Update Password"):
            if current_password != user.get("password"):
                st.error("Current password is incorrect")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters")
            else:
                user["password"] = new_password
                st.success("Password updated!")

    st.markdown("---")

    # 2FA
    st.markdown("#### Two-Factor Authentication (2FA)")

    if user.get("totp_enabled"):
        st.success("✅ 2FA is enabled")
        if st.button("Disable 2FA", type="secondary"):
            user["totp_enabled"] = False
            user["totp_secret"] = None
            st.warning("2FA has been disabled")
            st.rerun()
    else:
        st.warning("⚠️ 2FA is not enabled")
        st.info("Add an extra layer of security by enabling 2FA")

        if st.button("Enable 2FA", type="primary"):
            # Generate secret
            import secrets
            import base64
            secret = base64.b32encode(secrets.token_bytes(20)).decode()
            st.session_state.totp_setup_secret = secret

        if st.session_state.totp_setup_secret:
            st.markdown("#### Setup 2FA")
            st.code(st.session_state.totp_setup_secret, language=None)
            st.info("Enter this secret in your authenticator app (Google Authenticator, Authy, etc.)")

            with st.form("verify_totp"):
                code = st.text_input("Enter 6-digit code from app", max_chars=6)
                if st.form_submit_button("Verify and Enable"):
                    if len(code) == 6 and code.isdigit():
                        user["totp_enabled"] = True
                        user["totp_secret"] = st.session_state.totp_setup_secret
                        st.session_state.totp_setup_secret = None
                        st.success("2FA enabled successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid code")


def render_api_keys():
    """Render API key management."""
    user = st.session_state.current_user

    st.subheader("API Keys")

    st.info("API keys allow programmatic access to Axion. Keep them secret!")

    # Create new key
    with st.expander("Create New API Key"):
        with st.form("create_api_key"):
            key_name = st.text_input("Key Name", placeholder="My Trading Bot")
            scopes = st.multiselect(
                "Scopes",
                ["read", "write", "trade", "admin"],
                default=["read"],
            )
            expires = st.selectbox("Expires", ["Never", "30 days", "90 days", "1 year"])

            if st.form_submit_button("Create Key", type="primary"):
                if not key_name:
                    st.error("Please enter a key name")
                else:
                    import secrets
                    raw_key = f"axn_{secrets.token_urlsafe(32)}"
                    api_key = {
                        "id": f"key-{len(st.session_state.demo_api_keys)+1}",
                        "user_id": user["id"],
                        "name": key_name,
                        "key_prefix": raw_key[:12],
                        "scopes": scopes,
                        "created_at": datetime.now(),
                        "last_used_at": None,
                        "request_count": 0,
                    }
                    st.session_state.demo_api_keys.append(api_key)

                    st.success("API Key created!")
                    st.warning("Copy this key now. You won't be able to see it again!")
                    st.code(raw_key, language=None)

    # List existing keys
    user_keys = [k for k in st.session_state.demo_api_keys if k["user_id"] == user["id"]]

    if user_keys:
        st.markdown("#### Your API Keys")
        for key in user_keys:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                st.text(f"{key['name']} ({key['key_prefix']}...)")
            with col2:
                st.text(f"Scopes: {', '.join(key['scopes'])}")
            with col3:
                st.text(f"Requests: {key['request_count']}")
            with col4:
                if st.button("🗑️", key=f"del_{key['id']}"):
                    st.session_state.demo_api_keys.remove(key)
                    st.rerun()
    else:
        st.info("No API keys yet. Create one above.")


def render_sessions():
    """Render session management."""
    user = st.session_state.current_user

    st.subheader("Active Sessions")

    user_sessions = [s for s in st.session_state.demo_sessions if s["user_id"] == user["id"] and s["is_active"]]

    if user_sessions:
        for session in user_sessions:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                is_current = session == st.session_state.demo_sessions[-1]
                label = "🟢 Current Session" if is_current else f"Session {session['id']}"
                st.text(label)
            with col2:
                st.text(f"Created: {session['created_at'].strftime('%Y-%m-%d %H:%M')}")
            with col3:
                if not is_current:
                    if st.button("Revoke", key=f"revoke_{session['id']}"):
                        session["is_active"] = False
                        st.success("Session revoked")
                        st.rerun()

        st.markdown("---")
        if st.button("Revoke All Other Sessions", type="secondary"):
            current = st.session_state.demo_sessions[-1] if st.session_state.demo_sessions else None
            for session in user_sessions:
                if session != current:
                    session["is_active"] = False
            st.success("All other sessions revoked")
            st.rerun()
    else:
        st.info("No other active sessions")


def render_subscription():
    """Render subscription info."""
    user = st.session_state.current_user

    st.subheader("Subscription")

    subscription = user.get("subscription", "free")

    plans = {
        "free": {"name": "Free", "price": "$0/mo", "color": "#888"},
        "pro": {"name": "Pro", "price": "$29/mo", "color": "#4CAF50"},
        "enterprise": {"name": "Enterprise", "price": "$99/mo", "color": "#2196F3"},
    }

    current_plan = plans.get(subscription, plans["free"])

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {current_plan['color']}22, {current_plan['color']}44);
                padding: 20px; border-radius: 10px; border-left: 4px solid {current_plan['color']};">
        <h3 style="margin: 0; color: {current_plan['color']};">{current_plan['name']} Plan</h3>
        <p style="margin: 5px 0; font-size: 24px; font-weight: bold;">{current_plan['price']}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Feature comparison
    features = [
        ("Live Trading", "❌", "✅", "✅"),
        ("Max Accounts", "1 paper", "3", "Unlimited"),
        ("Strategies", "2", "Unlimited", "Unlimited"),
        ("Backtest History", "1 year", "10 years", "20 years"),
        ("ML Predictions", "❌", "✅", "✅"),
        ("API Access", "❌", "1,000/day", "Unlimited"),
        ("Team Workspace", "❌", "❌", "✅"),
        ("Priority Support", "❌", "Email", "Dedicated"),
    ]

    df = pd.DataFrame(features, columns=["Feature", "Free", "Pro", "Enterprise"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    if subscription == "free":
        if st.button("Upgrade to Pro", type="primary", use_container_width=True):
            st.info("Stripe checkout would open here")
    elif subscription == "pro":
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Upgrade to Enterprise", type="primary", use_container_width=True):
                st.info("Stripe checkout would open here")
        with col2:
            if st.button("Manage Subscription", use_container_width=True):
                st.info("Stripe customer portal would open here")


def render_role_permissions():
    """Render role and permissions info."""
    user = st.session_state.current_user

    st.subheader("Role & Permissions")

    role = user.get("role", "trader")
    role_display = {
        "viewer": ("👁️ Viewer", "View-only access to portfolios and reports"),
        "trader": ("📈 Trader", "Execute trades and manage orders"),
        "manager": ("👔 Manager", "Create strategies and manage accounts"),
        "admin": ("🔑 Admin", "Full administrative access"),
    }

    info = role_display.get(role, ("Unknown", ""))

    st.markdown(f"""
    <div style="background: #f0f2f6; padding: 20px; border-radius: 10px;">
        <h3 style="margin: 0;">{info[0]}</h3>
        <p style="margin: 5px 0; color: #666;">{info[1]}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Your Permissions")

    all_permissions = {
        "viewer": ["view_portfolios", "view_reports", "view_dashboards", "view_strategies"],
        "trader": ["view_portfolios", "view_reports", "view_dashboards", "view_strategies",
                   "execute_trades", "rebalance_portfolio", "manage_orders"],
        "manager": ["view_portfolios", "view_reports", "view_dashboards", "view_strategies",
                    "execute_trades", "rebalance_portfolio", "manage_orders",
                    "create_strategies", "manage_accounts", "invite_users"],
        "admin": ["view_portfolios", "view_reports", "view_dashboards", "view_strategies",
                  "execute_trades", "rebalance_portfolio", "manage_orders",
                  "create_strategies", "manage_accounts", "invite_users",
                  "manage_users", "manage_billing", "manage_compliance", "view_audit_logs"],
    }

    perms = all_permissions.get(role, [])
    cols = st.columns(3)
    for i, perm in enumerate(perms):
        with cols[i % 3]:
            st.markdown(f"✅ {perm.replace('_', ' ').title()}")


def render_logged_in_view():
    """Render view for logged-in users."""
    user = st.session_state.current_user

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"👤 {user.get('name', 'User')}")
        st.caption(f"{user.get('email')} • {user.get('role', 'trader').title()} • {user.get('subscription', 'free').title()}")
    with col2:
        if st.button("Sign Out", type="secondary"):
            st.session_state.current_user = None
            st.session_state.is_logged_in = False
            st.rerun()

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "👤 Profile",
        "🔒 Security",
        "🔑 API Keys",
        "📱 Sessions",
        "💳 Subscription",
        "🛡️ Permissions",
    ])

    with tab1:
        render_profile_settings()

    with tab2:
        render_security_settings()

    with tab3:
        render_api_keys()

    with tab4:
        render_sessions()

    with tab5:
        render_subscription()

    with tab6:
        render_role_permissions()


def render_logged_out_view():
    """Render view for logged-out users."""
    st.title("🔐 Authentication")

    tab1, tab2 = st.tabs(["Sign In", "Create Account"])

    with tab1:
        render_login_form()

    with tab2:
        render_register_form()

    # Demo credentials
    st.sidebar.markdown("### Demo Credentials")
    st.sidebar.code("Email: demo@axion.ai\nPassword: Demo123!")
    st.sidebar.code("Email: admin@axion.ai\nPassword: Admin123!\n2FA: any 6 digits")


def main():
    init_session_state()

    if st.session_state.is_logged_in and st.session_state.current_user:
        render_logged_in_view()
    else:
        render_logged_out_view()



main()
