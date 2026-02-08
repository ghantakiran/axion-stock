"""PRD-124: Secrets Management & API Credential Vaulting.

Revision ID: 124
Revises: 123
"""

from alembic import op
import sqlalchemy as sa

revision = "124"
down_revision = "123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "secrets",
        sa.Column("secret_id", sa.String(36), primary_key=True),
        sa.Column("key_path", sa.String(512), nullable=False),
        sa.Column("encrypted_value", sa.Text, nullable=False),
        sa.Column("secret_type", sa.String(50), nullable=False, server_default="generic"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("owner_service", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_secrets_key_path", "secrets", ["key_path"])
    op.create_index("ix_secrets_secret_type", "secrets", ["secret_type"])
    op.create_index("ix_secrets_owner_service", "secrets", ["owner_service"])
    op.create_index("ix_secrets_expires_at", "secrets", ["expires_at"])

    op.create_table(
        "secret_access_audit",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("secret_id", sa.String(36), nullable=True),
        sa.Column("requester_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("allowed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_secret_access_audit_secret_id", "secret_access_audit", ["secret_id"])
    op.create_index("ix_secret_access_audit_requester_id", "secret_access_audit", ["requester_id"])
    op.create_index("ix_secret_access_audit_action", "secret_access_audit", ["action"])
    op.create_index("ix_secret_access_audit_timestamp", "secret_access_audit", ["timestamp"])


def downgrade() -> None:
    op.drop_table("secret_access_audit")
    op.drop_table("secrets")
