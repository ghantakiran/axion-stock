"""Market Data API Routes.

Endpoints for quotes, OHLCV bars, fundamentals, and universe data.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    QuoteResponse,
    OHLCVResponse,
    OHLCVBar,
    FundamentalsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/quotes/{symbol}", response_model=QuoteResponse)
async def get_quote(symbol: str) -> QuoteResponse:
    """Get current quote for a symbol."""
    symbol = symbol.upper()

    # In production, would fetch from data service
    return QuoteResponse(
        symbol=symbol,
        price=0.0,
        timestamp=datetime.utcnow(),
    )


@router.get("/ohlcv/{symbol}", response_model=OHLCVResponse)
async def get_ohlcv(
    symbol: str,
    bar: str = Query(default="1d", pattern="^(1m|5m|15m|1h|1d|1w|1M)$"),
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> OHLCVResponse:
    """Get historical OHLCV bars."""
    symbol = symbol.upper()

    return OHLCVResponse(
        symbol=symbol,
        bar_type=bar,
        bars=[],
        count=0,
    )


@router.get("/fundamentals/{symbol}", response_model=FundamentalsResponse)
async def get_fundamentals(symbol: str) -> FundamentalsResponse:
    """Get fundamental data for a symbol."""
    symbol = symbol.upper()

    return FundamentalsResponse(
        symbol=symbol,
    )


@router.get("/universe/{index}")
async def get_universe(index: str) -> dict:
    """Get constituent symbols for a market index/universe."""
    index = index.lower()
    valid_indices = ["sp500", "nasdaq100", "dowjones", "russell2000"]

    if index not in valid_indices:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown index: {index}. Valid: {valid_indices}",
        )

    return {
        "index": index,
        "symbols": [],
        "count": 0,
    }
