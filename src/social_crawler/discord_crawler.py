"""Discord Crawler (PRD-140).

Monitors Discord channels for stock-related messages using discord.py bot.
Falls back to demo data when bot token isn't available.
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

_HAS_DISCORD = False
try:
    import discord
    _HAS_DISCORD = True
except ImportError:
    discord = None  # type: ignore


@dataclass
class DiscordConfig(CrawlConfig):
    """Discord-specific configuration."""
    platform: PlatformType = PlatformType.DISCORD
    # Channel IDs to monitor (numeric string IDs)
    channel_ids: list[str] = field(default_factory=list)
    # Server/guild IDs
    guild_ids: list[str] = field(default_factory=list)
    # Only channels with these name patterns
    channel_name_patterns: list[str] = field(default_factory=lambda: [
        "stock", "trading", "options", "crypto", "market",
        "signals", "alerts", "plays", "discussion",
    ])
    # Message history depth
    message_limit: int = 100
    # Filtering
    min_reactions: int = 1


class DiscordCrawler:
    """Crawls Discord servers for stock-related messages.

    Reads message history from configured channels. Requires a
    Discord bot token with MESSAGE_CONTENT intent.

    Example:
        crawler = DiscordCrawler(DiscordConfig(bot_token="..."))
        await crawler.connect()
        result = await crawler.crawl()
    """

    def __init__(self, config: Optional[DiscordConfig] = None):
        self._config = config or DiscordConfig()
        self._connected = False
        self._stats = CrawlerStats(platform=PlatformType.DISCORD)
        self._message_cache: list[dict] = []

    @property
    def platform(self) -> PlatformType:
        return PlatformType.DISCORD

    @property
    def stats(self) -> CrawlerStats:
        return self._stats

    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Connect to Discord."""
        # Discord bot runs as a persistent connection via discord.py
        # For crawling, we use the HTTP API to fetch message history
        self._connected = True
        self._stats.status = CrawlStatus.RUNNING
        mode = "demo" if self._config.demo_mode or not self._config.bot_token else "live"
        logger.info(f"Discord crawler connected ({mode} mode)")
        return True

    async def disconnect(self) -> None:
        """Disconnect from Discord."""
        self._connected = False
        self._stats.status = CrawlStatus.IDLE

    async def crawl(self) -> CrawlResult:
        """Execute one crawl cycle."""
        start = time.monotonic()
        posts: list[SocialPost] = []
        errors: list[str] = []

        if not self._config.demo_mode and self._config.bot_token and _HAS_DISCORD:
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
            platform=PlatformType.DISCORD,
            posts=posts,
            post_count=len(posts),
            tickers_found=sorted(all_tickers),
            crawl_duration_ms=(time.monotonic() - start) * 1000,
            errors=errors,
        )
        self._stats.record_crawl(result)
        return result

    async def _crawl_live(self) -> tuple[list[SocialPost], list[str]]:
        """Crawl live Discord channels via HTTP API."""
        posts: list[SocialPost] = []
        errors: list[str] = []

        try:
            _HAS_HTTPX = False
            try:
                import httpx
                _HAS_HTTPX = True
            except ImportError:
                pass

            if not _HAS_HTTPX:
                errors.append("httpx not available for Discord HTTP API")
                return posts, errors

            headers = {"Authorization": f"Bot {self._config.bot_token}"}

            async with httpx.AsyncClient(
                base_url="https://discord.com/api/v10",
                headers=headers,
                timeout=30,
            ) as client:
                for channel_id in self._config.channel_ids:
                    try:
                        resp = await client.get(
                            f"/channels/{channel_id}/messages",
                            params={"limit": self._config.message_limit},
                        )
                        if resp.status_code != 200:
                            errors.append(f"Channel {channel_id}: HTTP {resp.status_code}")
                            continue

                        for msg in resp.json():
                            content = msg.get("content", "")
                            if len(content) < self._config.min_text_length:
                                continue

                            tickers = extract_tickers(content)
                            if not tickers:
                                continue

                            reactions = sum(
                                r.get("count", 0)
                                for r in msg.get("reactions", [])
                            )

                            if reactions < self._config.min_reactions:
                                continue

                            author = msg.get("author", {})
                            posts.append(SocialPost(
                                text=content,
                                source="discord",
                                author=author.get("username", ""),
                                timestamp=msg.get("timestamp", ""),
                                upvotes=reactions,
                                comments=0,
                                sentiment=estimate_sentiment(content),
                                tickers=tickers,
                                url=f"https://discord.com/channels/-/{channel_id}/{msg['id']}",
                            ))

                    except Exception as e:
                        errors.append(f"Channel {channel_id}: {str(e)}")

        except Exception as e:
            errors.append(f"Discord API error: {str(e)}")

        return posts, errors

    def _demo_posts(self) -> list[SocialPost]:
        """Generate demo Discord posts."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            SocialPost(
                text="🟢 AAPL EMA cloud cross on 15m. Entering long at 185.20. Stop at 183.50.",
                source="discord", author="signal_bot", timestamp=now,
                upvotes=12, comments=0, sentiment=0.8, tickers=["AAPL"],
            ),
            SocialPost(
                text="NVDA breakout confirmed on daily. Volume surge 2x average. Target $550.",
                source="discord", author="chart_master", timestamp=now,
                upvotes=28, comments=0, sentiment=0.9, tickers=["NVDA"],
            ),
            SocialPost(
                text="$SPY rejecting at 480 again. Third time is NOT the charm. Going short here.",
                source="discord", author="bear_chad", timestamp=now,
                upvotes=8, comments=0, sentiment=-0.6, tickers=["SPY"],
            ),
            SocialPost(
                text="TSLA 0DTE calls looking juicy after this dip. IV crush risk though.",
                source="discord", author="options_yolo", timestamp=now,
                upvotes=15, comments=0, sentiment=0.4, tickers=["TSLA"],
            ),
            SocialPost(
                text="AMD earnings play: long straddle ATM. Expecting big move either way.",
                source="discord", author="vol_trader", timestamp=now,
                upvotes=22, comments=0, sentiment=0.1, tickers=["AMD"],
            ),
        ]
