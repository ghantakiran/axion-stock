"""Channel router for WebSocket API."""

from dataclasses import dataclass
from typing import Optional, Callable, Any

from src.websocket.config import ChannelType, MessageType, CHANNEL_CONFIGS
from src.websocket.models import (
    StreamMessage,
    QuoteData,
    TradeData,
    BarData,
    OrderUpdate,
    PortfolioUpdate,
    AlertNotification,
)
from src.websocket.manager import ConnectionManager


class ChannelRouter:
    """Routes messages to appropriate channels."""

    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        self._handlers: dict[ChannelType, Callable] = {}

    def register_handler(self, channel: ChannelType, handler: Callable) -> None:
        """Register a handler for a channel."""
        self._handlers[channel] = handler

    def get_channel_info(self, channel: ChannelType) -> dict:
        """Get channel configuration info."""
        config = CHANNEL_CONFIGS.get(channel, {})
        return {
            "channel": channel.value,
            "description": config.get("description", ""),
            "requires_symbols": config.get("requires_symbols", False),
            "default_throttle_ms": config.get("default_throttle_ms", 100),
            "max_symbols": config.get("max_symbols", 500),
        }

    def list_channels(self) -> list[dict]:
        """List all available channels."""
        return [self.get_channel_info(ch) for ch in ChannelType]

    def publish_quote(self, quote: QuoteData) -> int:
        """Publish a quote update."""
        return self.manager.broadcast_to_channel(
            ChannelType.QUOTES,
            quote.to_dict(),
            symbol=quote.symbol,
        )

    def publish_trade(self, trade: TradeData) -> int:
        """Publish a trade."""
        return self.manager.broadcast_to_channel(
            ChannelType.TRADES,
            trade.to_dict(),
            symbol=trade.symbol,
        )

    def publish_bar(self, bar: BarData) -> int:
        """Publish an OHLC bar."""
        return self.manager.broadcast_to_channel(
            ChannelType.BARS,
            bar.to_dict(),
            symbol=bar.symbol,
        )

    def publish_order_update(self, user_id: str, order: OrderUpdate) -> int:
        """Publish order update to a specific user."""
        message = StreamMessage(
            type=MessageType.UPDATE,
            channel=ChannelType.ORDERS,
            data=order.to_dict(),
        )
        return self.manager.send_to_user(user_id, message)

    def publish_portfolio_update(self, user_id: str, portfolio: PortfolioUpdate) -> int:
        """Publish portfolio update to a specific user."""
        message = StreamMessage(
            type=MessageType.UPDATE,
            channel=ChannelType.PORTFOLIO,
            data=portfolio.to_dict(),
        )
        return self.manager.send_to_user(user_id, message)

    def publish_alert(self, user_id: str, alert: AlertNotification) -> int:
        """Publish alert notification to a specific user."""
        message = StreamMessage(
            type=MessageType.UPDATE,
            channel=ChannelType.ALERTS,
            data=alert.to_dict(),
        )
        return self.manager.send_to_user(user_id, message)

    def publish_news(self, headline: str, source: str, symbols: list[str], sentiment: str = "neutral") -> int:
        """Publish news to interested subscribers."""
        data = {
            "headline": headline,
            "source": source,
            "symbols": symbols,
            "sentiment": sentiment,
        }

        total = 0
        # Publish to each symbol's subscribers
        for symbol in symbols:
            total += self.manager.broadcast_to_channel(
                ChannelType.NEWS,
                data,
                symbol=symbol,
            )

        return total

    def get_snapshot(self, channel: ChannelType, symbol: Optional[str] = None) -> Optional[dict]:
        """Get current snapshot for a channel/symbol."""
        # In a real implementation, this would fetch current state
        if channel == ChannelType.QUOTES and symbol:
            return self._mock_quote_snapshot(symbol)
        elif channel == ChannelType.BARS and symbol:
            return self._mock_bar_snapshot(symbol)
        elif channel == ChannelType.PORTFOLIO:
            return self._mock_portfolio_snapshot()

        return None

    def _mock_quote_snapshot(self, symbol: str) -> dict:
        """Generate mock quote snapshot."""
        return QuoteData(
            symbol=symbol,
            bid=185.50,
            ask=185.52,
            last=185.51,
            bid_size=100,
            ask_size=200,
            volume=45000000,
            change=2.51,
            change_pct=1.37,
        ).to_dict()

    def _mock_bar_snapshot(self, symbol: str) -> dict:
        """Generate mock bar snapshot."""
        return BarData(
            symbol=symbol,
            interval="1m",
            open=185.00,
            high=185.75,
            low=184.80,
            close=185.51,
            volume=150000,
            vwap=185.25,
            trade_count=500,
        ).to_dict()

    def _mock_portfolio_snapshot(self) -> dict:
        """Generate mock portfolio snapshot."""
        return PortfolioUpdate(
            total_value=100000.0,
            cash_balance=10000.0,
            positions_value=90000.0,
            day_pnl=500.0,
            day_return_pct=0.5,
            total_pnl=15000.0,
            total_return_pct=17.6,
            buying_power=50000.0,
            positions=[
                {"symbol": "AAPL", "quantity": 100, "value": 18550},
                {"symbol": "MSFT", "quantity": 50, "value": 21000},
            ],
        ).to_dict()
