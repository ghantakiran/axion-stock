"""PRD-117: Performance Profiling & Query Optimization.

Revision ID: 117
Revises: 116
"""

from alembic import op
import sqlalchemy as sa

revision = "117"
down_revision = "116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Query profile fingerprints
    op.create_table(
        "query_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("query_template", sa.Text(), nullable=False),
        sa.Column("call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_duration_ms", sa.Float(), nullable=True),
        sa.Column("p95_ms", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="normal", index=True),
        sa.Column("first_seen", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Index recommendations
    op.create_table(
        "index_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recommendation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("table_name", sa.String(128), nullable=False, index=True),
        sa.Column("columns", sa.Text(), nullable=False),
        sa.Column("index_type", sa.String(20), nullable=False, server_default="btree"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("impact", sa.String(20), nullable=True, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="recommended", index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("index_recommendations")
    op.drop_table("query_profiles")
