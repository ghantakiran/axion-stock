**Purpose**: Explain concepts, code, or systems at any depth level. Use for teaching/learning (vs /document for creating persistent docs, vs /analyze for finding issues).

---

## Command Execution
Execute: immediate. --plan→show plan first
Purpose: "[Action][Subject] in $ARGUMENTS"

Explain $ARGUMENTS at the requested depth level.

@include shared/flag-inheritance.yml#Universal_Always

Examples:
- `/explain --depth beginner "EMA cloud signals"` - Beginner explanation of Axion signals
- `/explain --depth advanced "bot pipeline orchestration"` - Deep dive into bot architecture
- `/explain --visual "signal→order flow"` - Visual diagram of data flow

## Flags
--depth: "beginner|intermediate|advanced|expert"
--style: "tutorial|reference|conversational|academic"
--visual: "Include diagrams (ASCII/Mermaid), flowcharts, sequence diagrams"

## Axion Explanation Topics
When explaining Axion-specific concepts, reference actual source:
- **Signal flow**: `src/ema_signals/` → `src/signal_fusion/` → `src/trade_executor/`
- **Bot pipeline**: `src/bot_pipeline/orchestrator.py` — 9 stages, thread-safe
- **Broker integration**: `src/multi_broker/` routes to 8 individual broker modules
- **Strategy selection**: `src/strategy_selector/` ADX-gated routing
- **Agent system**: `src/agents/` — 10 specialized agents + keyword router
