"""Query builder for audit event search and filtering."""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import EventCategory, EventOutcome
from .events import AuditEvent

logger = logging.getLogger(__name__)


class AuditQuery:
    """Builder-pattern query interface for audit events.

    Supports method chaining for composing complex queries:
        results = (AuditQuery(recorder)
            .filter_by_actor("user_42")
            .filter_by_time_range(start, end)
            .filter_by_category(EventCategory.TRADING)
            .paginate(page=1, page_size=50)
            .execute())
    """

    def __init__(self, recorder: Any) -> None:
        """Initialize query against a recorder's event store.

        Args:
            recorder: AuditRecorder instance to query.
        """
        self._recorder = recorder
        self._filters: List[Callable[[AuditEvent], bool]] = []
        self._page: Optional[int] = None
        self._page_size: int = 50
        self._sort_ascending: bool = True
        self._limit: Optional[int] = None

    def filter_by_actor(self, actor_id: str) -> "AuditQuery":
        """Filter events by actor ID.

        Args:
            actor_id: The actor identifier to match.

        Returns:
            Self for chaining.
        """
        self._filters.append(
            lambda e: e.actor is not None and e.actor.actor_id == actor_id
        )
        return self

    def filter_by_actor_type(self, actor_type: str) -> "AuditQuery":
        """Filter events by actor type.

        Args:
            actor_type: The actor type to match (e.g., "user", "system").

        Returns:
            Self for chaining.
        """
        self._filters.append(
            lambda e: e.actor is not None and e.actor.actor_type == actor_type
        )
        return self

    def filter_by_action(self, action: str) -> "AuditQuery":
        """Filter events by action name.

        Args:
            action: The action string to match (exact match).

        Returns:
            Self for chaining.
        """
        self._filters.append(lambda e: e.action == action)
        return self

    def filter_by_action_prefix(self, prefix: str) -> "AuditQuery":
        """Filter events by action prefix (e.g., "order." matches "order.create").

        Args:
            prefix: The action prefix to match.

        Returns:
            Self for chaining.
        """
        self._filters.append(lambda e: e.action.startswith(prefix))
        return self

    def filter_by_time_range(
        self, start: datetime, end: datetime
    ) -> "AuditQuery":
        """Filter events within a time range (inclusive).

        Args:
            start: Start of the time range.
            end: End of the time range.

        Returns:
            Self for chaining.
        """
        self._filters.append(
            lambda e: start <= e.timestamp <= end
        )
        return self

    def filter_by_category(self, category: EventCategory) -> "AuditQuery":
        """Filter events by category.

        Args:
            category: The EventCategory to match.

        Returns:
            Self for chaining.
        """
        self._filters.append(lambda e: e.category == category)
        return self

    def filter_by_outcome(self, outcome: EventOutcome) -> "AuditQuery":
        """Filter events by outcome.

        Args:
            outcome: The EventOutcome to match.

        Returns:
            Self for chaining.
        """
        self._filters.append(lambda e: e.outcome == outcome)
        return self

    def filter_by_resource_type(self, resource_type: str) -> "AuditQuery":
        """Filter events by resource type.

        Args:
            resource_type: The resource type to match.

        Returns:
            Self for chaining.
        """
        self._filters.append(
            lambda e: e.resource is not None
            and e.resource.resource_type == resource_type
        )
        return self

    def filter_by_resource_id(self, resource_id: str) -> "AuditQuery":
        """Filter events by resource ID.

        Args:
            resource_id: The resource identifier to match.

        Returns:
            Self for chaining.
        """
        self._filters.append(
            lambda e: e.resource is not None
            and e.resource.resource_id == resource_id
        )
        return self

    def filter(self, predicate: Callable[[AuditEvent], bool]) -> "AuditQuery":
        """Add a custom filter predicate.

        Args:
            predicate: Function that returns True for events to include.

        Returns:
            Self for chaining.
        """
        self._filters.append(predicate)
        return self

    def sort_ascending(self) -> "AuditQuery":
        """Sort results by timestamp ascending (oldest first).

        Returns:
            Self for chaining.
        """
        self._sort_ascending = True
        return self

    def sort_descending(self) -> "AuditQuery":
        """Sort results by timestamp descending (newest first).

        Returns:
            Self for chaining.
        """
        self._sort_ascending = False
        return self

    def paginate(
        self, page: int = 1, page_size: int = 50
    ) -> "AuditQuery":
        """Set pagination parameters.

        Args:
            page: Page number (1-based).
            page_size: Number of results per page.

        Returns:
            Self for chaining.
        """
        self._page = max(1, page)
        self._page_size = max(1, page_size)
        return self

    def limit(self, n: int) -> "AuditQuery":
        """Limit total results returned.

        Args:
            n: Maximum number of results.

        Returns:
            Self for chaining.
        """
        self._limit = n
        return self

    def execute(self) -> List[AuditEvent]:
        """Execute the query and return matching events.

        Returns:
            List of AuditEvent objects matching all filters.
        """
        all_events = self._recorder.get_all_events()

        # Apply all filters
        results = all_events
        for f in self._filters:
            results = [e for e in results if f(e)]

        # Sort
        results.sort(key=lambda e: e.timestamp, reverse=not self._sort_ascending)

        # Apply limit
        if self._limit is not None:
            results = results[: self._limit]

        # Apply pagination
        if self._page is not None:
            start = (self._page - 1) * self._page_size
            end = start + self._page_size
            results = results[start:end]

        logger.debug("Audit query returned %d results", len(results))
        return results

    def count(self) -> int:
        """Execute the query and return only the count of matching events.

        Returns:
            Number of matching events (before pagination).
        """
        all_events = self._recorder.get_all_events()
        results = all_events
        for f in self._filters:
            results = [e for e in results if f(e)]
        return len(results)
