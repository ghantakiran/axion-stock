"""PRD-69: Team Workspaces.

Revision ID: 069
Revises: 068
"""

from alembic import op
import sqlalchemy as sa

revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Workspace invitations (pending invites)
    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False, index=True),
        sa.Column("inviter_id", sa.String(36), nullable=False),
        sa.Column("invitee_email", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, default="member"),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Workspace discussion threads
    op.create_table(
        "workspace_discussions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False, index=True),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("author_name", sa.String(100), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), default=False),
        sa.Column("reply_count", sa.Integer(), default=0),
        sa.Column("last_reply_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("workspace_discussions")
    op.drop_table("workspace_invitations")
