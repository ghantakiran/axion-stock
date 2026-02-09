"""Social Signal Crawler (PRD-140).

Crawls X/Twitter, Discord, Telegram, Reddit, and WhatsApp for
stock-related posts and feeds them into the sentiment analysis pipeline.

Example:
    from src.social_crawler import (
        FeedAggregator, TwitterCrawler, RedditCrawler,
        DiscordCrawler, SocialCrawlerBridge,
    )

    # Create crawlers
    twitter = TwitterCrawler()
    reddit = RedditCrawler()
    discord = DiscordCrawler()

    # Aggregate
    agg = FeedAggregator()
    agg.add_crawler(twitter)
    agg.add_crawler(reddit)
    agg.add_crawler(discord)

    await agg.connect_all()
    feed = await agg.crawl_all()

    # Bridge to sentiment pipeline
    bridge = SocialCrawlerBridge()
    result = bridge.process_feed(feed)
    print(result.trending)
"""

from src.social_crawler.base import (
    PlatformType,
    CrawlStatus,
    CrawlConfig,
    CrawlResult,
    CrawlerStats,
    CrawlerProtocol,
    extract_tickers,
    estimate_sentiment,
)
from src.social_crawler.twitter_crawler import TwitterCrawler, TwitterConfig
from src.social_crawler.discord_crawler import DiscordCrawler, DiscordConfig
from src.social_crawler.telegram_crawler import TelegramCrawler, TelegramConfig
from src.social_crawler.reddit_crawler import RedditCrawler, RedditConfig
from src.social_crawler.whatsapp_crawler import WhatsAppCrawler, WhatsAppConfig
from src.social_crawler.aggregator import (
    FeedAggregator,
    AggregatedFeed,
    AggregatorConfig,
)
from src.social_crawler.bridge import SocialCrawlerBridge, BridgeResult

__all__ = [
    # Base
    "PlatformType",
    "CrawlStatus",
    "CrawlConfig",
    "CrawlResult",
    "CrawlerStats",
    "CrawlerProtocol",
    "extract_tickers",
    "estimate_sentiment",
    # Crawlers
    "TwitterCrawler",
    "TwitterConfig",
    "DiscordCrawler",
    "DiscordConfig",
    "TelegramCrawler",
    "TelegramConfig",
    "RedditCrawler",
    "RedditConfig",
    "WhatsAppCrawler",
    "WhatsAppConfig",
    # Aggregator
    "FeedAggregator",
    "AggregatedFeed",
    "AggregatorConfig",
    # Bridge
    "SocialCrawlerBridge",
    "BridgeResult",
]
