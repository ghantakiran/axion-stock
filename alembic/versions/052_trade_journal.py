"""PRD-66: Trade Journal Dashboard.

Revision ID: 052
Revises: 051
"""

from alembic import op
import sqlalchemy as sa

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trading strategies - user-defined strategies with rules
    op.create_table(
        "trading_strategies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("entry_rules", sa.JSON(), nullable=True),
        sa.Column("exit_rules", sa.JSON(), nullable=True),
        sa.Column("max_risk_per_trade", sa.Float(), nullable=True),
        sa.Column("target_risk_reward", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Trade setups - categorized patterns/setups
    op.create_table(
        "trade_setups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("setup_id", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),  # breakout, pullback, reversal, etc.
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Journal entries - extended trade data with emotions, setup, notes
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.String(50), unique=True, nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        # Direction & Type
        sa.Column("direction", sa.String(20), nullable=False),  # long, short
        sa.Column("trade_type", sa.String(30), nullable=True),  # swing, day, scalp, position
        # Entry
        sa.Column("entry_date", sa.DateTime(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("entry_quantity", sa.Float(), nullable=False),
        sa.Column("entry_reason", sa.Text(), nullable=True),
        # Exit
        sa.Column("exit_date", sa.DateTime(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.Text(), nullable=True),
        # P&L
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("realized_pnl_pct", sa.Float(), nullable=True),
        sa.Column("fees", sa.Float(), nullable=True),
        # Setup & Strategy (foreign key references)
        sa.Column("setup_id", sa.String(50), nullable=True),
        sa.Column("strategy_id", sa.String(50), nullable=True),
        sa.Column("timeframe", sa.String(20), nullable=True),  # 1m, 5m, 1h, 1d
        # Tags
        sa.Column("tags", sa.JSON(), nullable=True),
        # Notes
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lessons_learned", sa.Text(), nullable=True),
        # Emotions
        sa.Column("pre_trade_emotion", sa.String(30), nullable=True),
        sa.Column("during_trade_emotion", sa.String(30), nullable=True),
        sa.Column("post_trade_emotion", sa.String(30), nullable=True),
        # Screenshots
        sa.Column("screenshots", sa.JSON(), nullable=True),
        # Risk management
        sa.Column("initial_stop", sa.Float(), nullable=True),
        sa.Column("initial_target", sa.Float(), nullable=True),
        sa.Column("risk_reward_planned", sa.Float(), nullable=True),
        sa.Column("risk_reward_actual", sa.Float(), nullable=True),
        # Metadata
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Daily reviews
    op.create_table(
        "daily_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_date", sa.Date(), unique=True, nullable=False),
        # Summary
        sa.Column("trades_taken", sa.Integer(), nullable=True),
        sa.Column("gross_pnl", sa.Float(), nullable=True),
        sa.Column("net_pnl", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        # Self-assessment
        sa.Column("followed_plan", sa.Boolean(), nullable=True),
        sa.Column("mistakes_made", sa.JSON(), nullable=True),
        sa.Column("did_well", sa.JSON(), nullable=True),
        # Goals
        sa.Column("tomorrow_focus", sa.Text(), nullable=True),
        # Rating
        sa.Column("overall_rating", sa.Integer(), nullable=True),  # 1-5
        # Notes
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Weekly/monthly reviews
    op.create_table(
        "periodic_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_type", sa.String(20), nullable=False),  # weekly, monthly
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        # Performance
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("net_pnl", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        # Analysis
        sa.Column("best_setups", sa.JSON(), nullable=True),
        sa.Column("worst_setups", sa.JSON(), nullable=True),
        sa.Column("key_learnings", sa.JSON(), nullable=True),
        sa.Column("action_items", sa.JSON(), nullable=True),
        sa.Column("strategy_adjustments", sa.Text(), nullable=True),
        # Goals
        sa.Column("goals_achieved", sa.JSON(), nullable=True),
        sa.Column("next_period_goals", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes
    op.create_index("ix_journal_entries_symbol", "journal_entries", ["symbol"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_setup", "journal_entries", ["setup_id"])
    op.create_index("ix_journal_entries_strategy", "journal_entries", ["strategy_id"])
    op.create_index("ix_daily_reviews_date", "daily_reviews", ["review_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_reviews_date")
    op.drop_index("ix_journal_entries_strategy")
    op.drop_index("ix_journal_entries_setup")
    op.drop_index("ix_journal_entries_entry_date")
    op.drop_index("ix_journal_entries_symbol")
    op.drop_table("periodic_reviews")
    op.drop_table("daily_reviews")
    op.drop_table("journal_entries")
    op.drop_table("trade_setups")
    op.drop_table("trading_strategies")
