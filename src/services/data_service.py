"""Central data access layer for the Axion platform.

All data flows through DataService. Resolution order:
1. Redis cache (hot, sub-ms)
2. PostgreSQL / TimescaleDB (warm, ms)
3. External API (cold, seconds) — writes back to DB + cache

Output formats are designed to match existing DataFrame schemas
so downstream code (factor_model, portfolio, backtest) works unchanged.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.cache.redis_client import cache
from src.settings import get_settings

logger = logging.getLogger(__name__)


class DataService:
    """Async data service with multi-layer resolution."""

    def __init__(self):
        self.settings = get_settings()

    # =========================================================================
    # Universe
    # =========================================================================

    async def get_universe(self, index: str = "sp500") -> list[str]:
        """Get investable stock universe.

        Returns list of ticker strings matching existing build_universe() output.
        """
        cache_key = f"axion:universe:{index}"

        # 1. Redis
        cached = await cache.get_json(cache_key)
        if cached:
            return cached

        # 2. Database
        if self.settings.use_database:
            tickers = await self._get_universe_from_db()
            if tickers:
                await cache.set_json(cache_key, tickers, self.settings.redis_universe_ttl)
                return tickers

        # 3. Fallback to existing scraper
        from src.universe import build_universe
        tickers = build_universe()

        # Persist asynchronously
        await cache.set_json(cache_key, tickers, self.settings.redis_universe_ttl)
        if self.settings.use_database:
            asyncio.create_task(self._persist_universe(tickers))

        return tickers

    # =========================================================================
    # Price Data
    # =========================================================================

    async def get_prices(
        self,
        tickers: list[str],
        period: str = "14mo",
    ) -> pd.DataFrame:
        """Get historical close prices.

        Returns DataFrame[dates x tickers] matching download_price_data() format.
        """
        cache_key = "axion:prices:bulk:all"

        # 1. Redis
        cached = await cache.get_dataframe(cache_key)
        if cached is not None and not cached.empty:
            available = [t for t in tickers if t in cached.columns]
            if len(available) > len(tickers) * 0.9:  # 90% coverage
                return cached[available]

        # 2. Database
        if self.settings.use_database:
            df = await self._get_prices_from_db(tickers, period)
            if df is not None and not df.empty:
                await cache.set_dataframe(cache_key, df, 300)  # 5 min cache
                return df

        # 3. YFinance fallback
        if self.settings.fallback_to_yfinance:
            from src.services.providers.yfinance_provider import YFinanceProvider
            provider = YFinanceProvider()
            df = await provider.fetch_prices(tickers, period)
            if not df.empty:
                await cache.set_dataframe(cache_key, df, 300)
                if self.settings.use_database:
                    asyncio.create_task(self._persist_prices(df))
            return df

        return pd.DataFrame()

    # =========================================================================
    # Fundamentals
    # =========================================================================

    async def get_fundamentals(self, tickers: list[str]) -> pd.DataFrame:
        """Get fundamental data.

        Returns DataFrame[tickers x 10 fields] matching download_fundamentals() format.
        """
        cache_key = "axion:fundamentals:all"

        # 1. Redis
        cached = await cache.get_dataframe(cache_key)
        if cached is not None and not cached.empty:
            available = [t for t in tickers if t in cached.index]
            if len(available) > len(tickers) * 0.9:
                return cached.loc[available]

        # 2. Database
        if self.settings.use_database:
            df = await self._get_fundamentals_from_db(tickers)
            if df is not None and not df.empty:
                await cache.set_dataframe(cache_key, df, self.settings.redis_fundamental_ttl)
                return df

        # 3. YFinance fallback
        if self.settings.fallback_to_yfinance:
            from src.services.providers.yfinance_provider import YFinanceProvider
            provider = YFinanceProvider()
            df = await provider.fetch_fundamentals(tickers)
            if not df.empty:
                await cache.set_dataframe(cache_key, df, self.settings.redis_fundamental_ttl)
                if self.settings.use_database:
                    asyncio.create_task(self._persist_fundamentals(df))
            return df

        return pd.DataFrame()

    # =========================================================================
    # Real-time Quotes
    # =========================================================================

    async def get_quote(self, ticker: str) -> dict:
        """Get real-time quote. Redis → Polygon → YFinance."""
        # 1. Redis
        cached = await cache.get_quote(ticker)
        if cached:
            return cached

        # 2. Polygon
        if self.settings.polygon_api_key:
            from src.services.providers.polygon_provider import PolygonProvider
            provider = PolygonProvider()
            quote = await provider.get_quote(ticker)
            if quote and quote.get("price"):
                await cache.set_quote(ticker, quote)
                return quote

        # 3. YFinance
        if self.settings.fallback_to_yfinance:
            from src.services.providers.yfinance_provider import YFinanceProvider
            provider = YFinanceProvider()
            quote = await provider.get_quote(ticker)
            if quote:
                await cache.set_quote(ticker, quote)
                return quote

        return {"ticker": ticker, "price": None, "source": "unavailable"}

    # =========================================================================
    # Economic Indicators
    # =========================================================================

    async def get_economic_indicator(
        self,
        series_id: str,
        start: Optional[str] = None,
    ) -> pd.Series:
        """Get FRED economic indicator."""
        cache_key = f"axion:economic:{series_id}"

        # 1. Redis (store as JSON list)
        cached = await cache.get_json(cache_key)
        if cached:
            return pd.Series(
                cached.get("values"),
                index=pd.to_datetime(cached.get("dates")),
                name=series_id,
                dtype=float,
            )

        # 2. Database
        if self.settings.use_database:
            series = await self._get_economic_from_db(series_id, start)
            if series is not None and not series.empty:
                await self._cache_series(cache_key, series)
                return series

        # 3. FRED API
        if self.settings.fred_api_key:
            from src.services.providers.fred_provider import FREDProvider
            provider = FREDProvider()
            series = await provider.fetch_series(series_id, start)
            if not series.empty:
                await self._cache_series(cache_key, series)
                if self.settings.use_database:
                    asyncio.create_task(self._persist_economic(series_id, series))
            return series

        return pd.Series(dtype=float, name=series_id)

    # =========================================================================
    # Factor Scores
    # =========================================================================

    async def get_scores(self, tickers: Optional[list[str]] = None) -> pd.DataFrame:
        """Get pre-computed factor scores."""
        cache_key = "axion:scores:all"

        # 1. Redis
        cached = await cache.get_dataframe(cache_key)
        if cached is not None and not cached.empty:
            if tickers:
                available = [t for t in tickers if t in cached.index]
                return cached.loc[available]
            return cached

        # 2. Database
        if self.settings.use_database:
            scores = await self._get_scores_from_db()
            if scores is not None and not scores.empty:
                await cache.set_dataframe(cache_key, scores, self.settings.redis_score_ttl)
                if tickers:
                    available = [t for t in tickers if t in scores.index]
                    return scores.loc[available]
                return scores

        return pd.DataFrame()

    # =========================================================================
    # Private: Database Read Methods
    # =========================================================================

    async def _get_universe_from_db(self) -> list[str]:
        """Get active tickers from instruments table."""
        try:
            from src.db.engine import get_async_engine
            from src.db.models import Instrument
            engine = get_async_engine()
            async with engine.connect() as conn:
                result = await conn.execute(
                    select(Instrument.ticker)
                    .where(Instrument.is_active.is_(True))
                    .order_by(Instrument.ticker)
                )
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.warning("DB universe fetch failed: %s", e)
            return []

    async def _get_prices_from_db(self, tickers: list[str], period: str) -> Optional[pd.DataFrame]:
        """Get price history from TimescaleDB."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            # Parse period to start date
            months = int(period.replace("mo", ""))
            start_date = datetime.now() - timedelta(days=months * 30)

            query = text("""
                SELECT pb.time, i.ticker, pb.adj_close
                FROM price_bars pb
                JOIN instruments i ON pb.instrument_id = i.id
                WHERE i.ticker = ANY(:tickers)
                  AND pb.time >= :start_date
                ORDER BY pb.time
            """)

            async with engine.connect() as conn:
                result = await conn.execute(
                    query,
                    {"tickers": tickers, "start_date": start_date},
                )
                rows = result.fetchall()

            if not rows:
                return None

            df = pd.DataFrame(rows, columns=["time", "ticker", "adj_close"])
            pivot = df.pivot(index="time", columns="ticker", values="adj_close")
            return pivot

        except Exception as e:
            logger.warning("DB prices fetch failed: %s", e)
            return None

    async def _get_fundamentals_from_db(self, tickers: list[str]) -> Optional[pd.DataFrame]:
        """Get latest fundamentals from database."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            query = text("""
                SELECT DISTINCT ON (i.ticker)
                    i.ticker,
                    f.trailing_pe AS "trailingPE",
                    f.price_to_book AS "priceToBook",
                    f.dividend_yield AS "dividendYield",
                    f.ev_to_ebitda AS "enterpriseToEbitda",
                    f.return_on_equity AS "returnOnEquity",
                    f.debt_to_equity AS "debtToEquity",
                    f.revenue_growth AS "revenueGrowth",
                    f.earnings_growth AS "earningsGrowth",
                    f.market_cap AS "marketCap",
                    f.current_price AS "currentPrice"
                FROM financials f
                JOIN instruments i ON f.instrument_id = i.id
                WHERE i.ticker = ANY(:tickers)
                ORDER BY i.ticker, f.as_of_date DESC
            """)

            async with engine.connect() as conn:
                result = await conn.execute(query, {"tickers": tickers})
                rows = result.fetchall()

            if not rows:
                return None

            columns = [
                "ticker", "trailingPE", "priceToBook", "dividendYield",
                "enterpriseToEbitda", "returnOnEquity", "debtToEquity",
                "revenueGrowth", "earningsGrowth", "marketCap", "currentPrice",
            ]
            df = pd.DataFrame(rows, columns=columns)
            return df.set_index("ticker")

        except Exception as e:
            logger.warning("DB fundamentals fetch failed: %s", e)
            return None

    async def _get_scores_from_db(self) -> Optional[pd.DataFrame]:
        """Get latest factor scores from database."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            query = text("""
                SELECT DISTINCT ON (i.ticker)
                    i.ticker,
                    fs.value_score AS value,
                    fs.momentum_score AS momentum,
                    fs.quality_score AS quality,
                    fs.growth_score AS growth,
                    fs.composite_score AS composite
                FROM factor_scores fs
                JOIN instruments i ON fs.instrument_id = i.id
                ORDER BY i.ticker, fs.computed_date DESC
            """)

            async with engine.connect() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()

            if not rows:
                return None

            df = pd.DataFrame(rows, columns=["ticker", "value", "momentum", "quality", "growth", "composite"])
            return df.set_index("ticker")

        except Exception as e:
            logger.warning("DB scores fetch failed: %s", e)
            return None

    async def _get_economic_from_db(self, series_id: str, start: Optional[str]) -> Optional[pd.Series]:
        """Get economic indicator from database."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            query = text("""
                SELECT date, value
                FROM economic_indicators
                WHERE series_id = :series_id
                ORDER BY date
            """)
            params = {"series_id": series_id}

            async with engine.connect() as conn:
                result = await conn.execute(query, params)
                rows = result.fetchall()

            if not rows:
                return None

            df = pd.DataFrame(rows, columns=["date", "value"])
            return pd.Series(
                df["value"].values,
                index=pd.to_datetime(df["date"]),
                name=series_id,
                dtype=float,
            )

        except Exception as e:
            logger.warning("DB economic fetch failed: %s", e)
            return None

    # =========================================================================
    # Private: Database Write Methods
    # =========================================================================

    async def _persist_universe(self, tickers: list[str]) -> None:
        """Persist universe tickers to instruments table."""
        try:
            from src.db.engine import get_async_engine
            from src.db.models import Instrument
            engine = get_async_engine()

            async with engine.begin() as conn:
                for ticker in tickers:
                    stmt = pg_insert(Instrument.__table__).values(
                        ticker=ticker, is_active=True
                    ).on_conflict_do_update(
                        index_elements=["ticker"],
                        set_={"is_active": True},
                    )
                    await conn.execute(stmt)
            logger.info("Persisted %d tickers to instruments table", len(tickers))
        except Exception as e:
            logger.warning("Failed to persist universe: %s", e)

    async def _persist_prices(self, df: pd.DataFrame) -> None:
        """Persist price DataFrame to price_bars table."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            # Get instrument_id mapping
            ticker_ids = await self._get_ticker_id_map(list(df.columns))

            async with engine.begin() as conn:
                for dt_idx in df.index:
                    for ticker in df.columns:
                        if ticker not in ticker_ids:
                            continue
                        price = df.loc[dt_idx, ticker]
                        if pd.isna(price):
                            continue
                        stmt = text("""
                            INSERT INTO price_bars (time, instrument_id, close, adj_close, source)
                            VALUES (:time, :instrument_id, :close, :adj_close, 'yfinance')
                            ON CONFLICT (time, instrument_id) DO UPDATE SET
                                close = EXCLUDED.close,
                                adj_close = EXCLUDED.adj_close
                        """)
                        await conn.execute(stmt, {
                            "time": dt_idx,
                            "instrument_id": ticker_ids[ticker],
                            "close": float(price),
                            "adj_close": float(price),
                        })
            logger.info("Persisted prices for %d tickers", len(df.columns))
        except Exception as e:
            logger.warning("Failed to persist prices: %s", e)

    async def _persist_fundamentals(self, df: pd.DataFrame) -> None:
        """Persist fundamentals DataFrame to financials table."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            ticker_ids = await self._get_ticker_id_map(list(df.index))
            today = date.today()

            async with engine.begin() as conn:
                for ticker in df.index:
                    if ticker not in ticker_ids:
                        continue
                    row = df.loc[ticker]
                    stmt = text("""
                        INSERT INTO financials
                            (instrument_id, as_of_date, trailing_pe, price_to_book,
                             dividend_yield, ev_to_ebitda, return_on_equity,
                             debt_to_equity, revenue_growth, earnings_growth,
                             market_cap, current_price, source)
                        VALUES
                            (:iid, :date, :pe, :pb, :dy, :ev, :roe, :de, :rg, :eg, :mc, :cp, 'yfinance')
                        ON CONFLICT (instrument_id, as_of_date) DO UPDATE SET
                            trailing_pe = EXCLUDED.trailing_pe,
                            price_to_book = EXCLUDED.price_to_book,
                            current_price = EXCLUDED.current_price
                    """)
                    await conn.execute(stmt, {
                        "iid": ticker_ids[ticker],
                        "date": today,
                        "pe": self._safe_float(row.get("trailingPE")),
                        "pb": self._safe_float(row.get("priceToBook")),
                        "dy": self._safe_float(row.get("dividendYield")),
                        "ev": self._safe_float(row.get("enterpriseToEbitda")),
                        "roe": self._safe_float(row.get("returnOnEquity")),
                        "de": self._safe_float(row.get("debtToEquity")),
                        "rg": self._safe_float(row.get("revenueGrowth")),
                        "eg": self._safe_float(row.get("earningsGrowth")),
                        "mc": self._safe_int(row.get("marketCap")),
                        "cp": self._safe_float(row.get("currentPrice")),
                    })
            logger.info("Persisted fundamentals for %d tickers", len(df))
        except Exception as e:
            logger.warning("Failed to persist fundamentals: %s", e)

    async def _persist_economic(self, series_id: str, series: pd.Series) -> None:
        """Persist FRED series to economic_indicators table."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            async with engine.begin() as conn:
                for dt, val in series.dropna().items():
                    stmt = text("""
                        INSERT INTO economic_indicators (series_id, date, value, source)
                        VALUES (:sid, :date, :value, 'fred')
                        ON CONFLICT (series_id, date) DO UPDATE SET value = EXCLUDED.value
                    """)
                    await conn.execute(stmt, {
                        "sid": series_id,
                        "date": dt.date() if hasattr(dt, "date") else dt,
                        "value": float(val),
                    })
            logger.info("Persisted %d observations for %s", len(series.dropna()), series_id)
        except Exception as e:
            logger.warning("Failed to persist economic data: %s", e)

    # =========================================================================
    # Private: Helpers
    # =========================================================================

    async def _get_ticker_id_map(self, tickers: list[str]) -> dict[str, int]:
        """Get mapping of ticker -> instrument_id."""
        try:
            from src.db.engine import get_async_engine
            engine = get_async_engine()

            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT ticker, id FROM instruments WHERE ticker = ANY(:tickers)"),
                    {"tickers": tickers},
                )
                return {row[0]: row[1] for row in result.fetchall()}
        except Exception as e:
            logger.warning("Failed to get ticker ID map: %s", e)
            return {}

    async def _cache_series(self, cache_key: str, series: pd.Series) -> None:
        """Cache a pandas Series as JSON in Redis."""
        await cache.set_json(cache_key, {
            "dates": [str(d) for d in series.index],
            "values": [float(v) if pd.notna(v) else None for v in series.values],
        }, 3600)

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
