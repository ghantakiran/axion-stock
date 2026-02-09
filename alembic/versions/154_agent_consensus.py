"""PRD-154: Multi-Agent Trade Consensus tables.

Revision ID: 154
Revises: 153
"""

from alembic import op
import sqlalchemy as sa

revision = "154"
down_revision = "153"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Consensus decision log
    op.create_table(
        "consensus_decisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("signal_type", sa.String(50)),
        sa.Column("direction", sa.String(10)),
        sa.Column("conviction", sa.Integer),
        sa.Column("decision", sa.String(20), nullable=False, index=True),
        sa.Column("approval_rate", sa.Float),
        sa.Column("weighted_score", sa.Float),
        sa.Column("total_votes", sa.Integer),
        sa.Column("approve_count", sa.Integer),
        sa.Column("reject_count", sa.Integer),
        sa.Column("abstain_count", sa.Integer),
        sa.Column("vetoed", sa.Boolean, default=False),
        sa.Column("veto_reason", sa.Text),
        sa.Column("risk_assessment", sa.String(20)),
        sa.Column("debated", sa.Boolean, default=False),
        sa.Column("debate_rounds", sa.Integer),
        sa.Column("votes_json", sa.Text),
        sa.Column("adjustments_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Per-agent vote history
    op.create_table(
        "consensus_agent_votes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("vote_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("decision_id", sa.String(50), nullable=False, index=True),
        sa.Column("agent_type", sa.String(50), nullable=False, index=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("reasoning", sa.Text),
        sa.Column("risk_assessment", sa.String(20)),
        sa.Column("suggested_adjustments_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("consensus_agent_votes")
    op.drop_table("consensus_decisions")
