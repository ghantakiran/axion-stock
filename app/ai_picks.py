"""AI-driven stock selection with detailed investment thesis - Rallies.ai style."""

import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Stock pick categories
PICK_CATEGORIES = {
    "growth_champions": {
        "name": "Growth Champions",
        "description": "High-growth companies with strong momentum",
        "filter": lambda s: (s["growth"] > 0.7) & (s["momentum"] > 0.5),
        "sort_by": "growth",
    },
    "value_gems": {
        "name": "Value Gems",
        "description": "Undervalued quality companies",
        "filter": lambda s: (s["value"] > 0.7) & (s["quality"] > 0.5),
        "sort_by": "value",
    },
    "momentum_leaders": {
        "name": "Momentum Leaders",
        "description": "Stocks with strong price momentum",
        "filter": lambda s: s["momentum"] > 0.75,
        "sort_by": "momentum",
    },
    "quality_compounders": {
        "name": "Quality Compounders",
        "description": "High-quality businesses with sustainable growth",
        "filter": lambda s: (s["quality"] > 0.7) & (s["growth"] > 0.4),
        "sort_by": "quality",
    },
    "balanced_picks": {
        "name": "Balanced Picks",
        "description": "Well-rounded stocks excelling across all factors",
        "filter": lambda s: s["composite"] > 0.7,
        "sort_by": "composite",
    },
}


def generate_ai_thesis(ticker: str, scores: dict, fundamentals: dict, api_key: str = None) -> dict:
    """Generate AI investment thesis for a stock using Claude."""

    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return _generate_rule_based_thesis(ticker, scores, fundamentals)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Analyze this stock and provide a concise investment thesis.

Stock: {ticker}

Factor Scores (percentile rank vs S&P 500, 0-1 scale):
- Value Score: {scores['value']:.2f} (higher = more undervalued)
- Momentum Score: {scores['momentum']:.2f} (higher = stronger price momentum)
- Quality Score: {scores['quality']:.2f} (higher = better fundamentals)
- Growth Score: {scores['growth']:.2f} (higher = faster growth)
- Composite Score: {scores['composite']:.2f} (weighted average)

Fundamentals:
- Price: ${fundamentals.get('currentPrice', 'N/A')}
- P/E Ratio: {fundamentals.get('trailingPE', 'N/A')}
- Market Cap: ${fundamentals.get('marketCap', 0) / 1e9:.1f}B
- ROE: {(fundamentals.get('returnOnEquity', 0) or 0) * 100:.1f}%
- Revenue Growth: {(fundamentals.get('revenueGrowth', 0) or 0) * 100:.1f}%

Provide a response in this exact JSON format:
{{
    "thesis": "2-3 sentence investment thesis explaining why this stock is attractive",
    "bull_case": "Key reason to be bullish",
    "bear_case": "Key risk to monitor",
    "conviction": "high/medium/low based on factor alignment",
    "investment_style": "growth/value/momentum/quality/balanced"
}}

Be direct and specific. Reference the actual scores and metrics."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        text = response.content[0].text
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            result["ai_generated"] = True
            return result

    except Exception as e:
        pass

    return _generate_rule_based_thesis(ticker, scores, fundamentals)


def _generate_rule_based_thesis(ticker: str, scores: dict, fundamentals: dict) -> dict:
    """Generate thesis using rule-based logic when AI is unavailable."""

    # Determine primary strength
    factors = {
        "value": scores["value"],
        "momentum": scores["momentum"],
        "quality": scores["quality"],
        "growth": scores["growth"],
    }
    primary = max(factors, key=factors.get)
    primary_score = factors[primary]

    # Determine weakness
    secondary = min(factors, key=factors.get)
    secondary_score = factors[secondary]

    # Build thesis based on factor profile
    thesis_templates = {
        "value": f"{ticker} trades at an attractive valuation (value score: {scores['value']:.0%} percentile) with solid fundamentals, offering potential upside as the market recognizes its intrinsic worth.",
        "momentum": f"{ticker} shows strong price momentum ({scores['momentum']:.0%} percentile) driven by positive sentiment and technical strength, suggesting continued outperformance.",
        "quality": f"{ticker} is a high-quality business ({scores['quality']:.0%} percentile) with strong profitability and low leverage, positioned for sustainable long-term compounding.",
        "growth": f"{ticker} leads on growth metrics ({scores['growth']:.0%} percentile) with robust revenue and earnings expansion, making it attractive for growth-oriented investors.",
    }

    bull_templates = {
        "value": "Undervalued relative to peers with potential for multiple expansion",
        "momentum": "Strong technical setup with positive price trends intact",
        "quality": "Superior business fundamentals provide downside protection",
        "growth": "Accelerating growth could drive significant upside",
    }

    bear_templates = {
        "value": f"Low {secondary} score ({secondary_score:.0%}) may indicate underlying issues",
        "momentum": "Momentum can reverse quickly in market corrections",
        "quality": "Premium valuation leaves less margin for error",
        "growth": "High expectations already priced in; execution risk",
    }

    # Determine conviction
    if scores["composite"] > 0.8 and primary_score > 0.75:
        conviction = "high"
    elif scores["composite"] > 0.6:
        conviction = "medium"
    else:
        conviction = "low"

    return {
        "thesis": thesis_templates[primary],
        "bull_case": bull_templates[primary],
        "bear_case": bear_templates.get(secondary, f"Monitor {secondary} weakness ({secondary_score:.0%})"),
        "conviction": conviction,
        "investment_style": primary,
        "ai_generated": False,
    }


def get_ai_picks(scores_df, fundamentals_df, category: str = "balanced_picks",
                 num_picks: int = 5, api_key: str = None) -> dict:
    """Get AI-curated stock picks with investment thesis."""

    if category not in PICK_CATEGORIES:
        category = "balanced_picks"

    cat_config = PICK_CATEGORIES[category]

    # Apply filter
    mask = cat_config["filter"](scores_df)
    filtered = scores_df[mask]

    if len(filtered) == 0:
        filtered = scores_df.nlargest(num_picks, "composite")

    # Get top picks
    top = filtered.nlargest(num_picks, cat_config["sort_by"])

    picks = []
    for ticker in top.index:
        row = scores_df.loc[ticker]
        fund = fundamentals_df.loc[ticker] if ticker in fundamentals_df.index else {}

        scores = {
            "value": float(row["value"]),
            "momentum": float(row["momentum"]),
            "quality": float(row["quality"]),
            "growth": float(row["growth"]),
            "composite": float(row["composite"]),
        }

        fund_dict = fund.to_dict() if hasattr(fund, "to_dict") else {}

        # Generate AI thesis
        thesis_data = generate_ai_thesis(ticker, scores, fund_dict, api_key)

        picks.append({
            "ticker": ticker,
            "scores": scores,
            "price": fund_dict.get("currentPrice"),
            "pe_ratio": fund_dict.get("trailingPE"),
            "market_cap_B": round(fund_dict.get("marketCap", 0) / 1e9, 1) if fund_dict.get("marketCap") else None,
            "thesis": thesis_data["thesis"],
            "bull_case": thesis_data["bull_case"],
            "bear_case": thesis_data["bear_case"],
            "conviction": thesis_data["conviction"],
            "investment_style": thesis_data["investment_style"],
            "ai_generated": thesis_data.get("ai_generated", False),
        })

    return {
        "category": cat_config["name"],
        "category_description": cat_config["description"],
        "generated_at": datetime.now().isoformat(),
        "num_picks": len(picks),
        "picks": picks,
    }


def format_ai_picks_markdown(picks_data: dict) -> str:
    """Format AI picks as markdown for display."""

    lines = [
        f"## {picks_data['category']}",
        f"*{picks_data['category_description']}*",
        "",
    ]

    for i, pick in enumerate(picks_data["picks"], 1):
        conviction_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(pick["conviction"], "⚪")

        lines.extend([
            f"### {i}. {pick['ticker']} {conviction_emoji}",
            f"**Price:** ${pick['price']:.2f} | **P/E:** {pick['pe_ratio']:.1f}" if pick['price'] else "",
            "",
            f"**Investment Thesis:** {pick['thesis']}",
            "",
            f"- 📈 **Bull Case:** {pick['bull_case']}",
            f"- ⚠️ **Bear Case:** {pick['bear_case']}",
            "",
            f"**Factor Scores:** Value {pick['scores']['value']:.0%} | Momentum {pick['scores']['momentum']:.0%} | Quality {pick['scores']['quality']:.0%} | Growth {pick['scores']['growth']:.0%}",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)
