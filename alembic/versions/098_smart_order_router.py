"""PRD-98: Smart Order Router.

Revision ID: 098
Revises: 097
"""

from alembic import op
import sqlalchemy as sa

revision = "098"
down_revision = "097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Routing decision records
    op.create_table(
        "routing_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("strategy", sa.String(30), nullable=False),
        sa.Column("n_venues", sa.Integer(), nullable=False),
        sa.Column("dark_pool_pct", sa.Float(), nullable=True),
        sa.Column("total_estimated_cost", sa.Float(), nullable=True),
        sa.Column("splits", sa.JSON(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=True),
        sa.Column("nbbo_bid", sa.Float(), nullable=True),
        sa.Column("nbbo_ask", sa.Float(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Venue quality metrics over time
    op.create_table(
        "venue_performance_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("venue_id", sa.String(30), nullable=False, index=True),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("orders_routed", sa.Integer(), nullable=False),
        sa.Column("fill_rate", sa.Float(), nullable=True),
        sa.Column("avg_fill_time_ms", sa.Float(), nullable=True),
        sa.Column("avg_price_improvement", sa.Float(), nullable=True),
        sa.Column("net_cost", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("venue_performance_log")
    op.drop_table("routing_decisions")
