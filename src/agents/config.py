"""Configuration types for the Multi-Agent AI System."""

import enum
from dataclasses import dataclass, field
from typing import Optional


class AgentCategory(enum.Enum):
    """Category of agent."""

    INVESTMENT_STYLE = "investment_style"
    FUNCTIONAL_ROLE = "functional_role"


class AgentType(enum.Enum):
    """Enumeration of all available agents."""

    # Investment Style Agents
    ALPHA_STRATEGIST = "alpha_strategist"
    VALUE_ORACLE = "value_oracle"
    GROWTH_HUNTER = "growth_hunter"
    MOMENTUM_RIDER = "momentum_rider"
    INCOME_ARCHITECT = "income_architect"
    RISK_SENTINEL = "risk_sentinel"

    # Functional Role Agents
    RESEARCH_ANALYST = "research_analyst"
    PORTFOLIO_ARCHITECT = "portfolio_architect"
    OPTIONS_STRATEGIST = "options_strategist"
    MARKET_SCOUT = "market_scout"


@dataclass
class ToolWeight:
    """Weight assigned to a tool for an agent.

    A weight of 0.0 means the tool is excluded from the agent's toolkit.
    Non-zero weights are used as priority hints in the system prompt.
    """

    tool_name: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        self.weight = max(0.0, min(1.0, self.weight))


@dataclass
class ResponseStyleConfig:
    """Controls the agent's response verbosity and tone."""

    verbosity: str = "balanced"  # concise, balanced, detailed
    data_density: str = "medium"  # low, medium, high
    tone: str = "professional"  # casual, professional, academic
    max_tokens: int = 4096


@dataclass
class AgentConfig:
    """Full configuration for an AI agent."""

    agent_type: AgentType
    name: str
    category: AgentCategory
    description: str
    avatar: str
    system_prompt: str
    tool_weights: list[ToolWeight] = field(default_factory=list)
    response_style: ResponseStyleConfig = field(default_factory=ResponseStyleConfig)
    welcome_message: str = ""
    example_queries: list[str] = field(default_factory=list)
    color: str = "#06b6d4"
    preferred_model: Optional[str] = None  # Model ID override (None = use default)

    @property
    def available_tool_names(self) -> list[str]:
        """Return tool names with non-zero weight."""
        return [tw.tool_name for tw in self.tool_weights if tw.weight > 0.0]

    @property
    def priority_tools(self) -> list[str]:
        """Return tool names sorted by weight descending."""
        sorted_weights = sorted(self.tool_weights, key=lambda tw: tw.weight, reverse=True)
        return [tw.tool_name for tw in sorted_weights if tw.weight > 0.0]

    @property
    def excluded_tools(self) -> list[str]:
        """Return tool names with zero weight."""
        return [tw.tool_name for tw in self.tool_weights if tw.weight == 0.0]
