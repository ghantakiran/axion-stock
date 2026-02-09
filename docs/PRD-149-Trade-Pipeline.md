# PRD-149: Live Signal-to-Trade Pipeline

## Overview
Bridges the "last mile" gap between signal generation and trade execution. Normalizes signals from 3 different sources (signal fusion, social intelligence, EMA cloud) into a unified PipelineOrder format, validates against risk rules, and routes to the multi-broker execution system.

## Architecture
```
Signal Sources                    Pipeline
─────────────                    ────────
Recommendation  ─┐
SocialTradingSignal ─┼→ SignalBridge → PipelineOrder → Validate → Risk Check → Route → Execute → Reconcile
TradeSignal     ─┘                                                                ↓
                                                                           PositionStore
```

## Components

### Signal Bridge (`bridge.py`)
- **SignalType**: FUSION, SOCIAL, EMA_CLOUD, MANUAL
- **OrderSide**: BUY, SELL
- **OrderType**: MARKET, LIMIT, STOP, STOP_LIMIT
- **PipelineOrder**: Unified order format with 18 fields
- **SignalBridge**: 4 converters (from_recommendation, from_social_signal, from_trade_signal, from_dict)

### Pipeline Executor (`executor.py`)
- **5-stage pipeline**: validate → risk_check → route → execute → record
- **PipelineConfig**: min_confidence, max_positions, daily_loss_limit, blocked_symbols, paper_mode
- **Validation**: Symbol, qty, confidence, order type consistency
- **Risk checks**: Position limits, daily loss limit, blocked symbols, order value bounds
- **Paper mode**: Simulates fills without broker calls
- **Live mode**: Routes to MultiBrokerExecutor (PipelineStatus.ROUTED)

### Execution Reconciler (`reconciler.py`)
- **Slippage tracking**: (actual - expected) / expected as percentage
- **Fill quality**: Fill ratio (actual_qty / expected_qty)
- **Per-broker stats**: Average slippage by broker
- **Aggregate stats**: SlippageStats with min/max/avg slippage, fill rate, latency

### Position Store (`position_store.py`)
- **Open/close/reduce**: Position lifecycle management
- **Averaging**: Weighted average entry price on add-to-position
- **P&L tracking**: Unrealized and realized P&L
- **Exit detection**: Stop loss and target hit checking
- **Serialization**: JSON roundtrip for persistence

## Dashboard
4-tab Streamlit interface:
1. **Signal Bridge**: Convert signals to PipelineOrders interactively
2. **Pipeline Executor**: Demo pipeline with validation/risk metrics
3. **Reconciliation**: Slippage stats, per-broker quality, fill rates
4. **Position Tracker**: Open positions with P&L, exit trigger alerts

## Database Tables
- `pipeline_orders`: Order log with signal data and execution results
- `pipeline_positions`: Current open position tracking
- `pipeline_reconciliations`: Fill quality and slippage records
