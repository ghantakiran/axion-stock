"""Fetch and build the investable universe of US equities and ETFs."""

import io
from urllib.request import Request, urlopen

import pandas as pd

_HEADERS = {"User-Agent": "Axion/1.0"}


def _fetch_html(url: str) -> str:
    """Fetch URL with proper User-Agent header."""
    req = Request(url, headers=_HEADERS)
    with urlopen(req) as resp:
        return resp.read().decode("utf-8")


# Curated equity ETFs covering major sectors/themes
EQUITY_ETFS = [
    "SPY", "QQQ", "IWM", "DIA", "VTI",
    "XLK", "XLF", "XLE", "XLV", "XLI",
    "XLC", "XLY", "XLP", "XLU", "XLRE",
    "SMH", "IBB", "IYT",
]


def fetch_sp500_tickers() -> list[str]:
    """Scrape S&P 500 constituents from Wikipedia."""
    html = _fetch_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    tables = pd.read_html(io.StringIO(html))
    df = tables[0]
    tickers = df["Symbol"].tolist()
    return [_fix_ticker(t) for t in tickers]


def fetch_sp400_tickers() -> list[str]:
    """Scrape S&P 400 (MidCap) constituents from Wikipedia."""
    html = _fetch_html("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")
    tables = pd.read_html(io.StringIO(html))
    df = tables[0]
    col = "Symbol" if "Symbol" in df.columns else df.columns[1]
    tickers = df[col].tolist()
    return [_fix_ticker(t) for t in tickers]


def get_etf_tickers() -> list[str]:
    """Return curated list of equity ETFs."""
    return list(EQUITY_ETFS)


def build_universe(verbose: bool = False) -> list[str]:
    """Build universe from S&P 500 constituents."""
    sp500 = fetch_sp500_tickers()
    if verbose:
        print(f"  SP500: {len(sp500)} tickers")

    unique = list(dict.fromkeys(sp500))  # deduplicate

    if verbose:
        print(f"  Total unique: {len(unique)} tickers")

    return unique


def _fix_ticker(ticker: str) -> str:
    """Fix ticker format for yfinance (e.g., BRK.B → BRK-B)."""
    return ticker.strip().replace(".", "-")
