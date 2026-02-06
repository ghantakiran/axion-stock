"""PRD-67: User Authentication & RBAC.

Revision ID: 053
Revises: 052
"""

from alembic import op
import sqlalchemy as sa

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="trader"),
        sa.Column("subscription", sa.String(20), nullable=False, server_default="free"),
        # Profile
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("preferences", sa.JSON(), nullable=True),
        # OAuth IDs
        sa.Column("google_id", sa.String(100), nullable=True),
        sa.Column("github_id", sa.String(100), nullable=True),
        sa.Column("apple_id", sa.String(100), nullable=True),
        # 2FA
        sa.Column("totp_secret", sa.String(100), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), server_default="false"),
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_verified", sa.Boolean(), server_default="false"),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )

    # User sessions
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_token_hash", sa.String(64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("device_info", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
    )

    # API keys
    op.create_table(
        "user_api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("request_count", sa.Integer(), server_default="0"),
    )

    # Audit logs
    op.create_table(
        "user_audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    # OAuth state tokens (for OAuth flow)
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("state", sa.String(64), unique=True, nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("redirect_uri", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default="false"),
    )

    # Rate limiting records
    op.create_table(
        "rate_limit_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(255), nullable=False, index=True),
        sa.Column("count", sa.Integer(), server_default="1"),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
    )

    # Password reset tokens
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default="false"),
    )

    # Email verification tokens
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default="false"),
    )

    # Indexes
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_id", "users", ["google_id"])
    op.create_index("ix_users_github_id", "users", ["github_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_api_keys_user_id", "user_api_keys", ["user_id"])
    op.create_index("ix_user_api_keys_prefix", "user_api_keys", ["key_prefix"])
    op.create_index("ix_audit_logs_user_id", "user_audit_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_id")
    op.drop_index("ix_user_api_keys_prefix")
    op.drop_index("ix_user_api_keys_user_id")
    op.drop_index("ix_user_sessions_user_id")
    op.drop_index("ix_users_github_id")
    op.drop_index("ix_users_google_id")
    op.drop_index("ix_users_email")
    op.drop_table("email_verification_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_table("rate_limit_records")
    op.drop_table("oauth_states")
    op.drop_table("user_audit_logs")
    op.drop_table("user_api_keys")
    op.drop_table("user_sessions")
    op.drop_table("users")
