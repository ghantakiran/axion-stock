"""Performance attribution system tables.

Revision ID: 016
Revises: 015
Create Date: 2026-01-30

Adds:
- attribution_reports: Stored attribution analysis results
- benchmark_definitions: Benchmark configurations
- performance_snapshots: Periodic performance captures
- tear_sheets: Generated tear sheet data
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Attribution reports
    op.create_table(
        "attribution_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.String(32), unique=True, nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("benchmark_id", sa.String(32)),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("period", sa.String(16)),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("results_json", sa.JSON),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_attr_reports_portfolio", "attribution_reports", ["portfolio_id"])
    op.create_index("ix_attr_reports_dates", "attribution_reports", ["start_date", "end_date"])

    # Benchmark definitions
    op.create_table(
        "benchmark_definitions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("benchmark_id", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("benchmark_type", sa.String(16)),
        sa.Column("components_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Performance snapshots
    op.create_table(
        "perf_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("total_return", sa.Float),
        sa.Column("annualized_return", sa.Float),
        sa.Column("volatility", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("metrics_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_perf_snapshots_portfolio_date",
        "perf_snapshots", ["portfolio_id", "snapshot_date"],
    )

    # Tear sheets
    op.create_table(
        "tear_sheets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.String(32), unique=True, nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("period", sa.String(16)),
        sa.Column("metrics_json", sa.JSON),
        sa.Column("benchmark_json", sa.JSON),
        sa.Column("brinson_json", sa.JSON),
        sa.Column("factor_json", sa.JSON),
        sa.Column("monthly_json", sa.JSON),
        sa.Column("drawdowns_json", sa.JSON),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_tear_sheets_portfolio", "tear_sheets", ["portfolio_id"])


def downgrade() -> None:
    op.drop_table("tear_sheets")
    op.drop_table("perf_snapshots")
    op.drop_table("benchmark_definitions")
    op.drop_table("attribution_reports")
