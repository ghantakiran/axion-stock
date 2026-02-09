"""Telegram Crawler (PRD-140).

Monitors Telegram channels/groups for stock-related messages.
Uses Telegram Bot API for channel reading.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import logging
import time

from src.sentiment.social import SocialPost
from src.social_crawler.base import (
    CrawlConfig,
    CrawlResult,
    CrawlerStats,
    CrawlStatus,
    PlatformType,
    extract_tickers,
    estimate_sentiment,
)

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig(CrawlConfig):
    """Telegram-specific configuration."""
    platform: PlatformType = PlatformType.TELEGRAM
    # Channel usernames to monitor (public channels)
    channel_usernames: list[str] = field(default_factory=lambda: [
        "WallStreetBets", "StockMarketAlerts", "CryptoSignals",
    ])
    # Group chat IDs (for groups bot is member of)
    group_ids: list[str] = field(default_factory=list)
    # Message limit per channel per crawl
    messages_per_channel: int = 50


class TelegramCrawler:
    """Crawls Telegram channels for stock-related messages.

    Uses Telegram Bot API to read channel/group message history.

    Example:
        crawler = TelegramCrawler(TelegramConfig(bot_token="..."))
        await crawler.connect()
        result = await crawler.crawl()
    """

    def __init__(self, config: Optional[TelegramConfig] = None):
        self._config = config or TelegramConfig()
        self._connected = False
        self._stats = CrawlerStats(platform=PlatformType.TELEGRAM)

    @property
    def platform(self) -> PlatformType:
        return PlatformType.TELEGRAM

    @property
    def stats(self) -> CrawlerStats:
        return self._stats

    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Connect to Telegram Bot API."""
        self._connected = True
        self._stats.status = CrawlStatus.RUNNING
        mode = "demo" if self._config.demo_mode or not self._config.bot_token else "live"
        logger.info(f"Telegram crawler connected ({mode} mode)")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self._stats.status = CrawlStatus.IDLE

    async def crawl(self) -> CrawlResult:
        """Execute one crawl cycle."""
        start = time.monotonic()
        posts: list[SocialPost] = []
        errors: list[str] = []

        if not self._config.demo_mode and self._config.bot_token:
            posts, errors = await self._crawl_live()
        else:
            posts = self._demo_posts()

        all_tickers: set[str] = set()
        for post in posts:
            if not post.tickers:
                post.tickers = extract_tickers(post.text)
            if post.sentiment == 0.0:
                post.sentiment = estimate_sentiment(post.text)
            all_tickers.update(post.tickers)

        result = CrawlResult(
            platform=PlatformType.TELEGRAM,
            posts=posts,
            post_count=len(posts),
            tickers_found=sorted(all_tickers),
            crawl_duration_ms=(time.monotonic() - start) * 1000,
            errors=errors,
        )
        self._stats.record_crawl(result)
        return result

    async def _crawl_live(self) -> tuple[list[SocialPost], list[str]]:
        """Crawl live Telegram channels."""
        posts: list[SocialPost] = []
        errors: list[str] = []

        try:
            import httpx
        except ImportError:
            errors.append("httpx not available for Telegram API")
            return posts, errors

        base_url = f"https://api.telegram.org/bot{self._config.bot_token}"

        async with httpx.AsyncClient(timeout=30) as client:
            # Get updates for groups the bot is in
            for channel in self._config.channel_usernames:
                try:
                    # For public channels, use getChat + forwardMessage approach
                    # or use a userbot library for full channel reading
                    resp = await client.get(
                        f"{base_url}/getUpdates",
                        params={"limit": self._config.messages_per_channel},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for update in data.get("result", []):
                            msg = update.get("channel_post") or update.get("message", {})
                            text = msg.get("text", "")
                            if len(text) < self._config.min_text_length:
                                continue

                            tickers = extract_tickers(text)
                            if not tickers:
                                continue

                            chat = msg.get("chat", {})
                            posts.append(SocialPost(
                                text=text,
                                source="telegram",
                                author=chat.get("title", channel),
                                timestamp=str(msg.get("date", "")),
                                upvotes=0,
                                comments=0,
                                sentiment=estimate_sentiment(text),
                                tickers=tickers,
                                url=f"https://t.me/{channel}",
                            ))

                except Exception as e:
                    errors.append(f"Channel {channel}: {str(e)}")

        return posts, errors

    def _demo_posts(self) -> list[SocialPost]:
        """Generate demo Telegram posts."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            SocialPost(
                text="🚨 ALERT: $NVDA cloud cross bullish on 1H chart. Entry 480, SL 470, TP 510.",
                source="telegram", author="StockSignals", timestamp=now,
                upvotes=0, comments=0, sentiment=0.8, tickers=["NVDA"],
            ),
            SocialPost(
                text="$BTC breaking $70K resistance. Next target $75K. $ETH following.",
                source="telegram", author="CryptoAlerts", timestamp=now,
                upvotes=0, comments=0, sentiment=0.9, tickers=["BTC", "ETH"],
            ),
            SocialPost(
                text="$AAPL earnings beat expectations. Revenue up 8% YoY. Strong guidance.",
                source="telegram", author="EarningsWatch", timestamp=now,
                upvotes=0, comments=0, sentiment=0.7, tickers=["AAPL"],
            ),
            SocialPost(
                text="Market outlook: Expecting SPY pullback to 460 support. Hedging with puts.",
                source="telegram", author="MacroAnalysis", timestamp=now,
                upvotes=0, comments=0, sentiment=-0.4, tickers=["SPY"],
            ),
        ]
