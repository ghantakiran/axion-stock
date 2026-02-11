**Purpose**: Remove dead code, unused artifacts, and stale dependencies. Use for maintenance tasks (vs /improve for refactoring, vs /analyze for read-only inspection).

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Clean up project files, dependencies, and artifacts in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/cleanup --code --dry-run` - Preview dead code removal
- `/cleanup --deps` - Find and remove unused dependencies
- `/cleanup --files` - Remove build artifacts and temp files
- `/cleanup --all --dry-run` - Full preview before cleanup

## Flags
--code: "Remove unused imports, dead code, stale comments, debug statements"
--files: "Remove build artifacts, cache dirs, .pyc files, __pycache__, .DS_Store"
--deps: "Audit requirements.txt for unused packages"
--git: "Clean merged branches, stale refs (REQUIRES CONFIRMATION for history rewrites)"
--cfg: "Remove deprecated config settings, unused env vars"
--all: "Comprehensive cleanup across all categories"
--dry-run: "Preview changes without modifying anything"

## Safety Rules
- **--dry-run first**: Always run `--dry-run` before `--all` or `--git`
- **Git history**: NEVER rewrite git history without explicit user confirmation
- **Branch deletion**: Only delete branches already merged to main
- **Deps**: Only remove from requirements.txt after verifying no imports exist

## Axion-Specific Artifacts
- **Python cache**: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`
- **Build**: `dist/`, `build/`, `*.egg-info/`
- **State files**: `bot_state.json` (bot pipeline state — preserve in production)
- **Coverage**: `.coverage`, `htmlcov/`
- **Logs**: `*.log`, but preserve `logs/` directory structure
- **Temp migrations**: Alembic auto-generated files that weren't committed
