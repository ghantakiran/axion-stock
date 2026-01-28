"""Backfill fundamental data for all instruments.

Usage:
    python -m scripts.backfill_fundamentals
"""

import asyncio
import logging
from datetime import date

from sqlalchemy import text

from src.db.engine import get_async_engine
from src.services.providers.yfinance_provider import YFinanceProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def backfill_fundamentals():
    """Fetch and persist fundamentals for all active instruments."""
    engine = get_async_engine()
    provider = YFinanceProvider()

    # Get all active tickers with IDs
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT ticker, id FROM instruments WHERE is_active = true ORDER BY ticker")
        )
        tickers_with_ids = [(row[0], row[1]) for row in result.fetchall()]

    logger.info("Fetching fundamentals for %d tickers", len(tickers_with_ids))

    tickers = [t for t, _ in tickers_with_ids]
    id_map = {t: i for t, i in tickers_with_ids}

    # Fetch in batches
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        df = await provider.fetch_fundamentals(batch)

        if df.empty:
            continue

        today = date.today()
        async with engine.begin() as conn:
            for ticker in df.index:
                if ticker not in id_map:
                    continue
                row = df.loc[ticker]
                try:
                    await conn.execute(text("""
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
                    """), {
                        "iid": id_map[ticker],
                        "date": today,
                        "pe": _safe(row.get("trailingPE")),
                        "pb": _safe(row.get("priceToBook")),
                        "dy": _safe(row.get("dividendYield")),
                        "ev": _safe(row.get("enterpriseToEbitda")),
                        "roe": _safe(row.get("returnOnEquity")),
                        "de": _safe(row.get("debtToEquity")),
                        "rg": _safe(row.get("revenueGrowth")),
                        "eg": _safe(row.get("earningsGrowth")),
                        "mc": _safe_int(row.get("marketCap")),
                        "cp": _safe(row.get("currentPrice")),
                    })
                except Exception as e:
                    logger.warning("Failed to insert fundamentals for %s: %s", ticker, e)

        logger.info("Progress: %d/%d tickers", min(i + batch_size, len(tickers)), len(tickers))

    logger.info("Fundamentals backfill complete")


def _safe(val):
    if val is None:
        return None
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    if val is None:
        return None
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else int(f)
    except (ValueError, TypeError):
        return None


def main():
    asyncio.run(backfill_fundamentals())


if __name__ == "__main__":
    main()
