"""Backfill daily OHLCV price data into TimescaleDB.

Fetches data from Polygon.io (if API key set) or yfinance as fallback.
Processes tickers in batches with validation.

Usage:
    python -m scripts.backfill_daily --start 2005-01-01 --end 2026-01-27
    python -m scripts.backfill_daily --start 2024-01-01  # defaults end=today
    python -m scripts.backfill_daily --source yfinance --period 5y
"""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from src.db.engine import get_async_engine
from src.quality.validators import PriceValidator
from src.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def get_all_tickers() -> list[str]:
    """Get all active tickers from instruments table."""
    engine = get_async_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT ticker, id FROM instruments WHERE is_active = true ORDER BY ticker")
        )
        return [(row[0], row[1]) for row in result.fetchall()]


async def backfill_ticker_polygon(ticker: str, instrument_id: int, start: str, end: str):
    """Backfill one ticker from Polygon.io REST API."""
    from src.services.providers.polygon_provider import PolygonProvider

    provider = PolygonProvider()
    validator = PriceValidator()
    engine = get_async_engine()

    # Fetch in 2-year chunks to stay within API limits
    current = datetime.strptime(start, "%Y-%m-%d")
    final = datetime.strptime(end, "%Y-%m-%d")
    total_bars = 0

    while current < final:
        chunk_end = min(current + timedelta(days=730), final)
        df = await provider.fetch_historical(
            ticker,
            current.strftime("%Y-%m-%d"),
            chunk_end.strftime("%Y-%m-%d"),
        )

        if not df.empty:
            # Validate
            results = validator.validate_ohlcv(df, ticker)
            errors = [r for r in results if r.severity in ("error", "critical") and not r.passed]
            if errors:
                logger.warning("%s: validation errors: %s", ticker, [r.message for r in errors])

            # Insert into DB
            async with engine.begin() as conn:
                for dt_idx, row in df.iterrows():
                    await conn.execute(text("""
                        INSERT INTO price_bars (time, instrument_id, open, high, low, close, volume, adj_close, source)
                        VALUES (:time, :iid, :open, :high, :low, :close, :volume, :close, 'polygon')
                        ON CONFLICT (time, instrument_id) DO UPDATE SET
                            open = EXCLUDED.open, high = EXCLUDED.high,
                            low = EXCLUDED.low, close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """), {
                        "time": dt_idx, "iid": instrument_id,
                        "open": float(row.get("open", 0)),
                        "high": float(row.get("high", 0)),
                        "low": float(row.get("low", 0)),
                        "close": float(row.get("close", 0)),
                        "volume": int(row.get("volume", 0)),
                    })
            total_bars += len(df)

        current = chunk_end
        await asyncio.sleep(0.5)  # Rate limit

    return total_bars


async def backfill_ticker_yfinance(ticker: str, instrument_id: int, period: str):
    """Backfill one ticker from yfinance."""
    from src.services.providers.yfinance_provider import YFinanceProvider

    provider = YFinanceProvider()
    engine = get_async_engine()

    df = await provider.fetch_prices([ticker], period)
    if df.empty:
        return 0

    async with engine.begin() as conn:
        for dt_idx in df.index:
            price = df.loc[dt_idx].iloc[0] if len(df.columns) == 1 else df.loc[dt_idx, ticker]
            if price is None or (isinstance(price, float) and price != price):
                continue
            await conn.execute(text("""
                INSERT INTO price_bars (time, instrument_id, close, adj_close, source)
                VALUES (:time, :iid, :close, :close, 'yfinance')
                ON CONFLICT (time, instrument_id) DO UPDATE SET
                    close = EXCLUDED.close, adj_close = EXCLUDED.adj_close
            """), {"time": dt_idx, "iid": instrument_id, "close": float(price)})

    return len(df)


async def main():
    parser = argparse.ArgumentParser(description="Backfill daily OHLCV data")
    parser.add_argument("--start", default="2005-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"), help="End date")
    parser.add_argument("--source", default="auto", choices=["auto", "polygon", "yfinance"])
    parser.add_argument("--period", default="max", help="yfinance period (e.g. 5y, max)")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    use_polygon = args.source == "polygon" or (args.source == "auto" and settings.polygon_api_key)

    tickers_with_ids = await get_all_tickers()
    logger.info("Backfilling %d tickers using %s", len(tickers_with_ids),
                "Polygon" if use_polygon else "yfinance")

    total_bars = 0
    for i in range(0, len(tickers_with_ids), args.batch_size):
        batch = tickers_with_ids[i : i + args.batch_size]
        tasks = []
        for ticker, instrument_id in batch:
            if use_polygon:
                tasks.append(backfill_ticker_polygon(ticker, instrument_id, args.start, args.end))
            else:
                tasks.append(backfill_ticker_yfinance(ticker, instrument_id, args.period))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (ticker, _), result in zip(batch, results):
            if isinstance(result, Exception):
                logger.warning("Failed to backfill %s: %s", ticker, result)
            else:
                total_bars += result

        done = min(i + args.batch_size, len(tickers_with_ids))
        logger.info("Progress: %d/%d tickers, %d total bars", done, len(tickers_with_ids), total_bars)
        await asyncio.sleep(1)

    logger.info("Backfill complete: %d total bars inserted", total_bars)


if __name__ == "__main__":
    asyncio.run(main())
