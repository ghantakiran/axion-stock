"""PRD-172: Bot API — REST endpoints for remote bot control.

Provides a FastAPI router with 11 endpoints for starting, stopping,
pausing, resuming, killing, and monitoring the trading bot.
Uses BotController from src/bot_dashboard/state.py as the backend.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.bot_dashboard.state import BotController, DashboardConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["Bot"])

# Shared BotController instance (singleton per API process)
_controller = BotController()


def get_controller() -> BotController:
    """Return the global BotController instance."""
    return _controller


# ── Request / Response models ────────────────────────────────────────


class StartRequest(BaseModel):
    paper_mode: bool = True


class KillRequest(BaseModel):
    reason: str = "API kill switch"


class ConfigUpdate(BaseModel):
    refresh_interval_seconds: Optional[int] = None
    pnl_chart_lookback_days: Optional[int] = None
    max_signals_displayed: Optional[int] = None
    max_events_displayed: Optional[int] = None
    enable_sound_alerts: Optional[bool] = None
    paper_mode: Optional[bool] = None


class BotStatusResponse(BaseModel):
    status: str
    instrument_mode: str
    uptime_seconds: int
    account_equity: float
    daily_pnl: float
    daily_pnl_pct: float
    win_rate: float
    total_trades_today: int
    open_positions: int
    kill_switch_active: bool
    data_feed_status: str


class PositionItem(BaseModel):
    ticker: str
    direction: str
    entry_price: float
    current_price: float
    shares: float
    pnl: float
    pnl_pct: float


class HistoryItem(BaseModel):
    success: bool
    ticker: str
    direction: str
    conviction: float
    pipeline_stage: str
    rejection_reason: Optional[str] = None
    signal_id: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/start", response_model=MessageResponse)
async def start_bot(request: StartRequest) -> MessageResponse:
    """Start the trading bot in paper or live mode."""
    ctrl = get_controller()
    if ctrl.state.is_active:
        raise HTTPException(status_code=409, detail="Bot is already running")
    ctrl.start(paper_mode=request.paper_mode)
    mode = "paper" if request.paper_mode else "live"
    return MessageResponse(message=f"Bot started in {mode} mode")


@router.post("/stop", response_model=MessageResponse)
async def stop_bot() -> MessageResponse:
    """Gracefully stop the bot (pause + clear state)."""
    ctrl = get_controller()
    ctrl.pause()
    return MessageResponse(message="Bot stopped")


@router.post("/pause", response_model=MessageResponse)
async def pause_bot() -> MessageResponse:
    """Pause signal processing (keep monitoring positions)."""
    ctrl = get_controller()
    if ctrl.state.status == "paused":
        raise HTTPException(status_code=409, detail="Bot is already paused")
    ctrl.pause()
    return MessageResponse(message="Bot paused")


@router.post("/resume", response_model=MessageResponse)
async def resume_bot() -> MessageResponse:
    """Resume signal processing."""
    ctrl = get_controller()
    if ctrl.state.status != "paused":
        raise HTTPException(status_code=409, detail="Bot is not paused")
    ctrl.resume()
    return MessageResponse(message="Bot resumed")


@router.post("/kill", response_model=MessageResponse)
async def kill_bot(request: KillRequest) -> MessageResponse:
    """Emergency kill switch — halt all trading immediately."""
    ctrl = get_controller()
    ctrl.kill(reason=request.reason)
    return MessageResponse(message=f"Kill switch activated: {request.reason}")


@router.post("/kill/reset", response_model=MessageResponse)
async def reset_kill_switch() -> MessageResponse:
    """Reset the kill switch (bot goes to paused state)."""
    ctrl = get_controller()
    if not ctrl.state.kill_switch_active:
        raise HTTPException(status_code=409, detail="Kill switch is not active")
    ctrl.reset_kill_switch()
    return MessageResponse(message="Kill switch reset — bot paused")


@router.get("/status", response_model=BotStatusResponse)
async def get_status() -> BotStatusResponse:
    """Get full bot state snapshot."""
    ctrl = get_controller()
    state = ctrl.state
    return BotStatusResponse(**state.to_dict())


@router.get("/positions")
async def get_positions() -> list[dict]:
    """Get open positions with P&L."""
    # Positions come from the orchestrator if wired, otherwise empty
    return []


@router.get("/history")
async def get_history(
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Get execution history (paginated)."""
    ctrl = get_controller()
    events = ctrl.get_events(limit=limit + offset)
    paginated = events[offset : offset + limit]
    return [e.to_dict() for e in paginated]


@router.put("/config", response_model=MessageResponse)
async def update_config(update: ConfigUpdate) -> MessageResponse:
    """Hot-update bot configuration parameters."""
    ctrl = get_controller()
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No config fields provided")
    ctrl.update_config(updates)
    return MessageResponse(message=f"Config updated: {list(updates.keys())}")


@router.get("/config")
async def get_config() -> dict:
    """Get current bot configuration."""
    ctrl = get_controller()
    cfg = ctrl.config
    return {
        "refresh_interval_seconds": cfg.refresh_interval_seconds,
        "pnl_chart_lookback_days": cfg.pnl_chart_lookback_days,
        "max_signals_displayed": cfg.max_signals_displayed,
        "max_events_displayed": cfg.max_events_displayed,
        "enable_sound_alerts": cfg.enable_sound_alerts,
        "paper_mode": cfg.paper_mode,
    }
