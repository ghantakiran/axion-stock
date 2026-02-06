"""PRD-69: Team Workspaces.

Revision ID: 055
Revises: 054
"""

from alembic import op
import sqlalchemy as sa

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Workspaces
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # Settings
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        # Stats (cached)
        sa.Column("member_count", sa.Integer(), server_default="1"),
        sa.Column("strategy_count", sa.Integer(), server_default="0"),
        sa.Column("total_aum", sa.Float(), server_default="0"),
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Workspace members
    op.create_table(
        "workspace_members",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # owner, admin, member, viewer
        sa.Column("invited_by", sa.String(36), nullable=True),
        sa.Column("joined_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
    )

    # Shared strategies
    op.create_table(
        "shared_strategies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        # Performance (cached)
        sa.Column("ytd_return", sa.Float(), server_default="0"),
        sa.Column("sharpe_ratio", sa.Float(), server_default="0"),
        sa.Column("total_return", sa.Float(), server_default="0"),
        sa.Column("max_drawdown", sa.Float(), server_default="0"),
        sa.Column("win_rate", sa.Float(), server_default="0"),
        # Usage
        sa.Column("use_count", sa.Integer(), server_default="0"),
        sa.Column("fork_count", sa.Integer(), server_default="0"),
        # Status
        sa.Column("is_public", sa.Boolean(), server_default="true"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Workspace activities (activity feed)
    op.create_table(
        "workspace_activities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("user_name", sa.String(100), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),  # created_strategy, executed_trade, etc.
        sa.Column("resource_type", sa.String(30), nullable=True),  # strategy, trade, account
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("resource_name", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )

    # Strategy watchlists (shared watchlists per workspace)
    op.create_table(
        "workspace_watchlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("symbols", sa.JSON(), nullable=True),  # Array of symbols
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Research notes (shared research)
    op.create_table(
        "workspace_research_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_name", sa.String(100), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("symbols", sa.JSON(), nullable=True),  # Related symbols
        sa.Column("tags", sa.JSON(), nullable=True),  # Tags for categorization
        sa.Column("is_pinned", sa.Boolean(), server_default="false"),
        sa.Column("view_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # Indexes
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])
    op.create_index("ix_shared_strategies_workspace_id", "shared_strategies", ["workspace_id"])
    op.create_index("ix_shared_strategies_creator_id", "shared_strategies", ["creator_id"])
    op.create_index("ix_workspace_activities_workspace_id", "workspace_activities", ["workspace_id"])
    op.create_index("ix_workspace_activities_timestamp", "workspace_activities", ["timestamp"])
    op.create_index("ix_workspace_watchlists_workspace_id", "workspace_watchlists", ["workspace_id"])
    op.create_index("ix_workspace_research_notes_workspace_id", "workspace_research_notes", ["workspace_id"])

    # Unique constraint for member per workspace
    op.create_unique_constraint(
        "uq_workspace_member",
        "workspace_members",
        ["workspace_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_workspace_member", "workspace_members")
    op.drop_index("ix_workspace_research_notes_workspace_id")
    op.drop_index("ix_workspace_watchlists_workspace_id")
    op.drop_index("ix_workspace_activities_timestamp")
    op.drop_index("ix_workspace_activities_workspace_id")
    op.drop_index("ix_shared_strategies_creator_id")
    op.drop_index("ix_shared_strategies_workspace_id")
    op.drop_index("ix_workspace_members_user_id")
    op.drop_index("ix_workspace_members_workspace_id")
    op.drop_index("ix_workspaces_owner_id")
    op.drop_table("workspace_research_notes")
    op.drop_table("workspace_watchlists")
    op.drop_table("workspace_activities")
    op.drop_table("shared_strategies")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
