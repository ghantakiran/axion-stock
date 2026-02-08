# PRD-96: Dividend Tracker

## Overview
Dividend tracking system with calendar management, income forecasting, safety analysis (payout ratios, coverage), growth tracking (aristocrats/kings), DRIP simulation, and tax impact analysis.

## Components

### 1. Dividend Calendar (`src/dividends/calendar.py`)
- **DividendCalendar** — Ex-date/payment date management
- Add events, upcoming ex-dates, next ex-date lookup
- Sample calendar generation for demo

### 2. Income Projector (`src/dividends/income.py`)
- **IncomeProjector** — Income analysis and forecasting
- Single holding and portfolio projection
- 5+ year future income forecasts with growth rates
- Monthly breakdown by payment frequency, sector income allocation
- Income gap identification (low-income months)

### 3. Safety Analyzer (`src/dividends/safety.py`)
- **SafetyAnalyzer** — Dividend safety assessment (0-100 score)
- Payout ratios (earnings + cash), balance sheet metrics (D/EBITDA, interest coverage)
- 7+ red flag checks, weighted scoring
- Ratings: VERY_SAFE (85+), SAFE (70+), MODERATE (50+), RISKY (30+), DANGEROUS (<30)
- Safe dividend screening and comparison

### 4. Growth Analyzer (`src/dividends/growth.py`)
- **GrowthAnalyzer** — CAGR and streak tracking
- 1y/3y/5y/10y growth rates, consecutive increase tracking
- Status: KING (50+ yrs), ARISTOCRAT (25+), ACHIEVER (10+), CONTENDER (5-9), CHALLENGER (1-4)
- Aristocrat/King filtering, growth screening and ranking

### 5. DRIP Simulator (`src/dividends/drip.py`)
- **DRIPSimulator** — Dividend reinvestment modeling
- Year-by-year simulation with share accumulation
- DRIP vs no-DRIP comparison, doubling time calculation
- Sensitivity analysis (dividend growth × price growth matrix)

### 6. Tax Analyzer (`src/dividends/tax.py`)
- **TaxAnalyzer** — Dividend tax impact
- Qualified vs ordinary income breakdown
- Federal + state tax estimation, tax savings analysis
- Account placement recommendations (taxable vs tax-deferred vs tax-free)

### 7. Configuration (`src/dividends/config.py`)
- DividendFrequency, DividendType, SafetyRating, DividendStatus, TaxClassification
- Frequency multipliers, payout thresholds, 2024 tax brackets, sector yields

### 8. Models (`src/dividends/models.py`)
- 14 dataclasses: DividendEvent, DividendRecord, DividendHolding, DividendIncome, PortfolioIncome, DividendSafety, DividendGrowth, DRIPYear, DRIPSimulation, DividendTaxAnalysis

## Database Tables
- `dividend_income_projections` — Income forecast snapshots (migration 096)
- `dividend_safety_scores` — Safety assessment history (migration 096)

## Dashboard
Streamlit dashboard (`app/pages/dividends.py`) with 6 tabs: Calendar, Income, Safety, Growth, DRIP, Tax.

## Test Coverage
24 tests in `tests/test_dividends.py` covering DividendEvent (2), DividendHolding (4), DividendCalendar (4), IncomeProjector (3), SafetyAnalyzer (2), GrowthAnalyzer (3), DRIPSimulator (3), TaxAnalyzer (3).
