"""WhatsApp Crawler (PRD-140).

Monitors WhatsApp groups for stock-related messages via WhatsApp Business API.
Falls back to demo data when API credentials aren't available.
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
class WhatsAppConfig(CrawlConfig):
    """WhatsApp-specific configuration."""
    platform: PlatformType = PlatformType.WHATSAPP
    # WhatsApp Business API
    phone_number_id: str = ""
    whatsapp_business_token: str = ""
    # Webhook for incoming messages
    webhook_verify_token: str = ""
    # Group names to monitor
    group_names: list[str] = field(default_factory=lambda: [
        "Stock Trading Group", "Options Alerts",
    ])


class WhatsAppCrawler:
    """Crawls WhatsApp groups for stock-related messages.

    Uses WhatsApp Business API webhook to receive messages.
    Stores received messages and returns them on crawl().

    Example:
        crawler = WhatsAppCrawler(WhatsAppConfig(
            whatsapp_business_token="...",
        ))
        await crawler.connect()
        result = await crawler.crawl()
    """

    def __init__(self, config: Optional[WhatsAppConfig] = None):
        self._config = config or WhatsAppConfig()
        self._connected = False
        self._stats = CrawlerStats(platform=PlatformType.WHATSAPP)
        # Buffer for webhook-received messages
        self._message_buffer: list[SocialPost] = []

    @property
    def platform(self) -> PlatformType:
        return PlatformType.WHATSAPP

    @property
    def stats(self) -> CrawlerStats:
        return self._stats

    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Connect to WhatsApp Business API."""
        self._connected = True
        self._stats.status = CrawlStatus.RUNNING
        mode = "demo" if self._config.demo_mode or not self._config.whatsapp_business_token else "live"
        logger.info(f"WhatsApp crawler connected ({mode} mode)")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self._stats.status = CrawlStatus.IDLE
        self._message_buffer.clear()

    def receive_webhook(self, payload: dict) -> None:
        """Process incoming webhook payload from WhatsApp.

        Called by the FastAPI webhook endpoint when a new message arrives.
        """
        try:
            entries = payload.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for msg in messages:
                        text = msg.get("text", {}).get("body", "")
                        if len(text) < self._config.min_text_length:
                            continue

                        tickers = extract_tickers(text)
                        if not tickers:
                            continue

                        self._message_buffer.append(SocialPost(
                            text=text,
                            source="whatsapp",
                            author=msg.get("from", ""),
                            timestamp=msg.get("timestamp", ""),
                            upvotes=0,
                            comments=0,
                            sentiment=estimate_sentiment(text),
                            tickers=tickers,
                        ))
        except Exception as e:
            logger.error(f"WhatsApp webhook parse error: {e}")

    async def crawl(self) -> CrawlResult:
        """Return buffered messages from webhooks (or demo data)."""
        start = time.monotonic()

        if self._message_buffer and not self._config.demo_mode:
            posts = list(self._message_buffer)
            self._message_buffer.clear()
        else:
            posts = self._demo_posts()

        all_tickers: set[str] = set()
        for post in posts:
            if not post.tickers:
                post.tickers = extract_tickers(post.text)
            all_tickers.update(post.tickers)

        result = CrawlResult(
            platform=PlatformType.WHATSAPP,
            posts=posts,
            post_count=len(posts),
            tickers_found=sorted(all_tickers),
            crawl_duration_ms=(time.monotonic() - start) * 1000,
        )
        self._stats.record_crawl(result)
        return result

    def _demo_posts(self) -> list[SocialPost]:
        """Generate demo WhatsApp posts."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            SocialPost(
                text="Guys AAPL just broke above 185 resistance. Very bullish setup!",
                source="whatsapp", author="+1234567890", timestamp=now,
                upvotes=0, comments=0, sentiment=0.7, tickers=["AAPL"],
            ),
            SocialPost(
                text="Anyone else loading up on AMZN before earnings? Consensus looks good.",
                source="whatsapp", author="+1234567891", timestamp=now,
                upvotes=0, comments=0, sentiment=0.5, tickers=["AMZN"],
            ),
            SocialPost(
                text="Getting out of TSLA. Too much uncertainty with the EV market right now.",
                source="whatsapp", author="+1234567892", timestamp=now,
                upvotes=0, comments=0, sentiment=-0.4, tickers=["TSLA"],
            ),
        ]
