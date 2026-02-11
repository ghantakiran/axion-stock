**Purpose**: Development environment setup for Python/FastAPI/Streamlit projects. Use when initializing a new dev environment, configuring CI/CD, or setting up tooling.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Configure development environment for $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/dev-setup --tools` - Configure linters, formatters, pre-commit hooks
- `/dev-setup --ci github` - Setup GitHub Actions workflows
- `/dev-setup --docker` - Configure Docker environment

## Flags
--tools: "Linters (ruff/flake8), formatters (black/isort), type checkers (mypy), pre-commit hooks"
--ci: "CI/CD pipeline (github|gitlab|jenkins)"
--docker: "Docker + docker-compose configuration"
--full: "Complete environment: tools + ci + docker"

## Project Stack (Axion Platform)
- **Runtime**: Python 3.11+ | `python3` (not `python` — broken symlink on macOS)
- **API**: FastAPI + uvicorn | `fastapi>=0.110.0`, `uvicorn>=0.27.0`
- **Frontend**: Streamlit multi-tab dashboards (156 pages in `app/pages/`)
- **DB**: PostgreSQL + TimescaleDB, Redis | SQLAlchemy ORM (`src/db/models.py`)
- **Migrations**: Alembic (176 chained migrations in `alembic/versions/`)
- **Tests**: pytest class-based | Run: `python3 -m pytest tests/`
- **Deps**: `requirements.txt` (core), `requirements-optional.txt` (ML/broker SDKs)

## Setup Steps
1. Virtual env: `python3 -m venv venv && source venv/bin/activate`
2. Core deps: `pip install -r requirements.txt`
3. Optional deps: `pip install -r requirements-optional.txt`
4. DB: `docker-compose up -d postgres redis`
5. Migrations: `alembic upgrade head`
6. Verify: `python3 -m pytest tests/ -x --tb=short`

## Docker (docker-compose services)
7 services: `web` (FastAPI), `streamlit`, `postgres`, `timescaledb`, `redis`, `bot`, `worker`
Config: `.env.example` → `.env` | State volumes for bot persistence
