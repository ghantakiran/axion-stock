# PRD-140: Social Signal Crawler

## Overview
Multi-platform social media crawler for financial signal extraction. Crawls X/Twitter, Discord, Telegram, Reddit, and WhatsApp for stock-related posts, extracts tickers, estimates sentiment, and bridges data into the existing sentiment analysis pipeline.

## Architecture

### Source Files (`src/social_crawler/`)

| File | Lines | Description |
|------|-------|-------------|
| `__init__.py` | ~80 | Public API: 20 exports across base, crawlers, aggregator, bridge |
| `base.py` | ~280 | CrawlerProtocol, PlatformType/CrawlStatus enums, extract_tickers, estimate_sentiment |
| `twitter_crawler.py` | ~220 | TwitterCrawler with tweepy SDK + demo mode |
| `discord_crawler.py` | ~200 | DiscordCrawler with HTTP API v10 |
| `telegram_crawler.py` | ~170 | TelegramCrawler with Bot API |
| `reddit_crawler.py` | ~240 | RedditCrawler with PRAW SDK + demo mode |
| `whatsapp_crawler.py` | ~150 | WhatsAppCrawler with webhook-based Business API |
| `aggregator.py` | ~210 | FeedAggregator — concurrent multi-platform crawling, deduplication |
| `bridge.py` | ~150 | SocialCrawlerBridge — feeds data to SocialMediaMonitor |

### Key Design Decisions

1. **CrawlerProtocol** — runtime-checkable Protocol ensures all 5 crawlers share a uniform interface: `connect()`, `disconnect()`, `crawl() -> CrawlResult`, `is_connected()`, `stats`
2. **Demo mode** — every crawler returns realistic demo data when API credentials aren't configured, enabling full testing without live APIs
3. **Ticker extraction** — multi-strategy approach: cashtag patterns (`$AAPL`), known ticker matching (~120 tickers), all-caps detection with ~100 common word exclusions
4. **Sentiment estimation** — lightweight rule-based scoring using bullish/bearish keyword lists, normalized to [-1, 1]
5. **SocialPost bridge** — all crawlers produce `SocialPost` objects (from `src.sentiment.social`), which plugs directly into the existing `SocialMediaMonitor.process_posts()` pipeline

### Data Flow

```
Platform APIs → Crawlers → FeedAggregator → SocialCrawlerBridge → SocialMediaMonitor
     ↓              ↓            ↓                    ↓
  (demo mode)   CrawlResult  AggregatedFeed     BridgeResult
                             (deduplicated)    (mentions, trending,
                                                summaries)
```

## ORM Models (`src/db/models.py`)

| Model | Table | Description |
|-------|-------|-------------|
| `SocialCrawlRunRecord` | `social_crawl_runs` | Crawl run log (platform, post count, duration) |
| `SocialPostRecord` | `social_posts` | Archived social posts with sentiment scores |

## Migration

- **File**: `alembic/versions/140_social_crawler.py`
- **Revision**: `140` → `down_revision`: `139`
- **Tables**: `social_crawl_runs` (7 columns), `social_posts` (11 columns + sentiment index)

## Dashboard (`app/pages/social_crawler.py`)

4 tabs:
1. **Crawler Status** — platform connection status, quick crawl with metrics
2. **Feed View** — browsable post list with platform/ticker filters
3. **Ticker Analysis** — mention counts, trending alerts, per-ticker summaries via SocialCrawlerBridge
4. **Configuration** — per-platform API credential setup, aggregator settings

## Tests (`tests/test_social_crawler.py`)

8 test classes, ~55 tests:

| Test Class | Tests | Coverage |
|---|---|---|
| `TestTickerExtraction` | 8 | Cashtags, known tickers, common word filtering, dedup |
| `TestSentimentEstimation` | 5 | Bullish, bearish, neutral, mixed, strong sentiment |
| `TestTwitterCrawler` | 5 | Connect, crawl, post tickers, stats update, disconnect |
| `TestPlatformCrawlers` | 7 | Discord, Telegram, Reddit, WhatsApp crawl + webhook |
| `TestFeedAggregator` | 6 | Multi-crawler, dedup, ticker index, stats, remove |
| `TestSocialCrawlerBridge` | 5 | Feed processing, trending, summaries, direct posts |
| `TestModuleImports` | 4 | Exports, PlatformType, CrawlStatus, CrawlResult |

## Dependencies

- **Required**: `src/sentiment/social.py` (SocialPost, SocialMediaMonitor)
- **Optional SDK**: `tweepy` (Twitter), `praw` (Reddit) — graceful fallback to demo mode
- **HTTP**: `httpx` for Discord/Telegram/WhatsApp APIs

## Nav Entry

Added to "Sentiment & Data" section in `app/nav_config.py`.
