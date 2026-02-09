"""Social Trading Signal Generator (PRD-141).

Combines all intelligence layers (scorer, volume, influencer,
correlator) into actionable trading signals with confidence
scores and recommended actions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from src.sentiment.social import SocialPost
from src.social_intelligence.scorer import (
    SignalScorer, ScorerConfig, ScoredTicker, SignalStrength,
)
from src.social_intelligence.volume import (
    VolumeAnalyzer, VolumeConfig, VolumeAnomaly,
)
from src.social_intelligence.influencer import (
    InfluencerTracker, InfluencerConfig, InfluencerSignal,
)
from src.social_intelligence.correlator import (
    CrossPlatformCorrelator, CorrelatorConfig, CorrelationResult,
)

logger = logging.getLogger(__name__)


class SignalAction(Enum):
    """Recommended trading action."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    WATCH = "watch"


@dataclass
class GeneratorConfig:
    """Configuration for signal generation."""
    # Minimum signal score to generate a trading signal
    min_signal_score: float = 30.0
    # Confidence thresholds for action classification
    strong_buy_threshold: float = 80.0
    buy_threshold: float = 60.0
    sell_threshold: float = -60.0
    strong_sell_threshold: float = -80.0
    # Boost factors
    volume_anomaly_boost: float = 15.0
    influencer_boost: float = 10.0
    consensus_boost: float = 12.0
    # Component configs
    scorer_config: ScorerConfig = field(default_factory=ScorerConfig)
    volume_config: VolumeConfig = field(default_factory=VolumeConfig)
    influencer_config: InfluencerConfig = field(default_factory=InfluencerConfig)
    correlator_config: CorrelatorConfig = field(default_factory=CorrelatorConfig)


@dataclass
class SocialTradingSignal:
    """An actionable trading signal derived from social intelligence."""
    symbol: str = ""
    action: SignalAction = SignalAction.WATCH
    confidence: float = 0.0  # 0-100
    direction: str = "neutral"
    signal_score: float = 0.0
    volume_boost: float = 0.0
    influencer_boost: float = 0.0
    consensus_boost: float = 0.0
    final_score: float = 0.0
    mention_count: int = 0
    avg_sentiment: float = 0.0
    platforms: list = field(default_factory=list)
    is_consensus: bool = False
    has_volume_anomaly: bool = False
    has_influencer_signal: bool = False
    reasons: list = field(default_factory=list)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action.value,
            "confidence": round(self.confidence, 1),
            "direction": self.direction,
            "final_score": round(self.final_score, 1),
            "mention_count": self.mention_count,
            "avg_sentiment": round(self.avg_sentiment, 2),
            "platforms": self.platforms,
            "is_consensus": self.is_consensus,
            "has_volume_anomaly": self.has_volume_anomaly,
            "has_influencer_signal": self.has_influencer_signal,
            "reasons": self.reasons,
        }


@dataclass
class IntelligenceReport:
    """Complete social intelligence report."""
    signals: list = field(default_factory=list)  # list[SocialTradingSignal]
    scored_tickers: list = field(default_factory=list)  # list[ScoredTicker]
    volume_anomalies: list = field(default_factory=list)  # list[VolumeAnomaly]
    influencer_signals: list = field(default_factory=list)  # list[InfluencerSignal]
    correlations: list = field(default_factory=list)  # list[CorrelationResult]
    total_posts_analyzed: int = 0
    total_tickers_found: int = 0
    signals_generated: int = 0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "total_posts_analyzed": self.total_posts_analyzed,
            "total_tickers_found": self.total_tickers_found,
            "signals_generated": self.signals_generated,
            "top_signals": [s.to_dict() for s in self.signals[:10]],
            "volume_anomalies": [a.to_dict() for a in self.volume_anomalies],
            "consensus_tickers": [
                c.to_dict() for c in self.correlations if c.is_consensus
            ],
        }


class SocialSignalGenerator:
    """Generates actionable trading signals from social intelligence.

    Orchestrates the full intelligence pipeline:
    1. Score posts via SignalScorer
    2. Detect volume anomalies via VolumeAnalyzer
    3. Extract influencer signals via InfluencerTracker
    4. Correlate across platforms via CrossPlatformCorrelator
    5. Combine all layers into SocialTradingSignal

    Example:
        generator = SocialSignalGenerator()
        report = generator.analyze(posts)
        for signal in report.signals:
            print(f"{signal.symbol}: {signal.action.value} "
                  f"(confidence: {signal.confidence})")
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig()
        self._scorer = SignalScorer(self.config.scorer_config)
        self._volume = VolumeAnalyzer(self.config.volume_config)
        self._influencer = InfluencerTracker(self.config.influencer_config)
        self._correlator = CrossPlatformCorrelator(self.config.correlator_config)

    def analyze(
        self,
        posts: list[SocialPost],
        mention_baselines: Optional[dict[str, float]] = None,
        mention_history: Optional[dict[str, list[int]]] = None,
    ) -> IntelligenceReport:
        """Run full intelligence pipeline on social posts.

        Args:
            posts: Social media posts to analyze.
            mention_baselines: Historical average mention counts.
            mention_history: Hourly mention history for volume detection.

        Returns:
            IntelligenceReport with all signals and analysis.
        """
        report = IntelligenceReport()
        report.total_posts_analyzed = len(posts)

        if not posts:
            return report

        baselines = mention_baselines or {}

        # Step 1: Score all tickers
        scored = self._scorer.score_posts(posts, baselines)
        report.scored_tickers = scored
        report.total_tickers_found = len(scored)

        # Step 2: Volume anomaly detection
        if mention_history:
            anomalies = self._volume.detect_anomalies(mention_history)
        else:
            # Build mention counts from scored tickers
            counts = {st.symbol: st.mention_count for st in scored}
            anomalies = self._volume.update_batch(counts)
        report.volume_anomalies = anomalies

        # Step 3: Influencer signals
        self._influencer.process_posts(posts)
        inf_signals = self._influencer.get_influencer_signals(posts)
        report.influencer_signals = inf_signals

        # Step 4: Cross-platform correlation
        correlations = self._correlator.correlate(posts)
        report.correlations = correlations

        # Step 5: Generate trading signals
        anomaly_set = {a.symbol for a in anomalies}
        inf_by_ticker: dict[str, list[InfluencerSignal]] = {}
        for sig in inf_signals:
            inf_by_ticker.setdefault(sig.symbol, []).append(sig)

        corr_by_ticker = {c.symbol: c for c in correlations}

        signals = []
        for st in scored:
            trading_signal = self._generate_signal(
                st, anomaly_set, inf_by_ticker, corr_by_ticker
            )
            if trading_signal:
                signals.append(trading_signal)

        signals.sort(key=lambda s: abs(s.final_score), reverse=True)
        report.signals = signals
        report.signals_generated = len(signals)

        return report

    def generate_from_scored(
        self,
        scored_tickers: list[ScoredTicker],
    ) -> list[SocialTradingSignal]:
        """Generate signals from pre-scored tickers (without full pipeline).

        Args:
            scored_tickers: Pre-scored ticker list.

        Returns:
            List of SocialTradingSignal.
        """
        signals = []
        for st in scored_tickers:
            signal = self._generate_signal(st, set(), {}, {})
            if signal:
                signals.append(signal)
        signals.sort(key=lambda s: abs(s.final_score), reverse=True)
        return signals

    @property
    def scorer(self) -> SignalScorer:
        return self._scorer

    @property
    def volume_analyzer(self) -> VolumeAnalyzer:
        return self._volume

    @property
    def influencer_tracker(self) -> InfluencerTracker:
        return self._influencer

    @property
    def correlator(self) -> CrossPlatformCorrelator:
        return self._correlator

    def _generate_signal(
        self,
        st: ScoredTicker,
        anomaly_set: set,
        inf_by_ticker: dict,
        corr_by_ticker: dict,
    ) -> Optional[SocialTradingSignal]:
        """Generate a single trading signal from scored ticker + boosts."""
        cfg = self.config

        if st.score < cfg.min_signal_score:
            return None

        signal = SocialTradingSignal(
            symbol=st.symbol,
            signal_score=st.score,
            mention_count=st.mention_count,
            avg_sentiment=st.avg_sentiment,
            platforms=st.platforms,
            direction=st.direction,
        )

        # Directional base: positive for bullish, negative for bearish
        base = st.score if st.direction == "bullish" else (
            -st.score if st.direction == "bearish" else 0
        )

        # Volume anomaly boost
        if st.symbol in anomaly_set:
            signal.has_volume_anomaly = True
            signal.volume_boost = cfg.volume_anomaly_boost
            signal.reasons.append("volume_anomaly")

        # Influencer boost
        inf_sigs = inf_by_ticker.get(st.symbol, [])
        if inf_sigs:
            signal.has_influencer_signal = True
            max_conf = max(s.confidence for s in inf_sigs)
            signal.influencer_boost = cfg.influencer_boost * max_conf
            signal.reasons.append(f"influencer_{inf_sigs[0].tier}")

        # Consensus boost
        corr = corr_by_ticker.get(st.symbol)
        if corr and corr.is_consensus:
            signal.is_consensus = True
            signal.consensus_boost = cfg.consensus_boost * corr.agreement_score
            signal.reasons.append("cross_platform_consensus")

        # Final score with boosts (directional)
        boost_total = signal.volume_boost + signal.influencer_boost + signal.consensus_boost
        if base >= 0:
            signal.final_score = base + boost_total
        else:
            signal.final_score = base - boost_total

        # Confidence (0-100)
        signal.confidence = min(100.0, abs(signal.final_score))

        # Action classification
        signal.action = self._classify_action(signal.final_score)

        return signal

    def _classify_action(self, score: float) -> SignalAction:
        """Classify score into trading action."""
        cfg = self.config
        if score >= cfg.strong_buy_threshold:
            return SignalAction.STRONG_BUY
        elif score >= cfg.buy_threshold:
            return SignalAction.BUY
        elif score <= cfg.strong_sell_threshold:
            return SignalAction.STRONG_SELL
        elif score <= cfg.sell_threshold:
            return SignalAction.SELL
        elif abs(score) >= cfg.min_signal_score:
            return SignalAction.WATCH
        return SignalAction.HOLD
