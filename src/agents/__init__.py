"""Multi-Agent AI System for specialized investment analysis.

Provides 10 specialized AI agents (6 investment style + 4 functional role),
each with unique personalities, tool preferences, and persistent memory.
"""

from src.agents.config import (
    AgentCategory,
    AgentType,
    ToolWeight,
    ResponseStyleConfig,
    AgentConfig,
)
from src.agents.registry import (
    AGENT_CONFIGS,
    get_agent,
    list_agents,
    get_agents_by_category,
    get_default_agent,
)
from src.agents.engine import AgentEngine
from src.agents.memory import AgentMemory
from src.agents.router import AgentRouter

__all__ = [
    "AgentCategory",
    "AgentType",
    "ToolWeight",
    "ResponseStyleConfig",
    "AgentConfig",
    "AGENT_CONFIGS",
    "get_agent",
    "list_agents",
    "get_agents_by_category",
    "get_default_agent",
    "AgentEngine",
    "AgentMemory",
    "AgentRouter",
]
