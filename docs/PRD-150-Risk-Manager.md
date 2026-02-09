# PRD-150: Advanced Risk Management

## Overview
Production-grade risk controls that integrate with the trade pipeline (PRD-149). Provides portfolio-level monitoring, cascading loss protection, emergency halt capability, and market calendar enforcement.

## Architecture
```
Trade Pipeline → Portfolio Risk Monitor → approve/deny
                      ↓
              Circuit Breaker → halt on cascading losses
                      ↓
              Kill Switch → emergency halt with event log
                      ↓
              Market Hours → session-aware execution
```

## Components

### Portfolio Risk Monitor (`portfolio_risk.py`)
- **Leverage monitoring**: Gross and net leverage with configurable limits
- **Sector concentration**: 40-symbol sector map, max 30% per sector
- **Single-stock limits**: Max 15% of equity per position
- **VIX-based sizing**: Dynamic position sizing (1.2x @ VIX<15, 0.5x @ VIX>25, halt @ VIX>35)
- **5 risk levels**: LOW, MODERATE, ELEVATED, HIGH, CRITICAL
- **Trade approval**: Pre-trade check against sector/position limits

### Trading Circuit Breaker (`circuit_breaker.py`)
- **Three-state machine**: CLOSED (normal) → OPEN (halted) → HALF_OPEN (recovery)
- **Trip conditions**: Consecutive losses (3), daily drawdown (5%), loss rate (5/hour)
- **Cooldown**: Configurable time before OPEN → HALF_OPEN transition
- **Half-open recovery**: Reduced size (0.5x), auto-reset on win
- **Size multiplier**: 1.0x (CLOSED), 0.5x (HALF_OPEN), 0.0x (OPEN)

### Enhanced Kill Switch (`kill_switch.py`)
- **Three states**: DISARMED → ARMED → TRIGGERED
- **Auto-triggers**: Equity floor (PDT $25K), daily drawdown (10%), consecutive API errors (5)
- **Event logging**: All state changes recorded with equity/P&L context
- **Manual control**: arm(), disarm(), trigger()
- **Error tracking**: Consecutive API errors with auto-trigger

### Market Hours Enforcer (`market_hours.py`)
- **Session detection**: PRE_MARKET, REGULAR, AFTER_HOURS, CLOSED
- **Holiday calendar**: 2025-2026 NYSE holidays + early close days
- **Session restrictions**: Configurable pre-market/after-hours trading
- **Crypto support**: 24/7 trading for crypto assets
- **Next open**: Computes next regular session open
- **Time to close**: Minutes remaining in current session

## Dashboard
4-tab Streamlit interface:
1. **Portfolio Risk**: VIX slider, risk level indicator, sector heatmap, warnings
2. **Circuit Breaker**: Loss simulation, state visualization, size multiplier
3. **Kill Switch**: ARM/TRIGGER buttons, event history, state indicator
4. **Market Hours**: Current session, asset availability, time to close

## Database Tables
- `risk_snapshots`: Point-in-time portfolio risk assessments
- `circuit_breaker_events`: Circuit breaker state change log
- `kill_switch_events`: Kill switch activation/deactivation events
