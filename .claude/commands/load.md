**Purpose**: Load and analyze project context. Use at session start to understand codebase structure, or when switching focus to a new module.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Load project context for $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/load` - Load Axion platform overview
- `/load --focus api` - Focus on FastAPI routes and endpoints
- `/load --focus module src/bot_pipeline/` - Deep-dive specific module
- `/load --scope full` - Complete project analysis

## Flags
--scope: "minimal|standard|comprehensive|full"
--focus: "architecture|api|database|frontend|testing|module"
--format: "summary|detailed|structured"

## Axion Platform Structure
```
src/                    # ~137 modules, ~810 .py files
├── db/models.py        # ORM: 218 tables, ~5280 lines
├── api/routes/         # FastAPI endpoints
├── bot_pipeline/       # Trading bot orchestrator (PRD-170+)
├── ema_signals/        # EMA cloud signal engine
├── trade_executor/     # Signal→order pipeline
├── agents/             # Multi-agent AI system
├── model_providers/    # Multi-LLM provider
└── [130+ other modules]

tests/                  # 167 test files, 8,933 tests
app/pages/              # 156 Streamlit dashboards
alembic/versions/       # 176 chained migrations
docs/                   # 145 PRD documents
```

## Key Entry Points
- **API**: `src/api/app.py` → FastAPI app, mounts routes + WebSocket
- **Bot**: `src/bot_pipeline/orchestrator.py` → 9-stage trading pipeline
- **Dashboard**: `app/main.py` → Streamlit entry, `app/nav_config.py` → navigation
- **ORM**: `src/db/models.py` → all SQLAlchemy models
- **Config**: `.env` / `docker-compose.yml` / `alembic.ini`

## Progressive Loading Strategy
1. **Quick context**: Read MEMORY.md + CLAUDE.md (already loaded)
2. **Module focus**: Read `src/<module>/__init__.py` + its test file
3. **Cross-refs**: Check which modules import from target (`grep "from src.<module>"`)
4. **Full picture**: `src/db/models.py` for ORM, `app/nav_config.py` for dashboard registry

## Domain Map (179 PRDs)
- **Trading Bot**: ema_signals → trade_executor → options_scalper → bot_pipeline → bot_dashboard
- **Brokers**: alpaca_live, schwab, robinhood, coinbase, fidelity, ibkr, tastytrade, webull → multi_broker
- **Signals**: signal_fusion → signal_pipeline → signal_persistence → signal_feedback
- **Strategy**: strategy_optimizer → regime_adaptive → strategy_selector → qullamaggie
- **AI**: agents → model_providers → multi_agent_consensus
- **Infrastructure**: logging → resilience → observability → api_gateway → deployment
