"""PRD-113: ML Model Registry.

Revision ID: 113
Revises: 112
"""
from alembic import op
import sqlalchemy as sa

revision = "113"
down_revision = "112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(128), nullable=False, index=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("framework", sa.String(32), nullable=True),
        sa.Column("artifact_path", sa.String(512), nullable=True),
        sa.Column("metrics", sa.Text, nullable=True),
        sa.Column("hyperparameters", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "model_experiments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("experiment_name", sa.String(256), nullable=False, index=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("hyperparameters", sa.Text, nullable=True),
        sa.Column("metrics", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("model_experiments")
    op.drop_table("model_versions")
