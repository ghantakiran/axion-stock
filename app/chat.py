"""Claude API integration with tool use for stock analysis chat."""

import anthropic
from app.tools import TOOL_DEFINITIONS, execute_tool

SYSTEM_PROMPT = """You are an AI stock market research assistant. You help users analyze stocks, \
build portfolios, trade options, and understand market trends using a quantitative multi-factor model.

Your capabilities:
- Analyze individual stocks with factor scores (value, momentum, quality, growth)
- Compare multiple stocks side-by-side
- Screen the S&P 500 by specific factors
- Recommend score-weighted portfolios for any investment amount
- Analyze options chains (calls/puts, IV, volume, open interest)
- Recommend option strategies (covered calls, spreads, iron condors, etc.)
- Provide curated stock picks with buy thesis and risk analysis
- Provide market overviews

Factor scoring methodology:
- Value: Low PE, PB, EV/EBITDA, high dividend yield (lower valuation = higher score)
- Momentum: 6-month and 12-month price returns, skipping last month
- Quality: High ROE, low debt-to-equity
- Growth: Revenue growth + earnings growth
- Composite: Weighted average (Value 25%, Momentum 30%, Quality 25%, Growth 20%)
- All scores are percentile-ranked [0,1] against the S&P 500 universe

Options strategy selection:
- Bullish + Conservative: Cash-secured puts, covered calls
- Bullish + Moderate: Bull call spreads
- Bullish + Aggressive: Long calls
- Bearish + Conservative: Protective puts
- Bearish + Moderate: Bear put spreads
- Neutral: Iron condors, short straddles
- High IV favors selling strategies, low IV favors buying strategies

Guidelines:
- Always use tools to get real data before answering stock-specific questions
- Present factor scores clearly, explain what they mean
- For options, always show the specific strikes, expiry, and risk/reward profile
- Be direct about limitations: scores are backward-looking, not predictions
- When recommending, remind users this is for educational purposes, not financial advice
- Format numbers clearly: prices with $, percentages with %, large numbers abbreviated
- If a stock isn't in the S&P 500 universe, say so and suggest alternatives
- For options questions, use both analyze_options and recommend_options to give complete answers
"""


def get_chat_response(messages: list, api_key: str) -> tuple[str, list, list]:
    """Send messages to Claude with tools and return the final response.

    Returns (assistant_text, updated_messages, tool_calls).
    tool_calls is a list of {"name": str, "input": dict} for chart rendering.
    """
    client = anthropic.Anthropic(api_key=api_key)

    current_messages = list(messages)
    tool_calls = []

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=current_messages,
        )

        if response.stop_reason == "tool_use":
            assistant_content = response.content
            current_messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_calls.append({"name": block.name, "input": block.input})
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            current_messages.append({"role": "user", "content": tool_results})

        else:
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            final_text = "\n".join(text_parts)
            return final_text, current_messages, tool_calls
