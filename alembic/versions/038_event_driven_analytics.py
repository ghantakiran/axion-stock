"""Event-driven analytics tables.

Revision ID: 038
Revises: 037
Create Date: 2026-02-02

Adds:
- earnings_events: Earnings report records
- merger_events: M&A deal records
- corporate_actions: Corporate action records
- event_signals: Event-driven signal records
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earnings events
    op.create_table(
        "earnings_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("fiscal_quarter", sa.String(10)),
        sa.Column("eps_estimate", sa.Float),
        sa.Column("eps_actual", sa.Float),
        sa.Column("revenue_estimate", sa.Float),
        sa.Column("revenue_actual", sa.Float),
        sa.Column("result", sa.String(10)),
        sa.Column("pre_drift", sa.Float),
        sa.Column("post_drift", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_earnings_events_symbol", "earnings_events", ["symbol"])

    # Merger events
    op.create_table(
        "merger_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("acquirer", sa.String(16), nullable=False),
        sa.Column("target", sa.String(16), nullable=False),
        sa.Column("announce_date", sa.Date),
        sa.Column("deal_value", sa.Float),
        sa.Column("offer_price", sa.Float),
        sa.Column("premium", sa.Float),
        sa.Column("probability", sa.Float),
        sa.Column("status", sa.String(20)),
        sa.Column("expected_close", sa.Date),
        sa.Column("is_cash", sa.Boolean),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_merger_events_target", "merger_events", ["target"])

    # Corporate actions
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("announce_date", sa.Date),
        sa.Column("effective_date", sa.Date),
        sa.Column("amount", sa.Float),
        sa.Column("details_json", sa.Text),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_corporate_actions_symbol", "corporate_actions", ["symbol"])

    # Event signals
    op.create_table(
        "event_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(20)),
        sa.Column("strength", sa.String(20)),
        sa.Column("direction", sa.String(10)),
        sa.Column("score", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("description", sa.Text),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_event_signals_symbol", "event_signals", ["symbol"])


def downgrade() -> None:
    op.drop_table("event_signals")
    op.drop_table("corporate_actions")
    op.drop_table("merger_events")
    op.drop_table("earnings_events")
