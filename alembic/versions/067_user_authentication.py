"""PRD-67: User Authentication & RBAC.

Revision ID: 067
Revises: 066
"""

from alembic import op
import sqlalchemy as sa

revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Login attempt tracking for account lockout
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(200), nullable=False, index=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(50), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # 2FA backup codes
    op.create_table(
        "totp_backup_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("is_used", sa.Boolean(), default=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("totp_backup_codes")
    op.drop_table("login_attempts")
