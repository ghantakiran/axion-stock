"""PRD-102: Resilience Patterns.

Revision ID: 102
Revises: 101
"""

from alembic import op
import sqlalchemy as sa

revision = "102"
down_revision = "101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Circuit breaker state history
    op.create_table(
        "circuit_breaker_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("breaker_name", sa.String(100), nullable=False, index=True),
        sa.Column("previous_state", sa.String(20), nullable=False),
        sa.Column("new_state", sa.String(20), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, default=0),
        sa.Column("success_count", sa.Integer(), nullable=False, default=0),
        sa.Column("total_calls", sa.Integer(), nullable=False, default=0),
        sa.Column("rejected_calls", sa.Integer(), nullable=False, default=0),
        sa.Column("trigger_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Rate limiter activity log
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_key", sa.String(100), nullable=False, index=True),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("tokens_remaining", sa.Float(), nullable=True),
        sa.Column("endpoint", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Bulkhead usage snapshots
    op.create_table(
        "bulkhead_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("bulkhead_name", sa.String(100), nullable=False, index=True),
        sa.Column("max_concurrent", sa.Integer(), nullable=False),
        sa.Column("active_count", sa.Integer(), nullable=False),
        sa.Column("total_accepted", sa.Integer(), nullable=False, default=0),
        sa.Column("total_rejected", sa.Integer(), nullable=False, default=0),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("bulkhead_snapshots")
    op.drop_table("rate_limit_events")
    op.drop_table("circuit_breaker_events")
