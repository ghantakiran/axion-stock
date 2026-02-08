"""Trade surveillance engine for detecting manipulative patterns."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import AlertSeverity, SurveillanceConfig, SurveillanceType
from .models import SurveillanceAlert, TradePattern


class SurveillanceEngine:
    """Detects manipulative trading patterns and generates alerts."""

    def __init__(self, config: Optional[SurveillanceConfig] = None):
        self.config = config or SurveillanceConfig()
        self._alerts: List[SurveillanceAlert] = []

    def scan_trades(
        self, trades: List[Dict[str, Any]], account_id: str = ""
    ) -> List[SurveillanceAlert]:
        """Run all enabled surveillance checks on a batch of trades."""
        alerts = []

        if SurveillanceType.WASH_TRADE in self.config.enabled_checks:
            alerts.extend(self._detect_wash_trades(trades, account_id))

        if SurveillanceType.LAYERING in self.config.enabled_checks:
            alerts.extend(self._detect_layering(trades, account_id))

        if SurveillanceType.SPOOFING in self.config.enabled_checks:
            alerts.extend(self._detect_spoofing(trades, account_id))

        if SurveillanceType.EXCESSIVE_TRADING in self.config.enabled_checks:
            alerts.extend(self._detect_excessive_trading(trades, account_id))

        if SurveillanceType.MARKING_CLOSE in self.config.enabled_checks:
            alerts.extend(self._detect_marking_close(trades, account_id))

        self._alerts.extend(alerts)
        return alerts

    def _detect_wash_trades(
        self, trades: List[Dict[str, Any]], account_id: str
    ) -> List[SurveillanceAlert]:
        """Detect wash trading: buy/sell same security within short window."""
        alerts = []
        by_symbol: Dict[str, List[Dict]] = {}

        for t in trades:
            symbol = t.get("symbol", "")
            by_symbol.setdefault(symbol, []).append(t)

        for symbol, sym_trades in by_symbol.items():
            buys = [t for t in sym_trades if t.get("side", "").lower() == "buy"]
            sells = [t for t in sym_trades if t.get("side", "").lower() == "sell"]

            for buy in buys:
                buy_price = buy.get("price", 0)
                buy_time = buy.get("timestamp", 0)

                for sell in sells:
                    sell_price = sell.get("price", 0)
                    sell_time = sell.get("timestamp", 0)

                    time_diff = abs(sell_time - buy_time)
                    price_diff = abs(sell_price - buy_price) / max(buy_price, 0.01)

                    if (time_diff <= self.config.wash_trade_window
                            and price_diff <= self.config.wash_trade_price_tolerance):
                        pattern = TradePattern(
                            symbol=symbol,
                            pattern_type=SurveillanceType.WASH_TRADE.value,
                            trades=[buy, sell],
                            confidence=0.8,
                            details=f"Buy/sell within {time_diff}s, price diff {price_diff:.4f}",
                        )
                        alerts.append(SurveillanceAlert(
                            alert_id=str(uuid.uuid4())[:8],
                            alert_type=SurveillanceType.WASH_TRADE.value,
                            severity=AlertSeverity.HIGH.value,
                            symbol=symbol,
                            account_id=account_id,
                            pattern=pattern,
                            description=f"Potential wash trade in {symbol}",
                        ))

        return alerts

    def _detect_layering(
        self, trades: List[Dict[str, Any]], account_id: str
    ) -> List[SurveillanceAlert]:
        """Detect layering: multiple orders on same side to create false depth."""
        alerts = []
        by_symbol: Dict[str, Dict[str, int]] = {}

        for t in trades:
            symbol = t.get("symbol", "")
            side = t.get("side", "").lower()
            by_symbol.setdefault(symbol, {"buy": 0, "sell": 0})
            if side in ("buy", "sell"):
                by_symbol[symbol][side] += 1

        for symbol, counts in by_symbol.items():
            for side, count in counts.items():
                if count >= self.config.layering_threshold:
                    alerts.append(SurveillanceAlert(
                        alert_id=str(uuid.uuid4())[:8],
                        alert_type=SurveillanceType.LAYERING.value,
                        severity=AlertSeverity.MEDIUM.value,
                        symbol=symbol,
                        account_id=account_id,
                        description=f"{count} {side} orders in {symbol} (threshold: {self.config.layering_threshold})",
                    ))

        return alerts

    def _detect_spoofing(
        self, trades: List[Dict[str, Any]], account_id: str
    ) -> List[SurveillanceAlert]:
        """Detect spoofing: high cancellation rate indicating intent to mislead."""
        alerts = []
        by_symbol: Dict[str, Dict[str, int]] = {}

        for t in trades:
            symbol = t.get("symbol", "")
            status = t.get("status", "filled").lower()
            by_symbol.setdefault(symbol, {"total": 0, "cancelled": 0})
            by_symbol[symbol]["total"] += 1
            if status in ("cancelled", "canceled"):
                by_symbol[symbol]["cancelled"] += 1

        for symbol, stats in by_symbol.items():
            total = stats["total"]
            if total < 3:
                continue
            cancel_ratio = stats["cancelled"] / total
            if cancel_ratio >= self.config.spoofing_cancel_ratio:
                alerts.append(SurveillanceAlert(
                    alert_id=str(uuid.uuid4())[:8],
                    alert_type=SurveillanceType.SPOOFING.value,
                    severity=AlertSeverity.CRITICAL.value,
                    symbol=symbol,
                    account_id=account_id,
                    description=f"Cancel ratio {cancel_ratio:.0%} in {symbol} ({stats['cancelled']}/{total})",
                ))

        return alerts

    def _detect_excessive_trading(
        self, trades: List[Dict[str, Any]], account_id: str
    ) -> List[SurveillanceAlert]:
        """Detect excessive/churning trading activity."""
        alerts = []
        if len(trades) >= self.config.excessive_trading_limit:
            alerts.append(SurveillanceAlert(
                alert_id=str(uuid.uuid4())[:8],
                alert_type=SurveillanceType.EXCESSIVE_TRADING.value,
                severity=AlertSeverity.MEDIUM.value,
                symbol="PORTFOLIO",
                account_id=account_id,
                description=f"{len(trades)} trades exceed daily limit of {self.config.excessive_trading_limit}",
            ))
        return alerts

    def _detect_marking_close(
        self, trades: List[Dict[str, Any]], account_id: str
    ) -> List[SurveillanceAlert]:
        """Detect marking the close: large orders near market close."""
        alerts = []
        close_trades = [
            t for t in trades
            if t.get("minutes_to_close", 999) <= self.config.marking_close_window_min
               and t.get("quantity", 0) > 1000
        ]

        for t in close_trades:
            alerts.append(SurveillanceAlert(
                alert_id=str(uuid.uuid4())[:8],
                alert_type=SurveillanceType.MARKING_CLOSE.value,
                severity=AlertSeverity.HIGH.value,
                symbol=t.get("symbol", ""),
                account_id=account_id,
                description=f"Large order ({t.get('quantity', 0)} shares) near market close",
            ))

        return alerts

    def resolve_alert(self, alert_id: str, resolved_by: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.is_resolved:
                alert.is_resolved = True
                alert.resolved_by = resolved_by
                alert.resolved_at = datetime.now()
                return True
        return False

    def get_alerts(
        self, unresolved_only: bool = False, severity: Optional[str] = None
    ) -> List[SurveillanceAlert]:
        alerts = self._alerts
        if unresolved_only:
            alerts = [a for a in alerts if not a.is_resolved]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts

    def get_alert_count(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for alert in self._alerts:
            counts[alert.alert_type] = counts.get(alert.alert_type, 0) + 1
        return counts
