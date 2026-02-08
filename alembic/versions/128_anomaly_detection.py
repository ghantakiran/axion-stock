"""PRD-128: Real-Time Anomaly Detection Engine.

Revision ID: 128
Revises: 127
"""

from alembic import op
import sqlalchemy as sa

revision = "128"
down_revision = "127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Detected anomaly records with lifecycle tracking
    op.create_table(
        "anomaly_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("record_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("anomaly_id", sa.String(64), nullable=False, index=True),
        sa.Column("metric_name", sa.String(256), nullable=False, index=True),
        sa.Column("anomaly_type", sa.String(32), nullable=False, index=True),
        sa.Column("detection_method", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("baseline_mean", sa.Float(), nullable=True),
        sa.Column("baseline_std", sa.Float(), nullable=True),
        sa.Column("assigned_to", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Metric baseline snapshots for detection calibration
    op.create_table(
        "anomaly_baselines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("metric_name", sa.String(256), nullable=False, index=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("std", sa.Float(), nullable=False),
        sa.Column("min_val", sa.Float(), nullable=True),
        sa.Column("max_val", sa.Float(), nullable=True),
        sa.Column("median", sa.Float(), nullable=True),
        sa.Column("q1", sa.Float(), nullable=True),
        sa.Column("q3", sa.Float(), nullable=True),
        sa.Column("window_size", sa.Integer(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("anomaly_baselines")
    op.drop_table("anomaly_records")
