"""PRD-116: Disaster Recovery & Automated Backup.

Revision ID: 116
Revises: 115
"""
from alembic import op
import sqlalchemy as sa

revision = "116"
down_revision = "115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("backup_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("sources", sa.Text, nullable=True),
        sa.Column("storage_backend", sa.String(32), nullable=False),
        sa.Column("storage_tier", sa.String(16), nullable=False),
        sa.Column("total_size_bytes", sa.BigInteger, default=0),
        sa.Column("duration_seconds", sa.Float, default=0.0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "recovery_tests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("recovery_id", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("backup_job_id", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("steps_completed", sa.Integer, default=0),
        sa.Column("steps_total", sa.Integer, default=0),
        sa.Column("duration_seconds", sa.Float, default=0.0),
        sa.Column("integrity_valid", sa.Boolean, default=False),
        sa.Column("validation_details", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("recovery_tests")
    op.drop_table("backup_runs")
