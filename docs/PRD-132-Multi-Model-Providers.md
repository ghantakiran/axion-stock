# PRD-132: Multi-Model AI Provider System

## Overview
Extends the multi-agent system (PRD-131) with a unified interface to multiple LLM backends: Claude, OpenAI GPT, Google Gemini, DeepSeek, and local models via Ollama (Llama, Mistral, Qwen). Includes tool-calling normalization across providers, fallback chains, cost estimation, and a configuration dashboard.

## Supported Providers & Models

| Provider | Models | Tool Calling | API Style |
|----------|--------|-------------|-----------|
| **Anthropic** | Claude Opus 4.6, Sonnet 4.5, Sonnet 4, Haiku 4.5 | Native | Anthropic SDK |
| **OpenAI** | GPT-4o, GPT-4o Mini, o3-mini | Native | OpenAI SDK |
| **Google** | Gemini 2.0 Flash, Gemini 1.5 Pro | Native | google-generativeai |
| **DeepSeek** | V3 (Chat), R1 (Reasoner) | V3 only | OpenAI-compatible |
| **Ollama** | Llama 3.3, Mistral, Qwen 2.5 | Via OpenAI compat | OpenAI-compatible (local) |

## Architecture

### Provider Abstraction
```
BaseProvider (ABC)
├── AnthropicProvider   — native format (platform default)
├── OpenAIProvider      — converts tools to function calling format
│   ├── DeepSeekProvider  — inherits with different base_url
│   └── OllamaProvider    — inherits with local endpoint
└── GeminiProvider      — converts to function_declarations
```

### Components
- **`src/model_providers/config.py`** — `ProviderType`, `ModelTier`, `ModelInfo`, `ProviderConfig`, `ProviderResponse`, `ToolCall` + `MODEL_CATALOG` (15 models)
- **`src/model_providers/base.py`** — `BaseProvider` ABC with `chat()` and `build_tool_result_messages()`
- **`src/model_providers/anthropic_provider.py`** — Claude (native pass-through)
- **`src/model_providers/openai_provider.py`** — OpenAI with full message + tool format conversion
- **`src/model_providers/gemini_provider.py`** — Gemini with function declaration conversion
- **`src/model_providers/deepseek_provider.py`** — Inherits OpenAI, sets DeepSeek endpoint
- **`src/model_providers/ollama_provider.py`** — Inherits OpenAI, sets local Ollama endpoint
- **`src/model_providers/registry.py`** — `ProviderRegistry` for config management + caching
- **`src/model_providers/router.py`** — `ModelRouter` with fallback chains + cost estimation

### Agent Integration
- `AgentConfig.preferred_model` — optional model override per agent
- `AgentEngine` — dual-mode: direct Anthropic (backward-compatible) or provider-based

### Database Tables
- `model_provider_configs` — Stored provider configs per user
- `model_usage_log` — Token usage, cost tracking, latency metrics

### Dashboard
- `app/pages/model_providers.py` — 4-tab UI: Provider Setup, Model Catalog, Fallback Chains, Usage & Costs

## Key Design Decisions
1. **Lazy SDK imports** — Each provider guards its import; system works with any single SDK
2. **OpenAI-compatible inheritance** — DeepSeek and Ollama inherit from OpenAIProvider
3. **Backward-compatible** — No provider registry = direct Anthropic (existing behavior)
4. **Tool format normalization** — All providers receive Anthropic-format tools; conversion happens internally
5. **Fallback chains** — Pre-built chains (Flagship, Fast, Local) + custom chains

## Migration
- Revision: `132`, down_revision: `131`
- Creates 2 tables: `model_provider_configs`, `model_usage_log`

## Testing
- `tests/test_model_providers.py` — ~80 tests covering config, providers, registry, router
- Run: `python3 -m pytest tests/test_model_providers.py -v`
