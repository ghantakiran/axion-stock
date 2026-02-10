---
name: Axion Visualization & Reporting
description: >
  Build charts, dashboards, and performance reports for the Axion trading platform.
  Covers advanced charting with 20+ technical indicators, pattern detection, trend analysis,
  Fibonacci levels, support/resistance detection, system health monitoring with metrics
  collection and alerting, and GIPS-compliant performance reporting with composite
  management, dispersion calculations, and compliance validation.
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# Axion Visualization & Reporting Skill

## When to use this skill

Use this skill when you need to:

- Create or configure chart layouts with technical indicators and drawing tools
- Detect chart patterns (double top/bottom, head and shoulders, triangles)
- Analyze price trends, moving average crossovers, support/resistance levels
- Compute Fibonacci retracement and extension levels
- Monitor system health across services, data freshness, and dependencies
- Collect and analyze system metrics (CPU, memory, response times)
- Generate system alerts based on threshold violations
- Build GIPS-compliant performance reports with composite management
- Calculate time-weighted, money-weighted, or Modified Dietz returns
- Validate GIPS compliance and generate required disclosures

## Step-by-step instructions

### 1. Advanced Charting: Indicators and Layouts

Create a chart layout, add indicators, and compute indicator values.

```python
from src.charting import (
    IndicatorEngine, LayoutManager, DrawingManager,
    ChartType, Timeframe, IndicatorConfig, OHLCV,
)
from datetime import datetime, timezone

# Create layout manager and a user layout
layout_mgr = LayoutManager()
layout = layout_mgr.create_layout(
    user_id="user-123",
    name="Daily Trading",
    symbol="AAPL",
    timeframe=Timeframe.D1,
    chart_type=ChartType.CANDLESTICK,
)

# Add an indicator to the layout
sma_config = IndicatorConfig(
    indicator_id="sma_20",
    name="SMA",
    params={"period": 20},
    color="#2196F3",
    panel_index=0,  # 0 = overlay on main chart
)
layout_mgr.add_indicator("user-123", layout.layout_id, sma_config)

# Apply a built-in template (trend_following, momentum, scalping, volatility, volume_analysis)
layout_mgr.apply_template("user-123", layout.layout_id, "trend_following")

# Calculate indicator values from OHLCV data
engine = IndicatorEngine()
bars = [
    OHLCV(timestamp=datetime(2024, 1, i+1, tzinfo=timezone.utc),
           open=150+i*0.5, high=152+i*0.5, low=149+i*0.5,
           close=151+i*0.5, volume=1000000)
    for i in range(30)
]
result = engine.calculate("RSI", bars, params={"period": 14})
print(result.values["rsi"][-5:])  # Last 5 RSI values

# List available indicators by category
from src.charting.config import IndicatorCategory
momentum = engine.get_indicators_by_category(IndicatorCategory.MOMENTUM)
```

### 2. Chart Pattern Detection

Detect classic chart patterns from price data.

```python
from src.charting.patterns import PatternDetector
from src.charting.config import PatternConfig
import pandas as pd

detector = PatternDetector()

# Provide high, low, close as pandas Series
high = pd.Series([100, 105, 103, 106, 104, 107, 105, 108, ...])
low = pd.Series([98, 102, 100, 103, 101, 104, 102, 105, ...])
close = pd.Series([99, 104, 102, 105, 103, 106, 104, 107, ...])

# Detect all patterns (double top/bottom, H&S, triangles)
patterns = detector.detect_all(high, low, close, symbol="AAPL")
for p in patterns:
    print(f"{p.pattern_type.value}: confidence={p.confidence}, "
          f"target={p.target_price}, confirmed={p.confirmed}")

# Detect specific patterns
double_tops = detector.detect_double_top(high, close, symbol="AAPL")
triangles = detector.detect_triangle(high, low, close, symbol="AAPL")
```

### 3. Trend Analysis and Moving Average Crossovers

Analyze trend direction, strength, and detect golden/death crosses.

```python
from src.charting.trend import TrendAnalyzer
from src.charting.config import TrendDirection
import pandas as pd

analyzer = TrendAnalyzer()
close = pd.Series([...])  # Close prices

# Full trend analysis: direction, strength, R-squared, MA values
trend = analyzer.analyze(close, symbol="AAPL")
print(f"Direction: {trend.direction.value}, Strength: {trend.strength}")
print(f"Slope: {trend.slope}, R-squared: {trend.r_squared}")
print(f"MA Short: {trend.ma_short}, MA Long: {trend.ma_long}")

# Detect moving average crossovers
crossovers = analyzer.detect_crossovers(close, fast_window=50, slow_window=200, symbol="AAPL")
for xo in crossovers:
    print(f"{xo.crossover_type.value} at index {xo.idx}, price={xo.price_at_cross}")

# Compute specific MA values
ma_values = analyzer.compute_moving_averages(close, windows=[20, 50, 100, 200])
```

### 4. Support/Resistance and Fibonacci Levels

```python
from src.charting.support_resistance import SRDetector
from src.charting.fibonacci import FibCalculator
import pandas as pd

# Support and resistance detection
sr = SRDetector()
levels = sr.find_levels(high, low, close, symbol="AAPL")
for level in levels:
    print(f"{level.level_type.value}: ${level.price} "
          f"(touches={level.touches}, strength={level.strength})")

# Test proximity to a level
proximity = sr.test_level(levels[0], current_price=155.0)
print(f"Distance: {proximity['distance_pct']}%, Proximity: {proximity['proximity']}")

# Fibonacci retracement and extensions
fib = FibCalculator()
fib_levels = fib.compute(high, low, close, symbol="AAPL")
print(f"Swing high: {fib_levels.swing_high}, Swing low: {fib_levels.swing_low}")
for ratio, price in fib_levels.retracements.items():
    print(f"  {ratio:.1%} retracement: ${price}")

# From explicit swing points
fib_manual = fib.compute_from_points(swing_high=160.0, swing_low=140.0, is_uptrend=True)

# Find nearest Fibonacci level to current price
nearest = fib.find_nearest_level(fib_levels, price=152.5)
if nearest:
    level_type, ratio, fib_price = nearest
    print(f"Nearest: {level_type} {ratio:.1%} at ${fib_price}")
```

### 5. Drawing Tools

```python
from src.charting import DrawingManager
from datetime import datetime, timezone

dm = DrawingManager()

# Create various drawing types
trendline = dm.create_trendline(
    symbol="AAPL",
    start=(datetime(2024, 1, 1, tzinfo=timezone.utc), 150.0),
    end=(datetime(2024, 3, 1, tzinfo=timezone.utc), 165.0),
    color="#2196F3",
    extend_right=True,
)

fib_drawing = dm.create_fibonacci_retracement(
    symbol="AAPL",
    start=(datetime(2024, 1, 15, tzinfo=timezone.utc), 140.0),
    end=(datetime(2024, 2, 15, tzinfo=timezone.utc), 160.0),
    levels=[0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0],
)

hline = dm.create_horizontal_line("AAPL", price=155.0, color="#FF9800")
rect = dm.create_rectangle(
    "AAPL",
    top_left=(datetime(2024, 1, 1, tzinfo=timezone.utc), 160.0),
    bottom_right=(datetime(2024, 2, 1, tzinfo=timezone.utc), 150.0),
)

# Manage drawings on a layout
dm.add_drawing("layout-123", trendline)
dm.add_drawing("layout-123", fib_drawing)
drawings = dm.get_drawings("layout-123", symbol="AAPL")
dm.delete_drawing("layout-123", trendline.drawing_id)
```

### 6. System Health Monitoring

```python
from src.system_dashboard import (
    HealthChecker, MetricsCollector, SystemAlertManager,
    SystemConfig, AlertThresholds, SystemMetrics,
)

# Configure and run health checks
config = SystemConfig(
    check_interval_seconds=60,
    alert_thresholds=AlertThresholds(cpu_warn=0.80, cpu_crit=0.95),
)
checker = HealthChecker(config)

# Register a custom health check
checker.register_check("api", lambda: True)

# Check individual services
health = checker.check_service(
    service_name="api",
    response_time_ms=45,
    error_rate=0.002,
    is_available=True,
    version="2.1.0",
)

# Capture full system snapshot
metrics = SystemMetrics(cpu_usage=0.42, memory_usage=0.65, disk_usage=0.55)
snapshot = checker.capture_snapshot(
    service_data={"api": {"response_time_ms": 45, "error_rate": 0.002, "is_available": True}},
    metrics=metrics,
)
print(f"Overall: {snapshot.overall_status}, Healthy: {snapshot.n_healthy}")

# Generate summary
summary = checker.get_summary(snapshot)

# Metrics collection with percentile analysis
collector = MetricsCollector(max_history=1440)
collector.record_snapshot(metrics)
averages = collector.get_averages(last_n=60)
percentiles = collector.get_percentiles("cpu_usage", [50, 90, 95, 99])
anomaly = collector.detect_anomaly("cpu_usage", threshold_std=2.0)

# System alerting
alert_mgr = SystemAlertManager()
new_alerts = alert_mgr.evaluate_metrics(metrics)
service_alerts = alert_mgr.evaluate_snapshot(snapshot)
active = alert_mgr.get_active_alerts(level="critical")
alert_mgr.acknowledge_alert(alert_id="abc123", by="admin")
alert_mgr.resolve_alert(alert_id="abc123")
```

### 7. GIPS-Compliant Performance Reporting

```python
from src.performance_report import (
    CompositeManager, GIPSCalculator, DispersionCalculator,
    ComplianceValidator, GIPSReportGenerator,
    GIPSConfig, CompositeConfig, PerformanceRecord,
)
from datetime import date

# Create a composite
mgr = CompositeManager(CompositeConfig(
    name="US Large Cap Growth",
    strategy="Large Cap Growth Equity",
    benchmark_name="Russell 1000 Growth",
    min_portfolio_size=250_000,
))
composite = mgr.create_composite(
    name="US Large Cap Growth",
    strategy="Large Cap Growth Equity",
    benchmark_name="Russell 1000 Growth",
    inception_date=date(2018, 1, 1),
)

# Add portfolios to the composite
mgr.add_portfolio(composite.composite_id, "PORT-001", date(2018, 1, 1), market_value=500_000)

# Calculate returns
calc = GIPSCalculator()
twr = calc.time_weighted_return(values=[100000, 105000, 103000, 110000])
dietz = calc.modified_dietz_return(
    beginning_value=100000,
    ending_value=110000,
    cash_flows=[(5000, 0.75)],
)
annual = calc.annualize_return(total_return=0.25, years=2.0)
std_dev = calc.annualized_std_dev(returns=[0.01, -0.02, 0.015, ...], periods_per_year=12)

# Link monthly returns into annual
annual_return = calc.link_returns([0.01, 0.02, -0.01, 0.015, ...])

# Internal dispersion
from src.performance_report.config import DispersionMethod
disp_calc = DispersionCalculator(method=DispersionMethod.ASSET_WEIGHTED_STD)
records = [PerformanceRecord(portfolio_id=f"P{i}", period_start=date(2024,1,1),
           period_end=date(2024,12,31), gross_return=0.08+i*0.005,
           beginning_value=500000) for i in range(8)]
dispersion = disp_calc.calculate(records)
print(f"Dispersion: {dispersion.value:.4f}, Meaningful: {dispersion.is_meaningful}")

# All methods comparison
all_methods = disp_calc.compare_methods(records)

# Compliance validation
validator = ComplianceValidator(GIPSConfig(firm_name="Axion Capital"))
report = validator.validate_composite(composite, periods=[...])
print(f"Compliant: {report.overall_compliant}, Pass rate: {report.pass_rate:.0%}")
for check in report.errors:
    print(f"  FAIL [{check.rule_id}]: {check.description}")

# Generate full GIPS presentation
gen = GIPSReportGenerator(GIPSConfig(firm_name="Axion Capital"))
presentation = gen.generate_presentation(composite, periods=[...])
table = gen.format_presentation_table(presentation)
summary = gen.generate_summary(presentation)
```

## Key classes and methods

### Charting Module (`src/charting/`)

| Class | Method | Description |
|-------|--------|-------------|
| `IndicatorEngine` | `calculate(indicator_name, data, params)` | Compute indicator (SMA, EMA, RSI, MACD, STOCH, BB, ATR, OBV, VWAP) |
| `IndicatorEngine` | `get_available_indicators()` | List all 20+ available indicators |
| `IndicatorEngine` | `get_indicators_by_category(category)` | Filter by IndicatorCategory (TREND, MOMENTUM, VOLUME, VOLATILITY) |
| `LayoutManager` | `create_layout(user_id, name, symbol, timeframe, chart_type)` | Create new chart layout |
| `LayoutManager` | `apply_template(user_id, layout_id, template_id)` | Apply built-in template to layout |
| `LayoutManager` | `save_layout_as_template(user_id, layout_id, name, category)` | Save layout as reusable template |
| `LayoutManager` | `get_featured_templates()` | Get featured chart templates |
| `DrawingManager` | `create_trendline(symbol, start, end, ...)` | Create trendline drawing |
| `DrawingManager` | `create_fibonacci_retracement(symbol, start, end, levels)` | Create Fibonacci retracement |
| `DrawingManager` | `create_horizontal_line(symbol, price, ...)` | Create horizontal price line |
| `DrawingManager` | `create_rectangle(symbol, top_left, bottom_right, ...)` | Create rectangle annotation |
| `PatternDetector` | `detect_all(high, low, close, symbol)` | Detect all chart patterns |
| `PatternDetector` | `detect_double_top(high, close, symbol)` | Detect double top patterns |
| `PatternDetector` | `detect_head_and_shoulders(high, low, close, symbol)` | Detect H&S and inverse H&S |
| `PatternDetector` | `detect_triangle(high, low, close, symbol)` | Detect ascending/descending triangles |
| `TrendAnalyzer` | `analyze(close, symbol)` | Full trend analysis with direction, strength, R-squared |
| `TrendAnalyzer` | `detect_crossovers(close, fast_window, slow_window, symbol)` | Detect golden/death crosses |
| `TrendAnalyzer` | `compute_moving_averages(close, windows)` | Compute MA values for multiple periods |
| `SRDetector` | `find_levels(high, low, close, symbol)` | Find support and resistance levels |
| `SRDetector` | `test_level(level, current_price)` | Test distance/proximity to a level |
| `FibCalculator` | `compute(high, low, close, symbol)` | Auto-detect swings and compute Fibonacci levels |
| `FibCalculator` | `compute_from_points(swing_high, swing_low, is_uptrend)` | Fibonacci from explicit swing points |
| `FibCalculator` | `find_nearest_level(fib, price)` | Find nearest Fibonacci level to price |

### System Dashboard Module (`src/system_dashboard/`)

| Class | Method | Description |
|-------|--------|-------------|
| `HealthChecker` | `capture_snapshot(service_data, metrics, source_updates, dep_data)` | Full system health snapshot |
| `HealthChecker` | `check_service(service_name, response_time_ms, error_rate, is_available)` | Check single service health |
| `HealthChecker` | `check_all_services(service_data)` | Check all monitored services |
| `HealthChecker` | `check_data_freshness(source_updates)` | Check data staleness per source |
| `HealthChecker` | `get_summary(snapshot)` | Generate SystemSummary from snapshot |
| `HealthChecker` | `register_check(service_name, check_fn)` | Register custom health check |
| `MetricsCollector` | `record_snapshot(metrics)` | Record a SystemMetrics snapshot |
| `MetricsCollector` | `get_averages(last_n)` | Average metrics over N snapshots |
| `MetricsCollector` | `get_percentiles(metric, percentiles)` | p50/p90/p95/p99 for a metric |
| `MetricsCollector` | `detect_anomaly(metric, threshold_std)` | Z-score anomaly detection |
| `SystemAlertManager` | `evaluate_metrics(metrics)` | Generate alerts from metrics thresholds |
| `SystemAlertManager` | `evaluate_snapshot(snapshot)` | Generate alerts from health snapshot |
| `SystemAlertManager` | `acknowledge_alert(alert_id, by)` | Acknowledge an active alert |
| `SystemAlertManager` | `resolve_alert(alert_id)` | Resolve and deactivate an alert |

### Performance Report Module (`src/performance_report/`)

| Class | Method | Description |
|-------|--------|-------------|
| `CompositeManager` | `create_composite(name, strategy, benchmark_name, inception_date)` | Create GIPS composite |
| `CompositeManager` | `add_portfolio(composite_id, portfolio_id, join_date, market_value)` | Add portfolio to composite |
| `CompositeManager` | `calculate_composite_return(composite_id, records, benchmark_return)` | Asset-weighted composite return |
| `GIPSCalculator` | `time_weighted_return(values, cash_flows)` | TWR from sequential valuations |
| `GIPSCalculator` | `modified_dietz_return(beginning_value, ending_value, cash_flows)` | Modified Dietz with day-weighted flows |
| `GIPSCalculator` | `money_weighted_return(beginning_value, ending_value, cash_flows)` | IRR via Newton's method |
| `GIPSCalculator` | `annualize_return(total_return, years)` | Annualize cumulative return |
| `GIPSCalculator` | `annualized_std_dev(returns, periods_per_year)` | 3-year annualized std dev |
| `GIPSCalculator` | `link_returns(period_returns)` | Geometrically link sub-period returns |
| `GIPSCalculator` | `build_annual_periods(composite_returns, ...)` | Build annual CompositePeriod records |
| `DispersionCalculator` | `calculate(records, method)` | Internal dispersion across portfolios |
| `DispersionCalculator` | `compare_methods(records)` | Calculate all 4 dispersion methods |
| `ComplianceValidator` | `validate_composite(composite, periods)` | Run 13 GIPS compliance checks |
| `ComplianceValidator` | `generate_disclosures(composite, periods)` | Generate required GIPS disclosures |
| `GIPSReportGenerator` | `generate_presentation(composite, periods, disclosures)` | Full GIPS presentation |
| `GIPSReportGenerator` | `format_presentation_table(presentation)` | Format as text table |
| `GIPSReportGenerator` | `generate_summary(presentation)` | Dashboard summary dict |

## Common patterns

### Data models are dataclasses

All models use Python dataclasses with `to_dict()` methods for serialization.

```python
from src.charting.models import OHLCV, IndicatorResult, ChartLayout
from src.system_dashboard.models import SystemMetrics, HealthSnapshot, SystemSummary
from src.performance_report.models import CompositeReturn, CompositePeriod, GIPSPresentation
```

### Enums define valid options

```python
from src.charting.config import ChartType, Timeframe, DrawingType, IndicatorCategory, LineStyle
from src.system_dashboard.config import ServiceName, ServiceStatus, HealthLevel, MetricType
from src.performance_report.config import ReturnMethod, DispersionMethod, ReportPeriod
```

### Built-in sample data generators for demos

```python
# System dashboard demo
snapshot = HealthChecker.generate_sample_snapshot()
collector = MetricsCollector.generate_sample_history(n_points=60)

# Performance report demo
sample_returns = GIPSCalculator.generate_sample_returns(n_years=7)
sample_mgr = CompositeManager.generate_sample_composite()
```

### Config objects control behavior

Each module has a config dataclass with sensible defaults. Override specific fields as needed.

```python
from src.charting.config import ChartConfig, DEFAULT_CHART_CONFIG
from src.system_dashboard.config import SystemConfig, AlertThresholds
from src.performance_report.config import GIPSConfig, CompositeConfig, FeeSchedule
```

### Template system for chart layouts

Five built-in templates: `trend_following`, `momentum`, `scalping`, `volatility`, `volume_analysis`. Create custom templates from existing layouts with `save_layout_as_template()`.
