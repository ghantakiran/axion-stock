"""TradingView Scanner engine — query builder, executor, and result converter.

Lazily imports tvscreener so the module works without the library installed
(for testing with mocks).
"""

import math
import time
from typing import Any, Iterator, Optional

from src.tv_scanner.config import AssetClass, TV_FIELD_MAP, TVScannerConfig
from src.tv_scanner.models import (
    TVFilterCriterion,
    TVPreset,
    TVScanReport,
    TVScanResult,
)
from src.tv_scanner.presets import PRESET_TV_SCANS


def _safe_float(val: Any) -> Optional[float]:
    """Convert a value to float, returning None for NaN/None/non-numeric."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


class TVScannerEngine:
    """Core engine that builds, executes, and converts TradingView screener queries."""

    def __init__(self, config: Optional[TVScannerConfig] = None):
        self.config = config or TVScannerConfig()
        self._cache: dict[str, tuple[float, TVScanReport]] = {}

    # ── Screener factory ────────────────────────────────────────────

    def _get_screener(self, asset_class: AssetClass):
        """Return the appropriate tvscreener Screener instance."""
        import tvscreener as tvs

        screener_map = {
            AssetClass.STOCK: tvs.StockScreener,
            AssetClass.CRYPTO: tvs.CryptoScreener,
            AssetClass.FOREX: tvs.ForexScreener,
            AssetClass.BOND: tvs.BondScreener,
            AssetClass.FUTURES: tvs.FuturesScreener,
            AssetClass.COIN: tvs.CoinScreener,
        }
        cls = screener_map.get(asset_class, tvs.StockScreener)
        return cls()

    def _get_field_enum(self, asset_class: AssetClass):
        """Return the Field enum for a given asset class."""
        import tvscreener as tvs

        field_map = {
            AssetClass.STOCK: tvs.StockField,
            AssetClass.CRYPTO: tvs.CryptoField,
            AssetClass.FOREX: tvs.ForexField,
            AssetClass.BOND: tvs.BondField,
            AssetClass.FUTURES: tvs.FuturesField,
            AssetClass.COIN: tvs.CoinField,
        }
        return field_map.get(asset_class, tvs.StockField)

    # ── Query execution ─────────────────────────────────────────────

    def run_preset(self, preset_id: str) -> TVScanReport:
        """Run a named preset scan. Raises KeyError if not found."""
        preset = PRESET_TV_SCANS[preset_id]
        return self.run_scan(preset)

    def run_scan(self, preset: TVPreset) -> TVScanReport:
        """Execute a scan defined by a TVPreset. Returns TVScanReport."""
        # Check cache
        cache_key = preset.name
        cached = self._cache.get(cache_key)
        if cached:
            ts, report = cached
            if time.time() - ts < self.config.cache_ttl_seconds:
                return report

        start = time.time()
        try:
            screener = self._get_screener(preset.asset_class)

            # Select fields
            field_enum = self._get_field_enum(preset.asset_class)
            field_objects = []
            for fs in preset.select_fields:
                try:
                    field_obj = getattr(field_enum, fs.field_name, None)
                    if field_obj is not None:
                        if fs.interval:
                            field_obj = field_obj.with_interval(fs.interval.value)
                        field_objects.append(field_obj)
                except Exception:
                    pass

            if field_objects:
                screener.select(*field_objects)

            # Apply filters
            for criterion in preset.criteria:
                try:
                    self._apply_criterion(screener, field_enum, criterion)
                except (TypeError, AttributeError):
                    pass  # Skip unsupported field/operator combinations

            # Sort
            if preset.sort_field:
                sort_obj = getattr(field_enum, preset.sort_field, None)
                if sort_obj is not None:
                    screener.sort_by(sort_obj, ascending=preset.sort_ascending)

            # Execute
            df = screener.get()

            # Limit results
            if len(df) > preset.max_results:
                df = df.head(preset.max_results)

            results = self._dataframe_to_results(df)
            elapsed = (time.time() - start) * 1000

            report = TVScanReport(
                preset_name=preset.name,
                total_results=len(results),
                results=results,
                execution_time_ms=round(elapsed, 1),
            )
            self._cache[cache_key] = (time.time(), report)
            return report

        except ImportError:
            elapsed = (time.time() - start) * 1000
            return TVScanReport(
                preset_name=preset.name,
                execution_time_ms=round(elapsed, 1),
                error="tvscreener library is not installed. Run: pip install tvscreener",
            )
        except Exception as exc:
            elapsed = (time.time() - start) * 1000
            return TVScanReport(
                preset_name=preset.name,
                execution_time_ms=round(elapsed, 1),
                error=str(exc),
            )

    def run_custom_scan(
        self,
        criteria: list[TVFilterCriterion],
        select_fields: Optional[list[str]] = None,
        asset_class: Optional[AssetClass] = None,
        max_results: int = 150,
    ) -> TVScanReport:
        """Run an ad-hoc custom scan with arbitrary criteria."""
        from src.tv_scanner.models import TVFieldSpec

        ac = asset_class or self.config.default_asset_class
        fields = [TVFieldSpec(f) for f in select_fields] if select_fields else []
        preset = TVPreset(
            name="custom_scan",
            description="Custom scan",
            category=None,  # type: ignore[arg-type]
            asset_class=ac,
            select_fields=fields,
            criteria=criteria,
            max_results=max_results,
        )
        return self.run_scan(preset)

    # ── Field search ────────────────────────────────────────────────

    def search_fields(self, query: str, asset_class: Optional[AssetClass] = None) -> list[str]:
        """Search available fields by keyword. Returns field names."""
        ac = asset_class or self.config.default_asset_class
        try:
            field_enum = self._get_field_enum(ac)
            results = field_enum.search(query)
            return [str(f) for f in results]
        except ImportError:
            return []
        except Exception:
            return []

    # ── Streaming ───────────────────────────────────────────────────

    def stream_scan(
        self,
        preset: TVPreset,
        interval_seconds: float = 10.0,
        max_iterations: Optional[int] = None,
    ) -> Iterator[TVScanReport]:
        """Generator yielding periodic scan results. Clears cache each iteration."""
        iterations = 0
        while True:
            if max_iterations is not None and iterations >= max_iterations:
                break
            # Clear cache for this preset to get fresh data
            self._cache.pop(preset.name, None)
            yield self.run_scan(preset)
            iterations += 1
            time.sleep(interval_seconds)

    # ── Cache management ────────────────────────────────────────────

    def clear_cache(self) -> None:
        """Clear all cached scan results."""
        self._cache.clear()

    # ── Internal helpers ────────────────────────────────────────────

    def _apply_criterion(self, screener, field_enum, criterion: TVFilterCriterion) -> None:
        """Apply a single TVFilterCriterion to the screener."""
        field_obj = getattr(field_enum, criterion.field_name, None)
        if field_obj is None:
            return

        if criterion.interval:
            field_obj = field_obj.with_interval(criterion.interval.value)

        op = criterion.operator
        if op == "gt":
            screener.where(field_obj > criterion.value)
        elif op == "lt":
            screener.where(field_obj < criterion.value)
        elif op == "gte":
            screener.where(field_obj >= criterion.value)
        elif op == "lte":
            screener.where(field_obj <= criterion.value)
        elif op == "eq":
            screener.where(field_obj == criterion.value)
        elif op == "between":
            screener.where(field_obj.between(criterion.value, criterion.value2))
        elif op == "isin":
            screener.where(field_obj.isin(criterion.value))

    def _dataframe_to_results(self, df) -> list[TVScanResult]:
        """Convert a pandas DataFrame from tvscreener into TVScanResult list."""
        results = []
        for _, row in df.iterrows():
            raw = row.to_dict()

            # Extract symbol from index or 'symbol' column
            symbol = raw.get("symbol", raw.get("ticker", str(row.name) if hasattr(row, "name") else "UNKNOWN"))

            result = TVScanResult(
                symbol=str(symbol),
                company_name=raw.get("name") or raw.get("description"),
                price=_safe_float(raw.get("close")),
                change_pct=_safe_float(raw.get("change")),
                volume=_safe_float(raw.get("volume")),
                relative_volume=_safe_float(raw.get("relative_volume_10d_calc")),
                rsi=_safe_float(raw.get("RSI")),
                macd=_safe_float(raw.get("MACD.macd")),
                macd_signal=_safe_float(raw.get("MACD.signal")),
                sma_20=_safe_float(raw.get("SMA20")),
                sma_50=_safe_float(raw.get("SMA50")),
                sma_200=_safe_float(raw.get("SMA200")),
                tv_rating=_safe_float(raw.get("Recommend.All")),
                market_cap=_safe_float(raw.get("market_cap_basic")),
                pe_ratio=_safe_float(raw.get("price_earnings_ttm")),
                dividend_yield=_safe_float(raw.get("dividend_yield_recent")),
                sector=raw.get("sector"),
                perf_week=_safe_float(raw.get("Perf.W")),
                perf_month=_safe_float(raw.get("Perf.1M")),
                perf_year=_safe_float(raw.get("Perf.Y")),
                raw_data=raw,
            )
            result.signal_strength = self._compute_signal_strength(result)
            results.append(result)
        return results

    def _compute_signal_strength(self, result: TVScanResult) -> float:
        """Compute a 0-100 signal strength from available indicators.

        Components (weighted):
          - TV Rating (Recommend.All): mapped from [-1,1] → [0,40]  (40%)
          - RSI position: distance from 50, mapped to [0,20]         (20%)
          - Relative volume: capped at 3x, mapped to [0,20]          (20%)
          - Price momentum (change_pct): capped at ±10%, [0,20]      (20%)
        """
        score = 0.0

        # TV Rating component (0-40)
        if result.tv_rating is not None:
            # Recommend.All ranges from -1 (strong sell) to +1 (strong buy)
            rating_norm = (result.tv_rating + 1) / 2  # → [0, 1]
            score += rating_norm * 40

        # RSI component (0-20): higher when RSI shows strong trend
        if result.rsi is not None:
            rsi_deviation = abs(result.rsi - 50) / 50  # 0 at 50, 1 at 0 or 100
            score += min(rsi_deviation, 1.0) * 20

        # Relative volume component (0-20)
        if result.relative_volume is not None and result.relative_volume > 0:
            vol_score = min(result.relative_volume / 3.0, 1.0)
            score += vol_score * 20

        # Momentum component (0-20)
        if result.change_pct is not None:
            mom_score = min(abs(result.change_pct) / 10.0, 1.0)
            score += mom_score * 20

        return round(min(score, 100.0), 1)
