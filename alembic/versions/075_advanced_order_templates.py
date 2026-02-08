"""PRD-75: Advanced Order Type Templates.

Revision ID: 075
Revises: 074
"""

from alembic import op
import sqlalchemy as sa

revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Saved order templates
    op.create_table(
        "order_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_type", sa.String(30), nullable=False),
        sa.Column("side", sa.String(10), nullable=True),
        sa.Column("time_in_force", sa.String(10), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("usage_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Bracket order groups (linking parent + take-profit + stop-loss)
    op.create_table(
        "bracket_order_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("parent_order_id", sa.String(36), nullable=False),
        sa.Column("take_profit_order_id", sa.String(36), nullable=True),
        sa.Column("stop_loss_order_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bracket_order_groups")
    op.drop_table("order_templates")
