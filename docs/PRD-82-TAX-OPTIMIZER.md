# PRD-82: Tax Optimizer

## Overview
Comprehensive tax optimization system with tax lot management, wash sale detection, tax-loss harvesting, federal/state tax estimation, IRS form generation, dividend tax analysis, and tax-aware portfolio rebalancing.

## Components

### 1. Tax Lot Manager (`src/tax/lots.py`)
- **TaxLotManager** — Cost basis tracking with 6 lot selection methods
- Methods: FIFO, LIFO, HIGH_COST, MAX_LOSS, MIN_TAX, SPEC_ID
- Lot creation, retrieval, total shares, average cost, unrealized gains
- Execute sale with realized gain tracking, basis adjustments for wash sales
- Lots approaching long-term threshold identification

### 2. Wash Sale Tracker (`src/tax/wash_sales.py`)
- **WashSaleTracker** — IRS wash sale rule compliance
- 30-day lookback and lookforward windows
- Substantially identical security detection (ETF equivalence)
- Automatic basis and holding period adjustments
- Partial wash sale handling, disallowed loss tracking

### 3. Tax-Loss Harvester (`src/tax/harvesting.py`)
- **TaxLossHarvester** — Automated tax-loss harvesting
- Opportunity identification with minimum loss thresholds
- Tax savings estimation, wash sale risk flagging
- ETF substitute suggestions (SPY/IVV/VOO, QQQ/QQQM, VTI/ITOT, etc.)
- Harvest summary, repurchase calendar, year-end priorities

### 4. Tax Estimator (`src/tax/estimator.py`)
- **TaxEstimator** — Federal and state tax liability calculation
- Federal ordinary income brackets (4 filing statuses)
- Long-term capital gains rates (0%, 15%, 20%)
- Net Investment Income Tax (3.8% NIIT)
- All 50 state + DC tax rates with LTCG exclusions
- Scenario comparison, breakeven hold days calculation

### 5. Tax Report Generator (`src/tax/reports.py`)
- **TaxReportGenerator** — IRS form generation
- Form 8949 (Sales & Dispositions) with wash sale adjustments
- Schedule D (Capital Gains Summary)
- Gain/Loss reports (realized + unrealized)
- Annual tax summary with text formatting

### 6. Configuration (`src/tax/config.py`)
- **FilingStatus** — Single, Married Joint, Married Separate, Head of Household
- **HoldingPeriod** — Short-term, Long-term
- **LotSelectionMethod** — FIFO, LIFO, HIGH_COST, MAX_LOSS, MIN_TAX, SPEC_ID
- **AcquisitionType** — Buy, Dividend Reinvest, Transfer, Gift, Inheritance, Stock Split, Merger
- **AccountType** — Taxable, Traditional IRA, Roth IRA, SEP IRA, 401k, 403b, HSA
- **TaxProfile**, **HarvestingConfig**, **WashSaleConfig**, **LotSelectionConfig**, **TaxConfig**

### 7. Models (`src/tax/models.py`)
- **TaxLot** — Individual lot with cost basis tracking
- **RealizedGain** — Realized gains/losses from sales
- **LotSelectionResult** — Result of lot selection
- **WashSale** — Wash sale record with disallowed loss
- **WashSaleCheckResult** — Detection result
- **HarvestOpportunity** — Harvestable loss with tax savings
- **HarvestResult** — Harvest execution result
- **TaxEstimate** — Complete tax liability breakdown
- **Form8949**, **Form8949Entry**, **ScheduleD**, **GainLossReport**, **TaxSummaryReport**

### 8. Supporting Modules
- **Tax-Aware Rebalancer** (`src/optimizer/tax.py`) — Tax-optimized rebalancing with harvest candidate identification
- **Dividend Tax Analyzer** (`src/dividends/tax.py`) — Qualified vs ordinary dividend tax, account placement recommendations

## Database Tables
- `tax_lots` — Tax lot inventory with cost basis and acquisition details (migration 082)
- `tax_harvest_log` — Tax-loss harvesting execution log (migration 082)

## Dashboard
Streamlit dashboard (`app/pages/tax.py`) with 5 tabs:
1. **Tax Lots** — Lot inventory with unrealized gains
2. **Harvesting** — Tax-loss harvesting opportunities
3. **Estimator** — Tax liability estimation with scenarios
4. **Lot Selection** — Simulator for FIFO/LIFO/etc.
5. **Year-End** — Year-end tax planning tools

## Test Coverage
34 tests in `tests/test_tax.py` covering TaxLotManager (lot CRUD, selection methods, sale execution, holding periods), WashSaleTracker (detection, substantially identical securities, partial wash sales), TaxLossHarvester (opportunities, savings, summary), TaxEstimator (brackets, NIIT, state tax, filing status, breakeven), TaxReportGenerator (Form 8949, Schedule D, text formatting, summary), GainLossReport, and integration tests (full harvest workflow, wash sale prevention).
