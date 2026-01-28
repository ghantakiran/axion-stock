"""Compute and persist factor scores for all instruments.

Runs the existing factor model and saves results to the database.

Usage:
    python -m scripts.compute_scores
"""

import asyncio
import logging
from datetime import date

from sqlalchemy import text

from src.db.engine import get_async_engine
from src.services.sync_adapter import sync_data_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def compute_and_persist_scores():
    """Run factor model and persist scores to database."""
    logger.info("Building universe...")
    tickers = sync_data_service.build_universe()
    logger.info("Universe: %d tickers", len(tickers))

    logger.info("Downloading prices...")
    prices = sync_data_service.download_price_data(tickers)

    logger.info("Downloading fundamentals...")
    fundamentals = sync_data_service.download_fundamentals(tickers)

    logger.info("Filtering universe...")
    valid_tickers = sync_data_service.filter_universe(fundamentals, prices)
    logger.info("Valid tickers after filtering: %d", len(valid_tickers))

    logger.info("Computing returns...")
    returns = sync_data_service.compute_price_returns(prices)

    logger.info("Computing factor scores...")
    from src.factor_model import compute_composite_scores
    scores = compute_composite_scores(fundamentals, returns)
    logger.info("Computed scores for %d tickers", len(scores))

    # Persist to database
    engine = get_async_engine()
    today = date.today()

    # Get ticker -> instrument_id mapping
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT ticker, id FROM instruments WHERE is_active = true")
        )
        id_map = {row[0]: row[1] for row in result.fetchall()}

    persisted = 0
    async with engine.begin() as conn:
        for ticker in scores.index:
            if ticker not in id_map:
                continue
            row = scores.loc[ticker]
            try:
                await conn.execute(text("""
                    INSERT INTO factor_scores
                        (instrument_id, computed_date, value_score, momentum_score,
                         quality_score, growth_score, composite_score)
                    VALUES (:iid, :date, :v, :m, :q, :g, :c)
                    ON CONFLICT (instrument_id, computed_date) DO UPDATE SET
                        value_score = EXCLUDED.value_score,
                        momentum_score = EXCLUDED.momentum_score,
                        quality_score = EXCLUDED.quality_score,
                        growth_score = EXCLUDED.growth_score,
                        composite_score = EXCLUDED.composite_score
                """), {
                    "iid": id_map[ticker],
                    "date": today,
                    "v": _safe(row.get("value")),
                    "m": _safe(row.get("momentum")),
                    "q": _safe(row.get("quality")),
                    "g": _safe(row.get("growth")),
                    "c": _safe(row.get("composite")),
                })
                persisted += 1
            except Exception as e:
                logger.warning("Failed to persist scores for %s: %s", ticker, e)

    logger.info("Score computation complete: %d scores persisted", persisted)


def _safe(val):
    if val is None:
        return None
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def main():
    asyncio.run(compute_and_persist_scores())


if __name__ == "__main__":
    main()
