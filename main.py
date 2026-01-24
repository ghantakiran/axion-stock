"""CLI entry point: python main.py --amount 10000"""

import argparse
import sys

from src.universe import build_universe
from src.data_fetcher import (
    download_price_data,
    download_fundamentals,
    compute_price_returns,
    filter_universe,
)
from src.factor_model import compute_composite_scores
from src.portfolio import select_top_stocks, compute_allocations, format_portfolio_table
from src.backtest import run_backtest, format_backtest_results


def main():
    parser = argparse.ArgumentParser(
        description="Axion - Factor-based stock recommendation system"
    )
    parser.add_argument(
        "--amount", type=float, required=True,
        help="Portfolio amount in USD"
    )
    parser.add_argument(
        "--top", type=int, default=None,
        help="Number of stocks to recommend (default: 9)"
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Force fresh data download (ignore cache)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed progress and factor scores"
    )
    parser.add_argument(
        "--backtest", action="store_true",
        help="Run historical backtest after recommendation"
    )
    args = parser.parse_args()

    use_cache = not args.no_cache

    print("=" * 60)
    print("AXION - STOCK RECOMMENDATION SYSTEM")
    print(f"Portfolio: ${args.amount:,.2f}")
    print("=" * 60)

    # Step 1: Build universe
    print("\n[1/5] Building universe...")
    tickers = build_universe(verbose=args.verbose)
    print(f"  Universe: {len(tickers)} tickers")

    # Step 2: Download data
    print("\n[2/5] Downloading price data...")
    prices = download_price_data(tickers, use_cache=use_cache, verbose=args.verbose)
    print(f"  Prices: {prices.shape[0]} days × {prices.shape[1]} tickers")

    print("\n[3/5] Downloading fundamentals...")
    fundamentals = download_fundamentals(tickers, use_cache=use_cache, verbose=args.verbose)
    print(f"  Fundamentals: {len(fundamentals)} tickers")

    # Restrict to universe tickers (cache may contain more)
    fundamentals = fundamentals.loc[fundamentals.index.isin(tickers)]
    prices = prices[[c for c in prices.columns if c in tickers]]

    # Step 3: Filter universe
    valid_tickers = filter_universe(fundamentals, prices, verbose=args.verbose)
    fundamentals = fundamentals.loc[fundamentals.index.isin(valid_tickers)]
    prices = prices[[c for c in prices.columns if c in valid_tickers]]

    # Step 4: Compute factor scores
    print("\n[4/5] Computing factor scores...")
    returns = compute_price_returns(prices)
    scores = compute_composite_scores(fundamentals, returns, verbose=args.verbose)

    # Filter scores to valid tickers only
    scores = scores.loc[scores.index.isin(valid_tickers)]

    if args.verbose:
        print("\n  Top 15 by composite score:")
        top15 = scores.nlargest(15, "composite")
        for ticker, row in top15.iterrows():
            print(f"    {ticker:6s}  V={row['value']:.2f}  M={row['momentum']:.2f}  "
                  f"Q={row['quality']:.2f}  G={row['growth']:.2f}  C={row['composite']:.3f}")

    # Step 5: Build portfolio
    print("\n[5/5] Constructing portfolio...")
    top_stocks = select_top_stocks(scores, n=args.top, verbose=args.verbose)
    portfolio = compute_allocations(
        top_stocks, fundamentals, args.amount, verbose=args.verbose
    )

    print("\n" + format_portfolio_table(portfolio, args.amount))

    # Optional backtest
    if args.backtest:
        print("\n\nRunning backtest...")
        results = run_backtest(prices, fundamentals, verbose=args.verbose)
        print(format_backtest_results(results))

    return portfolio


if __name__ == "__main__":
    main()
