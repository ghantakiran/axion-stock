"""PRD-108: Integration & Load Testing Framework.

Revision ID: 108
Revises: 107
"""

from alembic import op
import sqlalchemy as sa

revision = "108"
down_revision = "107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("test_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("total_tests", sa.Integer, nullable=True),
        sa.Column("passed", sa.Integer, nullable=True),
        sa.Column("failed", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "benchmark_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("suite_name", sa.String(128), nullable=False),
        sa.Column("benchmark_name", sa.String(256), nullable=False),
        sa.Column("mean_ms", sa.Float, nullable=False),
        sa.Column("p50_ms", sa.Float, nullable=True),
        sa.Column("p95_ms", sa.Float, nullable=True),
        sa.Column("p99_ms", sa.Float, nullable=True),
        sa.Column("iterations", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("benchmark_results")
    op.drop_table("test_runs")
