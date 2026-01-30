"""AI & Predictions API Routes.

Endpoints for AI chat, ML predictions, and sentiment analysis.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from src.api.models import (
    ChatRequest,
    ChatResponse,
    PredictionResponse,
    SentimentResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI & Predictions"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with AI assistant."""
    return ChatResponse(
        response="AI chat is not available in this demo.",
        sources=[],
        symbols_mentioned=[],
    )


@router.get("/predictions/{symbol}", response_model=PredictionResponse)
async def get_prediction(symbol: str) -> PredictionResponse:
    """Get ML prediction for a symbol."""
    return PredictionResponse(
        symbol=symbol.upper(),
        direction="neutral",
        as_of=datetime.utcnow(),
    )


@router.get("/sentiment/{symbol}", response_model=SentimentResponse)
async def get_sentiment(symbol: str) -> SentimentResponse:
    """Get sentiment analysis for a symbol."""
    return SentimentResponse(
        symbol=symbol.upper(),
        as_of=datetime.utcnow(),
    )


@router.get("/picks/{category}")
async def get_picks(
    category: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Get AI stock picks by category."""
    valid = ["momentum", "value", "growth", "income", "overall"]
    category = category.lower()

    return {
        "category": category,
        "picks": [],
        "count": 0,
    }
