"""Portfolio construction: stock selection + allocation + share calculation."""

import numpy as np
import pandas as pd
from tabulate import tabulate

import config


def select_top_stocks(
    scores: pd.DataFrame, n: int = None, verbose: bool = False
) -> pd.DataFrame:
    """Select top N stocks by composite score, filtering to top percentile."""
    if n is None:
        n = config.TOP_N_STOCKS

    # Must be in top percentile
    threshold = scores["composite"].quantile(config.MIN_PERCENTILE)
    eligible = scores[scores["composite"] >= threshold].copy()

    if verbose:
        print(f"  Eligible (top {int((1-config.MIN_PERCENTILE)*100)}%): {len(eligible)} tickers")

    # Take top N
    top = eligible.nlargest(n, "composite")
    return top


def compute_allocations(
    top_scores: pd.DataFrame,
    fundamentals: pd.DataFrame,
    amount: float,
    verbose: bool = False,
) -> pd.DataFrame:
    """Compute score-weighted allocation and share quantities.

    Returns DataFrame with columns: ticker, score, weight, allocation, price, shares.
    """
    scores = top_scores["composite"]
    weights = scores / scores.sum()

    allocations = weights * amount

    # Get current prices
    prices = fundamentals.reindex(top_scores.index)["currentPrice"]

    # Floor shares to whole numbers
    shares = np.floor(allocations / prices.replace(0, np.nan)).fillna(0).astype(int)

    result = pd.DataFrame({
        "ticker": top_scores.index,
        "score": scores.values,
        "weight": weights.values,
        "allocation": allocations.values,
        "price": prices.values,
        "shares": shares.values,
    })

    result["invested"] = result["shares"] * result["price"]
    result = result.sort_values("score", ascending=False).reset_index(drop=True)

    if verbose:
        total_invested = result["invested"].sum()
        print(f"  Total invested: ${total_invested:,.2f} / ${amount:,.2f}")
        print(f"  Cash remaining: ${amount - total_invested:,.2f}")

    return result


def format_portfolio_table(portfolio: pd.DataFrame, amount: float) -> str:
    """Format portfolio as ASCII table."""
    display = portfolio[["ticker", "score", "weight", "price", "shares", "invested"]].copy()
    display["weight"] = (display["weight"] * 100).round(1).astype(str) + "%"
    display["price"] = display["price"].apply(lambda x: f"${x:,.2f}")
    display["invested"] = display["invested"].apply(lambda x: f"${x:,.2f}")
    display["score"] = display["score"].round(3)

    display.columns = ["Ticker", "Score", "Weight", "Price", "Shares", "Invested"]

    table = tabulate(display, headers="keys", tablefmt="simple", showindex=False)

    total_invested = portfolio["invested"].sum()
    cash = amount - total_invested

    summary = (
        f"\n{'─' * 60}\n"
        f"Portfolio Amount:  ${amount:,.2f}\n"
        f"Total Invested:   ${total_invested:,.2f}\n"
        f"Cash Remaining:   ${cash:,.2f}\n"
        f"Positions:        {len(portfolio)}\n"
        f"{'─' * 60}"
    )

    return table + summary
