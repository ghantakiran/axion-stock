"""Alert Rules Engine (PRD-142).

Defines user-configurable alert rules that trigger notifications
based on social signals, price movements, volume spikes, and
system events.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Types of alert triggers."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE_PCT = "price_change_pct"
    VOLUME_SPIKE = "volume_spike"
    SENTIMENT_BULLISH = "sentiment_bullish"
    SENTIMENT_BEARISH = "sentiment_bearish"
    SOCIAL_TRENDING = "social_trending"
    SIGNAL_GENERATED = "signal_generated"
    INFLUENCER_ALERT = "influencer_alert"
    CONSENSUS_FORMED = "consensus_formed"
    CUSTOM = "custom"


@dataclass
class AlertRule:
    """A user-configurable alert rule."""
    rule_id: str = ""
    name: str = ""
    trigger_type: TriggerType = TriggerType.CUSTOM
    symbol: Optional[str] = None
    threshold: float = 0.0
    channels: list = field(default_factory=list)
    enabled: bool = True
    cooldown_minutes: int = 30
    max_daily_alerts: int = 10
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "trigger_type": self.trigger_type.value,
            "symbol": self.symbol,
            "threshold": self.threshold,
            "channels": [c.value if hasattr(c, "value") else str(c) for c in self.channels],
            "enabled": self.enabled,
            "cooldown_minutes": self.cooldown_minutes,
        }


@dataclass
class TriggeredAlert:
    """An alert triggered by a rule match."""
    rule: AlertRule = field(default_factory=AlertRule)
    symbol: str = ""
    trigger_value: float = 0.0
    message: str = ""
    severity: str = "info"
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule.rule_id,
            "rule_name": self.rule.name,
            "symbol": self.symbol,
            "trigger_type": self.rule.trigger_type.value,
            "trigger_value": self.trigger_value,
            "message": self.message,
            "severity": self.severity,
        }


class RuleEngine:
    """Evaluates alert rules against incoming data.

    Supports cooldown enforcement and daily alert limits.

    Example:
        engine = RuleEngine()
        engine.add_rule(rule)
        triggered = engine.evaluate(data)
    """

    def __init__(self):
        self._rules: dict[str, AlertRule] = {}
        self._last_triggered: dict[str, datetime] = {}
        self._daily_counts: dict[str, int] = {}
        self._last_count_reset: Optional[datetime] = None

    def add_rule(self, rule: AlertRule) -> None:
        if not rule.rule_id:
            rule.rule_id = f"rule_{len(self._rules) + 1}"
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def get_rules(self) -> list[AlertRule]:
        return list(self._rules.values())

    def evaluate(self, data: dict) -> list[TriggeredAlert]:
        self._maybe_reset_daily_counts()
        triggered = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if not self._check_cooldown(rule):
                continue
            if not self._check_daily_limit(rule):
                continue
            alerts = self._evaluate_rule(rule, data)
            for alert in alerts:
                self._record_trigger(rule)
                triggered.append(alert)
        return triggered

    def _evaluate_rule(self, rule: AlertRule, data: dict) -> list[TriggeredAlert]:
        alerts = []
        trigger = rule.trigger_type

        if trigger == TriggerType.PRICE_ABOVE:
            prices = data.get("prices", {})
            if rule.symbol and rule.symbol in prices:
                price = prices[rule.symbol]
                if price >= rule.threshold:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=rule.symbol, trigger_value=price,
                        message=f"{rule.symbol} above ${rule.threshold:.2f} (now ${price:.2f})",
                    ))

        elif trigger == TriggerType.PRICE_BELOW:
            prices = data.get("prices", {})
            if rule.symbol and rule.symbol in prices:
                price = prices[rule.symbol]
                if price <= rule.threshold:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=rule.symbol, trigger_value=price,
                        message=f"{rule.symbol} below ${rule.threshold:.2f} (now ${price:.2f})",
                    ))

        elif trigger == TriggerType.VOLUME_SPIKE:
            for anomaly in data.get("volume_anomalies", []):
                if rule.symbol and anomaly.symbol != rule.symbol:
                    continue
                if anomaly.z_score >= rule.threshold:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=anomaly.symbol,
                        trigger_value=anomaly.z_score,
                        message=f"{anomaly.symbol} volume spike (z={anomaly.z_score:.1f})",
                        severity="warning",
                    ))

        elif trigger == TriggerType.SIGNAL_GENERATED:
            for signal in data.get("signals", []):
                if rule.symbol and signal.symbol != rule.symbol:
                    continue
                if signal.confidence >= rule.threshold:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=signal.symbol,
                        trigger_value=signal.confidence,
                        message=f"{signal.symbol}: {signal.action.value} signal "
                                f"(confidence: {signal.confidence:.0f})",
                    ))

        elif trigger == TriggerType.SOCIAL_TRENDING:
            for symbol in data.get("trending", []):
                if rule.symbol and symbol != rule.symbol:
                    continue
                alerts.append(TriggeredAlert(
                    rule=rule, symbol=symbol, trigger_value=1.0,
                    message=f"{symbol} is trending on social media",
                ))

        elif trigger == TriggerType.SENTIMENT_BULLISH:
            for signal in data.get("signals", []):
                if rule.symbol and signal.symbol != rule.symbol:
                    continue
                if signal.avg_sentiment >= rule.threshold:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=signal.symbol,
                        trigger_value=signal.avg_sentiment,
                        message=f"{signal.symbol} bullish ({signal.avg_sentiment:.2f})",
                    ))

        elif trigger == TriggerType.SENTIMENT_BEARISH:
            for signal in data.get("signals", []):
                if rule.symbol and signal.symbol != rule.symbol:
                    continue
                if signal.avg_sentiment <= -rule.threshold:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=signal.symbol,
                        trigger_value=signal.avg_sentiment,
                        message=f"{signal.symbol} bearish ({signal.avg_sentiment:.2f})",
                        severity="warning",
                    ))

        elif trigger == TriggerType.CONSENSUS_FORMED:
            for corr in data.get("consensus", []):
                if rule.symbol and corr.symbol != rule.symbol:
                    continue
                if corr.is_consensus:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=corr.symbol,
                        trigger_value=corr.agreement_score,
                        message=f"{corr.symbol} {corr.consensus_direction} consensus",
                    ))

        elif trigger == TriggerType.INFLUENCER_ALERT:
            for sig in data.get("influencer_signals", []):
                if rule.symbol and sig.symbol != rule.symbol:
                    continue
                if sig.confidence >= rule.threshold:
                    alerts.append(TriggeredAlert(
                        rule=rule, symbol=sig.symbol,
                        trigger_value=sig.confidence,
                        message=f"{sig.tier} influencer {sig.direction} on {sig.symbol}",
                    ))

        return alerts

    def _check_cooldown(self, rule: AlertRule) -> bool:
        last = self._last_triggered.get(rule.rule_id)
        if not last:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return elapsed >= rule.cooldown_minutes

    def _check_daily_limit(self, rule: AlertRule) -> bool:
        return self._daily_counts.get(rule.rule_id, 0) < rule.max_daily_alerts

    def _record_trigger(self, rule: AlertRule) -> None:
        self._last_triggered[rule.rule_id] = datetime.now(timezone.utc)
        self._daily_counts[rule.rule_id] = self._daily_counts.get(rule.rule_id, 0) + 1

    def _maybe_reset_daily_counts(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_count_reset is None or now.date() > self._last_count_reset.date():
            self._daily_counts.clear()
            self._last_count_reset = now
