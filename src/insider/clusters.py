"""Cluster Buying Detection.

Detect multiple insiders buying the same stock in a short period.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.insider.config import (
    InsiderConfig,
    DEFAULT_INSIDER_CONFIG,
    SignalStrength,
    TransactionType,
    InsiderType,
    CEO_BUY_MULTIPLIER,
)
from src.insider.models import (
    InsiderTransaction,
    InsiderCluster,
)
from src.insider.transactions import TransactionTracker

logger = logging.getLogger(__name__)


class ClusterDetector:
    """Detects cluster buying patterns.
    
    Cluster buying occurs when multiple insiders buy shares
    of the same company within a short time window.
    
    Example:
        detector = ClusterDetector(tracker)
        
        # Detect clusters
        clusters = detector.detect_clusters()
        
        for cluster in clusters:
            print(f"{cluster.symbol}: {cluster.insider_count} insiders, ${cluster.total_value:,.0f}")
    """
    
    def __init__(
        self,
        tracker: TransactionTracker,
        config: Optional[InsiderConfig] = None,
    ):
        self.tracker = tracker
        self.config = config or DEFAULT_INSIDER_CONFIG
        self._clusters: list[InsiderCluster] = []
    
    def detect_clusters(
        self,
        days: int = 90,
        window_days: Optional[int] = None,
        min_insiders: Optional[int] = None,
        min_value: Optional[float] = None,
    ) -> list[InsiderCluster]:
        """Detect cluster buying patterns.
        
        Args:
            days: Look back period.
            window_days: Cluster window (days between first and last transaction).
            min_insiders: Minimum number of unique insiders.
            min_value: Minimum total value.
            
        Returns:
            List of detected clusters.
        """
        window_days = window_days or self.config.cluster_window_days
        min_insiders = min_insiders or self.config.cluster_min_insiders
        min_value = min_value or self.config.cluster_min_value
        
        clusters = []
        
        # Get all symbols with recent activity
        all_transactions = self.tracker.get_recent_buys(days=days)
        symbols = set(t.symbol for t in all_transactions)
        
        for symbol in symbols:
            cluster = self._detect_cluster_for_symbol(
                symbol, days, window_days, min_insiders, min_value
            )
            if cluster:
                clusters.append(cluster)
        
        # Sort by score
        clusters.sort(key=lambda c: c.cluster_score, reverse=True)
        
        self._clusters = clusters
        return clusters
    
    def _detect_cluster_for_symbol(
        self,
        symbol: str,
        days: int,
        window_days: int,
        min_insiders: int,
        min_value: float,
    ) -> Optional[InsiderCluster]:
        """Detect cluster for a specific symbol."""
        # Get buy transactions only
        transactions = self.tracker.get_by_symbol(
            symbol, days=days, transaction_type=TransactionType.BUY
        )
        
        if len(transactions) < min_insiders:
            return None
        
        # Find clusters using sliding window
        best_cluster = None
        best_score = 0
        
        for i, start_txn in enumerate(transactions):
            if not start_txn.transaction_date:
                continue
            
            # Find transactions within window
            window_end = start_txn.transaction_date + timedelta(days=window_days)
            
            window_txns = [
                t for t in transactions
                if t.transaction_date
                and start_txn.transaction_date <= t.transaction_date <= window_end
            ]
            
            # Check if cluster criteria met
            unique_insiders = set(t.insider_name for t in window_txns)
            total_value = sum(t.value for t in window_txns)
            
            if len(unique_insiders) >= min_insiders and total_value >= min_value:
                # Calculate score
                score = self._calculate_cluster_score(window_txns, unique_insiders)
                
                if score > best_score:
                    best_score = score
                    
                    dates = [t.transaction_date for t in window_txns if t.transaction_date]
                    total_shares = sum(t.shares for t in window_txns)
                    
                    best_cluster = InsiderCluster(
                        symbol=symbol,
                        company_name=window_txns[0].company_name,
                        start_date=min(dates),
                        end_date=max(dates),
                        insider_count=len(unique_insiders),
                        insiders=list(unique_insiders),
                        transactions=window_txns,
                        total_shares=total_shares,
                        total_value=total_value,
                        avg_price=total_value / total_shares if total_shares > 0 else 0,
                        cluster_score=score,
                        signal_strength=self._score_to_strength(score),
                    )
        
        return best_cluster
    
    def _calculate_cluster_score(
        self,
        transactions: list[InsiderTransaction],
        unique_insiders: set[str],
    ) -> float:
        """Calculate cluster score (0-100)."""
        score = 0.0
        
        # Base score from insider count
        insider_count = len(unique_insiders)
        score += min(30, insider_count * 10)  # Up to 30 points
        
        # Value score
        total_value = sum(t.value for t in transactions)
        if total_value >= 1_000_000:
            score += 25
        elif total_value >= 500_000:
            score += 20
        elif total_value >= 250_000:
            score += 15
        elif total_value >= 100_000:
            score += 10
        
        # C-suite bonus
        c_suite_count = sum(
            1 for t in transactions
            if t.insider_type in {InsiderType.CEO, InsiderType.CFO, InsiderType.COO}
        )
        score += min(20, c_suite_count * 10)  # Up to 20 points
        
        # CEO specifically
        has_ceo = any(t.insider_type == InsiderType.CEO for t in transactions)
        if has_ceo:
            score += 15
        
        # Tightness bonus (shorter window = stronger signal)
        if transactions:
            dates = [t.transaction_date for t in transactions if t.transaction_date]
            if len(dates) >= 2:
                span = (max(dates) - min(dates)).days
                if span <= 3:
                    score += 10
                elif span <= 7:
                    score += 5
        
        return min(100, score)
    
    def _score_to_strength(self, score: float) -> SignalStrength:
        """Convert score to signal strength."""
        if score >= 80:
            return SignalStrength.VERY_STRONG
        elif score >= 60:
            return SignalStrength.STRONG
        elif score >= 40:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
    
    def get_clusters(
        self,
        min_score: float = 0,
        min_strength: Optional[SignalStrength] = None,
    ) -> list[InsiderCluster]:
        """Get detected clusters with optional filtering."""
        clusters = self._clusters
        
        if min_score > 0:
            clusters = [c for c in clusters if c.cluster_score >= min_score]
        
        if min_strength:
            strength_order = {
                SignalStrength.WEAK: 0,
                SignalStrength.MODERATE: 1,
                SignalStrength.STRONG: 2,
                SignalStrength.VERY_STRONG: 3,
            }
            min_level = strength_order[min_strength]
            clusters = [
                c for c in clusters
                if strength_order.get(c.signal_strength, 0) >= min_level
            ]
        
        return clusters
    
    def get_cluster_for_symbol(self, symbol: str) -> Optional[InsiderCluster]:
        """Get cluster for a specific symbol."""
        for cluster in self._clusters:
            if cluster.symbol == symbol:
                return cluster
        return None
    
    def get_strongest_clusters(self, limit: int = 10) -> list[InsiderCluster]:
        """Get strongest clusters."""
        return sorted(
            self._clusters,
            key=lambda c: c.cluster_score,
            reverse=True
        )[:limit]
