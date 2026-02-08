# PRD-83: Social Trading

## Overview
Social trading platform with trader profiles, strategy publishing, copy trading engine, performance leaderboards, and social feed for trade ideas and market analysis.

## Components

### 1. Profile Manager (`src/social/profiles.py`)
- **ProfileManager** — Trader profile CRUD with follow/unfollow system
- Badge system (8 types): Top Performer, Consistent, Risk Manager, Popular, Veteran, Diversified, Community, Verified
- Auto-badge awarding based on performance thresholds
- Community rating (1-5 stars), profile search by trading style
- Follower/following counts, profile visibility controls (public/private/followers-only)

### 2. Strategy Manager (`src/social/strategies.py`)
- **StrategyManager** — Strategy publishing and performance tracking
- Lifecycle: Draft → Published → Archived with version increment
- 10 categories: equity long/short, options, crypto, momentum, value, growth, income, macro, multi-asset
- Daily performance snapshots (return, cumulative, NAV, drawdown, positions)
- Strategy search, user strategy listing, max strategy limits

### 3. Copy Trading Engine (`src/social/copy_trading.py`)
- **CopyTradingEngine** — Full copy trading lifecycle
- Start/stop/pause/resume with allocation modes: FIXED_AMOUNT, PERCENTAGE, PROPORTIONAL
- Max loss protection with automatic stop-loss trigger
- Copy delay support (review before execution)
- Position size computation, P&L tracking per relationship
- Concurrent copy limits (default 10), self-copy prevention, duplicate blocking

### 4. Leaderboard Manager (`src/social/leaderboard.py`)
- **LeaderboardManager** — Performance ranking system
- 6 metrics: Total Return, Sharpe Ratio, Win Rate, Consistency, Risk-Adjusted, Profit Factor
- 5 periods: 1M, 3M, 6M, 1Y, All-time
- Anti-gaming rules: minimum 10 trades, 30 days history
- Rank change tracking (previous rank comparison)

### 5. Feed Manager (`src/social/feed.py`)
- **FeedManager** — Social feed for trade ideas and analysis
- 5 post types: Trade Idea, Position Update, Market Analysis, Strategy Update, Commentary
- Like/comment/bookmark interactions, trending detection (5+ interactions/24h)
- Global and user-specific feeds, symbol/type filtering
- Content limits (2000 chars), daily post limits (20/day)

### 6. Configuration (`src/social/config.py`)
- 11 enums: ProfileVisibility, TradingStyle, Badge, StrategyStatus, StrategyCategory, CopyStatus, CopyMode, LeaderboardMetric, LeaderboardPeriod, PostType, InteractionType
- BADGE_REQUIREMENTS, LEADERBOARD_MINIMUMS
- CopyConfig, LeaderboardConfig, FeedConfig, SocialConfig

### 7. Models (`src/social/models.py`)
- **PerformanceStats** — Win rate, total return, Sharpe, max drawdown, trade count
- **TraderProfile** — Bio, trading style, badges, verification, follower counts, rating
- **Strategy** — Name, category, tags, asset universe, risk level, copier count, versioning
- **StrategyPerformance** — Daily return, cumulative, NAV, drawdown, positions
- **CopyRelationship** — Copier/leader, mode, allocation, max loss, P&L, trade count
- **LeaderboardEntry** — User, rank, metric value, badge, rank change
- **SocialPost** — Content, symbol, target/stop, direction, engagement metrics
- **SocialInteraction** — Like/comment/bookmark with text
- **FollowRelationship** — Follower/following link

## Database Tables
- `trader_profiles` — Profile with bio, style, badges, stats, rating (migration 015)
- `strategies` — Published strategies with categories and stats (migration 015)
- `strategy_performance` — Daily performance snapshots (migration 015)
- `copy_relationships` — Copy trading links with P&L tracking (migration 015)
- `social_posts` — Feed posts with engagement metrics (migration 015)
- `social_interactions` — Like/comment/bookmark records (migration 015)
- `leaderboard_snapshots` — Computed leaderboard entries (migration 015)
- `social_analytics` — Platform-level engagement analytics (migration 083)
- `copy_trade_executions` — Individual copy trade execution log (migration 083)

## Dashboard
Streamlit dashboard (`app/pages/social.py`) with 4 tabs:
1. **Social Feed** — Trade ideas, market analysis, trending posts
2. **Leaderboard** — Rankings by metric/period with badges
3. **Copy Trading** — Active relationships, available strategies
4. **Strategy Marketplace** — Browse/filter strategies by category

## Test Coverage
76 tests in `tests/test_social.py` covering config/enums (8), model properties (12), ProfileManager (9), StrategyManager (10), CopyTradingEngine (12), LeaderboardManager (6), FeedManager (12), full workflow integration (2), and module imports (1). Includes tests for anti-gaming rules, self-copy prevention, max loss auto-stop, duplicate blocking, daily limits, and trending detection.
