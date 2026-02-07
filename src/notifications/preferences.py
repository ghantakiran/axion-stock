"""User notification preferences management."""

from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

from src.notifications.config import (
    NotificationCategory,
    NotificationPriority,
    NotificationConfig,
    DEFAULT_NOTIFICATION_CONFIG,
    CATEGORY_CONFIGS,
)
from src.notifications.models import NotificationPreference


class PreferenceManager:
    """Manages user notification preferences."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or DEFAULT_NOTIFICATION_CONFIG
        # user_id -> category -> preference
        self._preferences: dict[str, dict[NotificationCategory, NotificationPreference]] = defaultdict(dict)
        # Rate limiting: user_id -> category -> count in current hour
        self._hourly_counts: dict[str, dict[NotificationCategory, int]] = defaultdict(lambda: defaultdict(int))
        self._hourly_window_start: dict[str, datetime] = {}

    def get_preference(
        self,
        user_id: str,
        category: NotificationCategory,
    ) -> NotificationPreference:
        """Get user preference for a category, creating default if not exists."""
        user_prefs = self._preferences.get(user_id, {})

        if category in user_prefs:
            return user_prefs[category]

        # Create default preference
        category_config = CATEGORY_CONFIGS.get(category, {})
        default_pref = NotificationPreference(
            user_id=user_id,
            category=category,
            enabled=category_config.get("default_enabled", True),
            priority=category_config.get("default_priority", NotificationPriority.NORMAL),
        )

        self._preferences[user_id][category] = default_pref
        return default_pref

    def get_all_preferences(self, user_id: str) -> list[NotificationPreference]:
        """Get all preferences for a user."""
        return [self.get_preference(user_id, cat) for cat in NotificationCategory]

    def update_preference(
        self,
        user_id: str,
        category: NotificationCategory,
        enabled: Optional[bool] = None,
        priority: Optional[NotificationPriority] = None,
        channels: Optional[list[str]] = None,
        quiet_hours_enabled: Optional[bool] = None,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
        timezone: Optional[str] = None,
        max_per_hour: Optional[int] = None,
    ) -> NotificationPreference:
        """Update user preference for a category."""
        pref = self.get_preference(user_id, category)

        if enabled is not None:
            pref.enabled = enabled
        if priority is not None:
            pref.priority = priority
        if channels is not None:
            pref.channels = channels
        if quiet_hours_enabled is not None:
            pref.quiet_hours_enabled = quiet_hours_enabled
        if quiet_hours_start is not None:
            pref.quiet_hours_start = quiet_hours_start
        if quiet_hours_end is not None:
            pref.quiet_hours_end = quiet_hours_end
        if timezone is not None:
            pref.timezone = timezone
        if max_per_hour is not None:
            pref.max_per_hour = max_per_hour

        return pref

    def set_quiet_hours(
        self,
        user_id: str,
        start: str,
        end: str,
        timezone: str = "UTC",
        categories: Optional[list[NotificationCategory]] = None,
    ) -> int:
        """Set quiet hours for all or specific categories."""
        if categories is None:
            categories = list(NotificationCategory)

        count = 0
        for category in categories:
            self.update_preference(
                user_id=user_id,
                category=category,
                quiet_hours_enabled=True,
                quiet_hours_start=start,
                quiet_hours_end=end,
                timezone=timezone,
            )
            count += 1

        return count

    def disable_quiet_hours(
        self,
        user_id: str,
        categories: Optional[list[NotificationCategory]] = None,
    ) -> int:
        """Disable quiet hours for all or specific categories."""
        if categories is None:
            categories = list(NotificationCategory)

        count = 0
        for category in categories:
            self.update_preference(
                user_id=user_id,
                category=category,
                quiet_hours_enabled=False,
            )
            count += 1

        return count

    def enable_category(self, user_id: str, category: NotificationCategory) -> NotificationPreference:
        """Enable notifications for a category."""
        return self.update_preference(user_id, category, enabled=True)

    def disable_category(self, user_id: str, category: NotificationCategory) -> NotificationPreference:
        """Disable notifications for a category."""
        return self.update_preference(user_id, category, enabled=False)

    def enable_all(self, user_id: str) -> int:
        """Enable all notification categories."""
        count = 0
        for category in NotificationCategory:
            self.enable_category(user_id, category)
            count += 1
        return count

    def disable_all(self, user_id: str) -> int:
        """Disable all notification categories (mute)."""
        count = 0
        for category in NotificationCategory:
            self.disable_category(user_id, category)
            count += 1
        return count

    def is_notification_allowed(
        self,
        user_id: str,
        category: NotificationCategory,
        current_time: Optional[datetime] = None,
    ) -> tuple[bool, str]:
        """Check if notification is allowed based on preferences.

        Returns (allowed, reason) tuple.
        """
        pref = self.get_preference(user_id, category)
        current_time = current_time or datetime.now(timezone.utc)

        # Check if enabled
        if not pref.enabled:
            return False, "category_disabled"

        # Check quiet hours
        if pref.is_in_quiet_hours(current_time):
            return False, "quiet_hours"

        # Check rate limit
        if pref.max_per_hour:
            if not self._check_rate_limit(user_id, category, pref.max_per_hour):
                return False, "rate_limit_exceeded"

        return True, "allowed"

    def _check_rate_limit(
        self,
        user_id: str,
        category: NotificationCategory,
        max_per_hour: int,
    ) -> bool:
        """Check if under rate limit."""
        now = datetime.now(timezone.utc)

        # Reset hourly count if new hour
        if user_id in self._hourly_window_start:
            window_start = self._hourly_window_start[user_id]
            if (now - window_start).total_seconds() > 3600:
                self._hourly_counts[user_id] = defaultdict(int)
                self._hourly_window_start[user_id] = now
        else:
            self._hourly_window_start[user_id] = now

        current_count = self._hourly_counts[user_id][category]
        return current_count < max_per_hour

    def record_notification_sent(self, user_id: str, category: NotificationCategory) -> None:
        """Record that a notification was sent (for rate limiting)."""
        now = datetime.now(timezone.utc)

        # Initialize window if needed
        if user_id not in self._hourly_window_start:
            self._hourly_window_start[user_id] = now
            self._hourly_counts[user_id] = defaultdict(int)
        elif (now - self._hourly_window_start[user_id]).total_seconds() > 3600:
            # Reset for new hour
            self._hourly_window_start[user_id] = now
            self._hourly_counts[user_id] = defaultdict(int)

        self._hourly_counts[user_id][category] += 1

    def get_enabled_categories(self, user_id: str) -> list[NotificationCategory]:
        """Get list of enabled categories for a user."""
        return [cat for cat in NotificationCategory if self.get_preference(user_id, cat).enabled]

    def get_disabled_categories(self, user_id: str) -> list[NotificationCategory]:
        """Get list of disabled categories for a user."""
        return [cat for cat in NotificationCategory if not self.get_preference(user_id, cat).enabled]

    def export_preferences(self, user_id: str) -> dict:
        """Export all preferences as JSON-serializable dict."""
        return {
            "user_id": user_id,
            "preferences": [pref.to_dict() for pref in self.get_all_preferences(user_id)],
        }

    def import_preferences(self, user_id: str, data: list[dict]) -> int:
        """Import preferences from dict."""
        count = 0
        for pref_data in data:
            try:
                category = NotificationCategory(pref_data.get("category"))
                self.update_preference(
                    user_id=user_id,
                    category=category,
                    enabled=pref_data.get("enabled"),
                    priority=NotificationPriority(pref_data.get("priority", "normal")),
                    channels=pref_data.get("channels"),
                    quiet_hours_enabled=pref_data.get("quiet_hours_enabled"),
                    quiet_hours_start=pref_data.get("quiet_hours_start"),
                    quiet_hours_end=pref_data.get("quiet_hours_end"),
                    timezone=pref_data.get("timezone"),
                    max_per_hour=pref_data.get("max_per_hour"),
                )
                count += 1
            except (ValueError, KeyError):
                continue

        return count

    def reset_to_defaults(self, user_id: str) -> int:
        """Reset all preferences to defaults."""
        if user_id in self._preferences:
            del self._preferences[user_id]

        count = 0
        for category in NotificationCategory:
            self.get_preference(user_id, category)  # Creates default
            count += 1

        return count
