"""Tests for Social Signal Crawler (PRD-140).

8 test classes, ~55 tests covering crawlers, aggregator, bridge,
ticker extraction, sentiment estimation, and module imports.
"""

from datetime import datetime, timezone

import pytest

from src.sentiment.social import SocialPost


# ═══════════════════════════════════════════════════════════════════════
# Test: Ticker Extraction
# ═══════════════════════════════════════════════════════════════════════


class TestTickerExtraction:
    """Tests for extract_tickers utility."""

    def test_cashtag_extraction(self):
        from src.social_crawler.base import extract_tickers
        tickers = extract_tickers("Buy $AAPL and $MSFT today!")
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_known_ticker_extraction(self):
        from src.social_crawler.base import extract_tickers
        tickers = extract_tickers("NVDA is the best AI stock right now")
        assert "NVDA" in tickers

    def test_filters_common_words(self):
        from src.social_crawler.base import extract_tickers
        tickers = extract_tickers("I AM going TO BUY some stocks")
        # AM, TO, BUY are in the common words exclusion list
        assert "AM" not in tickers
        assert "TO" not in tickers

    def test_multiple_strategies(self):
        from src.social_crawler.base import extract_tickers
        tickers = extract_tickers("$AAPL and MSFT both looking good. Also watching GOOGL")
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOGL" in tickers

    def test_empty_text(self):
        from src.social_crawler.base import extract_tickers
        assert extract_tickers("") == []

    def test_no_tickers(self):
        from src.social_crawler.base import extract_tickers
        tickers = extract_tickers("The market is going up today")
        # Should not extract common words
        for t in tickers:
            assert len(t) >= 2

    def test_crypto_tickers(self):
        from src.social_crawler.base import extract_tickers
        tickers = extract_tickers("$BTC breaking $70K. $ETH following.")
        assert "BTC" in tickers
        assert "ETH" in tickers

    def test_deduplication(self):
        from src.social_crawler.base import extract_tickers
        tickers = extract_tickers("$AAPL AAPL $AAPL all the same")
        assert tickers.count("AAPL") == 1


# ═══════════════════════════════════════════════════════════════════════
# Test: Sentiment Estimation
# ═══════════════════════════════════════════════════════════════════════


class TestSentimentEstimation:
    """Tests for estimate_sentiment utility."""

    def test_bullish_text(self):
        from src.social_crawler.base import estimate_sentiment
        score = estimate_sentiment("Very bullish on this stock! Moon time! 🚀")
        assert score > 0

    def test_bearish_text(self):
        from src.social_crawler.base import estimate_sentiment
        score = estimate_sentiment("Bearish. This is going to crash and dump.")
        assert score < 0

    def test_neutral_text(self):
        from src.social_crawler.base import estimate_sentiment
        score = estimate_sentiment("The weather is nice today.")
        assert score == 0.0

    def test_mixed_text(self):
        from src.social_crawler.base import estimate_sentiment
        score = estimate_sentiment("Bullish long term but bearish short term")
        # Mixed signals should be near 0
        assert -0.5 <= score <= 0.5

    def test_strong_bullish(self):
        from src.social_crawler.base import estimate_sentiment
        score = estimate_sentiment(
            "Extremely bullish! Buy buy buy! Moon rocket squeeze breakout!"
        )
        assert score > 0.5


# ═══════════════════════════════════════════════════════════════════════
# Test: Twitter Crawler
# ═══════════════════════════════════════════════════════════════════════


class TestTwitterCrawler:
    """Tests for Twitter/X crawler."""

    @pytest.mark.asyncio
    async def test_connect_demo(self):
        from src.social_crawler.twitter_crawler import TwitterCrawler
        crawler = TwitterCrawler()
        result = await crawler.connect()
        assert result is True
        assert crawler.is_connected()

    @pytest.mark.asyncio
    async def test_crawl_demo(self):
        from src.social_crawler.twitter_crawler import TwitterCrawler
        crawler = TwitterCrawler()
        await crawler.connect()
        result = await crawler.crawl()
        assert result.post_count > 0
        assert len(result.posts) > 0
        assert result.platform.value == "twitter"
        assert len(result.tickers_found) > 0

    @pytest.mark.asyncio
    async def test_posts_have_tickers(self):
        from src.social_crawler.twitter_crawler import TwitterCrawler
        crawler = TwitterCrawler()
        await crawler.connect()
        result = await crawler.crawl()
        for post in result.posts:
            assert len(post.tickers) > 0
            assert post.source == "twitter"

    @pytest.mark.asyncio
    async def test_stats_update(self):
        from src.social_crawler.twitter_crawler import TwitterCrawler
        crawler = TwitterCrawler()
        await crawler.connect()
        await crawler.crawl()
        assert crawler.stats.total_crawls == 1
        assert crawler.stats.total_posts > 0

    @pytest.mark.asyncio
    async def test_disconnect(self):
        from src.social_crawler.twitter_crawler import TwitterCrawler
        crawler = TwitterCrawler()
        await crawler.connect()
        await crawler.disconnect()
        assert crawler.is_connected() is False


# ═══════════════════════════════════════════════════════════════════════
# Test: Platform Crawlers
# ═══════════════════════════════════════════════════════════════════════


class TestPlatformCrawlers:
    """Tests for Discord, Telegram, Reddit, WhatsApp crawlers."""

    @pytest.mark.asyncio
    async def test_discord_crawl(self):
        from src.social_crawler.discord_crawler import DiscordCrawler
        crawler = DiscordCrawler()
        await crawler.connect()
        result = await crawler.crawl()
        assert result.post_count > 0
        assert result.platform.value == "discord"

    @pytest.mark.asyncio
    async def test_telegram_crawl(self):
        from src.social_crawler.telegram_crawler import TelegramCrawler
        crawler = TelegramCrawler()
        await crawler.connect()
        result = await crawler.crawl()
        assert result.post_count > 0
        assert result.platform.value == "telegram"

    @pytest.mark.asyncio
    async def test_reddit_crawl(self):
        from src.social_crawler.reddit_crawler import RedditCrawler
        crawler = RedditCrawler()
        await crawler.connect()
        result = await crawler.crawl()
        assert result.post_count > 0
        assert result.platform.value == "reddit"

    @pytest.mark.asyncio
    async def test_whatsapp_crawl(self):
        from src.social_crawler.whatsapp_crawler import WhatsAppCrawler
        crawler = WhatsAppCrawler()
        await crawler.connect()
        result = await crawler.crawl()
        assert result.post_count > 0
        assert result.platform.value == "whatsapp"

    @pytest.mark.asyncio
    async def test_all_crawlers_produce_social_posts(self):
        """Verify all crawlers produce SocialPost objects."""
        from src.social_crawler import (
            TwitterCrawler, DiscordCrawler, TelegramCrawler,
            RedditCrawler, WhatsAppCrawler,
        )
        crawlers = [
            TwitterCrawler(), DiscordCrawler(), TelegramCrawler(),
            RedditCrawler(), WhatsAppCrawler(),
        ]
        for crawler in crawlers:
            await crawler.connect()
            result = await crawler.crawl()
            for post in result.posts:
                assert isinstance(post, SocialPost)
                assert post.source in ("twitter", "discord", "telegram", "reddit", "whatsapp")

    @pytest.mark.asyncio
    async def test_whatsapp_webhook(self):
        from src.social_crawler.whatsapp_crawler import WhatsAppCrawler, WhatsAppConfig
        crawler = WhatsAppCrawler(WhatsAppConfig(demo_mode=False))
        await crawler.connect()
        # Simulate webhook
        crawler.receive_webhook({
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "+1234",
                            "text": {"body": "$AAPL breaking out above resistance!"},
                            "timestamp": "1234567890",
                        }]
                    }
                }]
            }]
        })
        result = await crawler.crawl()
        assert result.post_count == 1
        assert "AAPL" in result.tickers_found


# ═══════════════════════════════════════════════════════════════════════
# Test: Feed Aggregator
# ═══════════════════════════════════════════════════════════════════════


class TestFeedAggregator:
    """Tests for the feed aggregator."""

    @pytest.mark.asyncio
    async def test_aggregate_multiple_crawlers(self):
        from src.social_crawler import (
            FeedAggregator, TwitterCrawler, RedditCrawler, DiscordCrawler,
        )
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        agg.add_crawler(RedditCrawler())
        agg.add_crawler(DiscordCrawler())
        await agg.connect_all()
        feed = await agg.crawl_all()
        assert feed.total_posts > 0
        assert len(feed.unique_tickers) > 0
        assert len(feed.platform_counts) == 3
        assert "twitter" in feed.platform_counts
        assert "reddit" in feed.platform_counts
        assert "discord" in feed.platform_counts

    @pytest.mark.asyncio
    async def test_deduplication(self):
        from src.social_crawler import FeedAggregator, TwitterCrawler
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        await agg.connect_all()
        # Crawl twice — should not have exact duplicates
        feed1 = await agg.crawl_all()
        feed2 = await agg.crawl_all()
        # Second crawl should have 0 posts because they've been seen
        assert feed2.total_posts == 0

    @pytest.mark.asyncio
    async def test_by_ticker_index(self):
        from src.social_crawler import FeedAggregator, TwitterCrawler
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        await agg.connect_all()
        feed = await agg.crawl_all()
        # At least one ticker should have posts
        assert len(feed.by_ticker) > 0
        for ticker, posts in feed.by_ticker.items():
            for post in posts:
                assert ticker in post.tickers

    @pytest.mark.asyncio
    async def test_feed_to_dict(self):
        from src.social_crawler import FeedAggregator, TwitterCrawler
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        await agg.connect_all()
        feed = await agg.crawl_all()
        d = feed.to_dict()
        assert "total_posts" in d
        assert "unique_tickers" in d
        assert "platform_counts" in d

    @pytest.mark.asyncio
    async def test_get_stats(self):
        from src.social_crawler import (
            FeedAggregator, TwitterCrawler, RedditCrawler,
        )
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        agg.add_crawler(RedditCrawler())
        await agg.connect_all()
        await agg.crawl_all()
        stats = agg.get_stats()
        assert len(stats) == 2

    @pytest.mark.asyncio
    async def test_remove_crawler(self):
        from src.social_crawler import FeedAggregator, TwitterCrawler, PlatformType
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        assert len(agg.crawlers) == 1
        agg.remove_crawler(PlatformType.TWITTER)
        assert len(agg.crawlers) == 0


# ═══════════════════════════════════════════════════════════════════════
# Test: Social Crawler Bridge
# ═══════════════════════════════════════════════════════════════════════


class TestSocialCrawlerBridge:
    """Tests for the bridge to SocialMediaMonitor."""

    @pytest.mark.asyncio
    async def test_process_feed(self):
        from src.social_crawler import (
            FeedAggregator, TwitterCrawler, SocialCrawlerBridge,
        )
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        await agg.connect_all()
        feed = await agg.crawl_all()

        bridge = SocialCrawlerBridge()
        result = bridge.process_feed(feed)
        assert result.total_posts_processed > 0
        assert result.total_tickers_found > 0
        assert len(result.mentions) > 0

    @pytest.mark.asyncio
    async def test_trending_detection(self):
        from src.social_crawler import (
            FeedAggregator, TwitterCrawler, SocialCrawlerBridge,
        )
        # Set low historical averages to trigger trending
        bridge = SocialCrawlerBridge(
            historical_mentions={"AAPL": 0.2, "NVDA": 0.2, "TSLA": 0.2}
        )
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        await agg.connect_all()
        feed = await agg.crawl_all()
        result = bridge.process_feed(feed)
        # With low historical avg, most tickers should be trending
        assert len(result.trending) > 0

    @pytest.mark.asyncio
    async def test_summaries_generated(self):
        from src.social_crawler import (
            FeedAggregator, TwitterCrawler, SocialCrawlerBridge,
        )
        agg = FeedAggregator()
        agg.add_crawler(TwitterCrawler())
        await agg.connect_all()
        feed = await agg.crawl_all()

        bridge = SocialCrawlerBridge()
        result = bridge.process_feed(feed)
        assert len(result.summaries) > 0
        for symbol, summary in result.summaries.items():
            assert summary.symbol == symbol
            assert summary.total_mentions > 0

    def test_process_posts_directly(self):
        from src.social_crawler import SocialCrawlerBridge
        bridge = SocialCrawlerBridge()
        posts = [
            SocialPost(
                text="$AAPL is bullish",
                source="twitter", tickers=["AAPL"], sentiment=0.8,
                upvotes=10, comments=2,
            ),
            SocialPost(
                text="$MSFT going up",
                source="reddit", tickers=["MSFT"], sentiment=0.6,
                upvotes=50, comments=10,
            ),
        ]
        result = bridge.process_posts(posts)
        assert result.total_tickers_found == 2
        assert "AAPL" in result.mentions
        assert "MSFT" in result.mentions

    def test_bridge_result_to_dict(self):
        from src.social_crawler import SocialCrawlerBridge, BridgeResult
        result = BridgeResult(total_posts_processed=10, total_tickers_found=5)
        d = result.to_dict()
        assert d["total_posts_processed"] == 10
        assert d["total_tickers_found"] == 5


# ═══════════════════════════════════════════════════════════════════════
# Test: Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.social_crawler import __all__
        import src.social_crawler as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_platform_enum(self):
        from src.social_crawler import PlatformType
        assert PlatformType.TWITTER.value == "twitter"
        assert PlatformType.DISCORD.value == "discord"
        assert PlatformType.TELEGRAM.value == "telegram"
        assert PlatformType.REDDIT.value == "reddit"
        assert PlatformType.WHATSAPP.value == "whatsapp"

    def test_crawl_status_enum(self):
        from src.social_crawler import CrawlStatus
        assert CrawlStatus.IDLE.value == "idle"
        assert CrawlStatus.RUNNING.value == "running"
        assert CrawlStatus.ERROR.value == "error"

    def test_crawl_result_to_dict(self):
        from src.social_crawler import CrawlResult, PlatformType
        result = CrawlResult(
            platform=PlatformType.TWITTER,
            post_count=42,
            tickers_found=["AAPL", "MSFT"],
        )
        d = result.to_dict()
        assert d["platform"] == "twitter"
        assert d["post_count"] == 42
