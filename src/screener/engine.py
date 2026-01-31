"""Screening Engine.

Core engine for running stock screens.
"""

import time
from typing import Any, Optional
import logging

from src.screener.config import (
    ScreenerConfig,
    DEFAULT_SCREENER_CONFIG,
    Universe,
    SortOrder,
    DEFAULT_COLUMNS,
)
from src.screener.models import (
    Screen,
    ScreenResult,
    ScreenMatch,
    FilterCondition,
    CustomFormula,
)
from src.screener.filters import FILTER_REGISTRY, FilterRegistry
from src.screener.expression import ExpressionParser

logger = logging.getLogger(__name__)


class ScreenerEngine:
    """Stock screening engine.
    
    Runs screens against stock universe with support for:
    - Built-in filters
    - Custom formulas
    - Universe filtering
    - Sorting and pagination
    
    Example:
        engine = ScreenerEngine()
        result = engine.run_screen(screen, stock_data)
    """
    
    def __init__(
        self,
        config: Optional[ScreenerConfig] = None,
        filter_registry: Optional[FilterRegistry] = None,
    ):
        self.config = config or DEFAULT_SCREENER_CONFIG
        self.filter_registry = filter_registry or FILTER_REGISTRY
        self.expression_parser = ExpressionParser()
    
    def run_screen(
        self,
        screen: Screen,
        stock_data: dict[str, dict[str, Any]],
    ) -> ScreenResult:
        """Run a screen against stock data.
        
        Args:
            screen: Screen configuration.
            stock_data: Dict of symbol -> metrics dict.
            
        Returns:
            ScreenResult with matching stocks.
        """
        start_time = time.time()
        
        # Filter universe
        universe = self._filter_universe(screen, stock_data)
        
        # Apply filters
        matches = []
        for symbol, data in universe.items():
            if self._matches_screen(screen, data):
                match = self._create_match(symbol, data, screen)
                matches.append(match)
        
        # Sort results
        matches = self._sort_matches(matches, screen.sort_by, screen.sort_order)
        
        # Limit results
        matches = matches[:screen.max_results]
        
        execution_time = (time.time() - start_time) * 1000
        
        return ScreenResult(
            screen_id=screen.screen_id,
            screen_name=screen.name,
            total_universe=len(universe),
            matches=len(matches),
            stocks=matches,
            filters_applied=len(screen.filters) + len(screen.custom_formulas),
            execution_time_ms=execution_time,
        )
    
    def _filter_universe(
        self,
        screen: Screen,
        stock_data: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Filter stock universe based on screen settings."""
        filtered = {}
        
        for symbol, data in stock_data.items():
            # Skip excluded symbols
            if symbol in screen.exclude_symbols:
                continue
            
            # Sector filter
            if screen.sectors:
                stock_sector = data.get("sector", "")
                if stock_sector not in screen.sectors:
                    continue
            
            # Industry filter
            if screen.industries:
                stock_industry = data.get("industry", "")
                if stock_industry not in screen.industries:
                    continue
            
            # Market cap filter
            market_cap = data.get("market_cap", 0)
            if screen.market_cap_min and market_cap < screen.market_cap_min:
                continue
            if screen.market_cap_max and market_cap > screen.market_cap_max:
                continue
            
            # Universe filter (simplified - in production would use index membership)
            if screen.universe != Universe.ALL:
                # Would check index membership here
                pass
            
            filtered[symbol] = data
        
        return filtered
    
    def _matches_screen(
        self,
        screen: Screen,
        data: dict[str, Any],
    ) -> bool:
        """Check if stock data matches all screen criteria."""
        # Check built-in filters
        for filter_cond in screen.filters:
            filter_def = self.filter_registry.get_filter(filter_cond.filter_id)
            if not filter_def:
                logger.warning(f"Unknown filter: {filter_cond.filter_id}")
                continue
            
            # Get actual value
            actual_value = data.get(filter_cond.filter_id) or data.get(filter_def.expression_name)
            
            # Evaluate condition
            if not filter_cond.evaluate(actual_value):
                return False
        
        # Check custom formulas
        for formula in screen.custom_formulas:
            if not formula.is_valid:
                continue
            
            try:
                result = self.expression_parser.evaluate(formula.expression, data)
                if not result:
                    return False
            except Exception as e:
                logger.warning(f"Formula evaluation error: {e}")
                return False
        
        return True
    
    def _create_match(
        self,
        symbol: str,
        data: dict[str, Any],
        screen: Screen,
    ) -> ScreenMatch:
        """Create a screen match from stock data."""
        return ScreenMatch(
            symbol=symbol,
            name=data.get("name", symbol),
            sector=data.get("sector", ""),
            industry=data.get("industry", ""),
            price=data.get("price", 0.0),
            market_cap=data.get("market_cap", 0.0),
            metrics=data,
            matched_filters=[f.filter_id for f in screen.filters],
        )
    
    def _sort_matches(
        self,
        matches: list[ScreenMatch],
        sort_by: str,
        sort_order: SortOrder,
    ) -> list[ScreenMatch]:
        """Sort screen matches."""
        reverse = sort_order == SortOrder.DESC
        
        def get_sort_key(match: ScreenMatch) -> Any:
            if sort_by == "symbol":
                return match.symbol
            elif sort_by == "name":
                return match.name
            elif sort_by == "price":
                return match.price or 0
            elif sort_by == "market_cap":
                return match.market_cap or 0
            else:
                return match.metrics.get(sort_by, 0) or 0
        
        return sorted(matches, key=get_sort_key, reverse=reverse)
    
    def validate_screen(self, screen: Screen) -> tuple[bool, list[str]]:
        """Validate a screen configuration.
        
        Args:
            screen: Screen to validate.
            
        Returns:
            Tuple of (is_valid, error_messages).
        """
        errors = []
        
        # Validate filters
        for filter_cond in screen.filters:
            filter_def = self.filter_registry.get_filter(filter_cond.filter_id)
            if not filter_def:
                errors.append(f"Unknown filter: {filter_cond.filter_id}")
        
        # Validate custom formulas
        for formula in screen.custom_formulas:
            is_valid, error = self.expression_parser.validate(formula.expression)
            if not is_valid:
                errors.append(f"Invalid formula '{formula.name}': {error}")
                formula.is_valid = False
                formula.validation_error = error
            else:
                formula.is_valid = True
        
        return len(errors) == 0, errors
    
    def get_available_filters(self) -> list[dict]:
        """Get list of available filters for UI."""
        filters = []
        for f in self.filter_registry.get_all_filters():
            filters.append({
                "id": f.filter_id,
                "name": f.name,
                "category": f.category.value,
                "type": f.data_type.value,
                "description": f.description,
                "unit": f.unit,
                "min": f.min_value,
                "max": f.max_value,
            })
        return filters


class ScreenManager:
    """Manages saved screens.
    
    Handles CRUD operations for screens.
    
    Example:
        manager = ScreenManager()
        manager.save_screen(screen)
        screens = manager.get_screens_by_user(user_id)
    """
    
    def __init__(self):
        self._screens: dict[str, Screen] = {}
    
    def save_screen(self, screen: Screen) -> str:
        """Save a screen configuration.
        
        Args:
            screen: Screen to save.
            
        Returns:
            Screen ID.
        """
        self._screens[screen.screen_id] = screen
        return screen.screen_id
    
    def get_screen(self, screen_id: str) -> Optional[Screen]:
        """Get a screen by ID."""
        return self._screens.get(screen_id)
    
    def delete_screen(self, screen_id: str) -> bool:
        """Delete a screen.
        
        Returns:
            True if deleted, False if not found.
        """
        if screen_id in self._screens:
            del self._screens[screen_id]
            return True
        return False
    
    def get_screens_by_user(self, user_id: str) -> list[Screen]:
        """Get all screens created by a user."""
        return [s for s in self._screens.values() if s.created_by == user_id]
    
    def get_public_screens(self) -> list[Screen]:
        """Get all public screens."""
        return [s for s in self._screens.values() if s.is_public]
    
    def search_screens(self, query: str) -> list[Screen]:
        """Search screens by name or description."""
        query = query.lower()
        return [
            s for s in self._screens.values()
            if query in s.name.lower() or (s.description and query in s.description.lower())
        ]
    
    def duplicate_screen(self, screen_id: str, new_name: str) -> Optional[Screen]:
        """Duplicate an existing screen.
        
        Args:
            screen_id: Screen to duplicate.
            new_name: Name for the new screen.
            
        Returns:
            New screen or None if not found.
        """
        original = self.get_screen(screen_id)
        if not original:
            return None
        
        from dataclasses import replace
        new_screen = replace(
            original,
            screen_id=Screen().screen_id,  # New ID
            name=new_name,
            is_public=False,
            is_preset=False,
        )
        self.save_screen(new_screen)
        return new_screen
