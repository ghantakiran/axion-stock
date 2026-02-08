# PRD-66: Trade Journal Dashboard

## Overview
Comprehensive trade journaling system for logging trades, tracking performance, analyzing patterns, and developing trader psychology insights.

## Components

### 1. Journal Service (`src/journal/service.py`)
- **Setup Management** — 8 default setups (breakout, pullback, reversal, momentum, mean_reversion, gap_play, earnings, news), custom setup creation
- **Strategy Management** — CRUD for trading strategies with entry/exit rules and risk parameters
- **Trade Entry** — Full trade logging with direction, entry/exit prices, quantities, stop/target, setup, strategy, emotions, timeframe, rationale
- **Trade Close** — Auto P&L calculation (long/short aware), actual R:R computation, exit emotion capture
- **Daily Reviews** — Auto-aggregation of daily stats (trades, P&L, win rate), self-assessment, plan adherence
- **Periodic Reviews** — Weekly/monthly review with auto-calculated performance metrics, best/worst setup detection

### 2. Analytics Engine (`src/journal/analytics.py`)
- **Performance Metrics** — Win rate, profit factor, expectancy, avg winner/loser, largest win/loss, R:R ratio
- **Dimensional Breakdowns** — By setup, strategy, day of week, hour of day, trade type
- **Emotion Analysis** — Pre/during/post trade emotion correlation with P&L, recommendations (favorable/neutral/avoid)
- **Equity & Risk** — Equity curve, drawdown analysis (max DD, DD series), streak analysis (win/loss streaks)
- **R-Multiple Distribution** — Risk-adjusted return analysis with statistics
- **Pattern Recognition** — Automated insight generation for strengths, weaknesses, patterns, and recommendations

### 3. Execution Journal (`src/execution/journal.py`)
- Lower-level order/trade/snapshot logging
- Order status tracking, portfolio daily snapshots
- Performance metrics with Sharpe ratio and drawdown

## Database Tables
- `trading_strategies` — User-defined strategy configurations
- `trade_setups` — Categorized trade patterns/setups
- `journal_entries` — Core trade journal (50+ fields)
- `daily_reviews` — Daily self-assessment and stats
- `periodic_reviews` — Weekly/monthly reviews with goals

## Dashboard
6-tab Streamlit dashboard (`app/pages/trade_journal.py`):
1. **Dashboard** — Metrics row, equity curve, open positions, setup performance, day-of-week P&L
2. **Log Trade** — Entry and close trade forms with full context capture
3. **Analytics** — Metrics, setup breakdown, emotion analysis, time patterns
4. **Insights** — Automated pattern recommendations
5. **Review** — Daily review form with auto-calculated stats
6. **History** — Closed trades table with P&L styling

## Enums
- `TradeDirection` — LONG, SHORT
- `TradeType` — SCALP, DAY, SWING, POSITION
- `EmotionalState` — CALM, CONFIDENT, ANXIOUS, FOMO, GREEDY, FEARFUL, FRUSTRATED, EUPHORIC, REVENGE

## Test Coverage
45+ tests in `tests/test_trade_journal.py` covering metrics, setup analysis, emotion analysis, equity curve, drawdown, streaks, day-of-week, R-multiples, service layer, daily reviews, insights, and data validation.
