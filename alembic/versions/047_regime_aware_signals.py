"""PRD-61: Regime-Aware Signals.

Revision ID: 047
Revises: 046
"""

from alembic import op
import sqlalchemy as sa

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adapted signal snapshots
    op.create_table(
        "adapted_signal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=True),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("regime_confidence", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("n_signals", sa.Integer(), nullable=True),
        sa.Column("n_amplified", sa.Integer(), nullable=True),
        sa.Column("n_suppressed", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Dynamic threshold snapshots
    op.create_table(
        "threshold_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("entry_threshold", sa.Float(), nullable=False),
        sa.Column("exit_threshold", sa.Float(), nullable=False),
        sa.Column("stop_loss_pct", sa.Float(), nullable=True),
        sa.Column("take_profit_pct", sa.Float(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("position_size_scalar", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Ensemble results
    op.create_table(
        "ensemble_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("consensus_regime", sa.String(20), nullable=False),
        sa.Column("consensus_confidence", sa.Float(), nullable=False),
        sa.Column("agreement_ratio", sa.Float(), nullable=True),
        sa.Column("n_methods", sa.Integer(), nullable=True),
        sa.Column("is_unanimous", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Regime signal summaries
    op.create_table(
        "regime_signal_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("current_regime", sa.String(20), nullable=False),
        sa.Column("overall_bias", sa.String(10), nullable=True),
        sa.Column("overall_conviction", sa.Float(), nullable=True),
        sa.Column("transition_type", sa.String(20), nullable=True),
        sa.Column("persistence_ratio", sa.Float(), nullable=True),
        sa.Column("alignment_score", sa.Float(), nullable=True),
        sa.Column("divergence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("regime_signal_summaries")
    op.drop_table("ensemble_results")
    op.drop_table("threshold_snapshots")
    op.drop_table("adapted_signal_snapshots")
