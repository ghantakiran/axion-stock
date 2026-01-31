"""Social feed management.

Trade ideas, commentary, interactions, and trending content.
"""

import logging
from collections import defaultdict
from typing import Optional

from src.social.config import (
    PostType,
    InteractionType,
    SocialConfig,
    DEFAULT_SOCIAL_CONFIG,
)
from src.social.models import (
    SocialPost,
    SocialInteraction,
    _utc_now,
)

logger = logging.getLogger(__name__)


class FeedManager:
    """Manages the social feed, posts, and interactions.

    Features:
    - Post creation with content validation
    - Like, comment, bookmark interactions
    - Trending detection
    - Feed curation (following-based and global)
    """

    def __init__(self, config: Optional[SocialConfig] = None) -> None:
        self.config = config or DEFAULT_SOCIAL_CONFIG
        self._posts: dict[str, SocialPost] = {}
        self._interactions: dict[str, list[SocialInteraction]] = defaultdict(list)
        self._user_post_counts: dict[str, int] = defaultdict(int)

    def create_post(
        self,
        user_id: str,
        display_name: str,
        post_type: PostType,
        content: str,
        symbol: Optional[str] = None,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        direction: Optional[str] = None,
    ) -> SocialPost:
        """Create a new social post.

        Args:
            user_id: Author user ID.
            display_name: Author display name.
            post_type: Type of post.
            content: Post text content.
            symbol: Related symbol (for trade ideas).
            target_price: Target price (for trade ideas).
            stop_loss: Stop loss (for trade ideas).
            direction: 'long' or 'short' (for trade ideas).

        Returns:
            Created SocialPost.

        Raises:
            ValueError: If content exceeds max length or daily limit hit.
        """
        feed_config = self.config.feed

        if len(content) > feed_config.max_post_length:
            raise ValueError(
                f"Content exceeds max length ({feed_config.max_post_length})"
            )

        if self._user_post_counts[user_id] >= feed_config.max_posts_per_day:
            raise ValueError(
                f"Daily post limit reached ({feed_config.max_posts_per_day})"
            )

        post = SocialPost(
            user_id=user_id,
            display_name=display_name,
            post_type=post_type,
            content=content,
            symbol=symbol,
            target_price=target_price,
            stop_loss=stop_loss,
            direction=direction,
        )

        self._posts[post.post_id] = post
        self._user_post_counts[user_id] += 1
        logger.info(
            "User %s created %s post: %s",
            user_id, post_type.value, post.post_id,
        )
        return post

    def get_post(self, post_id: str) -> Optional[SocialPost]:
        """Get a post by ID."""
        return self._posts.get(post_id)

    def delete_post(self, post_id: str) -> bool:
        """Delete a post.

        Args:
            post_id: Post to delete.

        Returns:
            True if found and deleted.
        """
        if post_id in self._posts:
            del self._posts[post_id]
            self._interactions.pop(post_id, None)
            return True
        return False

    def like_post(self, post_id: str, user_id: str) -> bool:
        """Like a post.

        Args:
            post_id: Post to like.
            user_id: User liking the post.

        Returns:
            True if successful.
        """
        return self._add_interaction(
            post_id, user_id, InteractionType.LIKE,
        )

    def comment_on_post(
        self,
        post_id: str,
        user_id: str,
        comment_text: str,
    ) -> Optional[SocialInteraction]:
        """Comment on a post.

        Args:
            post_id: Post to comment on.
            user_id: User commenting.
            comment_text: Comment text.

        Returns:
            Created interaction, or None if post not found.
        """
        post = self._posts.get(post_id)
        if not post:
            return None

        feed_config = self.config.feed
        existing_comments = [
            i for i in self._interactions.get(post_id, [])
            if i.interaction_type == InteractionType.COMMENT
        ]
        if len(existing_comments) >= feed_config.max_comments_per_post:
            return None

        interaction = SocialInteraction(
            post_id=post_id,
            user_id=user_id,
            interaction_type=InteractionType.COMMENT,
            comment_text=comment_text,
        )

        self._interactions[post_id].append(interaction)
        post.comments_count += 1
        return interaction

    def bookmark_post(self, post_id: str, user_id: str) -> bool:
        """Bookmark a post.

        Args:
            post_id: Post to bookmark.
            user_id: User bookmarking.

        Returns:
            True if successful.
        """
        return self._add_interaction(
            post_id, user_id, InteractionType.BOOKMARK,
        )

    def _add_interaction(
        self,
        post_id: str,
        user_id: str,
        interaction_type: InteractionType,
    ) -> bool:
        """Add an interaction to a post.

        Args:
            post_id: Post ID.
            user_id: User ID.
            interaction_type: Type of interaction.

        Returns:
            True if successful.
        """
        post = self._posts.get(post_id)
        if not post:
            return False

        # Check for duplicate (user can only like/bookmark once)
        if interaction_type in (InteractionType.LIKE, InteractionType.BOOKMARK):
            for existing in self._interactions.get(post_id, []):
                if (
                    existing.user_id == user_id
                    and existing.interaction_type == interaction_type
                ):
                    return False

        interaction = SocialInteraction(
            post_id=post_id,
            user_id=user_id,
            interaction_type=interaction_type,
        )

        self._interactions[post_id].append(interaction)

        if interaction_type == InteractionType.LIKE:
            post.likes_count += 1
        elif interaction_type == InteractionType.BOOKMARK:
            post.bookmarks_count += 1

        return True

    def get_comments(self, post_id: str) -> list[SocialInteraction]:
        """Get comments for a post.

        Args:
            post_id: Post ID.

        Returns:
            List of comment interactions.
        """
        return [
            i for i in self._interactions.get(post_id, [])
            if i.interaction_type == InteractionType.COMMENT
        ]

    def get_bookmarks(self, user_id: str) -> list[SocialPost]:
        """Get bookmarked posts for a user.

        Args:
            user_id: User ID.

        Returns:
            List of bookmarked posts.
        """
        bookmarked_post_ids = set()
        for post_id, interactions in self._interactions.items():
            for i in interactions:
                if i.user_id == user_id and i.interaction_type == InteractionType.BOOKMARK:
                    bookmarked_post_ids.add(post_id)

        return [
            self._posts[pid] for pid in bookmarked_post_ids
            if pid in self._posts
        ]

    def get_global_feed(
        self,
        post_type: Optional[PostType] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> list[SocialPost]:
        """Get the global feed (all posts, newest first).

        Args:
            post_type: Filter by post type.
            symbol: Filter by symbol.
            limit: Max posts.

        Returns:
            List of posts.
        """
        posts = list(self._posts.values())

        if post_type:
            posts = [p for p in posts if p.post_type == post_type]

        if symbol:
            posts = [p for p in posts if p.symbol == symbol]

        posts.sort(key=lambda p: p.created_at, reverse=True)
        return posts[:limit]

    def get_user_feed(
        self,
        following_ids: list[str],
        limit: int = 50,
    ) -> list[SocialPost]:
        """Get personalized feed based on followed users.

        Args:
            following_ids: User IDs being followed.
            limit: Max posts.

        Returns:
            List of posts from followed users.
        """
        following_set = set(following_ids)
        posts = [
            p for p in self._posts.values()
            if p.user_id in following_set
        ]
        posts.sort(key=lambda p: p.created_at, reverse=True)
        return posts[:limit]

    def get_trending(self, limit: int = 10) -> list[SocialPost]:
        """Get trending posts by total interactions.

        Args:
            limit: Max posts.

        Returns:
            List of trending posts.
        """
        posts = list(self._posts.values())

        # Score = likes + 2*comments + bookmarks
        def score(post: SocialPost) -> int:
            return post.likes_count + 2 * post.comments_count + post.bookmarks_count

        posts.sort(key=score, reverse=True)

        trending = posts[:limit]
        for p in trending:
            p.is_trending = True

        return trending

    def get_user_posts(self, user_id: str) -> list[SocialPost]:
        """Get all posts by a user.

        Args:
            user_id: User ID.

        Returns:
            List of posts.
        """
        return [
            p for p in self._posts.values()
            if p.user_id == user_id
        ]

    def get_stats(self) -> dict:
        """Get feed statistics."""
        all_posts = list(self._posts.values())
        total_interactions = sum(
            len(ints) for ints in self._interactions.values()
        )
        return {
            "total_posts": len(all_posts),
            "total_interactions": total_interactions,
            "posts_by_type": {
                pt.value: sum(1 for p in all_posts if p.post_type == pt)
                for pt in PostType
            },
        }
