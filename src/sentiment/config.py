"""Sentiment Intelligence Configuration.

Contains all configurable parameters for news sentiment,
social media monitoring, insider tracking, analyst consensus,
earnings NLP, and composite scoring.
"""

from dataclasses import dataclass, field


@dataclass
class NewsSentimentConfig:
    """News sentiment engine configuration."""

    time_decay_rate: float = 0.1  # Exponential decay per hour
    max_text_length: int = 512
    default_window_hours: int = 24
    source_credibility: dict = field(default_factory=lambda: {
        "benzinga": 0.85,
        "reuters": 0.95,
        "bloomberg": 0.95,
        "sec_edgar": 0.90,
        "pr_newswire": 0.70,
        "seeking_alpha": 0.65,
        "newsapi": 0.60,
        "unknown": 0.50,
    })
    positive_threshold: float = 0.6
    negative_threshold: float = 0.4


@dataclass
class SocialMediaConfig:
    """Social media monitoring configuration."""

    subreddits: list = field(default_factory=lambda: [
        "wallstreetbets", "stocks", "investing", "options", "stockmarket",
    ])
    mention_lookback_hours: int = 24
    trending_threshold_multiplier: float = 3.0
    min_upvotes: int = 10
    min_comments: int = 5
    influencer_follower_threshold: int = 100_000
    spike_detection_window_hours: int = 4
    spike_multiplier: float = 5.0


@dataclass
class InsiderConfig:
    """Insider trading signal configuration."""

    lookback_months: int = 6
    cluster_window_days: int = 30
    cluster_min_insiders: int = 3
    signal_weights: dict = field(default_factory=lambda: {
        "cluster_buy": 0.8,
        "ceo_cfo_buy": 0.6,
        "director_buy": 0.4,
        "10b5_1_sale": -0.1,
        "open_market_sale": -0.3,
        "cluster_sell": -0.7,
    })


@dataclass
class AnalystConfig:
    """Analyst consensus configuration."""

    revision_windows_days: list = field(default_factory=lambda: [30, 60, 90])
    rating_scale: dict = field(default_factory=lambda: {
        "strong_buy": 1.0,
        "buy": 0.5,
        "hold": 0.0,
        "sell": -0.5,
        "strong_sell": -1.0,
    })
    min_analysts: int = 3


@dataclass
class EarningsNLPConfig:
    """Earnings call NLP configuration."""

    positive_words: list = field(default_factory=lambda: [
        "strong", "growth", "record", "exceeded", "accelerat", "robust",
        "confident", "optimistic", "outperform", "beat", "upside", "momentum",
        "improve", "expand", "opportunity", "innovative", "excited",
    ])
    negative_words: list = field(default_factory=lambda: [
        "challenging", "uncertain", "headwind", "decline", "weak",
        "disappoint", "risk", "concern", "pressure", "difficult",
        "slowdown", "cautious", "volatile", "impair", "restructur",
    ])
    uncertainty_words: list = field(default_factory=lambda: [
        "uncertain", "maybe", "possibly", "might", "unclear",
        "unpredictable", "volatile", "depends", "contingent",
    ])
    forward_looking_words: list = field(default_factory=lambda: [
        "expect", "anticipate", "project", "forecast", "guidance",
        "outlook", "plan", "intend", "will", "going to", "target",
    ])


@dataclass
class CompositeConfig:
    """Composite sentiment score configuration."""

    weights: dict = field(default_factory=lambda: {
        "news_sentiment": 0.25,
        "social_sentiment": 0.15,
        "insider_signal": 0.20,
        "analyst_revision": 0.20,
        "earnings_tone": 0.10,
        "options_flow": 0.10,
    })
    min_sources_required: int = 2
    score_range: tuple = (-1.0, 1.0)


@dataclass
class SentimentConfig:
    """Top-level sentiment intelligence configuration."""

    news: NewsSentimentConfig = field(default_factory=NewsSentimentConfig)
    social: SocialMediaConfig = field(default_factory=SocialMediaConfig)
    insider: InsiderConfig = field(default_factory=InsiderConfig)
    analyst: AnalystConfig = field(default_factory=AnalystConfig)
    earnings: EarningsNLPConfig = field(default_factory=EarningsNLPConfig)
    composite: CompositeConfig = field(default_factory=CompositeConfig)
