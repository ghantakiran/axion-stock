"""Portfolio Risk Monitor — leverage, concentration, and dynamic sizing.

Monitors portfolio-level risk metrics:
- Gross/net leverage with limits
- Sector concentration limits
- Correlation-based position limits
- VIX-based dynamic position sizing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════
# Sector Mapping
# ═══════════════════════════════════════════════════════════════════════


SECTOR_MAP: dict[str, str] = {
    # Technology
    "AAPL": "technology", "MSFT": "technology", "GOOG": "technology",
    "GOOGL": "technology", "META": "technology", "NVDA": "technology",
    "AMZN": "technology", "AMD": "technology", "INTC": "technology",
    "CRM": "technology", "ORCL": "technology", "ADBE": "technology",
    "NFLX": "technology", "TSLA": "technology",
    # Financials
    "JPM": "financials", "BAC": "financials", "GS": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "BRK-B": "financials", "V": "financials", "MA": "financials",
    # Healthcare
    "JNJ": "healthcare", "UNH": "healthcare", "PFE": "healthcare",
    "ABBV": "healthcare", "MRK": "healthcare", "LLY": "healthcare",
    # Energy
    "XOM": "energy", "CVX": "energy", "COP": "energy",
    "SLB": "energy", "OXY": "energy",
    # Consumer
    "KO": "consumer", "PEP": "consumer", "PG": "consumer",
    "WMT": "consumer", "COST": "consumer", "HD": "consumer",
    # Industrials
    "BA": "industrials", "CAT": "industrials", "GE": "industrials",
    "UPS": "industrials", "HON": "industrials",
    # Crypto-related
    "BTC-USD": "crypto", "ETH-USD": "crypto", "COIN": "crypto",
    "MSTR": "crypto",
}


# ═══════════════════════════════════════════════════════════════════════
# Enums & Config
# ═══════════════════════════════════════════════════════════════════════


class RiskLevel(str, Enum):
    """Overall portfolio risk level."""

    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PortfolioRiskConfig:
    """Configuration for portfolio risk monitoring.

    Attributes:
        max_gross_leverage: Max total exposure / equity ratio.
        max_net_leverage: Max (long - short) / equity ratio.
        max_sector_pct: Max single sector as % of portfolio.
        max_single_stock_pct: Max single position as % of portfolio.
        max_correlated_positions: Max positions in same sector.
        vix_low_threshold: VIX below this = expand sizing.
        vix_high_threshold: VIX above this = reduce sizing.
        vix_critical_threshold: VIX above this = halt new entries.
        base_position_size_pct: Base position size in normal conditions.
    """

    max_gross_leverage: float = 2.0
    max_net_leverage: float = 1.5
    max_sector_pct: float = 30.0
    max_single_stock_pct: float = 15.0
    max_correlated_positions: int = 5
    vix_low_threshold: float = 15.0
    vix_high_threshold: float = 25.0
    vix_critical_threshold: float = 35.0
    base_position_size_pct: float = 5.0


# ═══════════════════════════════════════════════════════════════════════
# Risk Snapshot
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class RiskSnapshot:
    """Point-in-time portfolio risk assessment.

    Attributes:
        risk_level: Overall portfolio risk level.
        gross_leverage: Total exposure / equity.
        net_leverage: Net (long - short) / equity.
        long_exposure: Total long market value.
        short_exposure: Total short market value.
        sector_concentrations: % of portfolio by sector.
        largest_position_pct: Largest single position as % of portfolio.
        correlated_count: Max positions in any single sector.
        vix_adjusted_size_pct: VIX-adjusted position sizing recommendation.
        warnings: List of risk warnings.
        timestamp: When this snapshot was taken.
    """

    risk_level: RiskLevel = RiskLevel.LOW
    gross_leverage: float = 0.0
    net_leverage: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    sector_concentrations: dict[str, float] = field(default_factory=dict)
    largest_position_pct: float = 0.0
    correlated_count: int = 0
    vix_adjusted_size_pct: float = 5.0
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "gross_leverage": round(self.gross_leverage, 3),
            "net_leverage": round(self.net_leverage, 3),
            "long_exposure": round(self.long_exposure, 2),
            "short_exposure": round(self.short_exposure, 2),
            "sector_concentrations": {
                k: round(v, 2) for k, v in self.sector_concentrations.items()
            },
            "largest_position_pct": round(self.largest_position_pct, 2),
            "correlated_count": self.correlated_count,
            "vix_adjusted_size_pct": round(self.vix_adjusted_size_pct, 2),
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Portfolio Risk Monitor
# ═══════════════════════════════════════════════════════════════════════


class PortfolioRiskMonitor:
    """Monitors portfolio-level risk with leverage, concentration, and VIX sizing.

    Integrates with PositionStore to produce real-time risk snapshots
    and approve/deny new trades based on portfolio constraints.

    Args:
        config: PortfolioRiskConfig with thresholds and limits.
        equity: Current account equity.

    Example:
        monitor = PortfolioRiskMonitor(equity=100_000)
        snapshot = monitor.assess(positions, vix=22.5)
        approved, reason = monitor.approve_new_trade("AAPL", 5000, "long", positions)
    """

    def __init__(
        self,
        config: PortfolioRiskConfig | None = None,
        equity: float = 100_000.0,
    ) -> None:
        self.config = config or PortfolioRiskConfig()
        self._equity = equity
        self._history: list[RiskSnapshot] = []

    @property
    def equity(self) -> float:
        return self._equity

    @equity.setter
    def equity(self, value: float) -> None:
        self._equity = max(0.0, value)

    def assess(
        self,
        positions: list[dict[str, Any]],
        vix: float = 20.0,
    ) -> RiskSnapshot:
        """Assess current portfolio risk.

        Args:
            positions: List of position dicts with keys:
                symbol, qty, current_price, side, market_value.
            vix: Current VIX level for dynamic sizing.

        Returns:
            RiskSnapshot with all metrics and warnings.
        """
        warnings: list[str] = []

        # Compute exposures
        long_exp = 0.0
        short_exp = 0.0
        sector_values: dict[str, float] = {}
        position_pcts: list[float] = []

        for pos in positions:
            mv = float(pos.get("market_value", 0))
            side = pos.get("side", "long")
            symbol = pos.get("symbol", "")
            sector = SECTOR_MAP.get(symbol, "other")

            if side == "long":
                long_exp += mv
            else:
                short_exp += mv

            sector_values[sector] = sector_values.get(sector, 0.0) + mv

            if self._equity > 0:
                position_pcts.append(mv / self._equity * 100.0)

        gross_exp = long_exp + short_exp
        net_exp = long_exp - short_exp

        gross_leverage = gross_exp / max(self._equity, 1.0)
        net_leverage = net_exp / max(self._equity, 1.0)

        # Sector concentrations as % of total
        total_value = gross_exp if gross_exp > 0 else 1.0
        sector_pcts = {s: v / total_value * 100.0 for s, v in sector_values.items()}

        # Largest position
        largest_pct = max(position_pcts) if position_pcts else 0.0

        # Max correlated positions (positions in same sector)
        sector_counts = {}
        for pos in positions:
            sector = SECTOR_MAP.get(pos.get("symbol", ""), "other")
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        correlated_count = max(sector_counts.values()) if sector_counts else 0

        # VIX-based dynamic sizing
        vix_size = self._vix_adjusted_size(vix)

        # Generate warnings
        if gross_leverage > self.config.max_gross_leverage:
            warnings.append(
                f"Gross leverage {gross_leverage:.2f}x exceeds limit {self.config.max_gross_leverage}x"
            )
        if abs(net_leverage) > self.config.max_net_leverage:
            warnings.append(
                f"Net leverage {net_leverage:.2f}x exceeds limit {self.config.max_net_leverage}x"
            )
        for sector, pct in sector_pcts.items():
            if pct > self.config.max_sector_pct:
                warnings.append(
                    f"Sector '{sector}' at {pct:.1f}% exceeds limit {self.config.max_sector_pct}%"
                )
        if largest_pct > self.config.max_single_stock_pct:
            warnings.append(
                f"Largest position {largest_pct:.1f}% exceeds limit {self.config.max_single_stock_pct}%"
            )
        if correlated_count > self.config.max_correlated_positions:
            warnings.append(
                f"Correlated positions ({correlated_count}) exceeds limit {self.config.max_correlated_positions}"
            )

        # Determine risk level
        risk_level = self._classify_risk(gross_leverage, warnings, vix)

        snapshot = RiskSnapshot(
            risk_level=risk_level,
            gross_leverage=gross_leverage,
            net_leverage=net_leverage,
            long_exposure=long_exp,
            short_exposure=short_exp,
            sector_concentrations=sector_pcts,
            largest_position_pct=largest_pct,
            correlated_count=correlated_count,
            vix_adjusted_size_pct=vix_size,
            warnings=warnings,
        )
        self._history.append(snapshot)
        return snapshot

    def approve_new_trade(
        self,
        symbol: str,
        trade_value: float,
        side: str,
        positions: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """Check if a new trade is acceptable given current portfolio risk.

        Args:
            symbol: Ticker to trade.
            trade_value: Dollar value of the trade.
            side: 'long' or 'short'.
            positions: Current open positions.

        Returns:
            Tuple of (approved, reason).
        """
        # Check single stock concentration
        position_pct = trade_value / max(self._equity, 1.0) * 100.0
        if position_pct > self.config.max_single_stock_pct:
            return False, f"Position {position_pct:.1f}% exceeds {self.config.max_single_stock_pct}% limit"

        # Check sector concentration
        sector = SECTOR_MAP.get(symbol, "other")
        sector_total = trade_value
        for pos in positions:
            if SECTOR_MAP.get(pos.get("symbol", ""), "other") == sector:
                sector_total += float(pos.get("market_value", 0))
        sector_pct = sector_total / max(self._equity, 1.0) * 100.0
        if sector_pct > self.config.max_sector_pct:
            return False, f"Sector '{sector}' would be {sector_pct:.1f}%, exceeds {self.config.max_sector_pct}%"

        # Check correlated positions
        same_sector = sum(
            1 for p in positions
            if SECTOR_MAP.get(p.get("symbol", ""), "other") == sector
        )
        if same_sector >= self.config.max_correlated_positions:
            return False, f"Already {same_sector} positions in '{sector}' sector"

        return True, "approved"

    def get_dynamic_size(self, vix: float = 20.0) -> float:
        """Get VIX-adjusted position size recommendation.

        Args:
            vix: Current VIX level.

        Returns:
            Recommended position size as % of equity.
        """
        return self._vix_adjusted_size(vix)

    def get_history(self, limit: int = 20) -> list[RiskSnapshot]:
        """Return recent risk snapshots."""
        return list(reversed(self._history[-limit:]))

    # ── Internals ───────────────────────────────────────────────────

    def _vix_adjusted_size(self, vix: float) -> float:
        """Compute position size adjusted for VIX regime.

        Low VIX (<15): 1.2x base size (risk-on)
        Normal VIX (15-25): 1.0x base size
        High VIX (25-35): 0.5x base size
        Critical VIX (>35): 0.0x (halt new entries)
        """
        base = self.config.base_position_size_pct
        if vix < self.config.vix_low_threshold:
            return base * 1.2
        elif vix < self.config.vix_high_threshold:
            return base
        elif vix < self.config.vix_critical_threshold:
            return base * 0.5
        else:
            return 0.0

    def _classify_risk(
        self, gross_leverage: float, warnings: list[str], vix: float
    ) -> RiskLevel:
        """Classify overall risk level from metrics."""
        warning_count = len(warnings)
        if warning_count == 0 and vix < self.config.vix_high_threshold:
            return RiskLevel.LOW
        elif warning_count <= 1 and vix < self.config.vix_high_threshold:
            return RiskLevel.MODERATE
        elif warning_count <= 2 or vix >= self.config.vix_high_threshold:
            return RiskLevel.ELEVATED
        elif gross_leverage > self.config.max_gross_leverage or vix >= self.config.vix_critical_threshold:
            return RiskLevel.CRITICAL
        else:
            return RiskLevel.HIGH
