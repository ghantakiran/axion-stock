**Purpose**: Complex feature management across sessions. Use for multi-step tasks that span conversation sessions with automatic breakdown and context preservation.

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Manage complex tasks in $ARGUMENTS.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/task:create "Implement PRD-180: New Trading Strategy"` - Create task with breakdown
- `/task:status` - Check all task progress
- `/task:resume task-id` - Resume work from last checkpoint
- `/task:complete task-id` - Mark done with summary

## Operations

**/task:create** [description]: Break down into subtasks, set milestones, initialize tracking
**/task:update** [task-id] [updates]: Update progress, modify requirements, add findings
**/task:status** [task-id]: Show progress, completed subtasks, blockers, remaining estimate
**/task:resume** [task-id]: Load context, continue from checkpoint, restore state
**/task:complete** [task-id]: Mark done, generate summary, archive artifacts

## Implementation
Uses Claude Code's **TaskCreate/TaskUpdate/TaskList/TaskGet** tools:
- Tasks persist across the session via the built-in task management system
- Each subtask gets `status: pending → in_progress → completed`
- Dependencies tracked via `blockedBy`/`blocks` relationships
- `activeForm` shows progress in status line (e.g., "Running tests")

## Axion Task Patterns
- **PRD implementation**: 5 subtasks (source, tests, dashboard, migration, docs)
- **Bug fix**: 3 subtasks (reproduce, fix, test)
- **Module enhancement**: analyze → plan → implement → test → review

@include shared/task-management-patterns.yml#Task_Management_Hierarchy
