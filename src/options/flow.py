"""Options Flow Detector.

Classifies options flow events (sweep, block, split),
detects unusual activity, and computes net premium sentiment.
"""

import logging
from typing import Optional

from src.options.config import (
    FlowConfig,
    FlowType,
    ActivityLevel,
    Sentiment,
)
from src.options.pricing import OptionType
from src.options.models import OptionContract, OptionsFlow, UnusualActivity

logger = logging.getLogger(__name__)


class FlowDetector:
    """Detects and classifies options flow."""

    def __init__(self, config: Optional[FlowConfig] = None) -> None:
        self.config = config or FlowConfig()
        self._flows: list[OptionsFlow] = []

    def classify_flow(
        self,
        size: int,
        price: float,
        n_exchanges: int = 1,
        option_type: OptionType = OptionType.CALL,
        strike: float = 0.0,
        expiry_days: float = 30.0,
        side: str = "buy",
        symbol: str = "",
    ) -> OptionsFlow:
        """Classify a single options flow event.

        Args:
            size: Number of contracts.
            price: Premium per contract.
            n_exchanges: Number of exchanges the order hit.
            option_type: Call or put.
            strike: Strike price.
            expiry_days: Days to expiration.
            side: 'buy' or 'sell'.
            symbol: Asset symbol.

        Returns:
            OptionsFlow with classification.
        """
        premium = size * price * 100  # Dollar premium
        flow_type = self._classify_type(size, n_exchanges)
        sentiment = self._classify_sentiment(option_type, side)

        flow = OptionsFlow(
            symbol=symbol,
            strike=strike,
            expiry_days=expiry_days,
            option_type=option_type,
            flow_type=flow_type,
            size=size,
            premium=round(premium, 0),
            side=side,
            sentiment=sentiment,
        )

        self._flows.append(flow)
        return flow

    def detect_unusual(
        self,
        contracts: list[OptionContract],
        symbol: str = "",
    ) -> list[UnusualActivity]:
        """Detect unusual options activity from contract data.

        Args:
            contracts: Option contracts with volume and OI.
            symbol: Asset symbol.

        Returns:
            List of UnusualActivity for flagged contracts.
        """
        unusual: list[UnusualActivity] = []

        for c in contracts:
            if c.open_interest <= 0:
                continue

            ratio = c.vol_oi_ratio
            level = self._classify_activity(ratio)

            if level == ActivityLevel.NORMAL:
                continue

            premium = c.volume * c.mid * 100
            score = self._compute_score(ratio, premium, c.volume)

            unusual.append(UnusualActivity(
                symbol=symbol or c.symbol,
                strike=c.strike,
                expiry_days=c.expiry_days,
                option_type=c.option_type,
                volume=c.volume,
                open_interest=c.open_interest,
                vol_oi_ratio=round(ratio, 2),
                premium=round(premium, 0),
                activity_level=level,
                score=round(score, 2),
            ))

        unusual.sort(key=lambda u: u.score, reverse=True)
        return unusual

    def compute_net_sentiment(
        self,
        flows: Optional[list[OptionsFlow]] = None,
    ) -> tuple[Sentiment, float]:
        """Compute net premium sentiment from flow events.

        Args:
            flows: Flow events (uses internal history if None).

        Returns:
            (Sentiment, net_premium) tuple.
        """
        events = flows if flows is not None else self._flows
        if not events:
            return Sentiment.NEUTRAL, 0.0

        bullish_premium = 0.0
        bearish_premium = 0.0

        for f in events:
            if f.sentiment == Sentiment.BULLISH:
                bullish_premium += f.premium
            elif f.sentiment == Sentiment.BEARISH:
                bearish_premium += f.premium

        net = bullish_premium - bearish_premium
        total = bullish_premium + bearish_premium

        if total == 0:
            return Sentiment.NEUTRAL, 0.0

        ratio = bullish_premium / total
        if ratio >= 0.6:
            return Sentiment.BULLISH, net
        elif ratio <= 0.4:
            return Sentiment.BEARISH, net
        return Sentiment.NEUTRAL, net

    def get_flows(self) -> list[OptionsFlow]:
        return list(self._flows)

    def reset(self) -> None:
        self._flows.clear()

    def _classify_type(self, size: int, n_exchanges: int) -> FlowType:
        """Classify flow type from size and execution pattern."""
        if n_exchanges >= self.config.sweep_min_exchanges and size >= self.config.block_min_size:
            return FlowType.SWEEP
        elif size >= self.config.block_min_size:
            return FlowType.BLOCK
        elif n_exchanges > 1:
            return FlowType.SPLIT
        return FlowType.NORMAL

    def _classify_sentiment(
        self,
        option_type: OptionType,
        side: str,
    ) -> Sentiment:
        """Derive sentiment from option type and trade side.

        Buy call / Sell put = Bullish
        Buy put / Sell call = Bearish
        """
        if option_type == OptionType.CALL:
            return Sentiment.BULLISH if side == "buy" else Sentiment.BEARISH
        else:
            return Sentiment.BEARISH if side == "buy" else Sentiment.BULLISH

    def _classify_activity(self, vol_oi_ratio: float) -> ActivityLevel:
        """Classify activity level from volume/OI ratio."""
        if vol_oi_ratio >= self.config.extreme_vol_oi_ratio:
            return ActivityLevel.EXTREME
        elif vol_oi_ratio >= self.config.unusual_vol_oi_ratio:
            return ActivityLevel.UNUSUAL
        elif vol_oi_ratio >= self.config.elevated_vol_oi_ratio:
            return ActivityLevel.ELEVATED
        return ActivityLevel.NORMAL

    def _compute_score(
        self,
        vol_oi_ratio: float,
        premium: float,
        volume: int,
    ) -> float:
        """Compute unusual activity score (0-100).

        Weighted: 40% vol/OI ratio, 30% premium, 30% volume.
        """
        # Ratio score (capped at 10x)
        ratio_score = min(vol_oi_ratio / 10.0, 1.0) * 100

        # Premium score (capped at $5M)
        premium_score = min(premium / 5_000_000, 1.0) * 100

        # Volume score (capped at 10000 contracts)
        volume_score = min(volume / 10_000, 1.0) * 100

        return 0.4 * ratio_score + 0.3 * premium_score + 0.3 * volume_score
