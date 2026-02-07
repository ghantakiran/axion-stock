# PRD-61: Strategy Marketplace

## Overview

A marketplace for trading strategies where users can publish, discover, and subscribe to strategies created by other traders. Includes performance tracking, ratings, and revenue sharing for strategy creators.

## Goals

1. Enable strategy creators to monetize their expertise
2. Allow subscribers to follow proven strategies
3. Provide transparent performance metrics and rankings
4. Build community through ratings and reviews
5. Ensure fair revenue sharing model

## Components

### 1. Strategy Publishing
- Strategy metadata (name, description, risk level)
- Trading rules and parameters (encrypted)
- Backtest results and live performance
- Pricing tiers (free, subscription, performance fee)
- Version control for strategy updates

### 2. Strategy Discovery
- Browse by category, asset class, risk level
- Search and filter capabilities
- Performance leaderboards
- Featured and trending strategies
- Similar strategy recommendations

### 3. Subscription Management
- Subscribe/unsubscribe to strategies
- Subscription tiers and billing
- Auto-trade vs signal-only modes
- Position sizing preferences
- Risk overrides per subscriber

### 4. Performance Tracking
- Real-time P&L tracking
- Risk-adjusted returns (Sharpe, Sortino)
- Drawdown analysis
- Win rate and profit factor
- Comparison vs benchmarks

### 5. Creator Dashboard
- Subscriber analytics
- Revenue tracking
- Performance attribution
- Strategy versioning
- Subscriber communications

### 6. Rating & Reviews
- Star ratings (1-5)
- Written reviews
- Verified subscriber reviews
- Creator responses
- Review moderation

## Database Tables

### marketplace_strategies
- id, creator_id, name, description, category
- risk_level, asset_classes, min_capital
- pricing_model, monthly_price, performance_fee_pct
- is_published, is_featured, created_at

### marketplace_subscriptions
- id, strategy_id, subscriber_id
- subscription_type, auto_trade, position_size_pct
- started_at, expires_at, status

### marketplace_performance
- id, strategy_id, date
- daily_return, cumulative_return
- sharpe_ratio, max_drawdown
- win_rate, profit_factor

### marketplace_reviews
- id, strategy_id, reviewer_id
- rating, title, content
- is_verified, created_at

## API Endpoints

```
GET    /api/v1/marketplace/strategies          # Browse strategies
GET    /api/v1/marketplace/strategies/{id}     # Strategy details
POST   /api/v1/marketplace/strategies          # Publish strategy
PUT    /api/v1/marketplace/strategies/{id}     # Update strategy
POST   /api/v1/marketplace/subscribe/{id}      # Subscribe
DELETE /api/v1/marketplace/subscribe/{id}      # Unsubscribe
GET    /api/v1/marketplace/leaderboard         # Performance rankings
POST   /api/v1/marketplace/reviews             # Submit review
```

## Pricing Models

1. **Free**: No cost, creator builds following
2. **Subscription**: Fixed monthly fee ($9.99-$99.99)
3. **Performance Fee**: Percentage of profits (10-30%)
4. **Hybrid**: Low subscription + performance fee

## Revenue Split

- Platform: 20%
- Creator: 80%

## Success Metrics

| Metric | Target |
|--------|--------|
| Published strategies | > 100 |
| Active subscribers | > 1,000 |
| Avg strategy rating | > 4.0 |
| Creator retention | > 70% |

## Files

- `src/marketplace/config.py` - Configuration and enums
- `src/marketplace/models.py` - Data models
- `src/marketplace/strategies.py` - Strategy management
- `src/marketplace/subscriptions.py` - Subscription handling
- `src/marketplace/performance.py` - Performance tracking
- `src/marketplace/discovery.py` - Search and recommendations
- `app/pages/marketplace.py` - Marketplace dashboard
