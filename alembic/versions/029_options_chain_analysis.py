"""Options chain analysis tables.

Revision ID: 029
Revises: 028
Create Date: 2026-02-01

Adds:
- options_greeks: Computed Greeks snapshots
- options_chain_snapshots: Chain-level summary metrics
- options_flow: Detected flow events
- options_unusual_activity: Flagged unusual activity
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Greeks snapshots
    op.create_table(
        "options_greeks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("strike", sa.Float),
        sa.Column("expiry_days", sa.Float),
        sa.Column("option_type", sa.String(4)),
        sa.Column("delta", sa.Float),
        sa.Column("gamma", sa.Float),
        sa.Column("theta", sa.Float),
        sa.Column("vega", sa.Float),
        sa.Column("rho", sa.Float),
        sa.Column("implied_vol", sa.Float),
        sa.Column("price", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_options_greeks_symbol", "options_greeks", ["symbol"])

    # Chain snapshots
    op.create_table(
        "options_chain_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("underlying_price", sa.Float),
        sa.Column("total_call_volume", sa.Integer),
        sa.Column("total_put_volume", sa.Integer),
        sa.Column("total_call_oi", sa.Integer),
        sa.Column("total_put_oi", sa.Integer),
        sa.Column("pcr_volume", sa.Float),
        sa.Column("pcr_oi", sa.Float),
        sa.Column("max_pain_strike", sa.Float),
        sa.Column("iv_skew", sa.Float),
        sa.Column("atm_iv", sa.Float),
        sa.Column("n_contracts", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_options_chain_snapshots_symbol", "options_chain_snapshots", ["symbol"])

    # Flow events
    op.create_table(
        "options_flow",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("strike", sa.Float),
        sa.Column("expiry_days", sa.Float),
        sa.Column("option_type", sa.String(4)),
        sa.Column("flow_type", sa.String(16)),
        sa.Column("size", sa.Integer),
        sa.Column("premium", sa.Float),
        sa.Column("side", sa.String(4)),
        sa.Column("sentiment", sa.String(16)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_options_flow_symbol", "options_flow", ["symbol"])
    op.create_index("ix_options_flow_type", "options_flow", ["flow_type"])

    # Unusual activity
    op.create_table(
        "options_unusual_activity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("strike", sa.Float),
        sa.Column("expiry_days", sa.Float),
        sa.Column("option_type", sa.String(4)),
        sa.Column("volume", sa.Integer),
        sa.Column("open_interest", sa.Integer),
        sa.Column("vol_oi_ratio", sa.Float),
        sa.Column("premium", sa.Float),
        sa.Column("activity_level", sa.String(16)),
        sa.Column("score", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_options_unusual_activity_symbol", "options_unusual_activity", ["symbol"])
    op.create_index("ix_options_unusual_activity_level", "options_unusual_activity", ["activity_level"])


def downgrade() -> None:
    op.drop_table("options_unusual_activity")
    op.drop_table("options_flow")
    op.drop_table("options_chain_snapshots")
    op.drop_table("options_greeks")
