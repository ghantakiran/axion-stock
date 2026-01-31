"""Market Scanner.

Real-time market scanning for trading setups and unusual activity.

Example:
    from src.scanner import (
        ScannerEngine, Scanner, ScanCriterion, Operator,
        UnusualActivityDetector, PatternDetector,
        PRESET_SCANNERS, get_preset_scanner,
    )
    
    # Create scanner engine
    engine = ScannerEngine()
    
    # Use a preset scanner
    gap_scanner = get_preset_scanner("gap_up")
    engine.add_scanner(gap_scanner)
    
    # Run scan
    results = engine.run_scan(gap_scanner, market_data)
    for result in results:
        print(f"{result.symbol}: {result.change_pct:.1%}")
"""

from src.scanner.config import (
    Operator,
    ScanCategory,
    ActivityType,
    PatternType,
    CandlePattern,
    SignalStrength,
    Universe,
    SCAN_FIELDS,
    SCAN_INTERVALS,
    ScannerConfig,
    UnusualActivityConfig,
    DEFAULT_SCANNER_CONFIG,
    DEFAULT_UNUSUAL_CONFIG,
)

from src.scanner.models import (
    ScanCriterion,
    Scanner,
    ScanResult,
    UnusualActivity,
    ChartPattern,
    CandlestickPattern,
    ScanAlert,
)

from src.scanner.engine import ScannerEngine, create_scanner

from src.scanner.presets import (
    PRESET_SCANNERS,
    get_preset_scanner,
    get_presets_by_category,
    get_all_presets,
    # Individual presets
    GAP_UP_SCAN,
    GAP_DOWN_SCAN,
    NEW_HIGH_SCAN,
    NEW_LOW_SCAN,
    VOLUME_SPIKE_SCAN,
    RSI_OVERSOLD_SCAN,
    RSI_OVERBOUGHT_SCAN,
    MACD_BULLISH_SCAN,
    BIG_GAINERS_SCAN,
    BIG_LOSERS_SCAN,
)

from src.scanner.unusual import UnusualActivityDetector

from src.scanner.patterns import PatternDetector


__all__ = [
    # Config
    "Operator",
    "ScanCategory",
    "ActivityType",
    "PatternType",
    "CandlePattern",
    "SignalStrength",
    "Universe",
    "SCAN_FIELDS",
    "SCAN_INTERVALS",
    "ScannerConfig",
    "UnusualActivityConfig",
    "DEFAULT_SCANNER_CONFIG",
    "DEFAULT_UNUSUAL_CONFIG",
    # Models
    "ScanCriterion",
    "Scanner",
    "ScanResult",
    "UnusualActivity",
    "ChartPattern",
    "CandlestickPattern",
    "ScanAlert",
    # Engine
    "ScannerEngine",
    "create_scanner",
    # Presets
    "PRESET_SCANNERS",
    "get_preset_scanner",
    "get_presets_by_category",
    "get_all_presets",
    "GAP_UP_SCAN",
    "GAP_DOWN_SCAN",
    "NEW_HIGH_SCAN",
    "NEW_LOW_SCAN",
    "VOLUME_SPIKE_SCAN",
    "RSI_OVERSOLD_SCAN",
    "RSI_OVERBOUGHT_SCAN",
    "MACD_BULLISH_SCAN",
    "BIG_GAINERS_SCAN",
    "BIG_LOSERS_SCAN",
    # Unusual Activity
    "UnusualActivityDetector",
    # Patterns
    "PatternDetector",
]
