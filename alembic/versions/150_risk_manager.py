"""Advanced Risk Management tables.

Revision ID: 150
Revises: 149
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "150"
down_revision = "149"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Risk snapshots
    op.create_table(
        "risk_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False, index=True),
        sa.Column("gross_leverage", sa.Float),
        sa.Column("net_leverage", sa.Float),
        sa.Column("long_exposure", sa.Float),
        sa.Column("short_exposure", sa.Float),
        sa.Column("sector_concentrations_json", sa.Text),
        sa.Column("largest_position_pct", sa.Float),
        sa.Column("vix_adjusted_size_pct", sa.Float),
        sa.Column("warnings_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Circuit breaker events
    op.create_table(
        "circuit_breaker_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trip_reason", sa.Text),
        sa.Column("consecutive_losses", sa.Integer),
        sa.Column("daily_pnl", sa.Float),
        sa.Column("trip_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Kill switch events
    op.create_table(
        "kill_switch_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("equity_at_event", sa.Float),
        sa.Column("daily_pnl", sa.Float),
        sa.Column("triggered_by", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("kill_switch_events")
    op.drop_table("circuit_breaker_events")
    op.drop_table("risk_snapshots")
