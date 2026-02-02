"""Fund flow analysis system tables.

Revision ID: 032
Revises: 031
Create Date: 2026-02-01

Adds:
- fund_flows: Daily fund flow records
- institutional_positions: 13F position snapshots
- sector_rotations: Sector rotation scores
- smart_money_signals: Smart money signal records
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fund flows
    op.create_table(
        "fund_flows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fund_name", sa.String(100), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("inflow", sa.Float),
        sa.Column("outflow", sa.Float),
        sa.Column("net_flow", sa.Float),
        sa.Column("aum", sa.Float),
        sa.Column("flow_pct", sa.Float),
        sa.Column("direction", sa.String(20)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_fund_flows_fund", "fund_flows", ["fund_name"])
    op.create_index("ix_fund_flows_date", "fund_flows", ["date"])

    # Institutional positions
    op.create_table(
        "institutional_positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("holder_name", sa.String(200), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("shares", sa.Float),
        sa.Column("market_value", sa.Float),
        sa.Column("ownership_pct", sa.Float),
        sa.Column("change_shares", sa.Float),
        sa.Column("change_pct", sa.Float),
        sa.Column("quarter", sa.String(10)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_institutional_positions_symbol", "institutional_positions", ["symbol"])
    op.create_index("ix_institutional_positions_holder", "institutional_positions", ["holder_name"])

    # Sector rotations
    op.create_table(
        "sector_rotations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sector", sa.String(50), nullable=False),
        sa.Column("flow_score", sa.Float),
        sa.Column("momentum_score", sa.Float),
        sa.Column("rank", sa.Integer),
        sa.Column("phase", sa.String(20)),
        sa.Column("relative_strength", sa.Float),
        sa.Column("composite_score", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sector_rotations_sector", "sector_rotations", ["sector"])

    # Smart money signals
    op.create_table(
        "smart_money_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("institutional_flow", sa.Float),
        sa.Column("retail_flow", sa.Float),
        sa.Column("smart_money_score", sa.Float),
        sa.Column("conviction", sa.Float),
        sa.Column("signal", sa.String(20)),
        sa.Column("flow_price_divergence", sa.Float),
        sa.Column("is_contrarian", sa.Boolean),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_smart_money_signals_symbol", "smart_money_signals", ["symbol"])


def downgrade() -> None:
    op.drop_table("smart_money_signals")
    op.drop_table("sector_rotations")
    op.drop_table("institutional_positions")
    op.drop_table("fund_flows")
