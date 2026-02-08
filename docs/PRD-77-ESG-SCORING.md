# PRD-77: ESG Scoring & Impact Tracking

## Overview
ESG scoring and impact tracking system with composite scoring from Environmental/Social/Governance pillars, letter ratings (AAA-CCC), controversy penalties, security screening, carbon metrics, sector ranking, portfolio-level ESG aggregation, and impact benchmarking.

## Components

### 1. ESG Scorer (`src/esg/scoring.py`)
- **ESGScorer** — Composite scoring with configurable E/S/G weights (default 35/30/35)
- Score clamping (0-100), controversy penalty application
- Letter rating assignment (AAA >=85, AA >=75, A >=65, BBB >=55, BB >=45, B >=35, CCC <35)
- **ESG Screening** — Exclude sin stocks, fossil fuels, weapons; min score filter; carbon intensity threshold
- **Portfolio Summary** — Weighted E/S/G/composite scores, carbon intensity, best/worst in class
- **Sector Ranking** — Rank securities within sector by composite score with percentiles

### 2. Impact Tracker (`src/esg/impact.py`)
- **ImpactTracker** — Record and track impact metrics by symbol and category
- Industry benchmark comparison (carbon footprint, renewable energy, water, waste, satisfaction, pay gap, board independence, tax transparency)
- Portfolio-level weighted impact aggregation
- Trend tracking (improving, stable, declining)

### 3. Configuration (`src/esg/config.py`)
- **ESGCategory** — ENVIRONMENTAL, SOCIAL, GOVERNANCE, COMPOSITE
- **ESGPillar** — 15 pillars (carbon, energy, waste, water, biodiversity, labor, diversity, community, privacy, rights, board, compensation, shareholders, ethics, transparency)
- **ESGRating** — AAA, AA, A, BBB, BB, B, CCC
- **ImpactCategory** — CARBON_FOOTPRINT, RENEWABLE_ENERGY, WATER_INTENSITY, WASTE_RECYCLED, EMPLOYEE_SATISFACTION, GENDER_PAY_GAP, BOARD_INDEPENDENCE, TAX_TRANSPARENCY
- **ESGConfig** — Weights, score bounds, exclusion flags, carbon threshold, controversy penalty

### 4. Models (`src/esg/models.py`)
- **ESGScore** — Composite score with E/S/G breakdown, rating, controversies, sector rank
- **PillarScore** — Individual pillar score with weight and data quality
- **CarbonMetrics** — Scope 1/2/3 emissions, carbon intensity, renewable %, net zero target
- **ESGScreenResult** — Pass/fail with exclusion reasons
- **ImpactMetric** — Category value with unit, benchmark, percentile, trend
- **ESGPortfolioSummary** — Weighted portfolio scores, rating, coverage, best/worst in class

## Database Tables
- `esg_scores` — Security ESG scores with E/S/G breakdown, rating, controversies (migration 077)
- `esg_impact_metrics` — Impact measurements by category with benchmarks (migration 077)

## Dashboard
5-tab Streamlit dashboard (`app/pages/esg.py`):
1. **Portfolio ESG** — Weighted scores, rating, coverage, best/worst in class
2. **Security Scores** — Individual security E/S/G breakdown with controversies
3. **Carbon Metrics** — Scope 1/2/3 emissions, renewable energy %
4. **Impact Tracking** — Portfolio impact vs benchmarks
5. **ESG Screening** — Exclusion screening with pass/fail results

## Test Coverage
58 tests in `tests/test_esg.py` covering enums/config, model properties/serialization (PillarScore, ESGScore, CarbonMetrics, ESGScreenResult, ImpactMetric, ESGPortfolioSummary), ESGScorer (scoring, ratings, controversy penalty, clamping, carbon metrics), ESG screening (sin stocks, fossil fuels, weapons, min score, carbon intensity), portfolio summary (weighted scores, controversies, best/worst), sector ranking, ImpactTracker (record/get/latest/portfolio/symbols/custom/trend), and module imports.
