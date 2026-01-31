"""Scanner Engine.

Core scanning functionality for detecting trading setups.
"""

from datetime import datetime, timezone
from typing import Optional, Callable
import logging

from src.scanner.config import (
    ScannerConfig,
    DEFAULT_SCANNER_CONFIG,
    Operator,
    Universe,
    SCAN_FIELDS,
)
from src.scanner.models import (
    Scanner,
    ScanCriterion,
    ScanResult,
    ScanAlert,
)

logger = logging.getLogger(__name__)


class ScannerEngine:
    """Core scanner engine.
    
    Runs scans against market data to find trading opportunities.
    
    Example:
        engine = ScannerEngine()
        
        # Create a gap up scanner
        scanner = Scanner(
            name="Gap Up >3%",
            criteria=[
                ScanCriterion(field="gap_pct", operator=Operator.GT, value=3.0)
            ]
        )
        
        results = engine.run_scan(scanner, market_data)
    """
    
    def __init__(self, config: Optional[ScannerConfig] = None):
        self.config = config or DEFAULT_SCANNER_CONFIG
        self._scanners: dict[str, Scanner] = {}
        self._results: dict[str, list[ScanResult]] = {}  # scanner_id -> results
        self._alert_subscribers: list[Callable[[ScanAlert], None]] = []
    
    def subscribe_alerts(self, callback: Callable[[ScanAlert], None]) -> None:
        """Subscribe to scan alerts."""
        self._alert_subscribers.append(callback)
    
    def _notify_alert(self, alert: ScanAlert) -> None:
        """Notify subscribers of an alert."""
        for callback in self._alert_subscribers:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    # =========================================================================
    # Scanner CRUD
    # =========================================================================
    
    def add_scanner(self, scanner: Scanner) -> None:
        """Add a scanner."""
        self._scanners[scanner.scanner_id] = scanner
        self._results[scanner.scanner_id] = []
    
    def get_scanner(self, scanner_id: str) -> Optional[Scanner]:
        """Get scanner by ID."""
        return self._scanners.get(scanner_id)
    
    def get_all_scanners(self) -> list[Scanner]:
        """Get all scanners."""
        return list(self._scanners.values())
    
    def get_active_scanners(self) -> list[Scanner]:
        """Get active scanners."""
        return [s for s in self._scanners.values() if s.is_active]
    
    def update_scanner(self, scanner: Scanner) -> None:
        """Update a scanner."""
        if scanner.scanner_id in self._scanners:
            self._scanners[scanner.scanner_id] = scanner
    
    def delete_scanner(self, scanner_id: str) -> bool:
        """Delete a scanner."""
        if scanner_id in self._scanners:
            del self._scanners[scanner_id]
            if scanner_id in self._results:
                del self._results[scanner_id]
            return True
        return False
    
    def toggle_scanner(self, scanner_id: str) -> bool:
        """Toggle scanner active state."""
        scanner = self._scanners.get(scanner_id)
        if scanner:
            scanner.is_active = not scanner.is_active
            return scanner.is_active
        return False
    
    # =========================================================================
    # Scanning
    # =========================================================================
    
    def run_scan(
        self,
        scanner: Scanner,
        market_data: dict[str, dict],
    ) -> list[ScanResult]:
        """Run a single scan.
        
        Args:
            scanner: Scanner configuration.
            market_data: Dict of symbol -> data dict.
            
        Returns:
            List of ScanResults.
        """
        results = []
        
        # Filter universe
        symbols = self._filter_universe(scanner, market_data)
        
        for symbol in symbols:
            data = market_data.get(symbol)
            if not data:
                continue
            
            # Apply pre-filters
            if not self._passes_filters(scanner, data):
                continue
            
            # Check all criteria
            matched_criteria = []
            all_matched = True
            
            for criterion in scanner.criteria:
                if criterion.evaluate(data):
                    matched_criteria.append(self._describe_criterion(criterion))
                else:
                    all_matched = False
                    break
            
            if all_matched and matched_criteria:
                result = ScanResult(
                    scanner_id=scanner.scanner_id,
                    scanner_name=scanner.name,
                    symbol=symbol,
                    company_name=data.get("name", ""),
                    matched_criteria=matched_criteria,
                    price=data.get("price", 0),
                    change=data.get("change", 0),
                    change_pct=data.get("change_pct", 0),
                    volume=data.get("volume", 0),
                    relative_volume=data.get("relative_volume", 0),
                    signal_strength=self._calculate_signal_strength(scanner, data),
                    sector=data.get("sector", ""),
                    market_cap=data.get("market_cap", 0),
                )
                results.append(result)
        
        # Sort by signal strength
        results.sort(key=lambda r: r.signal_strength, reverse=True)
        
        # Limit results
        results = results[:scanner.max_results]
        
        # Update scanner state
        scanner.last_scan = datetime.now(timezone.utc)
        scanner.last_result_count = len(results)
        
        # Store results
        self._results[scanner.scanner_id] = results
        
        # Generate alerts for new results
        if self.config.enable_alerts and results:
            self._generate_alerts(scanner, results)
        
        return results
    
    def run_all_scans(
        self,
        market_data: dict[str, dict],
    ) -> dict[str, list[ScanResult]]:
        """Run all active scanners.
        
        Args:
            market_data: Dict of symbol -> data dict.
            
        Returns:
            Dict of scanner_id -> results.
        """
        all_results = {}
        
        for scanner in self.get_active_scanners():
            results = self.run_scan(scanner, market_data)
            all_results[scanner.scanner_id] = results
        
        return all_results
    
    def _filter_universe(
        self,
        scanner: Scanner,
        market_data: dict[str, dict],
    ) -> list[str]:
        """Filter symbols based on universe setting."""
        all_symbols = list(market_data.keys())
        
        if scanner.universe == Universe.CUSTOM and scanner.universe_symbols:
            return [s for s in scanner.universe_symbols if s in all_symbols]
        
        # For other universes, we'd need external data
        # For now, return all symbols
        return all_symbols
    
    def _passes_filters(self, scanner: Scanner, data: dict) -> bool:
        """Check if data passes scanner filters."""
        price = data.get("price", 0)
        volume = data.get("volume", 0)
        market_cap = data.get("market_cap", 0)
        sector = data.get("sector", "")
        
        # Price filter
        if price < scanner.min_price:
            return False
        if scanner.max_price and price > scanner.max_price:
            return False
        
        # Volume filter
        if volume < scanner.min_volume:
            return False
        
        # Market cap filter
        if scanner.min_market_cap and market_cap < scanner.min_market_cap:
            return False
        
        # Sector filter
        if scanner.sectors and sector not in scanner.sectors:
            return False
        
        return True
    
    def _describe_criterion(self, criterion: ScanCriterion) -> str:
        """Generate human-readable description of criterion."""
        field_name = SCAN_FIELDS.get(criterion.field, criterion.field)
        
        if criterion.operator == Operator.GT:
            return f"{field_name} > {criterion.value}"
        elif criterion.operator == Operator.LT:
            return f"{field_name} < {criterion.value}"
        elif criterion.operator == Operator.GTE:
            return f"{field_name} >= {criterion.value}"
        elif criterion.operator == Operator.LTE:
            return f"{field_name} <= {criterion.value}"
        elif criterion.operator == Operator.BETWEEN:
            return f"{field_name} between {criterion.value}"
        elif criterion.operator == Operator.CROSSES_ABOVE:
            return f"{field_name} crosses above {criterion.value}"
        elif criterion.operator == Operator.CROSSES_BELOW:
            return f"{field_name} crosses below {criterion.value}"
        
        return f"{field_name} {criterion.operator.value} {criterion.value}"
    
    def _calculate_signal_strength(
        self,
        scanner: Scanner,
        data: dict,
    ) -> float:
        """Calculate signal strength (0-100)."""
        strength = 50.0  # Base strength
        
        # Boost for volume
        rel_vol = data.get("relative_volume", 1.0)
        if rel_vol > 2:
            strength += min(20, (rel_vol - 1) * 10)
        
        # Boost for price momentum
        change_pct = abs(data.get("change_pct", 0))
        if change_pct > 3:
            strength += min(15, change_pct * 2)
        
        # Cap at 100
        return min(100, strength)
    
    def _generate_alerts(
        self,
        scanner: Scanner,
        results: list[ScanResult],
    ) -> None:
        """Generate alerts for scan results."""
        for result in results[:5]:  # Top 5 only
            alert = ScanAlert(
                scanner_id=scanner.scanner_id,
                scanner_name=scanner.name,
                symbol=result.symbol,
                title=f"{scanner.name}: {result.symbol}",
                message=f"{result.symbol} matched: {', '.join(result.matched_criteria[:2])}",
                priority="high" if result.signal_strength > 80 else "normal",
            )
            self._notify_alert(alert)
    
    # =========================================================================
    # Results
    # =========================================================================
    
    def get_results(self, scanner_id: str) -> list[ScanResult]:
        """Get latest results for a scanner."""
        return self._results.get(scanner_id, [])
    
    def get_all_results(self) -> list[ScanResult]:
        """Get all results across all scanners."""
        all_results = []
        for results in self._results.values():
            all_results.extend(results)
        return sorted(all_results, key=lambda r: r.matched_at, reverse=True)
    
    def clear_results(self, scanner_id: Optional[str] = None) -> None:
        """Clear scan results."""
        if scanner_id:
            self._results[scanner_id] = []
        else:
            for key in self._results:
                self._results[key] = []


def create_scanner(
    name: str,
    criteria: list[tuple],
    **kwargs,
) -> Scanner:
    """Helper to create a scanner.
    
    Args:
        name: Scanner name.
        criteria: List of (field, operator, value) tuples.
        **kwargs: Additional scanner parameters.
        
    Returns:
        Scanner object.
    """
    scan_criteria = []
    for field, op, value in criteria:
        criterion = ScanCriterion(
            field=field,
            operator=op if isinstance(op, Operator) else Operator(op),
            value=value,
        )
        scan_criteria.append(criterion)
    
    return Scanner(
        name=name,
        criteria=scan_criteria,
        **kwargs,
    )
