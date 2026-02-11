**Purpose**: Generate documentation from code and systems. Use when creating API docs, README files, architecture docs, PRD documents, or user guides.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Generate documentation for $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/document --type api src/api/routes/` - Generate API documentation
- `/document --type architecture` - System architecture doc
- `/document --type prd "PRD-180: Feature"` - PRD document
- `/document --type readme` - Project README

## Flags
--type: "api|code|readme|architecture|user|prd"
--format: "markdown (default)|html"
--style: "concise|detailed|tutorial|reference"

## Axion Documentation Structure
- **PRDs**: `docs/PRD-XX-<name>.md` — 145 existing PRD documents
- **API docs**: Generated from FastAPI route decorators + Pydantic models
- **Architecture**: Module dependency graphs, domain maps (see /load for overview)
- **Code docs**: Python docstrings following Google style

## Doc Generation Patterns
- **API**: Read `src/api/routes/*.py`, extract endpoint signatures + Pydantic models
- **Module**: Read `src/<module>/__init__.py`, document public classes and functions
- **Architecture**: Reference MEMORY.md domain map + cross-module import graph
- **PRD**: Follow template in `/design --prd` (overview, architecture, data model, API, dashboard, testing)
