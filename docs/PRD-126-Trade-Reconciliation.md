# PRD-126: Trade Reconciliation & Settlement Engine

## Overview
Automated reconciliation engine that matches internal trade records against broker/exchange confirmations, tracks settlement status, identifies breaks, and provides resolution workflows.

## Goals
1. Automated matching of internal orders with broker execution reports
2. Settlement lifecycle tracking (T+0 through T+2)
3. Break detection and classification (price, quantity, timing, missing)
4. Resolution workflow with audit trail
5. Reconciliation reporting and dashboards

## Components

### 1. Reconciliation Config (`config.py`)
- ReconciliationStatus enum: PENDING, MATCHED, BROKEN, RESOLVED, SETTLED
- BreakType enum: PRICE_MISMATCH, QUANTITY_MISMATCH, MISSING_BROKER, MISSING_INTERNAL, TIMING, DUPLICATE
- SettlementStatus enum: PENDING, IN_PROGRESS, SETTLED, FAILED, CANCELLED
- MatchStrategy enum: EXACT, FUZZY, MANUAL
- ToleranceConfig dataclass (price_tolerance, quantity_tolerance, time_window)
- ReconciliationConfig dataclass (strategy, tolerances, auto_resolve, settlement_days)

### 2. Matching Engine (`matcher.py`)
- TradeRecord dataclass (trade_id, symbol, side, quantity, price, timestamp, source)
- MatchResult dataclass (internal_trade, broker_trade, status, break_type, confidence)
- MatchingEngine class:
  - match_trades(internal, broker) -> list of MatchResult
  - exact_match(trade1, trade2) -> bool
  - fuzzy_match(trade1, trade2, tolerances) -> (bool, confidence)
  - find_unmatched(results) -> (missing_internal, missing_broker)
  - batch_reconcile(date_range) -> ReconciliationReport

### 3. Settlement Tracker (`settlement.py`)
- SettlementEvent dataclass (event_id, trade_id, status, expected_date, actual_date)
- SettlementTracker class:
  - track_settlement(trade_id, settlement_date) -> SettlementEvent
  - update_status(event_id, status) -> SettlementEvent
  - get_pending_settlements(date) -> list
  - check_overdue(as_of) -> list of overdue
  - settlement_summary(date_range) -> statistics

### 4. Break Manager (`breaks.py`)
- ReconciliationBreak dataclass (break_id, match_result, break_type, severity, resolution)
- BreakResolution dataclass (resolution_id, break_id, action, resolved_by, notes)
- BreakManager class:
  - create_break(match_result) -> ReconciliationBreak
  - classify_break(match_result) -> BreakType
  - resolve_break(break_id, resolution) -> BreakResolution
  - auto_resolve(break) -> optional BreakResolution
  - get_open_breaks() -> list
  - break_statistics() -> dict

### 5. Reconciliation Reporter (`reporter.py`)
- ReconciliationReport dataclass (report_id, period, total_trades, matched, broken, resolved, match_rate)
- DailyReconciliation dataclass (date, statistics, breaks, settlements)
- ReconciliationReporter class:
  - generate_daily_report(date) -> DailyReconciliation
  - generate_period_report(start, end) -> ReconciliationReport
  - aging_report() -> aged break analysis
  - trend_analysis(days) -> matching trend

## Database Tables
- `reconciliation_records`: Trade match records with status
- `settlement_events`: Settlement lifecycle tracking

## Dashboard (4 tabs)
1. Reconciliation Overview — match rates, break counts, metrics
2. Trade Matching — recent matches, unmatched trades
3. Settlement Tracking — pending settlements, overdue items
4. Break Management — open breaks, resolution history

## Test Coverage
- Unit tests for matching engine (exact/fuzzy/batch)
- Settlement lifecycle tests
- Break detection and resolution tests
- Reporter tests
- ~80+ tests
