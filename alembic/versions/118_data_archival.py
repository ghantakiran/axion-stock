"""PRD-118: Data Archival & GDPR Compliance.

Revision ID: 118
Revises: 117
"""

from alembic import op
import sqlalchemy as sa

revision = "118"
down_revision = "117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Archival job tracking
    op.create_table(
        "archival_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("table_name", sa.String(128), nullable=False, index=True),
        sa.Column("date_range_start", sa.DateTime(), nullable=False),
        sa.Column("date_range_end", sa.DateTime(), nullable=False),
        sa.Column("format", sa.String(20), nullable=False, default="parquet"),
        sa.Column("status", sa.String(20), nullable=False, default="pending", index=True),
        sa.Column("records_archived", sa.Integer(), default=0),
        sa.Column("bytes_written", sa.BigInteger(), default=0),
        sa.Column("storage_path", sa.String(512), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # GDPR data subject requests
    op.create_table(
        "gdpr_requests",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("request_type", sa.String(20), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, default="pending", index=True),
        sa.Column("tables_affected", sa.Text(), nullable=True),
        sa.Column("records_affected", sa.Integer(), default=0),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("audit_proof", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("gdpr_requests")
    op.drop_table("archival_jobs")
