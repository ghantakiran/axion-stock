"""Factor Scores API Routes.

Endpoints for factor scores, screening, and market regime.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import AuthContext, check_rate_limit
from src.api.models import (
    FactorScoreResponse,
    ScreenRequest,
    ScreenResponse,
    RegimeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/factors", tags=["Factors"])


@router.get("/{symbol}", response_model=FactorScoreResponse)
async def get_factor_scores(
    symbol: str,
    as_of: Optional[date] = None,
    auth: AuthContext = Depends(check_rate_limit),
) -> FactorScoreResponse:
    """Get all factor scores for a symbol."""
    symbol = symbol.upper()

    return FactorScoreResponse(
        symbol=symbol,
        date=as_of or date.today(),
    )


@router.get("/{symbol}/history")
async def get_factor_history(
    symbol: str,
    factor: str = "composite",
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = Query(default=252, ge=1, le=1260),
    auth: AuthContext = Depends(check_rate_limit),
) -> dict:
    """Get historical factor scores for a symbol."""
    symbol = symbol.upper()

    return {
        "symbol": symbol,
        "factor": factor,
        "history": [],
        "count": 0,
    }


@router.get("/screen/results", response_model=ScreenResponse)
async def screen_factors(
    factor: str = Query(default="composite"),
    top: int = Query(default=20, ge=1, le=100),
    universe: str = Query(default="sp500"),
    sector: Optional[str] = None,
    min_market_cap: Optional[float] = None,
    auth: AuthContext = Depends(check_rate_limit),
) -> ScreenResponse:
    """Screen stocks by factor scores."""
    return ScreenResponse(
        factor=factor,
        results=[],
        count=0,
        universe=universe,
    )


@router.get("/regime", response_model=RegimeResponse)
async def get_regime(auth: AuthContext = Depends(check_rate_limit)) -> RegimeResponse:
    """Get current market regime."""
    return RegimeResponse(
        regime="unknown",
        confidence=0.0,
    )
