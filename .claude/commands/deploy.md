**Purpose**: Safe application deployment with rollback. Use when deploying to staging/production or managing Docker services.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Deploy application to environment specified in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/deploy --env staging` - Deploy to staging
- `/deploy --env prod --plan` - Production deploy with plan review first
- `/deploy --rollback` - Revert to previous deployment
- `/deploy --docker` - Rebuild and restart Docker services

## Flags
--env: "Target environment: dev|staging|prod"
--rollback: "Revert to previous stable deployment"
--docker: "Docker-compose rebuild and restart"
--dry-run: "Preview deployment steps without executing"

## Axion Deployment

### Docker (primary)
```bash
# Full stack
docker-compose up -d --build

# Individual services
docker-compose up -d --build web        # FastAPI
docker-compose up -d --build streamlit  # Dashboard
docker-compose up -d --build bot        # Trading bot
```
7 services: web, streamlit, postgres, timescaledb, redis, bot, worker

### Pre-Deploy Checklist
1. `python3 -m pytest tests/ -x` — all tests pass
2. `alembic current` — migrations up to date
3. `alembic upgrade head --sql` — preview pending migrations
4. Check `.env` vs `.env.example` — no missing vars
5. `docker-compose config` — validate compose file

### Post-Deploy Verification
- `/health` endpoint → returns `"ok"` with DB/Redis/bot component status
- `/metrics` endpoint → Prometheus scrape working
- Bot healthcheck: `bot_state.json` file-based check

### Rollback
- Docker: `docker-compose down && git checkout <prev-tag> && docker-compose up -d --build`
- Migrations: `alembic downgrade -1` (per step, verify between each)
- Bot state: Restore `bot_state.json` from backup volume
