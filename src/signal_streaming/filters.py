"""Stream Filters — threshold-based update filtering.

Configurable rules that determine which updates get broadcast
to clients. Prevents noise from minor score fluctuations.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ThresholdRule:
    """A single filtering rule."""

    name: str = ""
    min_score_change: float = 0.1
    min_confidence: float = 0.3
    min_observations: int = 1
    allowed_urgencies: list[str] = field(default_factory=lambda: ["low", "medium", "high"])
    allowed_tickers: Optional[list[str]] = None  # None = all tickers
    blocked_tickers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "min_score_change": self.min_score_change,
            "min_confidence": self.min_confidence,
            "min_observations": self.min_observations,
            "allowed_urgencies": self.allowed_urgencies,
        }


@dataclass
class FilterConfig:
    """Configuration for stream filtering."""

    default_rule: ThresholdRule = field(default_factory=lambda: ThresholdRule(
        name="default",
        min_score_change=0.1,
        min_confidence=0.3,
    ))
    ticker_rules: dict[str, ThresholdRule] = field(default_factory=dict)
    global_min_confidence: float = 0.1
    pass_high_urgency: bool = True  # Always pass high urgency updates


@dataclass
class FilterResult:
    """Result of applying a filter to an update."""

    passed: bool = False
    rule_applied: str = ""
    rejection_reason: str = ""
    ticker: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "rule_applied": self.rule_applied,
            "rejection_reason": self.rejection_reason,
            "ticker": self.ticker,
        }


class StreamFilter:
    """Apply threshold rules to filter streaming updates.

    Supports per-ticker rules, global confidence minimums,
    and urgency bypass for breaking news.

    Example::

        filt = StreamFilter(FilterConfig(
            default_rule=ThresholdRule(min_score_change=0.15),
        ))
        result = filt.apply(update)
        if result.passed:
            broadcast(update)
    """

    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
        self._passed_count = 0
        self._rejected_count = 0

    def apply(self, update) -> FilterResult:
        """Apply filtering rules to an update.

        Args:
            update: AggregatedUpdate-like object with ticker, score_change,
                    confidence, observation_count, urgency.

        Returns:
            FilterResult indicating pass/reject and reason.
        """
        ticker = getattr(update, "ticker", "")
        score_change = abs(getattr(update, "score_change", 0.0))
        confidence = getattr(update, "confidence", 0.0)
        obs_count = getattr(update, "observation_count", 0)
        urgency = getattr(update, "urgency", "low")

        # Urgency bypass
        if urgency == "high" and self.config.pass_high_urgency:
            self._passed_count += 1
            return FilterResult(
                passed=True,
                rule_applied="urgency_bypass",
                ticker=ticker,
            )

        # Global confidence floor
        if confidence < self.config.global_min_confidence:
            self._rejected_count += 1
            return FilterResult(
                passed=False,
                rule_applied="global",
                rejection_reason=f"Confidence {confidence:.2f} below global minimum {self.config.global_min_confidence}",
                ticker=ticker,
            )

        # Select rule (per-ticker or default)
        rule = self.config.ticker_rules.get(ticker, self.config.default_rule)

        # Check blocked tickers
        if ticker in rule.blocked_tickers:
            self._rejected_count += 1
            return FilterResult(
                passed=False,
                rule_applied=rule.name,
                rejection_reason=f"Ticker {ticker} is blocked",
                ticker=ticker,
            )

        # Check allowed tickers
        if rule.allowed_tickers is not None and ticker not in rule.allowed_tickers:
            self._rejected_count += 1
            return FilterResult(
                passed=False,
                rule_applied=rule.name,
                rejection_reason=f"Ticker {ticker} not in allowed list",
                ticker=ticker,
            )

        # Check score change threshold
        if score_change < rule.min_score_change:
            self._rejected_count += 1
            return FilterResult(
                passed=False,
                rule_applied=rule.name,
                rejection_reason=f"Score change {score_change:.3f} below threshold {rule.min_score_change}",
                ticker=ticker,
            )

        # Check confidence
        if confidence < rule.min_confidence:
            self._rejected_count += 1
            return FilterResult(
                passed=False,
                rule_applied=rule.name,
                rejection_reason=f"Confidence {confidence:.2f} below threshold {rule.min_confidence}",
                ticker=ticker,
            )

        # Check observation count
        if obs_count < rule.min_observations:
            self._rejected_count += 1
            return FilterResult(
                passed=False,
                rule_applied=rule.name,
                rejection_reason=f"Only {obs_count} observations (need {rule.min_observations})",
                ticker=ticker,
            )

        # Check urgency
        if urgency not in rule.allowed_urgencies:
            self._rejected_count += 1
            return FilterResult(
                passed=False,
                rule_applied=rule.name,
                rejection_reason=f"Urgency '{urgency}' not in allowed list",
                ticker=ticker,
            )

        self._passed_count += 1
        return FilterResult(
            passed=True,
            rule_applied=rule.name,
            ticker=ticker,
        )

    @property
    def passed_count(self) -> int:
        return self._passed_count

    @property
    def rejected_count(self) -> int:
        return self._rejected_count

    @property
    def pass_rate(self) -> float:
        total = self._passed_count + self._rejected_count
        return self._passed_count / total if total > 0 else 0.0

    def reset_stats(self):
        """Reset pass/reject counters."""
        self._passed_count = 0
        self._rejected_count = 0
