"""Team Workspaces and Collaboration.

Provides shared workspaces for teams with strategy sharing,
activity feeds, and leaderboards.
"""

import logging
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field

from src.enterprise.config import SubscriptionTier, SUBSCRIPTION_LIMITS
from src.enterprise.models import (
    User, Workspace, WorkspaceMember, WorkspaceRole,
    SharedStrategy, ActivityItem, generate_uuid,
)

logger = logging.getLogger(__name__)


@dataclass
class LeaderboardEntry:
    """Strategy leaderboard entry."""

    rank: int
    user_id: str
    user_name: str
    strategy_id: str
    strategy_name: str
    ytd_return: float
    sharpe_ratio: float
    total_return: float
    use_count: int


@dataclass
class WorkspaceStats:
    """Workspace statistics."""

    workspace_id: str
    member_count: int
    strategy_count: int
    total_aum: float
    active_today: int
    trades_today: int


class WorkspaceManager:
    """Manages team workspaces and collaboration.

    Features:
    - Create/manage workspaces
    - Invite/remove members
    - Share strategies
    - Activity feeds
    - Strategy leaderboards
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._workspaces: dict[str, Workspace] = {}
        self._members: dict[str, List[WorkspaceMember]] = {}  # workspace_id -> members
        self._strategies: dict[str, List[SharedStrategy]] = {}  # workspace_id -> strategies
        self._activities: dict[str, List[ActivityItem]] = {}  # workspace_id -> activities

    def create_workspace(
        self,
        owner: User,
        name: str,
        description: str = "",
    ) -> tuple[Optional[Workspace], Optional[str]]:
        """Create a new workspace.

        Args:
            owner: User creating the workspace.
            name: Workspace name.
            description: Workspace description.

        Returns:
            Tuple of (Workspace, error_message).
        """
        # Check subscription
        limits = SUBSCRIPTION_LIMITS.get(owner.subscription, {})
        if not limits.get("team_workspace", False):
            return None, "Upgrade to Enterprise for team workspaces"

        workspace = Workspace(
            name=name,
            description=description,
            owner_id=owner.id,
            member_count=1,
        )

        self._workspaces[workspace.id] = workspace
        self._members[workspace.id] = []
        self._strategies[workspace.id] = []
        self._activities[workspace.id] = []

        # Add owner as member
        owner_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner.id,
            role=WorkspaceRole.OWNER,
        )
        self._members[workspace.id].append(owner_member)

        # Record activity
        self._add_activity(
            workspace.id,
            owner.id,
            owner.name,
            "created_workspace",
            "workspace",
            workspace.id,
            workspace.name,
        )

        logger.info(f"Workspace created: {workspace.name} by {owner.email}")
        return workspace, None

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID."""
        return self._workspaces.get(workspace_id)

    def get_user_workspaces(self, user_id: str) -> List[Workspace]:
        """Get all workspaces a user belongs to."""
        workspace_ids = set()
        for ws_id, members in self._members.items():
            for member in members:
                if member.user_id == user_id:
                    workspace_ids.add(ws_id)
                    break

        return [
            self._workspaces[ws_id]
            for ws_id in workspace_ids
            if ws_id in self._workspaces
        ]

    def invite_member(
        self,
        workspace_id: str,
        inviter_id: str,
        user_id: str,
        user_name: str,
        role: WorkspaceRole = WorkspaceRole.MEMBER,
    ) -> tuple[Optional[WorkspaceMember], Optional[str]]:
        """Invite a user to a workspace.

        Args:
            workspace_id: Workspace to invite to.
            inviter_id: User doing the inviting.
            user_id: User being invited.
            user_name: Name of user being invited.
            role: Role to assign.

        Returns:
            Tuple of (WorkspaceMember, error_message).
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return None, "Workspace not found"

        # Check inviter permission
        inviter_member = self._get_member(workspace_id, inviter_id)
        if not inviter_member or inviter_member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            return None, "Not authorized to invite members"

        # Check if already a member
        existing = self._get_member(workspace_id, user_id)
        if existing:
            return None, "User is already a member"

        # Check seat limit
        limits = SUBSCRIPTION_LIMITS.get(SubscriptionTier.ENTERPRISE, {})
        max_seats = limits.get("team_seats", 10)
        if len(self._members.get(workspace_id, [])) >= max_seats:
            return None, f"Workspace seat limit reached ({max_seats})"

        # Add member
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            invited_by=inviter_id,
        )

        self._members[workspace_id].append(member)
        workspace.member_count = len(self._members[workspace_id])

        # Record activity
        self._add_activity(
            workspace_id,
            inviter_id,
            "",  # Will be filled by caller
            "invited_member",
            "user",
            user_id,
            user_name,
        )

        logger.info(f"Member invited to workspace: {user_id} to {workspace.name}")
        return member, None

    def remove_member(
        self,
        workspace_id: str,
        remover_id: str,
        user_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Remove a member from workspace.

        Args:
            workspace_id: Workspace ID.
            remover_id: User doing the removal.
            user_id: User being removed.

        Returns:
            Tuple of (success, error_message).
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False, "Workspace not found"

        # Check permission
        remover_member = self._get_member(workspace_id, remover_id)
        if not remover_member or remover_member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            return False, "Not authorized"

        # Cannot remove owner
        if workspace.owner_id == user_id:
            return False, "Cannot remove workspace owner"

        # Remove member
        members = self._members.get(workspace_id, [])
        self._members[workspace_id] = [m for m in members if m.user_id != user_id]
        workspace.member_count = len(self._members[workspace_id])

        return True, None

    def share_strategy(
        self,
        workspace_id: str,
        user_id: str,
        user_name: str,
        name: str,
        description: str,
        config: dict,
        ytd_return: float = 0.0,
        sharpe_ratio: float = 0.0,
    ) -> tuple[Optional[SharedStrategy], Optional[str]]:
        """Share a strategy with the workspace.

        Args:
            workspace_id: Workspace to share to.
            user_id: User sharing.
            user_name: Name of user sharing.
            name: Strategy name.
            description: Strategy description.
            config: Strategy configuration.
            ytd_return: YTD performance.
            sharpe_ratio: Risk-adjusted performance.

        Returns:
            Tuple of (SharedStrategy, error_message).
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return None, "Workspace not found"

        # Check membership
        member = self._get_member(workspace_id, user_id)
        if not member:
            return None, "Not a workspace member"

        if member.role == WorkspaceRole.VIEWER:
            return None, "Viewers cannot share strategies"

        strategy = SharedStrategy(
            workspace_id=workspace_id,
            creator_id=user_id,
            name=name,
            description=description,
            config=config,
            ytd_return=ytd_return,
            sharpe_ratio=sharpe_ratio,
            is_public=True,
        )

        if workspace_id not in self._strategies:
            self._strategies[workspace_id] = []
        self._strategies[workspace_id].append(strategy)

        workspace.strategy_count = len(self._strategies[workspace_id])

        # Record activity
        self._add_activity(
            workspace_id,
            user_id,
            user_name,
            "shared_strategy",
            "strategy",
            strategy.id,
            name,
        )

        logger.info(f"Strategy shared: {name} in {workspace.name}")
        return strategy, None

    def get_workspace_strategies(
        self,
        workspace_id: str,
        user_id: str,
    ) -> List[SharedStrategy]:
        """Get all strategies in a workspace.

        Args:
            workspace_id: Workspace ID.
            user_id: User requesting (for permission check).

        Returns:
            List of SharedStrategy.
        """
        # Check membership
        member = self._get_member(workspace_id, user_id)
        if not member:
            return []

        return self._strategies.get(workspace_id, [])

    def get_leaderboard(
        self,
        workspace_id: str,
        metric: str = "ytd_return",
        limit: int = 10,
    ) -> List[LeaderboardEntry]:
        """Get strategy performance leaderboard.

        Args:
            workspace_id: Workspace ID.
            metric: Metric to rank by (ytd_return, sharpe_ratio, total_return).
            limit: Max entries to return.

        Returns:
            List of LeaderboardEntry sorted by metric.
        """
        strategies = self._strategies.get(workspace_id, [])

        # Sort by metric
        if metric == "ytd_return":
            sorted_strategies = sorted(strategies, key=lambda s: s.ytd_return, reverse=True)
        elif metric == "sharpe_ratio":
            sorted_strategies = sorted(strategies, key=lambda s: s.sharpe_ratio, reverse=True)
        else:
            sorted_strategies = sorted(strategies, key=lambda s: s.total_return, reverse=True)

        entries = []
        for i, strategy in enumerate(sorted_strategies[:limit], 1):
            entries.append(LeaderboardEntry(
                rank=i,
                user_id=strategy.creator_id,
                user_name="",  # Would be filled from user lookup
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                ytd_return=strategy.ytd_return,
                sharpe_ratio=strategy.sharpe_ratio,
                total_return=strategy.total_return,
                use_count=strategy.use_count,
            ))

        return entries

    def get_activity_feed(
        self,
        workspace_id: str,
        limit: int = 50,
    ) -> List[ActivityItem]:
        """Get workspace activity feed.

        Args:
            workspace_id: Workspace ID.
            limit: Max items to return.

        Returns:
            List of ActivityItem, newest first.
        """
        activities = self._activities.get(workspace_id, [])
        return sorted(activities, key=lambda a: a.timestamp, reverse=True)[:limit]

    def record_activity(
        self,
        workspace_id: str,
        user_id: str,
        user_name: str,
        action: str,
        resource_type: str,
        resource_id: str,
        resource_name: str,
        details: Optional[dict] = None,
    ):
        """Record an activity to the feed.

        Args:
            workspace_id: Workspace ID.
            user_id: User who performed action.
            user_name: User's name.
            action: Action type.
            resource_type: Type of resource.
            resource_id: Resource ID.
            resource_name: Resource name.
            details: Additional details.
        """
        self._add_activity(
            workspace_id, user_id, user_name,
            action, resource_type, resource_id, resource_name,
            details,
        )

    def get_workspace_stats(self, workspace_id: str) -> Optional[WorkspaceStats]:
        """Get workspace statistics.

        Args:
            workspace_id: Workspace ID.

        Returns:
            WorkspaceStats or None.
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return None

        # Count today's activities
        today = datetime.utcnow().date()
        activities = self._activities.get(workspace_id, [])
        active_users = set()
        trades_today = 0

        for activity in activities:
            if activity.timestamp.date() == today:
                active_users.add(activity.user_id)
                if activity.action in ["executed_trade", "rebalanced"]:
                    trades_today += 1

        return WorkspaceStats(
            workspace_id=workspace_id,
            member_count=len(self._members.get(workspace_id, [])),
            strategy_count=len(self._strategies.get(workspace_id, [])),
            total_aum=workspace.total_aum,
            active_today=len(active_users),
            trades_today=trades_today,
        )

    def update_member_role(
        self,
        workspace_id: str,
        updater_id: str,
        user_id: str,
        new_role: WorkspaceRole,
    ) -> tuple[bool, Optional[str]]:
        """Update a member's role.

        Args:
            workspace_id: Workspace ID.
            updater_id: User making the change.
            user_id: User to update.
            new_role: New role.

        Returns:
            Tuple of (success, error_message).
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False, "Workspace not found"

        # Only owner can change roles
        if workspace.owner_id != updater_id:
            return False, "Only owner can change roles"

        # Cannot change owner's role
        if user_id == workspace.owner_id:
            return False, "Cannot change owner's role"

        member = self._get_member(workspace_id, user_id)
        if not member:
            return False, "Member not found"

        member.role = new_role
        return True, None

    def _get_member(self, workspace_id: str, user_id: str) -> Optional[WorkspaceMember]:
        """Get workspace member."""
        members = self._members.get(workspace_id, [])
        for member in members:
            if member.user_id == user_id:
                return member
        return None

    def _add_activity(
        self,
        workspace_id: str,
        user_id: str,
        user_name: str,
        action: str,
        resource_type: str,
        resource_id: str,
        resource_name: str,
        details: Optional[dict] = None,
    ):
        """Add activity to feed."""
        activity = ActivityItem(
            workspace_id=workspace_id,
            user_id=user_id,
            user_name=user_name,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details or {},
        )

        if workspace_id not in self._activities:
            self._activities[workspace_id] = []

        self._activities[workspace_id].append(activity)
