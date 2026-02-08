"""PRD-103: Observability & Metrics Export.

Revision ID: 103
Revises: 102
"""

from alembic import op
import sqlalchemy as sa

revision = "103"
down_revision = "102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Metric definitions registry
    op.create_table(
        "observability_metric_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metric_type", sa.String(20), nullable=False),
        sa.Column("label_names", sa.JSON(), nullable=True),
        sa.Column("bucket_bounds", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Time-series metric snapshots
    op.create_table(
        "observability_metric_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("metric_name", sa.String(200), nullable=False, index=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("total_sum", sa.Float(), nullable=True),
        sa.Column("bucket_counts", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Export configuration
    op.create_table(
        "observability_export_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("export_format", sa.String(20), nullable=False),
        sa.Column("endpoint_path", sa.String(100), nullable=False, default="/metrics"),
        sa.Column("prefix", sa.String(50), nullable=True),
        sa.Column("global_labels", sa.JSON(), nullable=True),
        sa.Column("include_timestamp", sa.Boolean(), default=True),
        sa.Column("collection_interval_seconds", sa.Float(), default=15.0),
        sa.Column("retention_minutes", sa.Integer(), default=60),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("observability_export_config")
    op.drop_table("observability_metric_snapshots")
    op.drop_table("observability_metric_definitions")
