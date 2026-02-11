**Purpose**: System architecture and API design. Use when designing new modules, APIs, or PRDs before implementation (vs /build for implementation, vs /analyze for reviewing existing design).

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Design system architecture and APIs for $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/design --api "bot control endpoints"` - Design REST API
- `/design --ddd "order execution domain"` - Domain model design
- `/design --prd "PRD-180: Feature Name"` - Create PRD document

## Flags
--api: "REST/WebSocket API design with OpenAPI spec"
--ddd: "Domain-driven design: entities, value objects, aggregates, services"
--prd: "Product Requirements Document following Axion PRD template"

## Axion API Patterns
- **Framework**: FastAPI with Pydantic models for request/response
- **Routes**: `src/api/routes/<module>.py`, mounted in `src/api/app.py`
- **WebSocket**: `src/api/routes/bot_ws.py` — channels: signals, orders, alerts, lifecycle, metrics
- **Auth**: Token-based, middleware in `src/api/`
- **Rate limiting**: Per-endpoint via API gateway (`src/api_gateway/`)

## Axion PRD Template
PRD-XX follows this structure in `docs/PRD-XX-<name>.md`:
1. **Overview**: Problem statement, goals, non-goals
2. **Architecture**: Module design, data flow, integration points
3. **Data Model**: Dataclasses (business logic) + ORM records (persistence)
4. **API**: Endpoints if applicable
5. **Dashboard**: Streamlit page layout (typically 4 tabs)
6. **Testing**: Test strategy, edge cases, expected test count

## Module Design Checklist
- ORM records → `src/db/models.py` (check tablename collisions)
- Migration → chain to latest in `alembic/versions/`
- Dashboard → register in `app/nav_config.py`
- Cross-module deps → use bridge adapter pattern (lazy-load)
- Config → environment variables via `.env`
