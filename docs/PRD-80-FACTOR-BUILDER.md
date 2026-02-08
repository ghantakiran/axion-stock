# PRD-80: Custom Factor Builder

## Overview
User-defined custom factor construction system allowing analysts to combine existing metrics with configurable weights, transformations, and aggregation methods to create proprietary scoring factors.

## Components

### 1. Factor Builder (`src/factors/builder.py`)
- **CustomFactorBuilder** — Full CRUD + computation engine for custom factors
- **Create/Update/Delete/Get/List** — Factor management with creator filtering
- **Compute** — Score a universe of securities against a custom factor definition
- **Transformations** — RAW, PERCENTILE_RANK, ZSCORE, LOG, INVERSE, ABS
- **Aggregation** — WEIGHTED_AVERAGE, EQUAL_WEIGHT, MAX, MIN, GEOMETRIC_MEAN
- **Direction** — positive (higher is better) or negative (lower is better)

### 2. Data Models (`src/factors/builder.py`)
- **FactorComponent** — metric_name, weight, transform, direction
- **CustomFactor** — id, name, description, components, aggregation, created_by, timestamps; properties: n_components, total_weight, component_names
- **FactorResult** — factor_id, factor_name, scores dict; methods: top_n(), bottom_n(), n_scored

### 3. Enums
- **TransformType** — RAW, PERCENTILE_RANK, ZSCORE, LOG, INVERSE, ABS (6 values)
- **AggregationMethod** — WEIGHTED_AVERAGE, EQUAL_WEIGHT, MAX, MIN, GEOMETRIC_MEAN (5 values)

### 4. Existing Factor Infrastructure (`src/factors/`)
- **FactorRegistry** — Plugin-based factor registration system
- **Built-in Calculators** — Value (PE, PB, EV/EBITDA), Momentum (1/3/6/12M returns), Quality (ROE, margins, debt), Growth (revenue/earnings growth), Volatility (realized vol, beta), Technical (RSI, MACD, Bollinger)
- **FactorAnalyzer** — Factor exposure analysis and decomposition

## Database Tables
- `custom_factor_definitions` — Stored factor configurations with components JSON (migration 080)
- `custom_factor_results` — Computed factor scores with timestamps (migration 080)

## Dashboard
Streamlit dashboard (`app/pages/factor_builder.py`) with 4 tabs:
1. **Build Factor** — Interactive factor creation with component configuration
2. **Factor Library** — Browse, view, and delete saved factors
3. **Compute & Rank** — Score securities using custom factors (CSV upload or sample data)
4. **Factor Analysis** — Factor summary, component weight visualization

## Test Coverage
37 tests in `tests/test_factor_builder.py` covering enums (transform types, aggregation methods), model properties/serialization (FactorComponent, CustomFactor, FactorResult), CRUD operations (create/get/list/update/delete with validation), computation (single component, weighted average, equal weight, max, min, geometric mean, negative direction, raw/zscore/log transforms, missing column handling), and module imports.
