# PRD-14: Social Trading Platform

## Overview

Community-driven social trading platform enabling users to share strategies, copy trades from top performers, compete on leaderboards, and discover trading ideas through a social feed.

---

## Components

### 1. Trader Profiles
- Public profile with bio, trading style, join date
- Performance stats: return, Sharpe, win rate, max drawdown
- Badge system: Top Performer, Consistent, Rising Star, Veteran
- Verified status for institutional traders
- Privacy controls (public/private/followers-only)

### 2. Strategy Publishing
- Publish strategies with name, description, asset universe
- Track record with audited performance metrics
- Risk parameters and constraints
- Version history
- Tags and categories

### 3. Copy Trading
- Follow and auto-copy a trader's positions
- Allocation scaling (fixed amount or percentage)
- Selective copying (filter by asset class, max position size)
- Stop-loss and max drawdown limits on copy relationships
- Delayed copying option (time lag for review)

### 4. Leaderboards
- Rankings by: total return, Sharpe ratio, win rate, consistency
- Time periods: 1M, 3M, 6M, 1Y, All-time
- Category filters: by asset class, strategy type, risk level
- Anti-gaming rules (minimum trade count, minimum history)

### 5. Social Feed
- Trade ideas with thesis and targets
- Position updates (opened/closed)
- Commentary and market analysis
- Like, comment, bookmark functionality
- Trending ideas and popular traders

### 6. Database Tables
- `trader_profiles`: Public profile and settings
- `strategies`: Published strategy definitions
- `strategy_performance`: Daily performance snapshots
- `copy_relationships`: Active copy trading links
- `social_posts`: Feed items (trade ideas, commentary)
- `social_interactions`: Likes, comments, bookmarks
- `leaderboard_snapshots`: Periodic leaderboard captures

### 7. Success Metrics
- Copy trade execution latency: <2s
- Leaderboard update frequency: hourly
- User engagement: >30% publish or follow rate

---

*Priority: P2 | Phase: 7*
