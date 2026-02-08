# PRD-98: Smart Order Router

## Overview
Multi-venue smart order routing system with venue scoring, cost optimization, fill probability estimation, dark pool allocation, maker/taker fee optimization, and Reg NMS compliance audit trails.

## Components

### 1. Venue Manager (`src/smart_router/venue.py`)
- **VenueManager** — Venue registry and quality tracking
- Add/deactivate venues with type-specific configs
- Lit vs dark venue filtering
- Cheapest/fastest venue lookup
- Multi-criteria ranking (fill rate, latency, cost, price improvement)
- Real-time metrics update with venue quality drift
- 9 pre-configured US equity venues (NYSE, NASDAQ, ARCA, BATS BZX/BYX, IEX, MEMX, Dark Midpoint, Sigma X)

### 2. Smart Router (`src/smart_router/router.py`)
- **SmartRouter** — Core routing engine with 5 strategies
- BEST_PRICE: Route to highest-scored single venue
- LOWEST_COST: Route to cheapest venue by net cost
- FASTEST_FILL: Split across top venues proportionally
- LOWEST_IMPACT: Score-weighted split with dark pool allocation
- SMART: Balanced strategy with dark pool allocation and score-weighted lit splits
- Automatic dark pool inclusion for SMART/LOWEST_IMPACT strategies
- NBBO recording, audit trail generation

### 3. Route Scorer (`src/smart_router/scoring.py`)
- **RouteScorer** — Multi-factor venue scoring
- Fill probability estimation with size/participation adjustment
- 5-factor composite score: fill (30%), cost (25%), price improvement (20%), latency (15%), adverse selection (10%)
- Configurable weights via RoutingConfig
- Full venue ranking with ordinal position

### 4. Cost Optimizer (`src/smart_router/cost.py`)
- **CostOptimizer** — Execution cost estimation and optimization
- Component-level cost breakdown: exchange fee, spread, impact, opportunity cost
- Square-root market impact model
- Maker rebate calculation
- Venue cost comparison with net cost sorting
- Optimal split cost estimation
- Maker vs taker savings analysis

### 5. Configuration (`src/smart_router/config.py`)
- VenueType (LIT_EXCHANGE, DARK_POOL, ATS, INTERNALIZER, MIDPOINT)
- RoutingStrategy (BEST_PRICE, LOWEST_COST, FASTEST_FILL, LOWEST_IMPACT, SMART)
- OrderPriority (AGGRESSIVE, NEUTRAL, PASSIVE)
- FeeModel (MAKER_TAKER, FLAT, INVERTED, FREE)
- VENUE_FEES dictionary for 10 venues, DEFAULT_WEIGHTS
- VenueConfig, RoutingConfig

### 6. Models (`src/smart_router/models.py`)
- 8 dataclasses: Venue, FillProbability, CostEstimate, RoutingScore, RouteSplit, RouteDecision, VenueMetrics, RoutingAudit

## Database Tables
- `routing_decisions` — Routing decision records with splits (migration 098)
- `venue_performance_log` — Venue quality metrics over time (migration 098)

## Dashboard
Streamlit dashboard (`app/pages/smart_router.py`) with 4 tabs: Route Order, Venues, Cost Analysis, Audit Log.

## Test Coverage
50 tests in `tests/test_smart_router.py` covering enums (6), config (2), models (5), VenueManager (10), RouteScorer (5), CostOptimizer (7), SmartRouter (10), integration (2), module imports (1).
