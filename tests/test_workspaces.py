"""Unit tests for PRD-69: Team Workspaces.

Tests cover:
- WorkspaceManager CRUD operations
- Member management (invite, remove, roles)
- Strategy sharing and leaderboard
- Activity feed
- Subscription limits
- ORM models
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.enterprise.workspaces import (
    WorkspaceManager,
    LeaderboardEntry,
    WorkspaceStats,
)
from src.enterprise.models import (
    User, Workspace, WorkspaceMember, WorkspaceRole,
    SharedStrategy, ActivityItem, generate_uuid,
)
from src.enterprise.config import (
    SubscriptionTier,
    UserRole,
    SUBSCRIPTION_LIMITS,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def workspace_manager():
    """Create a fresh WorkspaceManager instance."""
    return WorkspaceManager()


@pytest.fixture
def enterprise_user():
    """Create an enterprise tier user."""
    return User(
        id=generate_uuid(),
        email="enterprise@example.com",
        name="Enterprise User",
        role=UserRole.ADMIN,
        subscription=SubscriptionTier.ENTERPRISE,
    )


@pytest.fixture
def pro_user():
    """Create a pro tier user (no team workspace access)."""
    return User(
        id=generate_uuid(),
        email="pro@example.com",
        name="Pro User",
        role=UserRole.TRADER,
        subscription=SubscriptionTier.PRO,
    )


@pytest.fixture
def member_user():
    """Create a second user to invite as member."""
    return User(
        id=generate_uuid(),
        email="member@example.com",
        name="Team Member",
        role=UserRole.TRADER,
        subscription=SubscriptionTier.ENTERPRISE,
    )


# =============================================================================
# Workspace Creation Tests
# =============================================================================


class TestWorkspaceCreation:
    """Tests for workspace creation."""

    def test_create_workspace(self, workspace_manager, enterprise_user):
        """Enterprise users can create workspaces."""
        workspace, error = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Alpha Research",
            description="Quantitative research team",
        )

        assert error is None
        assert workspace is not None
        assert workspace.name == "Alpha Research"
        assert workspace.owner_id == enterprise_user.id
        assert workspace.member_count == 1

    def test_create_workspace_generates_id(self, workspace_manager, enterprise_user):
        """Workspace gets a valid UUID on creation."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        assert workspace is not None
        assert len(workspace.id) == 36  # UUID length

    def test_pro_user_cannot_create_workspace(self, workspace_manager, pro_user):
        """Pro users cannot create team workspaces."""
        workspace, error = workspace_manager.create_workspace(
            owner=pro_user,
            name="Pro Workspace",
        )

        assert workspace is None
        assert "Enterprise" in error

    def test_owner_added_as_member(self, workspace_manager, enterprise_user):
        """Owner is automatically added as workspace member."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        # Check owner is a member
        user_workspaces = workspace_manager.get_user_workspaces(enterprise_user.id)
        assert len(user_workspaces) == 1
        assert user_workspaces[0].id == workspace.id


# =============================================================================
# Workspace Retrieval Tests
# =============================================================================


class TestWorkspaceRetrieval:
    """Tests for getting workspaces."""

    def test_get_workspace_by_id(self, workspace_manager, enterprise_user):
        """Can retrieve workspace by ID."""
        created, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        retrieved = workspace_manager.get_workspace(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test Workspace"

    def test_get_nonexistent_workspace(self, workspace_manager):
        """Returns None for nonexistent workspace."""
        workspace = workspace_manager.get_workspace("nonexistent-id")
        assert workspace is None

    def test_get_user_workspaces(self, workspace_manager, enterprise_user):
        """Get all workspaces a user belongs to."""
        workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Workspace 1",
        )
        workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Workspace 2",
        )

        workspaces = workspace_manager.get_user_workspaces(enterprise_user.id)
        assert len(workspaces) == 2
        names = [w.name for w in workspaces]
        assert "Workspace 1" in names
        assert "Workspace 2" in names


# =============================================================================
# Member Management Tests
# =============================================================================


class TestMemberManagement:
    """Tests for workspace member management."""

    def test_invite_member(self, workspace_manager, enterprise_user, member_user):
        """Owner can invite members."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        member, error = workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
            role=WorkspaceRole.MEMBER,
        )

        assert error is None
        assert member is not None
        assert member.user_id == member_user.id
        assert member.role == WorkspaceRole.MEMBER

    def test_invite_to_nonexistent_workspace(self, workspace_manager, enterprise_user, member_user):
        """Cannot invite to nonexistent workspace."""
        member, error = workspace_manager.invite_member(
            workspace_id="nonexistent",
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
        )

        assert member is None
        assert "not found" in error

    def test_member_cannot_invite(self, workspace_manager, enterprise_user, member_user):
        """Regular members cannot invite others."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        # Invite member_user first
        workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
            role=WorkspaceRole.MEMBER,
        )

        # Member tries to invite someone else
        third_user_id = generate_uuid()
        member, error = workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=member_user.id,  # Not owner/admin
            user_id=third_user_id,
            user_name="Third User",
        )

        assert member is None
        assert "Not authorized" in error

    def test_admin_can_invite(self, workspace_manager, enterprise_user, member_user):
        """Admins can invite members."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        # Invite member_user as admin
        workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
            role=WorkspaceRole.ADMIN,
        )

        # Admin invites someone else
        third_user_id = generate_uuid()
        member, error = workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=member_user.id,
            user_id=third_user_id,
            user_name="Third User",
        )

        assert error is None
        assert member is not None

    def test_cannot_invite_existing_member(self, workspace_manager, enterprise_user, member_user):
        """Cannot invite someone who is already a member."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        # Invite once
        workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
        )

        # Try to invite again
        member, error = workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
        )

        assert member is None
        assert "already a member" in error

    def test_remove_member(self, workspace_manager, enterprise_user, member_user):
        """Owner can remove members."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
        )

        success, error = workspace_manager.remove_member(
            workspace_id=workspace.id,
            remover_id=enterprise_user.id,
            user_id=member_user.id,
        )

        assert success is True
        assert error is None

    def test_cannot_remove_owner(self, workspace_manager, enterprise_user):
        """Cannot remove the workspace owner."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        success, error = workspace_manager.remove_member(
            workspace_id=workspace.id,
            remover_id=enterprise_user.id,
            user_id=enterprise_user.id,  # Trying to remove self
        )

        assert success is False
        assert "Cannot remove" in error

    def test_update_member_role(self, workspace_manager, enterprise_user, member_user):
        """Owner can update member roles."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
            role=WorkspaceRole.MEMBER,
        )

        success, error = workspace_manager.update_member_role(
            workspace_id=workspace.id,
            updater_id=enterprise_user.id,
            user_id=member_user.id,
            new_role=WorkspaceRole.ADMIN,
        )

        assert success is True
        assert error is None


# =============================================================================
# Strategy Sharing Tests
# =============================================================================


class TestStrategySharing:
    """Tests for sharing strategies in workspaces."""

    def test_share_strategy(self, workspace_manager, enterprise_user):
        """Members can share strategies."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        strategy, error = workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Quality Growth",
            description="Factor-based quality strategy",
            config={"factors": ["quality", "momentum"]},
            ytd_return=0.12,
            sharpe_ratio=1.5,
        )

        assert error is None
        assert strategy is not None
        assert strategy.name == "Quality Growth"
        assert strategy.ytd_return == 0.12

    def test_share_strategy_updates_count(self, workspace_manager, enterprise_user):
        """Sharing strategy updates workspace count."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        assert workspace.strategy_count == 0

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Strategy 1",
            description="",
            config={},
        )

        assert workspace.strategy_count == 1

    def test_viewer_cannot_share(self, workspace_manager, enterprise_user, member_user):
        """Viewers cannot share strategies."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
            role=WorkspaceRole.VIEWER,
        )

        strategy, error = workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=member_user.id,
            user_name=member_user.name,
            name="My Strategy",
            description="",
            config={},
        )

        assert strategy is None
        assert "cannot share" in error.lower()

    def test_get_workspace_strategies(self, workspace_manager, enterprise_user):
        """Can get all strategies in a workspace."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Strategy 1",
            description="",
            config={},
        )

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Strategy 2",
            description="",
            config={},
        )

        strategies = workspace_manager.get_workspace_strategies(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
        )

        assert len(strategies) == 2


# =============================================================================
# Leaderboard Tests
# =============================================================================


class TestLeaderboard:
    """Tests for strategy leaderboard."""

    def test_get_leaderboard(self, workspace_manager, enterprise_user):
        """Can get strategy leaderboard."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        # Add strategies with different returns
        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Top Strategy",
            description="",
            config={},
            ytd_return=0.15,
            sharpe_ratio=1.8,
        )

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Second Strategy",
            description="",
            config={},
            ytd_return=0.10,
            sharpe_ratio=1.5,
        )

        leaderboard = workspace_manager.get_leaderboard(
            workspace_id=workspace.id,
            metric="ytd_return",
        )

        assert len(leaderboard) == 2
        assert leaderboard[0].rank == 1
        assert leaderboard[0].strategy_name == "Top Strategy"
        assert leaderboard[0].ytd_return == 0.15

    def test_leaderboard_by_sharpe(self, workspace_manager, enterprise_user):
        """Leaderboard can sort by Sharpe ratio."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="High Return Low Sharpe",
            description="",
            config={},
            ytd_return=0.20,
            sharpe_ratio=1.0,
        )

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Lower Return High Sharpe",
            description="",
            config={},
            ytd_return=0.10,
            sharpe_ratio=2.0,
        )

        leaderboard = workspace_manager.get_leaderboard(
            workspace_id=workspace.id,
            metric="sharpe_ratio",
        )

        assert leaderboard[0].strategy_name == "Lower Return High Sharpe"
        assert leaderboard[0].sharpe_ratio == 2.0


# =============================================================================
# Activity Feed Tests
# =============================================================================


class TestActivityFeed:
    """Tests for workspace activity feed."""

    def test_activity_recorded_on_creation(self, workspace_manager, enterprise_user):
        """Activity is recorded when workspace is created."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        activities = workspace_manager.get_activity_feed(workspace.id)
        assert len(activities) >= 1
        assert any(a.action == "created_workspace" for a in activities)

    def test_activity_recorded_on_strategy_share(self, workspace_manager, enterprise_user):
        """Activity is recorded when strategy is shared."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="My Strategy",
            description="",
            config={},
        )

        activities = workspace_manager.get_activity_feed(workspace.id)
        assert any(a.action == "shared_strategy" for a in activities)

    def test_record_custom_activity(self, workspace_manager, enterprise_user):
        """Can record custom activities."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.record_activity(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            action="executed_trade",
            resource_type="trade",
            resource_id="trade-123",
            resource_name="BUY AAPL",
            details={"symbol": "AAPL", "qty": 100},
        )

        activities = workspace_manager.get_activity_feed(workspace.id)
        assert any(a.action == "executed_trade" for a in activities)


# =============================================================================
# Workspace Stats Tests
# =============================================================================


class TestWorkspaceStats:
    """Tests for workspace statistics."""

    def test_get_workspace_stats(self, workspace_manager, enterprise_user, member_user):
        """Can get workspace statistics."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=member_user.id,
            user_name=member_user.name,
        )

        workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Strategy",
            description="",
            config={},
        )

        stats = workspace_manager.get_workspace_stats(workspace.id)

        assert stats is not None
        assert stats.member_count == 2
        assert stats.strategy_count == 1

    def test_stats_for_nonexistent_workspace(self, workspace_manager):
        """Returns None for nonexistent workspace."""
        stats = workspace_manager.get_workspace_stats("nonexistent")
        assert stats is None


# =============================================================================
# Subscription Limits Tests
# =============================================================================


class TestSubscriptionLimits:
    """Tests for subscription tier limits."""

    def test_enterprise_has_team_workspace(self):
        """Enterprise tier has team workspace feature."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.ENTERPRISE]
        assert limits["team_workspace"] is True

    def test_pro_no_team_workspace(self):
        """Pro tier does not have team workspace feature."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.PRO]
        assert limits["team_workspace"] is False

    def test_free_no_team_workspace(self):
        """Free tier does not have team workspace feature."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.FREE]
        assert limits["team_workspace"] is False

    def test_seat_limit(self, workspace_manager, enterprise_user):
        """Cannot exceed team seat limit."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Workspace",
        )

        # Try to add more than allowed seats
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.ENTERPRISE]
        max_seats = limits["team_seats"]

        # Add members up to limit
        for i in range(max_seats - 1):  # -1 because owner counts
            user_id = generate_uuid()
            workspace_manager.invite_member(
                workspace_id=workspace.id,
                inviter_id=enterprise_user.id,
                user_id=user_id,
                user_name=f"User {i}",
            )

        # Try to add one more
        member, error = workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=generate_uuid(),
            user_name="Overflow User",
        )

        assert member is None
        assert "limit reached" in error


# =============================================================================
# ORM Model Tests
# =============================================================================


class TestORMModels:
    """Tests for ORM model definitions."""

    def test_workspace_model(self):
        """WorkspaceRecord model has required fields."""
        from src.db.models import WorkspaceRecord

        columns = {c.name for c in WorkspaceRecord.__table__.columns}
        assert "id" in columns
        assert "name" in columns
        assert "description" in columns
        assert "owner_id" in columns
        assert "member_count" in columns
        assert "strategy_count" in columns
        assert "total_aum" in columns

    def test_workspace_member_model(self):
        """WorkspaceMemberRecord model has required fields."""
        from src.db.models import WorkspaceMemberRecord

        columns = {c.name for c in WorkspaceMemberRecord.__table__.columns}
        assert "id" in columns
        assert "workspace_id" in columns
        assert "user_id" in columns
        assert "role" in columns
        assert "invited_by" in columns
        assert "joined_at" in columns

    def test_shared_strategy_model(self):
        """SharedStrategyRecord model has required fields."""
        from src.db.models import SharedStrategyRecord

        columns = {c.name for c in SharedStrategyRecord.__table__.columns}
        assert "id" in columns
        assert "workspace_id" in columns
        assert "creator_id" in columns
        assert "name" in columns
        assert "ytd_return" in columns
        assert "sharpe_ratio" in columns
        assert "use_count" in columns

    def test_workspace_activity_model(self):
        """WorkspaceActivityRecord model has required fields."""
        from src.db.models import WorkspaceActivityRecord

        columns = {c.name for c in WorkspaceActivityRecord.__table__.columns}
        assert "id" in columns
        assert "workspace_id" in columns
        assert "user_id" in columns
        assert "action" in columns
        assert "resource_type" in columns
        assert "timestamp" in columns

    def test_workspace_watchlist_model(self):
        """WorkspaceWatchlistRecord model has required fields."""
        from src.db.models import WorkspaceWatchlistRecord

        columns = {c.name for c in WorkspaceWatchlistRecord.__table__.columns}
        assert "id" in columns
        assert "workspace_id" in columns
        assert "name" in columns
        assert "symbols" in columns

    def test_workspace_research_note_model(self):
        """WorkspaceResearchNoteRecord model has required fields."""
        from src.db.models import WorkspaceResearchNoteRecord

        columns = {c.name for c in WorkspaceResearchNoteRecord.__table__.columns}
        assert "id" in columns
        assert "workspace_id" in columns
        assert "title" in columns
        assert "content" in columns
        assert "author_id" in columns


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum definitions."""

    def test_workspace_role_enum(self):
        """WorkspaceRoleEnum has all expected values."""
        from src.db.models import WorkspaceRoleEnum

        values = {e.value for e in WorkspaceRoleEnum}
        assert "owner" in values
        assert "admin" in values
        assert "member" in values
        assert "viewer" in values
