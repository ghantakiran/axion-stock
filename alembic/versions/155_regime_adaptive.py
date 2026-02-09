"""PRD-155: Regime-Adaptive Strategy tables.

Revision ID: 155
Revises: 154
"""

from alembic import op
import sqlalchemy as sa

revision = "155"
down_revision = "154"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Regime adaptation log
    op.create_table(
        "regime_adaptations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("adaptation_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("regime", sa.String(20), nullable=False, index=True),
        sa.Column("confidence", sa.Float),
        sa.Column("profile_used", sa.String(50)),
        sa.Column("changes_json", sa.Text),
        sa.Column("original_config_json", sa.Text),
        sa.Column("adapted_config_json", sa.Text),
        sa.Column("is_blended", sa.Boolean, default=False),
        sa.Column("transition_from", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Regime transition history
    op.create_table(
        "regime_transitions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("transition_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("from_regime", sa.String(20), nullable=False),
        sa.Column("to_regime", sa.String(20), nullable=False, index=True),
        sa.Column("confidence", sa.Float),
        sa.Column("method", sa.String(30)),
        sa.Column("circuit_broken", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("regime_transitions")
    op.drop_table("regime_adaptations")
