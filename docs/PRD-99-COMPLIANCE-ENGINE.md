# PRD-99: Compliance Engine

## Overview
Regulatory compliance engine with trade surveillance (wash trades, spoofing, layering, marking the close), insider trading blackout windows with pre-clearance workflow, best execution monitoring and quality scoring, and regulatory report generation.

## Components

### 1. Surveillance Engine (`src/compliance_engine/surveillance.py`)
- **SurveillanceEngine** — Pattern-based trade surveillance
- 5 detection algorithms: wash trades, layering, spoofing, excessive trading, marking the close
- Wash trade: buy/sell same security within 5-minute window at similar prices
- Layering: 5+ orders on same side for a symbol
- Spoofing: 90%+ cancellation rate indicating intent to mislead
- Excessive trading: daily trade count exceeding threshold
- Marking the close: large orders (>1000 shares) in last 5 minutes
- Alert resolution workflow, filtered queries, count aggregation

### 2. Blackout Manager (`src/compliance_engine/blackout.py`)
- **BlackoutManager** — Insider trading blackout window management
- Create custom and earnings-based blackout windows (14 days before, 2 after)
- Person-specific blackout enforcement
- Pre-clearance request workflow (submit → approve/deny)
- Pre-clearance validity period (5 days)
- Trade authorization check combining blackout, threshold, and pre-clearance status
- Window deactivation and listing

### 3. Best Execution Monitor (`src/compliance_engine/best_execution.py`)
- **BestExecutionMonitor** — Execution quality tracking and reporting
- Record individual executions with slippage and price improvement
- Quality classification: EXCELLENT (≤2bps), GOOD (≤5bps), ACCEPTABLE (≤10bps), POOR, FAILED
- Buy/sell-aware slippage calculation
- Period-based aggregate report with quality distribution
- Per-venue breakdown and ranking
- Cost savings from price improvement
- Poor execution flagging

### 4. Regulatory Reporter (`src/compliance_engine/reporting.py`)
- **RegulatoryReporter** — Compliance report generation
- Daily compliance report with alert summary, blackout violations, execution quality
- Surveillance summary with resolution rate and type/severity breakdown
- Best execution regulatory filing
- Overall compliance health summary (compliant/review_required/non_compliant)
- Filing status tracking (filed/unfiled) with timestamps

### 5. Configuration (`src/compliance_engine/config.py`)
- SurveillanceType (WASH_TRADE, LAYERING, SPOOFING, FRONT_RUNNING, INSIDER_TRADING, PUMP_AND_DUMP, EXCESSIVE_TRADING, MARKING_CLOSE)
- AlertSeverity (LOW, MEDIUM, HIGH, CRITICAL)
- BlackoutStatus (OPEN, BLACKOUT, PRE_CLEARANCE_REQUIRED)
- ExecutionQuality (EXCELLENT, GOOD, ACCEPTABLE, POOR, FAILED)
- ReportType (DAILY_COMPLIANCE, BEST_EXECUTION, SURVEILLANCE_SUMMARY, INSIDER_TRADING, VIOLATION_LOG)
- SurveillanceConfig, BlackoutConfig, BestExecutionConfig

### 6. Models (`src/compliance_engine/models.py`)
- 8 dataclasses: TradePattern, SurveillanceAlert, BlackoutWindow, PreClearanceRequest, ExecutionMetric, BestExecutionReport, RegulatoryFiling, ComplianceSummary

## Database Tables
- `surveillance_alerts` — Trade surveillance alert records (migration 099)
- `best_execution_log` — Execution quality metrics (migration 099)

## Dashboard
Streamlit dashboard (`app/pages/compliance_engine.py`) with 4 tabs: Surveillance, Blackout Windows, Best Execution, Reports.

## Test Coverage
55 tests in `tests/test_compliance_engine.py` covering enums (5), configs (3), models (6), SurveillanceEngine (10), BlackoutManager (12), BestExecutionMonitor (8), RegulatoryReporter (8), integration (2), module imports (1).
