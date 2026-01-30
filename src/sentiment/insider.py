"""Insider Trading Signal Analysis.

Analyzes SEC Form 4 filings to extract insider buying/selling
patterns and generate trading signals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.sentiment.config import InsiderConfig

logger = logging.getLogger(__name__)


@dataclass
class InsiderFiling:
    """Single SEC Form 4 insider filing."""

    symbol: str = ""
    insider_name: str = ""
    insider_title: str = ""  # CEO, CFO, Director, VP, etc.
    transaction_type: str = ""  # P=purchase, S=sale
    shares: int = 0
    price: float = 0.0
    value: float = 0.0
    filing_date: str = ""
    is_10b5_1: bool = False  # Pre-planned sale

    @property
    def is_purchase(self) -> bool:
        return self.transaction_type.upper() == "P"

    @property
    def is_sale(self) -> bool:
        return self.transaction_type.upper() == "S"

    @property
    def is_c_suite(self) -> bool:
        title = self.insider_title.upper()
        return any(t in title for t in ["CEO", "CFO", "CTO", "COO", "PRESIDENT", "CHIEF"])

    @property
    def is_director(self) -> bool:
        return "DIRECTOR" in self.insider_title.upper()


@dataclass
class InsiderReport:
    """Insider activity report for a symbol."""

    symbol: str = ""
    buy_count: int = 0
    sell_count: int = 0
    net_shares: int = 0
    net_value: float = 0.0
    cluster_buy: bool = False
    cluster_sell: bool = False
    ceo_activity: list = field(default_factory=list)
    insider_score: float = 0.0  # -1 to +1
    lookback_days: int = 180
    total_filings: int = 0
    notable_transactions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "net_shares": self.net_shares,
            "net_value": self.net_value,
            "cluster_buy": self.cluster_buy,
            "cluster_sell": self.cluster_sell,
            "insider_score": self.insider_score,
            "total_filings": self.total_filings,
        }


class InsiderTracker:
    """Analyze insider trading patterns from SEC filings.

    Detects cluster buying/selling, C-suite trades, and
    generates insider sentiment signals.

    Example:
        tracker = InsiderTracker()
        report = tracker.analyze(filings)
        score = report.insider_score
    """

    def __init__(self, config: Optional[InsiderConfig] = None):
        self.config = config or InsiderConfig()

    def analyze(
        self,
        filings: list[InsiderFiling],
        lookback_days: Optional[int] = None,
    ) -> InsiderReport:
        """Analyze insider filings for a symbol.

        Args:
            filings: List of SEC Form 4 filings.
            lookback_days: Only consider filings within this window.

        Returns:
            InsiderReport with scores and signal detection.
        """
        lookback = lookback_days or (self.config.lookback_months * 30)

        # Filter by lookback window
        cutoff = datetime.now() - timedelta(days=lookback)
        filtered = []
        for f in filings:
            try:
                filing_dt = datetime.fromisoformat(f.filing_date)
                if filing_dt >= cutoff:
                    filtered.append(f)
            except (ValueError, TypeError):
                filtered.append(f)  # Include if date can't be parsed

        if not filtered:
            return InsiderReport(
                symbol=filings[0].symbol if filings else "",
                lookback_days=lookback,
            )

        symbol = filtered[0].symbol

        buys = [f for f in filtered if f.is_purchase]
        sells = [f for f in filtered if f.is_sale]

        report = InsiderReport(
            symbol=symbol,
            buy_count=len(buys),
            sell_count=len(sells),
            net_shares=sum(f.shares for f in buys) - sum(f.shares for f in sells),
            net_value=sum(f.value for f in buys) - sum(f.value for f in sells),
            lookback_days=lookback,
            total_filings=len(filtered),
        )

        # Detect cluster buying/selling
        report.cluster_buy = self._detect_cluster(buys)
        report.cluster_sell = self._detect_cluster(sells)

        # C-suite activity
        report.ceo_activity = [
            f"{f.insider_name} ({f.insider_title}): "
            f"{'Bought' if f.is_purchase else 'Sold'} "
            f"{f.shares:,} shares (${f.value:,.0f})"
            for f in filtered if f.is_c_suite
        ]

        # Notable transactions (large or C-suite)
        report.notable_transactions = [
            f for f in filtered
            if f.is_c_suite or f.value > 500_000
        ]

        # Compute insider score
        report.insider_score = self._compute_score(filtered)

        return report

    def analyze_multiple(
        self,
        filings_by_symbol: dict[str, list[InsiderFiling]],
    ) -> dict[str, InsiderReport]:
        """Analyze insider activity for multiple symbols.

        Args:
            filings_by_symbol: Dict of symbol -> filings.

        Returns:
            Dict of symbol -> InsiderReport.
        """
        return {
            symbol: self.analyze(filings)
            for symbol, filings in filings_by_symbol.items()
        }

    def get_top_insider_buys(
        self,
        reports: dict[str, InsiderReport],
        top_n: int = 10,
    ) -> list[InsiderReport]:
        """Get symbols with strongest insider buying signals.

        Args:
            reports: Dict of symbol -> InsiderReport.
            top_n: Number of top results.

        Returns:
            Sorted list of InsiderReport by insider_score descending.
        """
        sorted_reports = sorted(
            reports.values(),
            key=lambda r: r.insider_score,
            reverse=True,
        )
        return [r for r in sorted_reports[:top_n] if r.insider_score > 0]

    def _detect_cluster(self, filings: list[InsiderFiling]) -> bool:
        """Detect cluster activity (multiple insiders within window)."""
        if len(filings) < self.config.cluster_min_insiders:
            return False

        # Check if enough unique insiders traded within cluster window
        window_days = self.config.cluster_window_days
        unique_insiders = set()

        dates = []
        for f in filings:
            try:
                dates.append((datetime.fromisoformat(f.filing_date), f.insider_name))
            except (ValueError, TypeError):
                unique_insiders.add(f.insider_name)

        if not dates:
            return len(unique_insiders) >= self.config.cluster_min_insiders

        dates.sort(key=lambda x: x[0])

        # Sliding window check
        for i in range(len(dates)):
            window_insiders = set()
            for j in range(i, len(dates)):
                if (dates[j][0] - dates[i][0]).days <= window_days:
                    window_insiders.add(dates[j][1])
                else:
                    break
            if len(window_insiders) >= self.config.cluster_min_insiders:
                return True

        return False

    def _compute_score(self, filings: list[InsiderFiling]) -> float:
        """Compute insider sentiment score from filings.

        Score ranges from -1 (strong selling) to +1 (strong buying).
        """
        if not filings:
            return 0.0

        weights = self.config.signal_weights
        score = 0.0
        weight_sum = 0.0

        for f in filings:
            if f.is_purchase:
                if f.is_c_suite:
                    w = weights["ceo_cfo_buy"]
                elif f.is_director:
                    w = weights["director_buy"]
                else:
                    w = weights["director_buy"] * 0.5  # Other insiders
            elif f.is_sale:
                if f.is_10b5_1:
                    w = weights["10b5_1_sale"]
                else:
                    w = weights["open_market_sale"]
            else:
                continue

            # Weight by transaction value (log scale)
            value_weight = np.log1p(abs(f.value)) / 15.0  # Normalize
            score += w * value_weight
            weight_sum += abs(value_weight)

        if weight_sum == 0:
            return 0.0

        # Apply cluster bonuses
        buys = [f for f in filings if f.is_purchase]
        sells = [f for f in filings if f.is_sale]

        if self._detect_cluster(buys):
            score += weights["cluster_buy"]
            weight_sum += 1.0

        if self._detect_cluster(sells):
            score += weights["cluster_sell"]
            weight_sum += 1.0

        result = score / weight_sum
        return float(np.clip(result, -1.0, 1.0))
