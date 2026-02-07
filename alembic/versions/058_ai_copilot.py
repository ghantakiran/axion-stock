"""PRD-58: AI Trading Copilot.

Revision ID: 058
Revises: 057
"""

from alembic import op
import sqlalchemy as sa

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Copilot sessions
    op.create_table(
        "copilot_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("session_type", sa.String(30), nullable=True),  # chat, analysis, portfolio_review
        # Context
        sa.Column("context", sa.JSON(), nullable=True),  # Portfolio snapshot, market context
        sa.Column("active_symbol", sa.String(20), nullable=True),
        # Stats
        sa.Column("message_count", sa.Integer(), server_default="0"),
        sa.Column("ideas_generated", sa.Integer(), server_default="0"),
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        # Timestamps
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Copilot messages
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("copilot_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.String(36), nullable=False),
        # Content
        sa.Column("role", sa.String(20), nullable=False),  # user, assistant, system
        sa.Column("content", sa.Text(), nullable=False),
        # Metadata
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("extracted_symbols", sa.JSON(), nullable=True),  # Symbols mentioned
        sa.Column("extracted_actions", sa.JSON(), nullable=True),  # Actions suggested
        sa.Column("confidence_score", sa.Float(), nullable=True),
        # Feedback
        sa.Column("user_rating", sa.Integer(), nullable=True),  # 1-5
        sa.Column("feedback", sa.Text(), nullable=True),
        # Timestamp
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )

    # Copilot preferences
    op.create_table(
        "copilot_preferences",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        # Risk & Style
        sa.Column("risk_tolerance", sa.String(20), server_default="'moderate'"),  # conservative, moderate, aggressive
        sa.Column("investment_style", sa.String(30), server_default="'balanced'"),  # value, growth, momentum, income, balanced
        sa.Column("time_horizon", sa.String(20), server_default="'medium'"),  # short, medium, long
        # Sectors
        sa.Column("preferred_sectors", sa.JSON(), nullable=True),
        sa.Column("excluded_sectors", sa.JSON(), nullable=True),
        # Response style
        sa.Column("response_style", sa.String(20), server_default="'balanced'"),  # concise, balanced, detailed
        sa.Column("include_technicals", sa.Boolean(), server_default="true"),
        sa.Column("include_fundamentals", sa.Boolean(), server_default="true"),
        sa.Column("include_sentiment", sa.Boolean(), server_default="true"),
        # Constraints
        sa.Column("max_position_size_pct", sa.Float(), nullable=True),
        sa.Column("min_market_cap", sa.BigInteger(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Saved trade ideas
    op.create_table(
        "copilot_saved_ideas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("message_id", sa.String(36), nullable=True),
        # Idea details
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),  # buy, sell, hold
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        # Targets
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("time_horizon", sa.String(20), nullable=True),
        # Tracking
        sa.Column("status", sa.String(20), server_default="'active'"),  # active, executed, expired, cancelled
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("execution_price", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=True),  # win, loss, breakeven
        sa.Column("outcome_pct", sa.Float(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )

    # Indexes
    op.create_index("ix_copilot_sessions_user_id", "copilot_sessions", ["user_id"])
    op.create_index("ix_copilot_sessions_started_at", "copilot_sessions", ["started_at"])
    op.create_index("ix_copilot_messages_session_id", "copilot_messages", ["session_id"])
    op.create_index("ix_copilot_messages_timestamp", "copilot_messages", ["timestamp"])
    op.create_index("ix_copilot_saved_ideas_user_id", "copilot_saved_ideas", ["user_id"])
    op.create_index("ix_copilot_saved_ideas_symbol", "copilot_saved_ideas", ["symbol"])
    op.create_index("ix_copilot_saved_ideas_status", "copilot_saved_ideas", ["status"])


def downgrade() -> None:
    op.drop_index("ix_copilot_saved_ideas_status")
    op.drop_index("ix_copilot_saved_ideas_symbol")
    op.drop_index("ix_copilot_saved_ideas_user_id")
    op.drop_index("ix_copilot_messages_timestamp")
    op.drop_index("ix_copilot_messages_session_id")
    op.drop_index("ix_copilot_sessions_started_at")
    op.drop_index("ix_copilot_sessions_user_id")
    op.drop_table("copilot_saved_ideas")
    op.drop_table("copilot_preferences")
    op.drop_table("copilot_messages")
    op.drop_table("copilot_sessions")
