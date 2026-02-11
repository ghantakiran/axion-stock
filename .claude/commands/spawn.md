**Purpose**: Parallel specialized agents via Claude Code Task tool. Use when work can be parallelized across independent subtasks or requires focused research.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Spawn sub-agents for parallel/sequential task execution in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/spawn --parallel "Research OAuth patterns" "Build auth middleware"` - Two agents in parallel
- `/spawn --sequential "Analyze codebase" "Write migration" "Run tests"` - Chained tasks
- `/spawn --explore "Find all API endpoints"` - Fast codebase exploration

## Flags
--parallel: "Launch independent agents simultaneously via multiple Task tool calls"
--sequential: "Chain agents where each depends on prior output"
--explore: "Use Explore subagent for fast codebase search"
--research: "Use general-purpose subagent for deep research"
--background: "Run agent in background, check output later"

## Implementation (maps to Claude Code tools)
Spawn uses the **Task tool** with `subagent_type`:
- `Explore` — fast file/code search, codebase questions
- `general-purpose` — multi-step research, analysis, code search
- `Bash` — command execution, git operations
- `Plan` — architecture design, implementation planning

## Execution Modes

**Parallel**: Multiple Task tool calls in a single message. Use when tasks are independent.
```
Task 1: subagent_type=Explore, "Find all broker integrations"
Task 2: subagent_type=Explore, "Find all dashboard pages"
```

**Sequential**: One Task completes before next starts. Use when outputs feed forward.
```
Task 1: Research → returns findings
Task 2: Build (using findings from Task 1)
```

**Background**: `run_in_background=true`. Check progress via Read on output_file.

## Axion-Specific Patterns
- **PRD implementation**: Spawn Explore to map existing patterns, then Plan for design
- **Test parallelism**: Spawn Bash agents for independent test suites
- **Module analysis**: Spawn Explore agents per `src/<module>/` directory
