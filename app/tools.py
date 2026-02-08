"""Tool definitions and implementations for Claude API tool_use."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st

import config
from src.data_fetcher import (
    download_price_data,
    download_fundamentals,
    compute_price_returns,
    filter_universe,
)
from src.factor_model import compute_composite_scores
from src.portfolio import select_top_stocks, compute_allocations
from src.universe import build_universe


# Tool schemas for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "get_stock_quote",
        "description": "Get the current stock quote including price, change, volume, market cap, and key stats for a given ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., AAPL, MSFT, GOOGL)"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "analyze_stock",
        "description": "Analyze a stock using the multi-factor model (value, momentum, quality, growth). Returns factor scores and percentile rankings vs S&P 500.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol to analyze"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "compare_stocks",
        "description": "Compare multiple stocks side-by-side on factor scores, price, and key metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols to compare (2-5 tickers)"
                }
            },
            "required": ["tickers"]
        }
    },
    {
        "name": "screen_stocks",
        "description": "Screen S&P 500 stocks by factor criteria. Returns top stocks matching the specified factor preferences.",
        "input_schema": {
            "type": "object",
            "properties": {
                "factor": {
                    "type": "string",
                    "enum": ["value", "momentum", "quality", "growth", "composite"],
                    "description": "Factor to screen by"
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top stocks to return (default 10)",
                    "default": 10
                }
            },
            "required": ["factor"]
        }
    },
    {
        "name": "recommend_portfolio",
        "description": "Generate a recommended portfolio with specific share allocations for a given investment amount. Uses the multi-factor model to select and weight stocks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Investment amount in USD"
                },
                "num_stocks": {
                    "type": "integer",
                    "description": "Number of stocks to include (default 9, max 15)",
                    "default": 9
                }
            },
            "required": ["amount"]
        }
    },
    {
        "name": "get_market_overview",
        "description": "Get a market overview including major index performance, sector leaders/laggards, and market breadth.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "analyze_options",
        "description": "Get options chain data for a stock including available expiration dates, calls and puts near the money, implied volatility, open interest, and volume. Useful for options trading analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "expiry_index": {
                    "type": "integer",
                    "description": "Index of expiration date to use (0=nearest, 1=next, etc). Default 0.",
                    "default": 0
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "recommend_options",
        "description": "Recommend option strategies for a stock based on its factor scores, implied volatility, and directional outlook. Suggests strategies like covered calls, bull call spreads, cash-secured puts, or iron condors with specific strikes and expiries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "outlook": {
                    "type": "string",
                    "enum": ["bullish", "bearish", "neutral", "auto"],
                    "description": "Market outlook. Use 'auto' to determine from factor scores.",
                    "default": "auto"
                },
                "risk_tolerance": {
                    "type": "string",
                    "enum": ["conservative", "moderate", "aggressive"],
                    "description": "Risk tolerance level",
                    "default": "moderate"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "recommend_top_picks",
        "description": "Get the top stock picks with detailed reasoning based on factor scores. Includes buy thesis, risk factors, and suggested entry strategy for each pick.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["overall", "momentum_plays", "value_traps_avoided", "quality_compounders", "growth_leaders"],
                    "description": "Category of picks to recommend",
                    "default": "overall"
                },
                "num_picks": {
                    "type": "integer",
                    "description": "Number of picks (default 5)",
                    "default": 5
                }
            },
            "required": []
        }
    },
]


@st.cache_data(ttl=3600, show_spinner="Loading market data...")
def _get_cached_scores():
    """Load or compute factor scores for the SP500 universe."""
    if "scores_cache" not in _get_cached_scores.__dict__:
        # Try new DataService backend
        try:
            from src.services.sync_adapter import sync_data_service
            tickers = sync_data_service.build_universe()
            prices = sync_data_service.download_price_data(tickers)
            fundamentals = sync_data_service.download_fundamentals(tickers)
        except Exception:
            # Fallback to original path
            tickers = build_universe()
            prices = download_price_data(tickers, use_cache=True)
            fundamentals = download_fundamentals(tickers, use_cache=True)

        # Restrict to universe
        fundamentals = fundamentals.loc[fundamentals.index.isin(tickers)]
        prices = prices[[c for c in prices.columns if c in tickers]]

        valid_tickers = filter_universe(fundamentals, prices)
        fundamentals = fundamentals.loc[fundamentals.index.isin(valid_tickers)]
        prices = prices[[c for c in prices.columns if c in valid_tickers]]

        returns = compute_price_returns(prices)
        scores = compute_composite_scores(fundamentals, returns)
        scores = scores.loc[scores.index.isin(valid_tickers)]

        _get_cached_scores.scores_cache = scores
        _get_cached_scores.fundamentals_cache = fundamentals
        _get_cached_scores.prices_cache = prices

    return (
        _get_cached_scores.scores_cache,
        _get_cached_scores.fundamentals_cache,
        _get_cached_scores.prices_cache,
    )


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return JSON string result."""
    try:
        if tool_name == "get_stock_quote":
            result = get_stock_quote(tool_input["ticker"])
        elif tool_name == "analyze_stock":
            result = analyze_stock(tool_input["ticker"])
        elif tool_name == "compare_stocks":
            result = compare_stocks(tool_input["tickers"])
        elif tool_name == "screen_stocks":
            result = screen_stocks(
                tool_input["factor"],
                tool_input.get("top_n", 10)
            )
        elif tool_name == "recommend_portfolio":
            result = recommend_portfolio(
                tool_input["amount"],
                tool_input.get("num_stocks", 9)
            )
        elif tool_name == "get_market_overview":
            result = get_market_overview()
        elif tool_name == "analyze_options":
            result = analyze_options(
                tool_input["ticker"],
                tool_input.get("expiry_index", 0)
            )
        elif tool_name == "recommend_options":
            result = recommend_options(
                tool_input["ticker"],
                tool_input.get("outlook", "auto"),
                tool_input.get("risk_tolerance", "moderate")
            )
        elif tool_name == "recommend_top_picks":
            result = recommend_top_picks(
                tool_input.get("category", "overall"),
                tool_input.get("num_picks", 5)
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result, default=str)


def get_stock_quote(ticker: str) -> dict:
    """Get current quote for a ticker."""
    ticker = ticker.upper().strip()
    t = yf.Ticker(ticker)
    info = t.info or {}

    return {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "change_percent": info.get("regularMarketChangePercent"),
        "volume": info.get("regularMarketVolume"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "dividend_yield": info.get("dividendYield"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


def analyze_stock(ticker: str) -> dict:
    """Analyze a stock with factor scores."""
    ticker = ticker.upper().strip()
    scores, fundamentals, _ = _get_cached_scores()

    if ticker not in scores.index:
        # Try fetching individually
        return {"error": f"{ticker} not found in S&P 500 universe. Try a different ticker."}

    row = scores.loc[ticker]
    fund = fundamentals.loc[ticker] if ticker in fundamentals.index else {}

    total = len(scores)
    composite_rank = int((scores["composite"] < row["composite"]).sum())

    return {
        "ticker": ticker,
        "composite_score": round(float(row["composite"]), 3),
        "composite_percentile": round(composite_rank / total * 100, 1),
        "factor_scores": {
            "value": round(float(row["value"]), 3),
            "momentum": round(float(row["momentum"]), 3),
            "quality": round(float(row["quality"]), 3),
            "growth": round(float(row["growth"]), 3),
        },
        "fundamentals": {
            "pe_ratio": _safe_round(fund.get("trailingPE")),
            "pb_ratio": _safe_round(fund.get("priceToBook")),
            "roe": _safe_round(fund.get("returnOnEquity")),
            "debt_to_equity": _safe_round(fund.get("debtToEquity")),
            "revenue_growth": _safe_round(fund.get("revenueGrowth")),
            "earnings_growth": _safe_round(fund.get("earningsGrowth")),
        },
        "universe_size": total,
        "overall_rank": total - composite_rank,
    }


def compare_stocks(tickers: list) -> dict:
    """Compare multiple stocks."""
    tickers = [t.upper().strip() for t in tickers[:5]]
    scores, fundamentals, _ = _get_cached_scores()

    comparisons = []
    for ticker in tickers:
        if ticker in scores.index:
            row = scores.loc[ticker]
            fund = fundamentals.loc[ticker] if ticker in fundamentals.index else {}
            comparisons.append({
                "ticker": ticker,
                "composite": round(float(row["composite"]), 3),
                "value": round(float(row["value"]), 3),
                "momentum": round(float(row["momentum"]), 3),
                "quality": round(float(row["quality"]), 3),
                "growth": round(float(row["growth"]), 3),
                "price": _safe_round(fund.get("currentPrice")),
                "pe_ratio": _safe_round(fund.get("trailingPE")),
                "market_cap_B": round(float(fund.get("marketCap", 0)) / 1e9, 1) if fund.get("marketCap") else None,
            })
        else:
            comparisons.append({"ticker": ticker, "error": "Not in S&P 500 universe"})

    return {"comparisons": comparisons}


def screen_stocks(factor: str, top_n: int = 10) -> dict:
    """Screen stocks by factor."""
    scores, fundamentals, _ = _get_cached_scores()

    if factor not in scores.columns:
        return {"error": f"Invalid factor: {factor}. Use: value, momentum, quality, growth, composite"}

    top = scores.nlargest(min(top_n, 30), factor)
    results = []
    for ticker, row in top.iterrows():
        fund = fundamentals.loc[ticker] if ticker in fundamentals.index else {}
        results.append({
            "ticker": ticker,
            "score": round(float(row[factor]), 3),
            "composite": round(float(row["composite"]), 3),
            "price": _safe_round(fund.get("currentPrice")),
            "sector": _get_sector(ticker),
        })

    return {"factor": factor, "top_stocks": results}


def recommend_portfolio(amount: float, num_stocks: int = 9) -> dict:
    """Generate portfolio recommendation."""
    scores, fundamentals, _ = _get_cached_scores()

    num_stocks = min(max(num_stocks, 3), 15)
    top_stocks = select_top_stocks(scores, n=num_stocks)
    portfolio = compute_allocations(top_stocks, fundamentals, amount)

    holdings = []
    for _, row in portfolio.iterrows():
        holdings.append({
            "ticker": row["ticker"],
            "score": round(float(row["score"]), 3),
            "weight": f"{row['weight']*100:.1f}%",
            "price": round(float(row["price"]), 2),
            "shares": int(row["shares"]),
            "invested": round(float(row["invested"]), 2),
        })

    total_invested = float(portfolio["invested"].sum())
    return {
        "amount": amount,
        "total_invested": round(total_invested, 2),
        "cash_remaining": round(amount - total_invested, 2),
        "positions": len(holdings),
        "holdings": holdings,
    }


def get_market_overview() -> dict:
    """Get market overview with index performance."""
    indices = {
        "SPY": "S&P 500",
        "QQQ": "Nasdaq 100",
        "DIA": "Dow Jones",
        "IWM": "Russell 2000",
    }

    overview = []
    for ticker, name in indices.items():
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            overview.append({
                "index": name,
                "ticker": ticker,
                "price": info.get("regularMarketPrice") or info.get("currentPrice"),
                "change_percent": info.get("regularMarketChangePercent"),
            })
        except Exception:
            overview.append({"index": name, "ticker": ticker, "error": "unavailable"})

    # Top/bottom from factor scores
    scores, _, _ = _get_cached_scores()
    top5 = scores.nlargest(5, "composite")
    bottom5 = scores.nsmallest(5, "composite")

    return {
        "indices": overview,
        "top_scored_stocks": [
            {"ticker": t, "composite": round(float(r["composite"]), 3)}
            for t, r in top5.iterrows()
        ],
        "bottom_scored_stocks": [
            {"ticker": t, "composite": round(float(r["composite"]), 3)}
            for t, r in bottom5.iterrows()
        ],
    }


def _safe_round(val, decimals=3):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return round(float(val), decimals)


def _get_sector(ticker: str) -> str:
    """Get sector from cached info or quick lookup."""
    try:
        t = yf.Ticker(ticker)
        return t.info.get("sector", "Unknown")
    except Exception:
        return "Unknown"


def analyze_options(ticker: str, expiry_index: int = 0) -> dict:
    """Get options chain data for a ticker."""
    ticker = ticker.upper().strip()
    t = yf.Ticker(ticker)

    # Get available expiration dates
    try:
        expirations = t.options
    except Exception:
        return {"error": f"No options data available for {ticker}"}

    if not expirations:
        return {"error": f"No options expirations found for {ticker}"}

    # Select expiration
    expiry_index = min(expiry_index, len(expirations) - 1)
    selected_expiry = expirations[expiry_index]

    # Get options chain
    chain = t.option_chain(selected_expiry)
    calls = chain.calls
    puts = chain.puts

    # Get current price
    info = t.info or {}
    current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)

    # Filter to near-the-money (within 10% of current price)
    if current_price and current_price > 0:
        low_strike = current_price * 0.90
        high_strike = current_price * 1.10
        calls_ntm = calls[(calls["strike"] >= low_strike) & (calls["strike"] <= high_strike)]
        puts_ntm = puts[(puts["strike"] >= low_strike) & (puts["strike"] <= high_strike)]
    else:
        calls_ntm = calls.head(10)
        puts_ntm = puts.head(10)

    def _format_options(df, max_rows=8):
        rows = []
        for _, row in df.head(max_rows).iterrows():
            rows.append({
                "strike": float(row["strike"]),
                "lastPrice": _safe_round(row.get("lastPrice")),
                "bid": _safe_round(row.get("bid")),
                "ask": _safe_round(row.get("ask")),
                "volume": int(row["volume"]) if pd.notna(row.get("volume")) else 0,
                "openInterest": int(row["openInterest"]) if pd.notna(row.get("openInterest")) else 0,
                "impliedVolatility": _safe_round(row.get("impliedVolatility")),
                "inTheMoney": bool(row.get("inTheMoney", False)),
            })
        return rows

    # Compute average IV
    avg_call_iv = float(calls_ntm["impliedVolatility"].mean()) if not calls_ntm.empty else None
    avg_put_iv = float(puts_ntm["impliedVolatility"].mean()) if not puts_ntm.empty else None

    return {
        "ticker": ticker,
        "current_price": current_price,
        "selected_expiry": selected_expiry,
        "all_expirations": list(expirations[:8]),
        "days_to_expiry": _days_to_expiry(selected_expiry),
        "avg_call_iv": _safe_round(avg_call_iv),
        "avg_put_iv": _safe_round(avg_put_iv),
        "calls_near_money": _format_options(calls_ntm),
        "puts_near_money": _format_options(puts_ntm),
        "total_call_volume": int(calls["volume"].sum()) if "volume" in calls.columns else 0,
        "total_put_volume": int(puts["volume"].sum()) if "volume" in puts.columns else 0,
        "put_call_ratio": round(
            float(puts["volume"].sum()) / max(float(calls["volume"].sum()), 1), 2
        ) if "volume" in calls.columns else None,
    }


def recommend_options(ticker: str, outlook: str = "auto", risk_tolerance: str = "moderate") -> dict:
    """Recommend option strategies based on factor scores and options data."""
    ticker = ticker.upper().strip()

    # Get factor scores for directional bias
    scores, fundamentals, _ = _get_cached_scores()
    factor_scores = None
    if ticker in scores.index:
        row = scores.loc[ticker]
        factor_scores = {
            "composite": float(row["composite"]),
            "value": float(row["value"]),
            "momentum": float(row["momentum"]),
            "quality": float(row["quality"]),
            "growth": float(row["growth"]),
        }

    # Determine outlook from scores if auto
    if outlook == "auto" and factor_scores:
        composite = factor_scores["composite"]
        momentum = factor_scores["momentum"]
        if composite > 0.7 and momentum > 0.6:
            outlook = "bullish"
        elif composite < 0.3 or momentum < 0.3:
            outlook = "bearish"
        else:
            outlook = "neutral"
    elif outlook == "auto":
        outlook = "neutral"

    # Get options data
    options_data = analyze_options(ticker, expiry_index=1)  # Use 2nd expiry for more time
    if "error" in options_data:
        return options_data

    current_price = options_data["current_price"]
    expiry = options_data["selected_expiry"]
    days = options_data.get("days_to_expiry", 30)
    avg_iv = options_data.get("avg_call_iv") or 0.3

    strategies = []

    if outlook == "bullish":
        if risk_tolerance == "conservative":
            # Cash-secured put (sell put below current price)
            put_strike = round(current_price * 0.95, 0)
            strategies.append({
                "strategy": "Cash-Secured Put",
                "description": f"Sell {expiry} ${put_strike} Put",
                "rationale": "Collect premium while willing to buy at discount. High-quality stock with strong momentum.",
                "max_profit": "Premium received",
                "max_loss": f"${put_strike} - premium (if stock goes to $0)",
                "breakeven": f"${put_strike} - premium",
                "capital_required": round(put_strike * 100, 2),
                "risk_level": "conservative",
            })
            # Covered call if you own shares
            call_strike = round(current_price * 1.05, 0)
            strategies.append({
                "strategy": "Covered Call",
                "description": f"Own 100 shares + Sell {expiry} ${call_strike} Call",
                "rationale": "Generate income on existing position. Cap upside at strike.",
                "max_profit": f"(${call_strike} - ${current_price:.0f}) x 100 + premium",
                "max_loss": "Stock goes to $0 minus premium received",
                "breakeven": f"${current_price:.0f} - premium",
                "risk_level": "conservative",
            })
        elif risk_tolerance == "moderate":
            # Bull call spread
            long_strike = round(current_price, 0)
            short_strike = round(current_price * 1.08, 0)
            strategies.append({
                "strategy": "Bull Call Spread",
                "description": f"Buy {expiry} ${long_strike} Call, Sell ${short_strike} Call",
                "rationale": "Defined-risk bullish bet. Factor scores support upside.",
                "max_profit": f"(${short_strike} - ${long_strike}) x 100 - net debit",
                "max_loss": "Net debit paid",
                "breakeven": f"${long_strike} + net debit",
                "risk_level": "moderate",
            })
        else:  # aggressive
            # Long call
            call_strike = round(current_price * 1.02, 0)
            strategies.append({
                "strategy": "Long Call",
                "description": f"Buy {expiry} ${call_strike} Call",
                "rationale": "High-conviction bullish bet. Strong momentum + growth scores.",
                "max_profit": "Unlimited",
                "max_loss": "Premium paid",
                "breakeven": f"${call_strike} + premium",
                "risk_level": "aggressive",
            })

    elif outlook == "bearish":
        if risk_tolerance == "conservative":
            # Protective put
            put_strike = round(current_price * 0.95, 0)
            strategies.append({
                "strategy": "Protective Put",
                "description": f"Buy {expiry} ${put_strike} Put (hedge existing long)",
                "rationale": "Protect downside on weak-scoring stock.",
                "max_profit": "Stock appreciation (capped at premium cost)",
                "max_loss": f"(${current_price:.0f} - ${put_strike}) + premium",
                "risk_level": "conservative",
            })
        elif risk_tolerance == "moderate":
            # Bear put spread
            long_strike = round(current_price, 0)
            short_strike = round(current_price * 0.92, 0)
            strategies.append({
                "strategy": "Bear Put Spread",
                "description": f"Buy {expiry} ${long_strike} Put, Sell ${short_strike} Put",
                "rationale": "Defined-risk bearish bet. Weak factor scores suggest downside.",
                "max_profit": f"(${long_strike} - ${short_strike}) x 100 - net debit",
                "max_loss": "Net debit paid",
                "breakeven": f"${long_strike} - net debit",
                "risk_level": "moderate",
            })
        else:
            # Long put
            put_strike = round(current_price * 0.98, 0)
            strategies.append({
                "strategy": "Long Put",
                "description": f"Buy {expiry} ${put_strike} Put",
                "rationale": "High-conviction bearish bet on weak fundamentals.",
                "max_profit": f"${put_strike} x 100 - premium",
                "max_loss": "Premium paid",
                "risk_level": "aggressive",
            })

    else:  # neutral
        if risk_tolerance in ("conservative", "moderate"):
            # Iron condor
            call_short = round(current_price * 1.06, 0)
            call_long = round(current_price * 1.10, 0)
            put_short = round(current_price * 0.94, 0)
            put_long = round(current_price * 0.90, 0)
            strategies.append({
                "strategy": "Iron Condor",
                "description": f"Sell ${put_short}/${call_short} strangle, Buy ${put_long}/${call_long} wings",
                "rationale": "Profit from time decay in range-bound stock. Neutral factor scores.",
                "max_profit": "Net premium received",
                "max_loss": "Wing width - premium received",
                "breakeven": f"${put_short} - premium to ${call_short} + premium",
                "expiry": expiry,
                "risk_level": "moderate",
            })
        else:
            # Short straddle (aggressive neutral)
            atm_strike = round(current_price, 0)
            strategies.append({
                "strategy": "Short Straddle",
                "description": f"Sell {expiry} ${atm_strike} Call + ${atm_strike} Put",
                "rationale": "Maximum premium collection. Betting on low volatility.",
                "max_profit": "Total premium received",
                "max_loss": "Unlimited",
                "breakeven": f"${atm_strike} +/- total premium",
                "risk_level": "aggressive",
            })

    # Add IV context
    iv_percentile = "high" if avg_iv > 0.4 else "moderate" if avg_iv > 0.25 else "low"

    return {
        "ticker": ticker,
        "current_price": round(current_price, 2),
        "outlook": outlook,
        "risk_tolerance": risk_tolerance,
        "expiry": expiry,
        "days_to_expiry": days,
        "implied_volatility": _safe_round(avg_iv),
        "iv_assessment": iv_percentile,
        "factor_scores": factor_scores,
        "strategies": strategies,
        "disclaimer": "Options involve significant risk. These are educational suggestions based on quantitative analysis, not financial advice.",
    }


def recommend_top_picks(category: str = "overall", num_picks: int = 5) -> dict:
    """Get top stock picks with detailed reasoning."""
    scores, fundamentals, _ = _get_cached_scores()
    num_picks = min(max(num_picks, 3), 10)

    if category == "overall":
        top = scores.nlargest(num_picks, "composite")
    elif category == "momentum_plays":
        # High momentum + decent composite
        eligible = scores[scores["composite"] > 0.5]
        top = eligible.nlargest(num_picks, "momentum")
    elif category == "value_traps_avoided":
        # High value + high quality (avoids value traps)
        eligible = scores[(scores["value"] > 0.6) & (scores["quality"] > 0.5)]
        top = eligible.nlargest(num_picks, "composite")
    elif category == "quality_compounders":
        # High quality + decent growth
        eligible = scores[(scores["quality"] > 0.6) & (scores["growth"] > 0.4)]
        top = eligible.nlargest(num_picks, "quality")
    elif category == "growth_leaders":
        eligible = scores[scores["growth"] > 0.7]
        top = eligible.nlargest(num_picks, "growth")
    else:
        top = scores.nlargest(num_picks, "composite")

    picks = []
    for ticker, row in top.iterrows():
        fund = fundamentals.loc[ticker] if ticker in fundamentals.index else {}

        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []
        for factor in ["value", "momentum", "quality", "growth"]:
            val = float(row[factor])
            if val > 0.75:
                strengths.append(f"{factor} ({val:.2f})")
            elif val < 0.35:
                weaknesses.append(f"{factor} ({val:.2f})")

        picks.append({
            "ticker": ticker,
            "composite_score": round(float(row["composite"]), 3),
            "rank": int((scores["composite"] >= row["composite"]).sum()),
            "factor_scores": {
                "value": round(float(row["value"]), 3),
                "momentum": round(float(row["momentum"]), 3),
                "quality": round(float(row["quality"]), 3),
                "growth": round(float(row["growth"]), 3),
            },
            "price": _safe_round(fund.get("currentPrice")),
            "pe_ratio": _safe_round(fund.get("trailingPE")),
            "market_cap_B": round(float(fund.get("marketCap", 0)) / 1e9, 1) if fund.get("marketCap") else None,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "sector": fund.get("sector", _get_sector(ticker)) if hasattr(fund, "get") else _get_sector(ticker),
        })

    return {
        "category": category,
        "num_picks": len(picks),
        "picks": picks,
        "methodology": "Multi-factor percentile ranking across S&P 500. Scores represent relative standing vs peers.",
    }


def _days_to_expiry(expiry_str: str) -> int:
    """Calculate days to expiry from date string."""
    from datetime import datetime
    try:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
        return max(0, (expiry_date - datetime.now()).days)
    except Exception:
        return 30
