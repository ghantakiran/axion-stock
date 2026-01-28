"""FRED (Federal Reserve Economic Data) provider.

Fetches economic indicators like VIX, Treasury yields, CPI, etc.
"""

import logging
from typing import Optional

import aiohttp
import pandas as pd

from src.settings import get_settings

logger = logging.getLogger(__name__)

# Key FRED series for market regime analysis
FRED_SERIES = {
    "VIXCLS": "CBOE Volatility Index (VIX)",
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "T10Y2Y": "10Y-2Y Yield Spread",
    "DGS30": "30-Year Treasury Yield",
    "FEDFUNDS": "Federal Funds Rate",
    "CPIAUCSL": "Consumer Price Index",
    "UNRATE": "Unemployment Rate",
    "DTWEXBGS": "USD Trade-Weighted Index",
    "BAMLH0A0HYM2": "High Yield Bond Spread",
    "ICSA": "Initial Jobless Claims",
    "UMCSENT": "Consumer Sentiment",
}


class FREDProvider:
    """FRED API provider for economic indicators."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def _enabled(self) -> bool:
        return bool(self.settings.fred_api_key)

    async def fetch_series(
        self,
        series_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.Series:
        """Fetch a single FRED series.

        Args:
            series_id: FRED series identifier (e.g. 'VIXCLS')
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)

        Returns:
            pd.Series with DatetimeIndex and float values
        """
        if not self._enabled:
            return pd.Series(dtype=float, name=series_id)

        url = f"{self.settings.fred_base_url}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.settings.fred_api_key,
            "file_type": "json",
        }
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning("FRED %s returned status %d", series_id, resp.status)
                        return pd.Series(dtype=float, name=series_id)

                    data = await resp.json()
                    observations = data.get("observations", [])
                    if not observations:
                        return pd.Series(dtype=float, name=series_id)

                    dates = []
                    values = []
                    for obs in observations:
                        dates.append(obs["date"])
                        val = obs["value"]
                        values.append(float(val) if val != "." else None)

                    return pd.Series(
                        values,
                        index=pd.to_datetime(dates),
                        name=series_id,
                        dtype=float,
                    )

        except Exception as e:
            logger.warning("FRED fetch failed for %s: %s", series_id, e)
            return pd.Series(dtype=float, name=series_id)

    async def fetch_all_indicators(
        self, start: Optional[str] = None
    ) -> pd.DataFrame:
        """Fetch all configured FRED series as a DataFrame."""
        import asyncio

        tasks = {sid: self.fetch_series(sid, start) for sid in FRED_SERIES}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        series_dict = {}
        for sid, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning("FRED %s failed: %s", sid, result)
                continue
            if not result.empty:
                series_dict[sid] = result

        if not series_dict:
            return pd.DataFrame()
        return pd.DataFrame(series_dict)

    async def get_vix(self) -> Optional[float]:
        """Get latest VIX value."""
        series = await self.fetch_series("VIXCLS")
        if series.empty:
            return None
        return float(series.dropna().iloc[-1])

    async def get_yield_curve_spread(self) -> Optional[float]:
        """Get 10Y minus 2Y treasury yield spread."""
        series = await self.fetch_series("T10Y2Y")
        if series.empty:
            return None
        return float(series.dropna().iloc[-1])

    async def get_fed_funds_rate(self) -> Optional[float]:
        """Get current Federal Funds rate."""
        series = await self.fetch_series("FEDFUNDS")
        if series.empty:
            return None
        return float(series.dropna().iloc[-1])
