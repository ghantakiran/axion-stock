# PRD-58: AI Trading Copilot

## Overview

Claude-powered intelligent trading assistant that provides personalized trade ideas,
research summaries, strategy recommendations, and natural language portfolio analysis.
The copilot understands market context, user preferences, and portfolio state to deliver
actionable insights through conversational interaction.

## Components

### 1. Copilot Engine (`src/copilot/engine.py`)
- **Context Builder**: Aggregates portfolio, market, and user preference data
- **Prompt Templates**: Structured prompts for different analysis types
- **Response Parser**: Extracts structured data from AI responses
- **Conversation Manager**: Maintains chat history and context

### 2. Analysis Modules (`src/copilot/analysis.py`)
- **Trade Ideas**: Generate buy/sell recommendations with rationale
- **Research Summary**: Summarize news, earnings, and filings for a symbol
- **Portfolio Review**: Analyze current holdings and suggest improvements
- **Risk Assessment**: Identify portfolio risks and hedging opportunities
- **Market Commentary**: Daily/weekly market outlook and themes

### 3. Action Executor (`src/copilot/actions.py`)
- **Quick Trade**: Execute trades directly from copilot suggestions
- **Watchlist Add**: Add suggested symbols to watchlists
- **Alert Creation**: Set up alerts based on copilot insights
- **Research Save**: Save analysis to research notes

### 4. Personalization (`src/copilot/preferences.py`)
- **Risk Tolerance**: Conservative, moderate, aggressive profiles
- **Investment Style**: Value, growth, momentum, income preferences
- **Sector Focus**: Preferred sectors and exclusions
- **Communication Style**: Concise vs detailed responses

## Data Models

### CopilotSession
- `session_id`: Unique session identifier
- `user_id`: Owner of the session
- `started_at`: Session start time
- `messages`: List of conversation messages
- `context`: Current analysis context

### CopilotMessage
- `message_id`: Unique message ID
- `role`: user, assistant, system
- `content`: Message text
- `metadata`: Extracted entities, actions
- `timestamp`: Message time

### TradeIdea
- `symbol`: Stock symbol
- `action`: buy, sell, hold
- `confidence`: AI confidence score (0-1)
- `rationale`: Explanation text
- `target_price`: Optional price target
- `stop_loss`: Optional stop loss level
- `time_horizon`: short, medium, long term

### CopilotPreferences
- `risk_tolerance`: Risk profile
- `investment_style`: Style preferences
- `preferred_sectors`: Sector list
- `excluded_sectors`: Exclusion list
- `response_style`: Communication preference

## Database Tables

### copilot_sessions
- Session tracking and metadata

### copilot_messages
- Conversation history with context

### copilot_preferences
- User personalization settings

### copilot_saved_ideas
- Saved trade ideas for tracking

## API Endpoints

### Chat Interface
- `POST /api/copilot/chat` - Send message, get response
- `GET /api/copilot/sessions` - List user sessions
- `GET /api/copilot/session/{id}` - Get session history
- `DELETE /api/copilot/session/{id}` - Delete session

### Analysis
- `POST /api/copilot/analyze/symbol` - Deep dive on a symbol
- `POST /api/copilot/analyze/portfolio` - Portfolio analysis
- `POST /api/copilot/ideas` - Generate trade ideas

### Actions
- `POST /api/copilot/execute` - Execute suggested action
- `POST /api/copilot/save-idea` - Save trade idea

## Dashboard

4-tab Streamlit page:
1. **Chat**: Conversational interface with Claude
2. **Trade Ideas**: AI-generated recommendations
3. **Portfolio Insights**: AI analysis of holdings
4. **Settings**: Personalization preferences

## Prompt Engineering

### System Prompt Template
```
You are an expert financial analyst and trading advisor. You have access to:
- User's current portfolio: {portfolio_summary}
- Market conditions: {market_context}
- User preferences: {preferences}

Provide actionable, specific advice. Always include:
- Clear rationale for recommendations
- Risk considerations
- Relevant price levels when applicable
```

### Analysis Types
- `TRADE_IDEA`: Generate buy/sell recommendation
- `SYMBOL_RESEARCH`: Deep dive on specific stock
- `PORTFOLIO_REVIEW`: Analyze and optimize portfolio
- `MARKET_OUTLOOK`: Broad market analysis
- `RISK_CHECK`: Identify and address risks

## Success Metrics

- Response latency: <3s for standard queries
- User satisfaction: >4.5/5 rating on responses
- Trade idea accuracy: >55% win rate on suggestions
- Engagement: >5 messages per session average
