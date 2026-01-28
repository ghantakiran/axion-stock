"""Populate the instruments table with S&P 500 constituents.

Usage:
    python -m scripts.backfill_instruments
"""

import asyncio
import logging
import sys

from sqlalchemy import text

from src.db.engine import get_async_engine
from src.services.providers.yfinance_provider import YFinanceProvider
from src.universe import build_universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def backfill_instruments():
    """Populate instruments table from S&P 500 universe."""
    logger.info("Building universe...")
    tickers = build_universe()
    logger.info("Found %d tickers", len(tickers))

    engine = get_async_engine()
    provider = YFinanceProvider()

    inserted = 0
    batch_size = 50

    async with engine.begin() as conn:
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            for ticker in batch:
                try:
                    # Try to get metadata from yfinance
                    quote = await provider.get_quote(ticker)
                    name = quote.get("name", "") if quote else ""
                    sector = quote.get("sector", "") if quote else ""

                    await conn.execute(text("""
                        INSERT INTO instruments (ticker, name, asset_type, sector, is_active)
                        VALUES (:ticker, :name, 'STOCK', :sector, true)
                        ON CONFLICT (ticker) DO UPDATE SET
                            name = EXCLUDED.name,
                            sector = EXCLUDED.sector,
                            is_active = true
                    """), {"ticker": ticker, "name": name, "sector": sector})
                    inserted += 1
                except Exception as e:
                    logger.warning("Failed to insert %s: %s", ticker, e)

            logger.info("Progress: %d/%d tickers", min(i + batch_size, len(tickers)), len(tickers))

    logger.info("Backfill complete: %d instruments inserted/updated", inserted)


def main():
    asyncio.run(backfill_instruments())


if __name__ == "__main__":
    main()
