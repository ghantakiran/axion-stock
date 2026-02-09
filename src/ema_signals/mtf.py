"""Multi-timeframe confluence engine.

Aggregates EMA cloud signals across timeframes (1m, 5m, 10m, 1h, 1d)
to boost conviction when multiple timeframes agree on direction.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal, Optional

from src.ema_signals.clouds import CloudState
from src.ema_signals.detector import SignalType, TradeSignal


class MTFEngine:
    """Aggregate signals across timeframes for confluence scoring.

    When 3+ timeframes emit signals in the same direction for the same
    ticker, a high-conviction MTF_CONFLUENCE signal is generated.
    """

    TIMEFRAMES = ["1m", "5m", "10m", "1h", "1d"]

    # Conviction boost by number of confirming timeframes
    CONFLUENCE_BOOST = {
        1: 0,
        2: 10,
        3: 20,
        4: 25,
        5: 25,
    }

    def compute_confluence(
        self, signals_by_tf: dict[str, list[TradeSignal]]
    ) -> list[TradeSignal]:
        """Merge signals across timeframes, boost conviction when aligned.

        Args:
            signals_by_tf: Dict mapping timeframe -> list of signals.

        Returns:
            List of signals with updated conviction and any new
            MTF_CONFLUENCE signals for tickers with 3+ TF agreement.
        """
        # Group all signals by (ticker, direction)
        grouped: dict[tuple[str, str], list[TradeSignal]] = defaultdict(list)
        for tf, signals in signals_by_tf.items():
            for sig in signals:
                grouped[(sig.ticker, sig.direction)].append(sig)

        result: list[TradeSignal] = []
        seen_tickers: set[tuple[str, str]] = set()

        for (ticker, direction), signals in grouped.items():
            # Count unique confirming timeframes
            confirming_tfs = {sig.timeframe for sig in signals}
            n_confirming = len(confirming_tfs)
            boost = self.CONFLUENCE_BOOST.get(n_confirming, 25)

            # Update metadata on all individual signals
            for sig in signals:
                sig.metadata["confirming_timeframes"] = n_confirming
                sig.metadata["total_timeframes"] = len(self.TIMEFRAMES)
                sig.metadata["confirmed_tfs"] = sorted(confirming_tfs)
                sig.conviction = min(100, sig.conviction + boost)
                result.append(sig)

            # Emit MTF_CONFLUENCE signal when 3+ timeframes agree
            if n_confirming >= 3 and (ticker, direction) not in seen_tickers:
                seen_tickers.add((ticker, direction))
                # Use the highest-timeframe signal as the base
                best = max(
                    signals,
                    key=lambda s: self.TIMEFRAMES.index(s.timeframe)
                    if s.timeframe in self.TIMEFRAMES
                    else 0,
                )
                confluence_signal = TradeSignal(
                    signal_type=SignalType.MTF_CONFLUENCE,
                    direction=direction,
                    ticker=ticker,
                    timeframe="mtf",
                    conviction=min(100, best.conviction + boost),
                    entry_price=best.entry_price,
                    stop_loss=best.stop_loss,
                    target_price=best.target_price,
                    cloud_states=best.cloud_states,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "trigger": "mtf_confluence",
                        "confirming_timeframes": n_confirming,
                        "total_timeframes": len(self.TIMEFRAMES),
                        "confirmed_tfs": sorted(confirming_tfs),
                        "source_signals": len(signals),
                    },
                )
                result.append(confluence_signal)

        return result

    def get_macro_bias(
        self, daily_clouds: list[CloudState]
    ) -> Literal["bullish", "bearish", "neutral"]:
        """Determine overall market bias from daily cloud states.

        Args:
            daily_clouds: Cloud states computed from daily timeframe.

        Returns:
            "bullish" if trend + macro clouds are bullish,
            "bearish" if both are bearish,
            "neutral" otherwise.
        """
        if not daily_clouds:
            return "neutral"

        cloud_map = {cs.cloud_name: cs for cs in daily_clouds}
        trend = cloud_map.get("trend")
        macro = cloud_map.get("macro")

        if not trend or not macro:
            return "neutral"

        if trend.is_bullish and macro.is_bullish:
            return "bullish"
        elif not trend.is_bullish and not macro.is_bullish:
            return "bearish"
        return "neutral"

    def filter_against_bias(
        self,
        signals: list[TradeSignal],
        bias: Literal["bullish", "bearish", "neutral"],
    ) -> list[TradeSignal]:
        """Remove signals that contradict the macro bias.

        In bullish bias, remove short signals with conviction < 75.
        In bearish bias, remove long signals with conviction < 75.
        Neutral passes everything through.
        """
        if bias == "neutral":
            return signals

        filtered = []
        for sig in signals:
            if bias == "bullish" and sig.direction == "short" and sig.conviction < 75:
                continue
            if bias == "bearish" and sig.direction == "long" and sig.conviction < 75:
                continue
            filtered.append(sig)

        return filtered
