# Axion Trading Platform

AI-native algorithmic trading platform for retail and institutional investors. 170 product modules spanning market analysis, autonomous trading, multi-broker execution, risk management, and ML-powered intelligence.

## Key Numbers

| Metric | Value |
|--------|-------|
| Source modules | 945 Python files |
| Test suite | 8,024 tests across 153 files |
| Dashboard pages | 139 Streamlit pages |
| Database migrations | 167 Alembic versions |
| ORM models | 194+ tables |
| Total LOC | ~358K lines |
| PRDs implemented | 170 |

## Architecture

```
                        ┌─────────────────────────┐
                        │   Streamlit Dashboard    │  :8501
                        │   (139 pages, 10 sections)│
                        └────────────┬────────────┘
                                     │
                        ┌────────────┴────────────┐
                        │    FastAPI + WebSocket   │  :8000
                        │    REST API / Streaming  │
                        └────────────┬────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
   ┌──────────┴──────────┐ ┌────────┴────────┐ ┌──────────┴──────────┐
   │   Signal Engine     │ │  Trade Executor │ │   Risk Management   │
   │  EMA Clouds, ML,    │ │  8 Brokers,     │ │  Unified Risk,      │
   │  Social, TV Scanner │ │  Options, ETFs  │ │  Kill Switch, VaR   │
   └─────────────────────┘ └────────┬────────┘ └─────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
   ┌──────────┴──────────┐ ┌────────┴────────┐ ┌──────────┴──────────┐
   │  PostgreSQL +       │ │     Redis       │ │  Prometheus +       │
   │  TimescaleDB        │ │  Cache & PubSub │ │  Grafana            │
   └─────────────────────┘ └─────────────────┘ └─────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (multi-tab dashboards) |
| API | FastAPI + WebSocket |
| ML/AI | Claude, XGBoost, LightGBM, Transformers |
| Database | PostgreSQL + TimescaleDB |
| Cache | Redis |
| Brokers | Alpaca, Interactive Brokers, Schwab, Robinhood, Coinbase, Fidelity, tastytrade, Webull |
| Data | Polygon.io, Yahoo Finance, FRED, TradingView |
| Monitoring | Prometheus + Grafana |
| CI/CD | GitHub Actions (security scanning, coverage, releases) |

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 16 with TimescaleDB (optional for dev)
- Redis (optional for dev)

### Local Development

```bash
# Clone the repository
git clone https://github.com/ghantakiran/axion-stock.git
cd axion-stock

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your API keys (Polygon, Anthropic, FRED)

# Run the dashboard
streamlit run app/streamlit_app.py
```

The dashboard starts at `http://localhost:8501` with Yahoo Finance data by default (no API keys required for basic functionality).

### Docker (Full Stack)

```bash
cp .env.example .env
# Fill in API keys and secrets in .env

docker compose up -d
```

This starts 7 services:

| Service | Port | Description |
|---------|------|-------------|
| `app` | 8501 | Streamlit dashboard |
| `api` | 8000 | FastAPI REST + WebSocket API |
| `worker` | - | Background scheduler (async tasks) |
| `postgres` | 5432 | PostgreSQL + TimescaleDB |
| `redis` | 6379 | Cache and pub/sub |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Monitoring dashboards |

## Running Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run a specific module's tests
python3 -m pytest tests/test_bot_lifecycle.py -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=html
```

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `AXION_DATABASE_URL` | `postgresql+asyncpg://...` | Async DB connection |
| `AXION_REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `AXION_POLYGON_API_KEY` | (empty) | Polygon.io market data |
| `ANTHROPIC_API_KEY` | (empty) | Claude AI features |
| `AXION_FALLBACK_TO_YFINANCE` | `true` | Use Yahoo Finance as fallback |
| `AXION_USE_DATABASE` | `false` | Enable PostgreSQL persistence |
| `AXION_LOG_LEVEL` | `INFO` | Logging level |
| `AXION_LOG_FORMAT` | `text` | `text` or `json` |

## Module Overview

### Core Trading

| Module | PRD | Description |
|--------|-----|-------------|
| `ema_signals` | 134 | Ripster 4-layer EMA cloud signal engine (10 signal types, conviction scoring 0-100) |
| `trade_executor` | 135 | Signal-to-order pipeline with 8-check risk gate and 7 exit strategies |
| `options_scalper` | 136 | 0DTE/1DTE options scalping with Greeks-aware validation |
| `bot_dashboard` | 137 | Bot lifecycle management and 6-tab command center |
| `bot_backtesting` | 138 | EMA Cloud strategy backtesting with walk-forward optimization |
| `bot_pipeline` | 170-171 | Hardened pipeline: kill switch, signal guard, order validation, position reconciliation |

### Broker Integrations (8 brokers)

| Module | PRD | Features |
|--------|-----|----------|
| `alpaca_live` | 139 | Streaming, position sync, paper + live |
| `robinhood_broker` | 143 | Zero-commission, crypto, fractional shares |
| `coinbase_broker` | 144 | Crypto-native exchange |
| `schwab_broker` | 145 | Full-service brokerage with OAuth2 |
| `fidelity_broker` | 156 | Mutual fund screening, research tools |
| `ibkr_broker` | 157 | Client Portal Gateway, forex/futures, global markets |
| `tastytrade_broker` | 158 | Options-first, multi-leg orders, IV rank/percentile |
| `webull_broker` | 159 | Extended hours 4am-8pm, built-in screener |
| `multi_broker` | 146 | Unified routing across all brokers |

### Intelligence & Signals

| Module | PRD | Description |
|--------|-----|-------------|
| `signal_fusion` | 147 | Cross-signal combination and ranking |
| `signal_pipeline` | 149 | End-to-end signal processing pipeline |
| `signal_persistence` | 162 | Full signal audit trail (signal -> risk -> execution) |
| `signal_feedback` | 166 | Rolling Sharpe per source, adaptive weight adjustment |
| `strategy_optimizer` | 148 | Multi-objective strategy optimization |
| `strategy_selector` | 165 | ADX-gated routing between trend and mean-reversion |
| `regime_adaptive` | 155 | Dynamic strategy switching based on market regime |
| `multi_agent_consensus` | 154 | Ensemble agent voting with confidence weighting |

### AI & Multi-Agent

| Module | PRD | Description |
|--------|-----|-------------|
| `agents` | 131 | 10 specialized agents (6 investment style + 4 functional role) |
| `model_providers` | 132 | Unified interface to Claude, OpenAI, Gemini, DeepSeek, Ollama |
| `tv_scanner` | - | Live TradingView screening (14 preset scans, 6 asset classes) |

### Risk & Portfolio

| Module | PRD | Description |
|--------|-----|-------------|
| `unified_risk` | 163 | Consolidated risk context with 7 checks, VaR/CVaR sizing |
| `risk_management_v2` | 150 | Advanced risk analytics |
| `portfolio_intelligence` | 151 | AI-powered portfolio analysis |
| `trade_attribution` | 160 | Trade-to-signal linking, P&L decomposition |
| `reconciliation` | 126 | Matching engine (exact/fuzzy), settlement tracker |

### Market Analysis (20+ modules)

Market breadth, correlation, volatility, macro indicators, microstructure, order flow, pairs trading, dark pool analytics, fund flow, crowding analysis, regime detection, sector rotation, charting, economic calendar, earnings, dividends, insider trading, and ESG scoring.

### Social & Alternative Data

| Module | PRD | Description |
|--------|-----|-------------|
| `social_crawler` | 140 | Multi-platform social media data collection |
| `social_intelligence` | 141 | Sentiment analysis on social data |
| `social_backtester` | 161 | Signal archive with replay, outcome validation |
| `alert_network` | 142 | Distributed alert routing and management |

### Platform Infrastructure

| Module | PRD | Description |
|--------|-----|-------------|
| `logging_config` | 101 | Structured JSON logging, request tracing |
| `resilience` | 102 | Circuit breaker, retry, rate limiter, bulkhead |
| `observability` | 103 | Prometheus metrics, trading/system metrics |
| `api_errors` | 106 | Exception hierarchy, input validation, request sanitization |
| `lifecycle` | 107 | Health probes (K8s-compatible), signal handling |
| `pipeline` | 112 | DAG-based data pipeline with SLA tracking |
| `config_service` | 111 | Feature flags, secrets manager, environment resolver |
| `event_bus` | 121 | Pub/sub bus with immutable event store |
| `secrets_vault` | 124 | Encrypted vault (envelope encryption), credential rotation |

### Governance

| Module | PRD | Description |
|--------|-----|-------------|
| `audit` | 109 | Immutable events with SHA-256 hash chain |
| `migration_safety` | 110 | AST-based migration validator |
| `data_contracts` | 129 | Schema compatibility checks (backward/forward/full) |
| `anomaly_detection` | 128 | Multi-method detection (Z-score, IQR, isolation forest) |
| `billing` | 125 | Usage metering, billing engine, cost analytics |
| `multi_tenancy` | 122 | Row-level security, RBAC policy engine |

## Project Structure

```
axion-stock/
├── app/                     # Streamlit frontend
│   ├── streamlit_app.py     # Entry point
│   ├── nav_config.py        # 10-section navigation (139 pages)
│   ├── styles.py            # Global CSS theme
│   └── pages/               # 139 dashboard pages
├── src/                     # Source modules (945 files)
│   ├── db/models.py         # 194+ ORM models (~5,174 lines)
│   ├── ema_signals/         # EMA cloud signal engine
│   ├── trade_executor/      # Execution engine + 7 exit strategies
│   ├── bot_pipeline/        # Hardened orchestrator pipeline
│   ├── agents/              # 10 AI agents
│   ├── model_providers/     # Multi-LLM provider system
│   └── ...                  # 130+ additional modules
├── tests/                   # Test suite (153 files, 8,024 tests)
├── alembic/versions/        # 167 database migrations
├── docs/                    # 172 documents (170 PRDs + TV Scanner + GAPS)
├── infrastructure/          # Docker, Prometheus, Grafana configs
├── Dockerfile               # Multi-stage production build
├── docker-compose.yml       # 7-service stack
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata, ruff, pytest config
└── .env.example             # Environment variable template
```

## Database Migrations

Migrations use Alembic with a sequential chain:

```bash
# Run all pending migrations
alembic upgrade head

# Check current migration version
alembic current

# Generate a new migration
alembic revision --autogenerate -m "description"
```

Migration chain: `001 → 002 → ... → 167 → 170 → 171`

## Documentation

All 170 PRDs are documented in `docs/`:

| Phase | PRDs | Theme |
|-------|------|-------|
| Foundation (PRD-01 to PRD-100) | 100 | Core platform: data, factors, execution, risk, ML, options, sentiment, portfolio, backtesting, enterprise |
| Production Readiness (PRD-101 to PRD-105) | 5 | Logging, resilience, observability, Docker, CI/CD |
| Operational Excellence (PRD-106 to PRD-110) | 5 | API errors, lifecycle, integration testing, audit trail, migration safety |
| Platform Infrastructure (PRD-111 to PRD-120) | 10 | Config management, data pipeline, model registry, alerting, API gateway, disaster recovery, profiling, archival, WebSocket scaling, deployment |
| Production Hardening (PRD-121 to PRD-130) | 10 | Event bus, multi-tenancy, feature store, secrets vault, billing, reconciliation, workflow, anomaly detection, data contracts, capacity planning |
| AI & Bot (PRD-131 to PRD-138) | 8 | Multi-agent AI, multi-model providers, navigation, EMA signals, trade executor, options scalper, bot dashboard, bot backtesting |
| Broker Expansion (PRD-139 to PRD-161) | 23 | 8 broker integrations, social analytics, signal fusion, strategy optimization, risk v2, portfolio intelligence, market microstructure, execution analytics, multi-agent consensus, regime-adaptive strategy, trade attribution, social backtester |
| Platform Enhancement (PRD-162 to PRD-171) | 10 | Signal persistence, unified risk, strategy selector, signal feedback, enhanced backtesting, integration tests, bot pipeline robustness, bot lifecycle hardening |

## License

Proprietary. All rights reserved.
