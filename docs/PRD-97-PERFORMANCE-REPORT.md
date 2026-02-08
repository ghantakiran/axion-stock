# PRD-97: GIPS-Compliant Performance Reporting

## Overview
GIPS (Global Investment Performance Standards) compliant performance reporting system with composite management, TWR/MWR return calculations, gross/net fee separation, internal dispersion metrics, compliance validation, and presentation generation.

## Components

### 1. Composite Manager (`src/performance_report/composite.py`)
- **CompositeManager** — Composite creation, portfolio membership, return aggregation
- Create/archive composites with strategy, benchmark, membership rules
- Add/remove portfolios with minimum size enforcement and duplicate prevention
- Asset-weighted composite return calculation
- Sample composite generation for demo

### 2. GIPS Calculator (`src/performance_report/calculator.py`)
- **GIPSCalculator** — GIPS-compliant return calculations
- Time-weighted return (TWR) with sub-period linking
- Modified Dietz return with day-weighted cash flows
- Money-weighted return (IRR) via Newton's method
- Gross-to-net and net-to-gross fee conversion
- Return annualization, geometric linking
- Annualized standard deviation (3-year GIPS requirement)
- Large cash flow detection (10% threshold)
- Annual CompositePeriod construction from monthly data

### 3. Dispersion Calculator (`src/performance_report/dispersion.py`)
- **DispersionCalculator** — Internal dispersion metrics
- Asset-weighted standard deviation
- Equal-weighted standard deviation
- High-low range
- Interquartile range
- Multi-method comparison
- Meaningful threshold (>= 6 portfolios)

### 4. Compliance Validator (`src/performance_report/compliance.py`)
- **ComplianceValidator** — 13-rule GIPS compliance engine
- GIPS-1.x: Composite definition, inception/creation dates
- GIPS-2.x: Benchmark designation
- GIPS-3.x: Membership rules, active portfolios
- GIPS-4.x: History length (5-year minimum)
- GIPS-5.x: Annual returns (gross+net), 3-year std dev
- GIPS-6.x: Assets, portfolio count, dispersion reporting
- GIPS-7.x: Firm assets reporting
- Required disclosure generation (8 categories): firm definition, compliance claim, composite description, benchmark, fees, currency, risk measures, policies

### 5. Report Generator (`src/performance_report/generator.py`)
- **GIPSReportGenerator** — GIPS-compliant presentation output
- Full presentation with periods, disclosures, compliance status
- Formatted text table with all required columns
- Summary dictionary for dashboard display
- Cumulative return calculations

### 6. Configuration (`src/performance_report/config.py`)
- ReturnMethod (TIME_WEIGHTED, MONEY_WEIGHTED, MODIFIED_DIETZ, DAILY_VALUATION)
- FeeType (GROSS, NET, BOTH)
- CompositeMembership (FULL_PERIOD, BEGINNING_OF_PERIOD, SINCE_INCEPTION)
- DispersionMethod (ASSET_WEIGHTED_STD, EQUAL_WEIGHTED_STD, HIGH_LOW_RANGE, INTERQUARTILE)
- ReportPeriod (MONTHLY, QUARTERLY, ANNUAL, SINCE_INCEPTION)
- FeeSchedule with tiered rate lookup
- CompositeConfig, GIPSConfig

### 7. Models (`src/performance_report/models.py`)
- 10 dataclasses: PortfolioAssignment, PerformanceRecord, CompositeDefinition, CompositeReturn, CompositePeriod, DispersionResult, GIPSDisclosure, ComplianceCheck, ComplianceReport, GIPSPresentation

## Database Tables
- `gips_composite_periods` — Annual composite performance records (migration 097)
- `gips_compliance_logs` — Compliance validation audit trail (migration 097)

## Dashboard
Streamlit dashboard (`app/pages/performance_report.py`) with 4 tabs: Composites, Performance, Compliance, Presentation.

## Test Coverage
59 tests in `tests/test_performance_report.py` covering enums (5), FeeSchedule (3), GIPSConfig (2), models (8), CompositeManager (9), GIPSCalculator (12), DispersionCalculator (7), ComplianceValidator (6), GIPSReportGenerator (4), integration (2), module imports (1).
