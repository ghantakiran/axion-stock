"""Strategy Registry API — REST endpoints for PRD-177 multi-strategy bot.

Provides a FastAPI router with 6 endpoints for listing, inspecting,
enabling/disabling, and running strategies from the StrategyRegistry.
Uses StrategySelector (PRD-165) for A/B comparison stats.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import AuthContext, check_rate_limit, require_scope
from src.strategies import (
    StrategyRegistry,
    VWAPStrategy,
    ORBStrategy,
    RSIDivergenceStrategy,
    PullbackToCloudStrategy,
    TrendDayStrategy,
    SessionScalpStrategy,
    QullamaggieBreakoutStrategy,
    EpisodicPivotStrategy,
    ParabolicShortStrategy,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategies", tags=["strategies"])

# ── Lazy-loaded singleton registry ───────────────────────────────────

_registry: Optional[StrategyRegistry] = None


def _get_registry() -> StrategyRegistry:
    """Return the module-level StrategyRegistry, creating it on first call."""
    global _registry
    if _registry is not None:
        return _registry

    _registry = StrategyRegistry()
    _registry.register(VWAPStrategy(), description="VWAP mean-reversion", category="mean-reversion")
    _registry.register(ORBStrategy(), description="Opening range breakout", category="breakout")
    _registry.register(RSIDivergenceStrategy(), description="RSI divergence detection", category="divergence")
    _registry.register(PullbackToCloudStrategy(), description="Pullback to EMA cloud", category="trend")
    _registry.register(TrendDayStrategy(), description="Trend day momentum", category="trend")
    _registry.register(SessionScalpStrategy(), description="Intraday session scalping", category="scalping")
    _registry.register(QullamaggieBreakoutStrategy(), description="Qullamaggie flag breakout", category="momentum")
    _registry.register(EpisodicPivotStrategy(), description="Qullamaggie episodic pivot", category="momentum")
    _registry.register(ParabolicShortStrategy(), description="Qullamaggie parabolic short", category="momentum")
    return _registry


# ── Request / Response models ────────────────────────────────────────


class StrategyItem(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    enabled: bool = True
    registered_at: str = ""


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="Symbol to analyze")
    opens: list[float] = Field(..., description="Open prices")
    highs: list[float] = Field(..., description="High prices")
    lows: list[float] = Field(..., description="Low prices")
    closes: list[float] = Field(..., description="Close prices")
    volumes: list[float] = Field(..., description="Volume data")


class AnalyzeResult(BaseModel):
    strategy: str
    signal: Optional[dict] = None


class MessageResponse(BaseModel):
    message: str


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=list[StrategyItem])
async def list_strategies(auth: AuthContext = Depends(check_rate_limit)) -> list[StrategyItem]:
    """List all registered strategies with their enabled/disabled status."""
    try:
        registry = _get_registry()
        items = registry.list_strategies()
        return [StrategyItem(**item) for item in items]
    except Exception as e:
        logger.error("Failed to list strategies: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to list strategies: {e}")


@router.get("/stats")
async def get_strategy_stats(auth: AuthContext = Depends(check_rate_limit)) -> dict:
    """Get A/B comparison stats from StrategySelector (PRD-165)."""
    try:
        from src.strategy_selector import StrategySelector
        selector = StrategySelector()
        return selector.get_strategy_stats()
    except ImportError:
        raise HTTPException(status_code=501, detail="StrategySelector module not available")
    except Exception as e:
        logger.error("Failed to get strategy stats: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to get strategy stats: {e}")


@router.get("/{name}", response_model=StrategyItem)
async def get_strategy(name: str, auth: AuthContext = Depends(check_rate_limit)) -> StrategyItem:
    """Get details of a single strategy by name."""
    try:
        registry = _get_registry()
        for item in registry.list_strategies():
            if item["name"] == name:
                return StrategyItem(**item)
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get strategy %s: %s", name, e)
        raise HTTPException(status_code=500, detail=f"Failed to get strategy: {e}")


@router.put("/{name}/enable", response_model=MessageResponse)
async def enable_strategy(
    name: str,
    auth: AuthContext = Depends(require_scope("write")),
) -> MessageResponse:
    """Enable a strategy for signal generation."""
    try:
        registry = _get_registry()
        if not registry.enable(name):
            raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
        return MessageResponse(message=f"Strategy '{name}' enabled")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to enable strategy %s: %s", name, e)
        raise HTTPException(status_code=500, detail=f"Failed to enable strategy: {e}")


@router.put("/{name}/disable", response_model=MessageResponse)
async def disable_strategy(
    name: str,
    auth: AuthContext = Depends(require_scope("write")),
) -> MessageResponse:
    """Disable a strategy — it will be skipped during signal generation."""
    try:
        registry = _get_registry()
        if not registry.disable(name):
            raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
        return MessageResponse(message=f"Strategy '{name}' disabled")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to disable strategy %s: %s", name, e)
        raise HTTPException(status_code=500, detail=f"Failed to disable strategy: {e}")


@router.post("/{name}/analyze", response_model=AnalyzeResult)
async def analyze_strategy(
    name: str,
    request: AnalyzeRequest,
    auth: AuthContext = Depends(require_scope("write")),
) -> AnalyzeResult:
    """Run a single strategy against provided OHLCV data."""
    try:
        registry = _get_registry()
        strategy = registry.get_strategy(name)
        if strategy is None:
            raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")

        signal = strategy.analyze(
            request.ticker,
            request.opens,
            request.highs,
            request.lows,
            request.closes,
            request.volumes,
        )
        return AnalyzeResult(
            strategy=name,
            signal=signal.to_dict() if signal is not None else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Strategy %s analysis failed: %s", name, e)
        raise HTTPException(status_code=500, detail=f"Strategy analysis failed: {e}")
