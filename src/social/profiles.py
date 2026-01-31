"""Trader profile management.

Profile CRUD, badge evaluation, and follower management.
"""

import logging
from typing import Optional

from src.social.config import (
    Badge,
    BADGE_REQUIREMENTS,
    ProfileVisibility,
    TradingStyle,
    SocialConfig,
    DEFAULT_SOCIAL_CONFIG,
)
from src.social.models import (
    TraderProfile,
    PerformanceStats,
    FollowRelationship,
    _utc_now,
)

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages trader profiles, badges, and follow relationships.

    Handles profile CRUD, badge evaluation, follow/unfollow,
    and profile discovery.
    """

    def __init__(self, config: Optional[SocialConfig] = None) -> None:
        self.config = config or DEFAULT_SOCIAL_CONFIG
        self._profiles: dict[str, TraderProfile] = {}
        self._follows: list[FollowRelationship] = []

    def create_profile(
        self,
        user_id: str,
        display_name: str,
        bio: str = "",
        trading_style: TradingStyle = TradingStyle.SWING_TRADING,
        visibility: ProfileVisibility = ProfileVisibility.PUBLIC,
    ) -> TraderProfile:
        """Create a new trader profile.

        Args:
            user_id: Platform user ID.
            display_name: Public display name.
            bio: Profile biography.
            trading_style: Primary trading style.
            visibility: Profile visibility.

        Returns:
            Created TraderProfile.
        """
        profile = TraderProfile(
            user_id=user_id,
            display_name=display_name,
            bio=bio,
            trading_style=trading_style,
            visibility=visibility,
        )
        self._profiles[user_id] = profile
        logger.info("Created profile for user %s: %s", user_id, display_name)
        return profile

    def get_profile(self, user_id: str) -> Optional[TraderProfile]:
        """Get a trader profile by user ID."""
        return self._profiles.get(user_id)

    def update_profile(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        bio: Optional[str] = None,
        trading_style: Optional[TradingStyle] = None,
        visibility: Optional[ProfileVisibility] = None,
    ) -> Optional[TraderProfile]:
        """Update an existing profile.

        Args:
            user_id: User ID.
            display_name: New display name.
            bio: New bio.
            trading_style: New trading style.
            visibility: New visibility.

        Returns:
            Updated profile, or None if not found.
        """
        profile = self._profiles.get(user_id)
        if not profile:
            return None

        if display_name is not None:
            profile.display_name = display_name
        if bio is not None:
            profile.bio = bio
        if trading_style is not None:
            profile.trading_style = trading_style
        if visibility is not None:
            profile.visibility = visibility

        profile.updated_at = _utc_now()
        return profile

    def update_stats(
        self,
        user_id: str,
        stats: PerformanceStats,
    ) -> Optional[TraderProfile]:
        """Update a profile's performance statistics.

        Args:
            user_id: User ID.
            stats: New performance stats.

        Returns:
            Updated profile, or None if not found.
        """
        profile = self._profiles.get(user_id)
        if not profile:
            return None

        profile.stats = stats
        profile.updated_at = _utc_now()

        # Re-evaluate badges
        self._evaluate_badges(profile)
        return profile

    def _evaluate_badges(self, profile: TraderProfile) -> None:
        """Evaluate and award badges based on performance.

        Args:
            profile: Profile to evaluate.
        """
        stats = profile.stats

        # Top Performer: high return percentile (simplified check)
        if stats.total_return > 0.20:
            profile.add_badge(Badge.TOP_PERFORMER)

        # Consistent: positive win rate over many trades
        if stats.win_rate >= 0.55 and stats.total_trades >= 50:
            profile.add_badge(Badge.CONSISTENT)

        # Veteran: long history with many trades
        if stats.total_trades >= 100:
            profile.add_badge(Badge.VETERAN)

        # Risk Master: good Sharpe with limited drawdown
        reqs = BADGE_REQUIREMENTS[Badge.RISK_MASTER]
        if (
            stats.sharpe_ratio >= reqs["min_sharpe"]
            and abs(stats.max_drawdown) <= reqs["max_drawdown"]
        ):
            profile.add_badge(Badge.RISK_MASTER)

        # Community Leader: many followers with good rating
        reqs = BADGE_REQUIREMENTS[Badge.COMMUNITY_LEADER]
        if (
            profile.followers_count >= reqs["min_followers"]
            and profile.rating >= reqs["min_rating"]
        ):
            profile.add_badge(Badge.COMMUNITY_LEADER)

    def follow(self, follower_id: str, following_id: str) -> bool:
        """Follow a trader.

        Args:
            follower_id: User who wants to follow.
            following_id: User to follow.

        Returns:
            True if follow was successful.
        """
        if follower_id == following_id:
            return False

        # Check if already following
        for f in self._follows:
            if f.follower_id == follower_id and f.following_id == following_id:
                return False

        follower = self._profiles.get(follower_id)
        following = self._profiles.get(following_id)

        if not follower or not following:
            return False

        # Check limits
        if follower.following_count >= self.config.max_following:
            return False
        if following.followers_count >= self.config.max_followers:
            return False

        rel = FollowRelationship(
            follower_id=follower_id,
            following_id=following_id,
        )
        self._follows.append(rel)
        follower.following_count += 1
        following.followers_count += 1

        logger.info("User %s followed %s", follower_id, following_id)
        return True

    def unfollow(self, follower_id: str, following_id: str) -> bool:
        """Unfollow a trader.

        Args:
            follower_id: User who wants to unfollow.
            following_id: User to unfollow.

        Returns:
            True if unfollow was successful.
        """
        for i, f in enumerate(self._follows):
            if f.follower_id == follower_id and f.following_id == following_id:
                self._follows.pop(i)
                follower = self._profiles.get(follower_id)
                following = self._profiles.get(following_id)
                if follower:
                    follower.following_count = max(0, follower.following_count - 1)
                if following:
                    following.followers_count = max(0, following.followers_count - 1)
                return True
        return False

    def get_followers(self, user_id: str) -> list[str]:
        """Get list of follower user IDs.

        Args:
            user_id: User to get followers for.

        Returns:
            List of follower user IDs.
        """
        return [f.follower_id for f in self._follows if f.following_id == user_id]

    def get_following(self, user_id: str) -> list[str]:
        """Get list of user IDs being followed.

        Args:
            user_id: User to get following list for.

        Returns:
            List of following user IDs.
        """
        return [f.following_id for f in self._follows if f.follower_id == user_id]

    def is_following(self, follower_id: str, following_id: str) -> bool:
        """Check if a user is following another."""
        return any(
            f.follower_id == follower_id and f.following_id == following_id
            for f in self._follows
        )

    def search_profiles(
        self,
        query: Optional[str] = None,
        trading_style: Optional[TradingStyle] = None,
        min_sharpe: Optional[float] = None,
        has_badge: Optional[Badge] = None,
        limit: int = 20,
    ) -> list[TraderProfile]:
        """Search for trader profiles.

        Args:
            query: Text search in display name or bio.
            trading_style: Filter by trading style.
            min_sharpe: Minimum Sharpe ratio.
            has_badge: Must have this badge.
            limit: Max results.

        Returns:
            List of matching profiles.
        """
        results = [
            p for p in self._profiles.values()
            if p.visibility == ProfileVisibility.PUBLIC
        ]

        if query:
            q = query.lower()
            results = [
                p for p in results
                if q in p.display_name.lower() or q in p.bio.lower()
            ]

        if trading_style:
            results = [p for p in results if p.trading_style == trading_style]

        if min_sharpe is not None:
            results = [p for p in results if p.stats.sharpe_ratio >= min_sharpe]

        if has_badge:
            results = [p for p in results if has_badge in p.badges]

        # Sort by followers (most popular first)
        results.sort(key=lambda p: p.followers_count, reverse=True)
        return results[:limit]

    def get_all_profiles(self) -> list[TraderProfile]:
        """Get all profiles."""
        return list(self._profiles.values())

    def rate_trader(self, user_id: str, rating: float) -> Optional[TraderProfile]:
        """Rate a trader.

        Args:
            user_id: Trader to rate.
            rating: Rating value (1-5).

        Returns:
            Updated profile, or None if not found.
        """
        profile = self._profiles.get(user_id)
        if not profile:
            return None
        profile.update_rating(rating)
        return profile
