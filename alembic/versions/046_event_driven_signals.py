"""PRD-60: Event-Driven Signals.

Revision ID: 046
Revises: 045
"""

from alembic import op
import sqlalchemy as sa

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earnings quality scores
    op.create_table(
        "earnings_quality_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("quarter", sa.String(10), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("surprise_score", sa.Float(), nullable=True),
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("revenue_quality_score", sa.Float(), nullable=True),
        sa.Column("guidance_score", sa.Float(), nullable=True),
        sa.Column("beat_breadth_score", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(2), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Deal completion estimates
    op.create_table(
        "deal_completion_estimates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("target", sa.String(30), nullable=False),
        sa.Column("acquirer", sa.String(30), nullable=False),
        sa.Column("base_probability", sa.Float(), nullable=False),
        sa.Column("adjusted_probability", sa.Float(), nullable=False),
        sa.Column("regulatory_risk", sa.Float(), nullable=True),
        sa.Column("financing_risk", sa.Float(), nullable=True),
        sa.Column("antitrust_risk", sa.Float(), nullable=True),
        sa.Column("expected_days_to_close", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Corporate action impacts
    op.create_table(
        "corporate_action_impacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("expected_impact_pct", sa.Float(), nullable=False),
        sa.Column("impact_details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Event calendar analytics
    op.create_table(
        "event_calendar_analytics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("n_events", sa.Integer(), nullable=False),
        sa.Column("density_score", sa.Float(), nullable=True),
        sa.Column("high_importance_count", sa.Integer(), nullable=True),
        sa.Column("symbols_affected", sa.Integer(), nullable=True),
        sa.Column("n_clusters", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("event_calendar_analytics")
    op.drop_table("corporate_action_impacts")
    op.drop_table("deal_completion_estimates")
    op.drop_table("earnings_quality_scores")
