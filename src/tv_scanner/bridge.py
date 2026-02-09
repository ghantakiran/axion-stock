"""TradingView Scanner bridge — adapters for cross-module integration.

Converts TVScanReport results into formats consumed by:
  - src/scanner/  (ScannerEngine)
  - src/screener/ (ScreenerEngine)
  - src/ema_signals/ (UniverseScanner)
"""

from src.tv_scanner.models import TVScanReport


class TVDataBridge:
    """Adapter to convert TV scan results for other Axion modules."""

    @staticmethod
    def to_scanner_format(report: TVScanReport) -> dict[str, dict]:
        """Convert TVScanReport → dict compatible with src/scanner/ScannerEngine.

        Returns {symbol: {field: value, ...}} matching ScannerEngine's market_data.
        """
        out: dict[str, dict] = {}
        for r in report.results:
            out[r.symbol] = {
                "name": r.company_name or r.symbol,
                "price": r.price or 0.0,
                "change_pct": r.change_pct or 0.0,
                "volume": r.volume or 0,
                "relative_volume": r.relative_volume or 0.0,
                "rsi": r.rsi or 50.0,
                "market_cap": r.market_cap or 0.0,
                "sector": r.sector or "Unknown",
                "signal_strength": r.signal_strength,
            }
        return out

    @staticmethod
    def to_screener_format(report: TVScanReport) -> dict[str, dict]:
        """Convert TVScanReport → dict compatible with src/screener/ScreenerEngine.

        Returns {symbol: {field: value, ...}} matching ScreenerEngine's stock_data.
        """
        out: dict[str, dict] = {}
        for r in report.results:
            out[r.symbol] = {
                "symbol": r.symbol,
                "name": r.company_name or r.symbol,
                "price": r.price or 0.0,
                "change_pct": r.change_pct or 0.0,
                "volume": r.volume or 0,
                "market_cap": r.market_cap or 0.0,
                "pe_ratio": r.pe_ratio,
                "dividend_yield": r.dividend_yield,
                "rsi": r.rsi,
                "sma_20": r.sma_20,
                "sma_50": r.sma_50,
                "sma_200": r.sma_200,
                "sector": r.sector or "Unknown",
            }
        return out

    @staticmethod
    def to_ema_scan_list(report: TVScanReport) -> list[str]:
        """Extract ticker symbols for EMA UniverseScanner input.

        Returns a simple list of symbol strings.
        """
        return [r.symbol for r in report.results]
