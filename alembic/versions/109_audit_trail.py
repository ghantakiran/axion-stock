"""PRD-109: Audit Trail & Event Sourcing.

Revision ID: 109
Revises: 108
"""

from alembic import op
import sqlalchemy as sa

revision = "109"
down_revision = "108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(64),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.Column("actor_id", sa.String(128), nullable=True, index=True),
        sa.Column("actor_type", sa.String(64), nullable=True),
        sa.Column("action", sa.String(256), nullable=False, index=True),
        sa.Column("resource_type", sa.String(128), nullable=True),
        sa.Column("resource_id", sa.String(256), nullable=True),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
