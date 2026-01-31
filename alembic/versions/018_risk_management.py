"""Risk management system tables.

Revision ID: 018
Revises: 017
Create Date: 2026-01-30

Adds:
- risk_snapshots: Point-in-time risk metric captures
- risk_alerts: Historical alert records
- stress_test_results: Stored stress test outputs
- risk_limits: Configurable risk limit definitions
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Risk limits
    op.create_table(
        "risk_limits",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("limit_id", sa.String(32), unique=True, nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("limit_type", sa.String(32), nullable=False),
        sa.Column("limit_value", sa.Float, nullable=False),
        sa.Column("current_value", sa.Float),
        sa.Column("severity", sa.String(16), server_default="warning"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_risk_limits_portfolio", "risk_limits", ["portfolio_id"])

    # Risk snapshots
    op.create_table(
        "risk_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("snapshot_time", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(16)),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("volatility", sa.Float),
        sa.Column("beta", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("current_drawdown", sa.Float),
        sa.Column("var_95", sa.Float),
        sa.Column("var_99", sa.Float),
        sa.Column("cvar_95", sa.Float),
        sa.Column("herfindahl_index", sa.Float),
        sa.Column("metrics_json", sa.JSON),
        sa.Column("concentration_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_risk_snapshots_portfolio_time",
        "risk_snapshots", ["portfolio_id", "snapshot_time"],
    )

    # Risk alerts
    op.create_table(
        "risk_alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alert_id", sa.String(32), unique=True, nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("metric_name", sa.String(64)),
        sa.Column("metric_value", sa.Float),
        sa.Column("threshold_value", sa.Float),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.text("false")),
        sa.Column("acknowledged_at", sa.DateTime),
        sa.Column("triggered_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_risk_alerts_portfolio", "risk_alerts", ["portfolio_id"])
    op.create_index("ix_risk_alerts_severity", "risk_alerts", ["severity"])

    # Stress test results
    op.create_table(
        "stress_test_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("result_id", sa.String(32), unique=True, nullable=False),
        sa.Column("portfolio_id", sa.String(64), nullable=False),
        sa.Column("scenario_name", sa.String(128), nullable=False),
        sa.Column("scenario_type", sa.String(16)),
        sa.Column("portfolio_impact", sa.Float),
        sa.Column("worst_position", sa.String(16)),
        sa.Column("worst_position_impact", sa.Float),
        sa.Column("positions_json", sa.JSON),
        sa.Column("sectors_json", sa.JSON),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_stress_results_portfolio", "stress_test_results", ["portfolio_id"])


def downgrade() -> None:
    op.drop_table("stress_test_results")
    op.drop_table("risk_alerts")
    op.drop_table("risk_snapshots")
    op.drop_table("risk_limits")
