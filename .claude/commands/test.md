**Purpose**: Run and create tests using pytest. Use for TDD, coverage reports, and running test suites.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Create or run tests for $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/test tests/test_bot_pipeline.py` - Run specific test file
- `/test --tdd "signal validation"` - TDD workflow
- `/test --coverage` - Generate coverage report
- `/test --integration` - Run integration tests

## Flags
--tdd: "Red→Green→Refactor cycle"
--coverage: "Generate coverage report with uncovered lines"
--integration: "Run integration/cross-module tests"
--e2e: "End-to-end tests"
--unit: "Unit tests only (default)"
--parallel: "Run in parallel workers"
--bail: "Stop on first failure"

## Axion Test Conventions
- **Runner**: `python3 -m pytest` (NOT `python -m pytest` — broken symlink)
- **Structure**: Class-based `class TestFeatureName:` in `tests/test_<module>.py`
- **Count**: 167 test files, 8,933 tests total
- **E2E**: `tests/test_bot_e2e.py` (41 tests), `tests/test_integration_pipeline.py` (25 tests)

## Common Commands
```bash
python3 -m pytest tests/test_<module>.py -v          # Single module
python3 -m pytest tests/ -x --tb=short               # All, stop on first fail
python3 -m pytest tests/ -k "TestClassName"           # By class name
python3 -m pytest tests/ --co -q                      # List tests without running
python3 -m pytest tests/ --cov=src --cov-report=html  # Coverage
```

## Mock Patterns
- **Module-level import** (`from src.x import Foo`): Patch `test_module.Foo`
- **Lazy import** (`import src.x` inside method): Patch `src.x.Foo` directly
- **Time-dependent**: Use `timeframe="1d"` to bypass market hours, `trade_type="swing"` for EOD
- **Dict vs object**: Use `_get_field()` helper that checks `isinstance(t, dict)` first
