# PRD-131: Multi-Agent AI System

## Overview
Introduces 10 specialized AI agents (6 investment style + 4 functional role) with unique personalities, tool preferences, and persistent memory. Users choose agents that match their trading philosophy.

## Architecture

### Agent Types
| # | Agent | Avatar | Category | Focus |
|---|-------|--------|----------|-------|
| 1 | Alpha Strategist | 🎯 | Investment Style | Balanced composite factor analysis (default) |
| 2 | Value Oracle | 🦉 | Investment Style | PE/PB/FCF, margin of safety, Buffett style |
| 3 | Growth Hunter | 🚀 | Investment Style | Revenue growth, TAM, disruption |
| 4 | Momentum Rider | ⚡ | Investment Style | Trend following, relative strength |
| 5 | Income Architect | 💰 | Investment Style | Dividends, yield, covered calls |
| 6 | Risk Sentinel | 🛡️ | Investment Style | VaR, drawdown, hedging |
| 7 | Research Analyst | 🔬 | Functional Role | Deep fundamental analysis |
| 8 | Portfolio Architect | 📐 | Functional Role | Allocation, diversification |
| 9 | Options Strategist | 🎲 | Functional Role | Greeks, IV, strategy selection |
| 10 | Market Scout | 🔭 | Functional Role | Screening, macro, sector rotation |

### Components
- **`src/agents/config.py`** — Enums (`AgentType`, `AgentCategory`) and dataclasses (`AgentConfig`, `ToolWeight`, `ResponseStyleConfig`)
- **`src/agents/registry.py`** — Registry of all 10 agents with system prompts and tool weights
- **`src/agents/engine.py`** — `AgentEngine` class: agentic tool-use loop with tool filtering
- **`src/agents/memory.py`** — `AgentMemory`: session/message storage (DB-optional, falls back to in-memory)
- **`src/agents/router.py`** — `AgentRouter`: keyword-based intent classification for agent suggestions

### Database Tables
- `agent_sessions` — Chat session metadata per agent
- `agent_messages` — Individual messages within sessions
- `agent_preferences` — User default agent and customizations

### App Integration
- **Sidebar agent selector** in main app (backward-compatible, default = no agent)
- **Agent Hub dashboard** at `app/pages/agents.py` with 4 tabs: Gallery, Sessions, Chat, Settings

## Key Design Decisions
1. **Agents are data configs, not classes** — Adding a new agent = adding a dict entry
2. **Tool filtering, not weighting** — Tools with weight=0.0 excluded; hints in system prompt
3. **Backward-compatible** — Existing `get_chat_response()` untouched; agent system is additive
4. **DB-optional memory** — Falls back to in-memory dicts for Streamlit Cloud
5. **Router is suggestive** — Shows hints, doesn't auto-switch agents

## Migration
- Revision: `131`, down_revision: `130`
- Creates 3 tables: `agent_sessions`, `agent_messages`, `agent_preferences`

## Testing
- `tests/test_agents.py` — ~80 tests covering enums, configs, registry, engine, memory, router
- Run: `python3 -m pytest tests/test_agents.py -v`
