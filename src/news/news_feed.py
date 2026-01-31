"""News Feed Management.

Aggregates and manages financial news from multiple sources.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable
import logging
import re

from src.news.config import (
    NewsCategory,
    NewsSource,
    SentimentLabel,
    NewsFeedConfig,
    NewsConfig,
    DEFAULT_NEWS_CONFIG,
    SENTIMENT_THRESHOLDS,
)
from src.news.models import NewsArticle

logger = logging.getLogger(__name__)


# Simple keyword-based sentiment analysis
POSITIVE_KEYWORDS = [
    "beat", "beats", "exceeds", "surpass", "strong", "growth", "profit",
    "upgrade", "buy", "bullish", "rally", "surge", "gain", "record",
    "outperform", "positive", "optimistic", "success", "boost", "soar",
]

NEGATIVE_KEYWORDS = [
    "miss", "misses", "decline", "drop", "fall", "loss", "weak",
    "downgrade", "sell", "bearish", "plunge", "crash", "cut", "warning",
    "underperform", "negative", "pessimistic", "fail", "concern", "risk",
]


class NewsFeedManager:
    """Manages news feed aggregation and retrieval.
    
    Features:
    - Multi-source aggregation
    - Sentiment analysis
    - Symbol filtering
    - Category classification
    - Read/bookmark tracking
    """
    
    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or DEFAULT_NEWS_CONFIG
        self._feed_config = self.config.news_feed
        self._articles: dict[str, NewsArticle] = {}  # article_id -> article
        self._symbol_index: dict[str, set[str]] = {}  # symbol -> article_ids
        self._category_index: dict[NewsCategory, set[str]] = {}
    
    def add_article(self, article: NewsArticle) -> NewsArticle:
        """Add an article to the feed.
        
        Args:
            article: NewsArticle to add.
            
        Returns:
            The added article (with sentiment if enabled).
        """
        # Analyze sentiment if enabled and not already set
        if self._feed_config.enable_sentiment_analysis and article.sentiment_score == 0.0:
            article.sentiment_score = self._analyze_sentiment(
                article.headline + " " + article.summary
            )
        
        # Auto-categorize if no categories
        if not article.categories:
            article.categories = self._categorize_article(article)
        
        # Store article
        self._articles[article.article_id] = article
        
        # Index by symbol
        for symbol in article.symbols:
            if symbol not in self._symbol_index:
                self._symbol_index[symbol] = set()
            self._symbol_index[symbol].add(article.article_id)
        
        # Index by category
        for category in article.categories:
            if category not in self._category_index:
                self._category_index[category] = set()
            self._category_index[category].add(article.article_id)
        
        logger.debug(f"Added article: {article.headline[:50]}...")
        return article
    
    def get_article(self, article_id: str) -> Optional[NewsArticle]:
        """Get an article by ID."""
        return self._articles.get(article_id)
    
    def get_feed(
        self,
        symbols: Optional[list[str]] = None,
        categories: Optional[list[NewsCategory]] = None,
        sources: Optional[list[NewsSource]] = None,
        min_sentiment: Optional[float] = None,
        max_sentiment: Optional[float] = None,
        breaking_only: bool = False,
        unread_only: bool = False,
        bookmarked_only: bool = False,
        since: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[NewsArticle]:
        """Get filtered news feed.
        
        Args:
            symbols: Filter by symbols.
            categories: Filter by categories.
            sources: Filter by sources.
            min_sentiment: Minimum sentiment score.
            max_sentiment: Maximum sentiment score.
            breaking_only: Only breaking news.
            unread_only: Only unread articles.
            bookmarked_only: Only bookmarked articles.
            since: Articles after this datetime.
            limit: Maximum articles to return.
            offset: Pagination offset.
            
        Returns:
            List of matching articles.
        """
        # Start with candidate articles
        if symbols:
            candidate_ids = set()
            for symbol in symbols:
                candidate_ids.update(self._symbol_index.get(symbol, set()))
        else:
            candidate_ids = set(self._articles.keys())
        
        # Filter by category
        if categories:
            category_ids = set()
            for category in categories:
                category_ids.update(self._category_index.get(category, set()))
            candidate_ids &= category_ids
        
        # Get articles and apply additional filters
        articles = []
        for article_id in candidate_ids:
            article = self._articles.get(article_id)
            if not article:
                continue
            
            # Source filter
            if sources and article.source not in sources:
                continue
            
            # Sentiment filter
            if min_sentiment is not None and article.sentiment_score < min_sentiment:
                continue
            if max_sentiment is not None and article.sentiment_score > max_sentiment:
                continue
            
            # Breaking filter
            if breaking_only and not article.is_breaking:
                continue
            
            # Read/bookmark filters
            if unread_only and article.is_read:
                continue
            if bookmarked_only and not article.is_bookmarked:
                continue
            
            # Time filter
            if since and article.published_at < since:
                continue
            
            # Relevance filter
            if article.relevance_score < self._feed_config.min_relevance_score:
                continue
            
            articles.append(article)
        
        # Sort by published date (newest first), breaking news prioritized
        articles.sort(
            key=lambda a: (a.is_breaking, a.published_at),
            reverse=True
        )
        
        # Paginate
        return articles[offset:offset + limit]
    
    def get_for_symbol(
        self,
        symbol: str,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> list[NewsArticle]:
        """Get news for a specific symbol."""
        return self.get_feed(symbols=[symbol], limit=limit, since=since)
    
    def get_breaking_news(self, limit: int = 10) -> list[NewsArticle]:
        """Get breaking news articles."""
        return self.get_feed(breaking_only=True, limit=limit)
    
    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[NewsArticle]:
        """Full-text search in headlines and summaries.
        
        Args:
            query: Search query.
            limit: Maximum results.
            
        Returns:
            Matching articles.
        """
        query_lower = query.lower()
        query_words = query_lower.split()
        
        results = []
        for article in self._articles.values():
            text = (article.headline + " " + article.summary).lower()
            
            # Check if all words are in text
            if all(word in text for word in query_words):
                results.append(article)
        
        # Sort by relevance (number of keyword matches)
        results.sort(
            key=lambda a: sum(
                1 for w in query_words 
                if w in (a.headline + " " + a.summary).lower()
            ),
            reverse=True
        )
        
        return results[:limit]
    
    def mark_read(self, article_id: str) -> bool:
        """Mark an article as read."""
        article = self._articles.get(article_id)
        if article:
            article.is_read = True
            return True
        return False
    
    def mark_bookmarked(self, article_id: str, bookmarked: bool = True) -> bool:
        """Bookmark/unbookmark an article."""
        article = self._articles.get(article_id)
        if article:
            article.is_bookmarked = bookmarked
            return True
        return False
    
    def _analyze_sentiment(self, text: str) -> float:
        """Simple keyword-based sentiment analysis.
        
        Returns a score from -1 (very negative) to 1 (very positive).
        """
        text_lower = text.lower()
        
        positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
        negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        # Score from -1 to 1
        score = (positive_count - negative_count) / total
        return max(-1.0, min(1.0, score))
    
    def _categorize_article(self, article: NewsArticle) -> list[NewsCategory]:
        """Auto-categorize article based on content."""
        text = (article.headline + " " + article.summary).lower()
        categories = []
        
        # Category keywords
        category_keywords = {
            NewsCategory.EARNINGS: ["earnings", "eps", "revenue", "profit", "quarter"],
            NewsCategory.MACRO: ["fed", "inflation", "gdp", "economy", "rates", "fomc"],
            NewsCategory.ANALYST: ["upgrade", "downgrade", "price target", "rating", "analyst"],
            NewsCategory.MERGER: ["merger", "acquisition", "acquire", "deal", "takeover", "buyout"],
            NewsCategory.IPO: ["ipo", "initial public offering", "debut", "goes public"],
            NewsCategory.DIVIDEND: ["dividend", "yield", "payout", "distribution"],
            NewsCategory.REGULATORY: ["sec", "fda", "ftc", "regulation", "compliance", "lawsuit"],
            NewsCategory.PRODUCT: ["launch", "product", "release", "unveil", "announce"],
            NewsCategory.MANAGEMENT: ["ceo", "cfo", "executive", "board", "resign", "appoint"],
        }
        
        for category, keywords in category_keywords.items():
            if any(kw in text for kw in keywords):
                categories.append(category)
        
        # Default to general if no match
        if not categories:
            categories.append(NewsCategory.GENERAL)
        
        return categories
    
    def get_sentiment_summary(
        self,
        symbol: Optional[str] = None,
        days: int = 7,
    ) -> dict:
        """Get sentiment summary for a symbol or overall.
        
        Returns:
            Dict with sentiment breakdown and average.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        articles = self.get_feed(
            symbols=[symbol] if symbol else None,
            since=since,
            limit=1000,
        )
        
        if not articles:
            return {
                "total_articles": 0,
                "average_sentiment": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
            }
        
        sentiments = [a.sentiment_score for a in articles]
        avg = sum(sentiments) / len(sentiments)
        
        positive = sum(1 for s in sentiments if s > 0.2)
        negative = sum(1 for s in sentiments if s < -0.2)
        neutral = len(sentiments) - positive - negative
        
        return {
            "total_articles": len(articles),
            "average_sentiment": avg,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "positive_pct": positive / len(articles) * 100,
            "negative_pct": negative / len(articles) * 100,
        }
    
    def get_trending_symbols(self, hours: int = 24, limit: int = 10) -> list[dict]:
        """Get symbols with most news activity.
        
        Returns:
            List of dicts with symbol and article count.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        symbol_counts: dict[str, int] = {}
        for article in self._articles.values():
            if article.published_at >= since:
                for symbol in article.symbols:
                    symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        # Sort by count
        sorted_symbols = sorted(
            symbol_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {"symbol": symbol, "article_count": count}
            for symbol, count in sorted_symbols[:limit]
        ]
