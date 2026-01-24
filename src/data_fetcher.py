"""Download price and fundamental data with caching and rate limiting."""

import os
import time
import pickle
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf
from tqdm import tqdm

import config


def _cache_path(name: str) -> str:
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    return os.path.join(config.CACHE_DIR, f"{name}.pkl")


def _cache_valid(path: str) -> bool:
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mtime < timedelta(hours=config.CACHE_EXPIRY_HOURS)


def _load_cache(path: str):
    with open(path, "rb") as f:
        return pickle.load(f)


def _save_cache(path: str, data):
    with open(path, "wb") as f:
        pickle.dump(data, f)


def download_price_data(
    tickers: list[str], use_cache: bool = True, verbose: bool = False
) -> pd.DataFrame:
    """Download adjusted close prices for all tickers in batches.

    Returns DataFrame with dates as index, tickers as columns.
    """
    cache_file = _cache_path("prices")
    if use_cache and _cache_valid(cache_file):
        if verbose:
            print("  Loading cached price data...")
        return _load_cache(cache_file)

    end = datetime.now()
    start = end - timedelta(days=config.PRICE_HISTORY_MONTHS * 30)

    all_data = pd.DataFrame()
    batches = [
        tickers[i : i + config.BATCH_SIZE]
        for i in range(0, len(tickers), config.BATCH_SIZE)
    ]

    if verbose:
        print(f"  Downloading prices in {len(batches)} batches...")

    for batch in tqdm(batches, desc="Price batches", disable=not verbose):
        try:
            df = yf.download(
                batch,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                auto_adjust=True,
                progress=False,
            )
            if isinstance(df.columns, pd.MultiIndex):
                closes = df["Close"]
            else:
                closes = df[["Close"]]
                closes.columns = batch[:1]

            all_data = pd.concat([all_data, closes], axis=1)
        except Exception as e:
            if verbose:
                print(f"    Batch failed: {e}")

        time.sleep(config.BATCH_SLEEP)

    all_data = all_data.loc[:, ~all_data.columns.duplicated()]
    _save_cache(cache_file, all_data)
    return all_data


def download_fundamentals(
    tickers: list[str], use_cache: bool = True, verbose: bool = False
) -> pd.DataFrame:
    """Download fundamental data for each ticker individually.

    Returns DataFrame with tickers as index, fundamental fields as columns.
    """
    cache_file = _cache_path("fundamentals")
    if use_cache and _cache_valid(cache_file):
        if verbose:
            print("  Loading cached fundamentals...")
        return _load_cache(cache_file)

    fields = [
        "trailingPE", "priceToBook", "dividendYield",
        "enterpriseToEbitda", "returnOnEquity", "debtToEquity",
        "revenueGrowth", "earningsGrowth", "marketCap",
        "currentPrice",
    ]

    records = []
    for ticker in tqdm(tickers, desc="Fundamentals", disable=not verbose):
        info = _fetch_ticker_info(ticker)
        row = {"ticker": ticker}
        for field in fields:
            val = info.get(field)
            if field == "debtToEquity" and val is not None:
                val = val / 100.0  # Yahoo returns percentage
            row[field] = val
        records.append(row)
        time.sleep(config.FUNDAMENTAL_SLEEP)

    df = pd.DataFrame(records).set_index("ticker")
    _save_cache(cache_file, df)
    return df


def _fetch_ticker_info(ticker: str) -> dict:
    """Fetch .info dict for a single ticker with error handling."""
    try:
        t = yf.Ticker(ticker)
        return t.info or {}
    except Exception:
        return {}


def compute_price_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute 6-month and 12-month momentum returns, skipping the last month.

    Returns DataFrame with tickers as index, columns: ret_6m, ret_12m.
    """
    if prices.empty:
        return pd.DataFrame(columns=["ret_6m", "ret_12m"])

    # Skip last ~21 trading days (1 month) to avoid short-term reversal
    prices_ex_last = prices.iloc[:-21] if len(prices) > 21 else prices

    results = {}
    for col in prices_ex_last.columns:
        series = prices_ex_last[col].dropna()
        if len(series) < 22:
            results[col] = {"ret_6m": np.nan, "ret_12m": np.nan}
            continue

        current = series.iloc[-1]
        # 6-month return (~126 trading days)
        idx_6m = max(0, len(series) - 126)
        ret_6m = (current / series.iloc[idx_6m] - 1) if series.iloc[idx_6m] > 0 else np.nan

        # 12-month return (~252 trading days)
        idx_12m = max(0, len(series) - 252)
        ret_12m = (current / series.iloc[idx_12m] - 1) if series.iloc[idx_12m] > 0 else np.nan

        results[col] = {"ret_6m": ret_6m, "ret_12m": ret_12m}

    return pd.DataFrame(results).T


def filter_universe(
    fundamentals: pd.DataFrame, prices: pd.DataFrame, verbose: bool = False
) -> list[str]:
    """Filter tickers by minimum price and market cap."""
    valid = set(fundamentals.index)

    # Price filter
    if not prices.empty:
        last_prices = prices.iloc[-1]
        price_ok = set(last_prices[last_prices >= config.MIN_PRICE].index)
        valid &= price_ok

    # Market cap filter
    cap_ok = set(
        fundamentals[
            fundamentals["marketCap"].fillna(0) >= config.MIN_MARKET_CAP
        ].index
    )
    valid &= cap_ok

    filtered = sorted(valid)
    if verbose:
        print(f"  After filters: {len(filtered)} tickers (from {len(fundamentals)})")
    return filtered
