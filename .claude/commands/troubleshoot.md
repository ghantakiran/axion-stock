**Purpose**: Debug and resolve issues using root cause analysis. Use when diagnosing bugs, performance problems, or test failures.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Debug and resolve $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/troubleshoot "test_bot_pipeline fails on CI"` - Debug test failure
- `/troubleshoot --performance "slow API response"` - Performance diagnosis
- `/troubleshoot --bisect "migration broke after commit"` - Git bisect to find cause

## Flags
--performance: "Focus on performance bottlenecks"
--memory: "Memory leak detection and analysis"
--network: "Network/API debugging"
--trace: "Detailed execution tracing"
--bisect: "Use git bisect to find breaking commit"

## Approach
1. **Reproduce**: Isolate minimal reproduction, capture error + stack trace
2. **Gather evidence**: Logs, recent changes (`git log`), system state
3. **Hypothesize**: Most likely causes, test predictions
4. **Verify**: Change one variable at a time, confirm root cause
5. **Fix & prevent**: Implement fix, add regression test

## Axion-Specific Issues
- **`python` vs `python3`**: Broken symlink on macOS — always use `python3`
- **ORM metadata reserved**: Use `extra_metadata = Column("metadata", Text, ...)`
- **Mock patch targets**: `from src.x import y` → patch `importing_module.y`, not `src.x.y`
- **Time-dependent tests**: Use `timeframe="1d"` / `trade_type="swing"` instead of mocking datetime
- **Dict vs object**: `getattr(dict, "key")` silently returns default — use `isinstance` check
- **WeightAdjuster clamp**: `max_weight` causes normalization equalization — use `max_weight=1.0` in tests
- **Flaky test**: `test_day_rollover_auto_resets` — known pre-existing issue in PersistentStateManager
