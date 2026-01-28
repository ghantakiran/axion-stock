"""Detect gaps in price data (missing trading days)."""

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Gap:
    """A detected gap in price data."""

    ticker: str
    missing_date: pd.Timestamp
    gap_type: str  # missing_bar, weekend_data, holiday_data
    previous_date: Optional[pd.Timestamp] = None
    gap_days: int = 1


class GapDetector:
    """Detect missing trading days in price data."""

    # US market holidays (approximate — not exhaustive)
    KNOWN_HOLIDAYS = {
        "New Year's Day", "Martin Luther King Jr. Day",
        "Presidents' Day", "Good Friday", "Memorial Day",
        "Independence Day", "Labor Day", "Thanksgiving Day",
        "Christmas Day",
    }

    def detect_gaps(
        self,
        df: pd.DataFrame,
        ticker: str,
        max_gap_days: int = 5,
    ) -> list[Gap]:
        """Find missing trading days in a price DataFrame.

        Args:
            df: DataFrame with DatetimeIndex
            ticker: Stock ticker for reporting
            max_gap_days: Maximum expected gap (holidays/weekends)

        Returns:
            List of Gap objects for unexpected missing days
        """
        if df.empty or len(df) < 2:
            return []

        gaps = []
        try:
            # Generate expected US business day calendar
            expected = pd.bdate_range(df.index.min(), df.index.max())
            actual = pd.DatetimeIndex(df.index).normalize()
            missing = expected.difference(actual)

            for missing_date in missing:
                # Skip known holiday windows (approximate)
                if self._is_likely_holiday(missing_date):
                    continue

                gaps.append(Gap(
                    ticker=ticker,
                    missing_date=missing_date,
                    gap_type="missing_bar",
                ))

        except Exception as e:
            logger.warning("Gap detection failed for %s: %s", ticker, e)

        if gaps:
            logger.info(
                "%s: %d missing trading days detected (out of %d expected)",
                ticker, len(gaps), len(pd.bdate_range(df.index.min(), df.index.max())),
            )

        return gaps

    def _is_likely_holiday(self, date: pd.Timestamp) -> bool:
        """Check if a date is likely a US market holiday."""
        month_day = (date.month, date.day)

        # Fixed holidays
        fixed_holidays = {
            (1, 1),   # New Year's
            (7, 4),   # Independence Day
            (12, 25), # Christmas
        }
        if month_day in fixed_holidays:
            return True

        # Approximate floating holidays
        # MLK: 3rd Monday of January
        if date.month == 1 and date.weekday() == 0 and 15 <= date.day <= 21:
            return True
        # Presidents: 3rd Monday of February
        if date.month == 2 and date.weekday() == 0 and 15 <= date.day <= 21:
            return True
        # Good Friday: varies (skip this — too complex)
        # Memorial: Last Monday of May
        if date.month == 5 and date.weekday() == 0 and date.day >= 25:
            return True
        # Labor: 1st Monday of September
        if date.month == 9 and date.weekday() == 0 and date.day <= 7:
            return True
        # Thanksgiving: 4th Thursday of November
        if date.month == 11 and date.weekday() == 3 and 22 <= date.day <= 28:
            return True

        return False

    def summarize_gaps(self, all_gaps: dict[str, list[Gap]]) -> pd.DataFrame:
        """Summarize gap detection across all tickers.

        Args:
            all_gaps: dict of ticker -> list of gaps

        Returns:
            Summary DataFrame with gap counts per ticker
        """
        rows = []
        for ticker, gaps in all_gaps.items():
            rows.append({
                "ticker": ticker,
                "total_gaps": len(gaps),
                "missing_bars": sum(1 for g in gaps if g.gap_type == "missing_bar"),
            })
        return pd.DataFrame(rows).sort_values("total_gaps", ascending=False)
