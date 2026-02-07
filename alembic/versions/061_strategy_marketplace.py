"""PRD-61: Strategy Marketplace.

Revision ID: 061
Revises: 060
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa


revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # marketplace_strategies - Published trading strategies
    op.create_table(
        "marketplace_strategies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("creator_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("short_description", sa.String(200), nullable=True),
        sa.Column("category", sa.String(30), nullable=False, index=True),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("asset_classes", sa.Text(), nullable=True),  # JSON array
        sa.Column("trading_style", sa.String(30), nullable=True),
        sa.Column("time_horizon", sa.String(20), nullable=True),
        sa.Column("min_capital", sa.Float(), default=1000),
        sa.Column("max_positions", sa.Integer(), default=10),
        # Pricing
        sa.Column("pricing_model", sa.String(20), nullable=False),  # free, subscription, performance, hybrid
        sa.Column("monthly_price", sa.Float(), default=0),
        sa.Column("performance_fee_pct", sa.Float(), default=0),
        # Visibility
        sa.Column("is_published", sa.Boolean(), default=False, index=True),
        sa.Column("is_featured", sa.Boolean(), default=False),
        sa.Column("is_verified", sa.Boolean(), default=False),
        # Stats (denormalized for performance)
        sa.Column("subscriber_count", sa.Integer(), default=0),
        sa.Column("avg_rating", sa.Float(), default=0),
        sa.Column("review_count", sa.Integer(), default=0),
        sa.Column("total_return_pct", sa.Float(), default=0),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )

    # marketplace_strategy_versions - Version history
    op.create_table(
        "marketplace_strategy_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("marketplace_strategies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("change_notes", sa.Text(), nullable=True),
        sa.Column("parameters", sa.Text(), nullable=True),  # JSON (encrypted)
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # marketplace_subscriptions - Strategy subscriptions
    op.create_table(
        "marketplace_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("marketplace_strategies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscriber_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscription_type", sa.String(20), nullable=False),  # signals, auto_trade
        sa.Column("auto_trade_enabled", sa.Boolean(), default=False),
        sa.Column("position_size_pct", sa.Float(), default=100),
        sa.Column("max_position_value", sa.Float(), nullable=True),
        sa.Column("risk_multiplier", sa.Float(), default=1.0),
        # Billing
        sa.Column("billing_cycle", sa.String(20), default="monthly"),
        sa.Column("next_billing_at", sa.DateTime(), nullable=True),
        sa.Column("total_paid", sa.Float(), default=0),
        # Status
        sa.Column("status", sa.String(20), nullable=False, default="active", index=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("strategy_id", "subscriber_id", name="uq_marketplace_sub_strategy_user"),
    )

    # marketplace_performance - Daily performance snapshots
    op.create_table(
        "marketplace_performance",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("marketplace_strategies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        # Returns
        sa.Column("daily_return_pct", sa.Float(), default=0),
        sa.Column("cumulative_return_pct", sa.Float(), default=0),
        sa.Column("benchmark_return_pct", sa.Float(), default=0),
        # Risk metrics
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("sortino_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), default=0),
        sa.Column("current_drawdown_pct", sa.Float(), default=0),
        sa.Column("volatility_pct", sa.Float(), nullable=True),
        # Trade stats
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("avg_win_pct", sa.Float(), nullable=True),
        sa.Column("avg_loss_pct", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), default=0),
        # Position info
        sa.Column("open_positions", sa.Integer(), default=0),
        sa.Column("portfolio_value", sa.Float(), nullable=True),
        sa.UniqueConstraint("strategy_id", "date", name="uq_marketplace_perf_strategy_date"),
    )

    # marketplace_reviews - User reviews
    op.create_table(
        "marketplace_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("strategy_id", sa.String(36), sa.ForeignKey("marketplace_strategies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),  # 1-5
        sa.Column("title", sa.String(100), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        # Verification
        sa.Column("is_verified_subscriber", sa.Boolean(), default=False),
        sa.Column("subscription_days", sa.Integer(), nullable=True),
        sa.Column("subscriber_return_pct", sa.Float(), nullable=True),
        # Moderation
        sa.Column("is_approved", sa.Boolean(), default=True),
        sa.Column("is_featured", sa.Boolean(), default=False),
        # Creator response
        sa.Column("creator_response", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # marketplace_payouts - Creator revenue payouts
    op.create_table(
        "marketplace_payouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("creator_id", sa.String(36), nullable=False, index=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        # Amounts
        sa.Column("gross_revenue", sa.Float(), default=0),
        sa.Column("platform_fee", sa.Float(), default=0),
        sa.Column("net_payout", sa.Float(), default=0),
        # Breakdown
        sa.Column("subscription_revenue", sa.Float(), default=0),
        sa.Column("performance_revenue", sa.Float(), default=0),
        sa.Column("subscriber_count", sa.Integer(), default=0),
        # Status
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("payment_method", sa.String(30), nullable=True),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("marketplace_payouts")
    op.drop_table("marketplace_reviews")
    op.drop_table("marketplace_performance")
    op.drop_table("marketplace_subscriptions")
    op.drop_table("marketplace_strategy_versions")
    op.drop_table("marketplace_strategies")
