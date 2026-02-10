"""Backtesting API Routes.

Endpoints for running backtests and retrieving results.
"""

import logging
import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import AuthContext, check_rate_limit, require_scope
from src.api.models import (
    BacktestRequest,
    BacktestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["Backtesting"])

# In-memory store
_backtests: dict[str, BacktestResponse] = {}


@router.post("", response_model=BacktestResponse, status_code=201)
async def run_backtest(request: BacktestRequest, auth: AuthContext = Depends(require_scope("write"))) -> BacktestResponse:
    """Run a backtest."""
    backtest_id = secrets.token_hex(8)

    result = BacktestResponse(
        backtest_id=backtest_id,
        strategy=request.strategy,
        start_date=request.start_date,
        end_date=request.end_date,
        status="completed",
    )

    _backtests[backtest_id] = result
    return result


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(backtest_id: str, auth: AuthContext = Depends(check_rate_limit)) -> BacktestResponse:
    """Get backtest results."""
    result = _backtests.get(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Backtest not found: {backtest_id}")
    return result


@router.get("/{backtest_id}/tearsheet")
async def get_tearsheet(backtest_id: str, auth: AuthContext = Depends(check_rate_limit)) -> dict:
    """Get backtest tear sheet."""
    result = _backtests.get(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Backtest not found: {backtest_id}")

    return {
        "backtest_id": backtest_id,
        "strategy": result.strategy,
        "tearsheet": "Tear sheet data not available in demo.",
    }
