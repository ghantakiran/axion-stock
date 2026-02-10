---
name: stock-research
description: Generate AI-powered stock research reports with DCF valuation, comparable analysis, competitive moat assessment, risk evaluation, and investment thesis (bull/base/bear cases). Use when building comprehensive equity research, performing DCF or comparable valuations, assessing competitive position, or generating buy/sell recommendations.
metadata:
  author: axion-platform
  version: "1.0"
---

# Stock Research

## When to use this skill

Use this skill when you need to:
- Generate a full equity research report for a stock
- Perform DCF (Discounted Cash Flow) valuation
- Run comparable company analysis with peer multiples
- Assess a company's economic moat (wide/narrow/none)
- Evaluate Porter's Five Forces for an industry
- Generate bull/base/bear price target scenarios
- Create SWOT analysis for competitive positioning
- Produce buy/sell/hold ratings with price targets
- Analyze financial health (earnings quality, balance sheet, cash flow)

## Step-by-step instructions

### 1. Generate a full research report (recommended)

```python
from src.research import ResearchEngine, ResearchConfig

engine = ResearchEngine()  # Uses DEFAULT_RESEARCH_CONFIG

report = engine.generate_full_report(
    symbol="AAPL",
    company_name="Apple Inc.",
    financial_data={
        "revenue": 383.3e9,
        "revenue_growth": 0.08,
        "gross_profit": 170.8e9,
        "gross_margin": 0.446,
        "operating_income": 114.3e9,
        "operating_margin": 0.298,
        "net_income": 97.0e9,
        "net_margin": 0.253,
        "eps": 6.42,
        "eps_growth": 0.09,
        "total_assets": 352.6e9,
        "total_liabilities": 290.4e9,
        "total_equity": 62.2e9,
        "total_debt": 111.1e9,
        "cash": 30.7e9,
        "operating_cash_flow": 110.5e9,
        "capex": 11.0e9,
        "market_cap": 2.8e12,
        "revenue_history": [274.5e9, 365.8e9, 394.3e9, 383.3e9],
    },
    market_data={
        "price": 185.0,
        "beta": 1.28,
        "sector": "Technology",
        "shares_outstanding": 15.1e9,
        "dividend_yield": 0.005,
    },
    peer_data={
        "MSFT": {"pe": 35.2, "ev_ebitda": 26.1, "ev_revenue": 13.0, "pb": 12.5},
        "GOOGL": {"pe": 25.8, "ev_ebitda": 18.5, "ev_revenue": 6.2, "pb": 6.3},
        "META": {"pe": 22.4, "ev_ebitda": 15.2, "ev_revenue": 7.8, "pb": 7.1},
    },
)

# Output as HTML or Markdown
html = engine.format_report(report, format="html")
markdown = engine.format_report(report, format="markdown")
```

### 2. Use individual analyzers

#### Financial Analysis
```python
from src.research.financial import FinancialAnalyzer
from src.research.models import FinancialAnalysis

analyzer = FinancialAnalyzer()
analysis: FinancialAnalysis = analyzer.analyze(
    symbol="AAPL",
    data=financial_data,  # dict with revenue, margins, cash flow, etc.
    sector="Technology",
)

print(f"Earnings quality: {analysis.earnings_quality_score:.0f}/100")
print(f"Balance sheet: {analysis.balance_sheet_strength:.0f}/100")
print(f"Cash flow quality: {analysis.cash_flow_quality:.0f}/100")
print(f"Overall health: {analysis.overall_financial_health:.0f}/100")
print(f"Revenue trend: {analysis.revenue_trend}")
print(f"Strengths: {analysis.strengths}")
print(f"Concerns: {analysis.concerns}")
```

#### DCF Valuation
```python
from src.research.valuation import ValuationEngine
from src.research.models import ValuationSummary, DCFValuation

engine = ValuationEngine()
valuation: ValuationSummary = engine.value_stock(
    symbol="AAPL",
    metrics=analysis.metrics,  # FinancialMetrics from FinancialAnalyzer
    market_data={"price": 185.0, "beta": 1.28, "shares_outstanding": 15.1e9},
    peer_data=peer_data,       # Optional, for comparable analysis
)

print(f"DCF value: ${valuation.dcf_value:.2f}")
print(f"Comparable value: ${valuation.comparable_value:.2f}")
print(f"Fair value: ${valuation.fair_value:.2f}")
print(f"Upside: {valuation.upside_pct:.1f}%")
print(f"Confidence: {valuation.confidence:.0%}")
print(f"Range: ${valuation.valuation_range_low:.2f} - ${valuation.valuation_range_high:.2f}")

# Access sensitivity matrix (WACC vs terminal growth)
if valuation.dcf and valuation.dcf.sensitivity_matrix:
    for wacc_key, growth_map in valuation.dcf.sensitivity_matrix.items():
        print(f"  WACC {wacc_key}: {growth_map}")
```

#### Competitive Analysis
```python
from src.research.competitive import CompetitiveAnalyzer
from src.research.models import CompetitiveAnalysis

comp_analyzer = CompetitiveAnalyzer()
competitive: CompetitiveAnalysis = comp_analyzer.analyze(
    symbol="AAPL",
    metrics=analysis.metrics,
    market_data={"market_share": 0.28, "market_growth": 0.05},
    competitor_data={
        "MSFT": {"name": "Microsoft", "market_cap": 2.8e12, "revenue": 211e9},
        "GOOGL": {"name": "Alphabet", "market_cap": 1.7e12, "revenue": 307e9},
    },
)

print(f"Moat: {competitive.moat_rating.value}")     # wide, narrow, none
print(f"Moat trend: {competitive.moat_trend.value}") # strengthening, stable, weakening
print(f"Position: {competitive.market_position}")     # leader, challenger, follower, niche
print(f"SWOT Strengths: {competitive.strengths}")
print(f"Porter's supplier power: {competitive.five_forces.supplier_power.value}")
```

#### Investment Thesis
```python
from src.research.thesis import ThesisGenerator
from src.research.models import InvestmentThesis

generator = ThesisGenerator()
thesis: InvestmentThesis = generator.generate(
    symbol="AAPL",
    valuation=valuation,
    financial=analysis,
    competitive=competitive,
    risk=risk_assessment,
    market_data=market_data,
)

print(f"Bull case: ${thesis.bull_price_target:.2f} ({thesis.bull_probability:.0%})")
print(f"Base case: ${thesis.base_price_target:.2f} ({thesis.base_probability:.0%})")
print(f"Bear case: ${thesis.bear_price_target:.2f} ({thesis.bear_probability:.0%})")
print(f"Expected: ${thesis.expected_price:.2f}")
print(f"Buy reasons: {thesis.reasons_to_buy}")
print(f"Sell reasons: {thesis.reasons_to_sell}")
print(f"Catalysts: {[c.title for c in thesis.catalysts]}")
```

## Code examples

### Complete research pipeline with formatted output

```python
from src.research import ResearchEngine, ResearchConfig, DCFConfig

# Custom configuration
config = ResearchConfig(
    dcf=DCFConfig(
        projection_years=5,
        risk_free_rate=0.045,
        market_premium=0.055,
        terminal_growth_rate=0.025,
        tax_rate=0.21,
    ),
)

engine = ResearchEngine(config=config)

report = engine.generate_full_report(
    symbol="NVDA",
    company_name="NVIDIA Corporation",
    financial_data=nvda_financials,
    market_data=nvda_market,
    peer_data=nvda_peers,
)

# Access report fields
print(f"Rating: {report.rating.value}")            # strong_buy, buy, hold, sell, strong_sell
print(f"Price target: ${report.price_target:.2f}")
print(f"Current: ${report.current_price:.2f}")
print(f"Upside: {report.upside_pct:.1f}%")
print(f"Summary: {report.executive_summary}")
print(f"Takeaways: {report.key_takeaways}")

# Generate Markdown report
md = engine.format_report(report, format="markdown")
```

### Standalone DCF with custom growth rates

```python
from src.research.valuation import ValuationEngine

engine = ValuationEngine()

dcf = engine.dcf_valuation(
    metrics=financial_metrics,
    market_data={"beta": 1.5},
    shares_outstanding=2.5e9,
    revenue_growth_override=[0.40, 0.30, 0.22, 0.15, 0.10],  # Custom 5-year growth
)

print(f"Enterprise value: ${dcf.enterprise_value / 1e9:.1f}B")
print(f"Equity value: ${dcf.equity_value / 1e9:.1f}B")
print(f"Fair value/share: ${dcf.fair_value_per_share:.2f}")
print(f"WACC: {dcf.wacc:.1%}")
print(f"Terminal growth: {dcf.terminal_growth_rate:.1%}")
```

## Key classes and methods

### `ResearchEngine` (`src/research/__init__.py`)
- `generate_full_report(symbol, company_name, financial_data, market_data, peer_data, competitor_data)` -> `ResearchReport`
- `format_report(report, format)` -> `str` (format: "html" or "markdown")

### `FinancialAnalyzer` (`src/research/financial.py`)
- `analyze(symbol, data, sector)` -> `FinancialAnalysis`
- Scores: `earnings_quality_score`, `balance_sheet_strength`, `cash_flow_quality`, `overall_financial_health` (0-100)

### `ValuationEngine` (`src/research/valuation.py`)
- `value_stock(symbol, metrics, market_data, peer_data)` -> `ValuationSummary`
- `dcf_valuation(metrics, market_data, shares_outstanding, revenue_growth_override)` -> `DCFValuation`
- `comparable_valuation(metrics, market_data, peer_data, shares_outstanding)` -> `ComparableValuation`
- `ddm_valuation(current_dividend, growth_rate, discount_rate)` -> `float`

### `CompetitiveAnalyzer` (`src/research/competitive.py`)
- `analyze(symbol, metrics, market_data, competitor_data)` -> `CompetitiveAnalysis`
- Produces: moat rating, Porter's Five Forces, SWOT analysis, competitor profiles

### `ThesisGenerator` (`src/research/thesis.py`)
- `generate(symbol, valuation, financial, competitive, risk, market_data)` -> `InvestmentThesis`
- `determine_rating(upside_pct, confidence, risk_level)` -> `Rating`

### `ReportGenerator` (`src/research/report_generator.py`)
- `generate_report(symbol, company_name, current_price, financial, valuation, competitive, risk, thesis)` -> `ResearchReport`
- `format_html(report)` -> `str`
- `format_markdown(report)` -> `str`

### Key data models (`src/research/models.py`)
- `FinancialMetrics` -- 25+ financial fields (revenue, margins, ratios, returns)
- `FinancialAnalysis` -- metrics + quality scores + trends + insights
- `DCFValuation` -- projected revenues/FCF, terminal value, sensitivity matrix
- `ComparableValuation` -- peer multiples, implied values, premium/discount
- `ValuationSummary` -- combined DCF + comparable + DDM with fair value
- `CompetitiveAnalysis` -- moat, Five Forces, SWOT, competitors
- `InvestmentThesis` -- bull/base/bear cases, catalysts, buy/sell reasons
- `ResearchReport` -- complete report with all sections

### Enums (`src/research/config.py`)
- `Rating`: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
- `MoatRating`: WIDE, NARROW, NONE
- `MoatTrend`: STRENGTHENING, STABLE, WEAKENING
- `RiskLevel`: LOW, MEDIUM, HIGH, VERY_HIGH
- `ValuationMethod`: DCF, COMPARABLE, DDM, SOTP, ASSET_BASED
- `ReportType`: FULL, QUICK_TAKE, EARNINGS_PREVIEW, EARNINGS_REVIEW

## Common patterns

### Rating thresholds
Ratings are determined by risk-adjusted upside:
- **Strong Buy**: >30% adjusted upside
- **Buy**: 15-30% adjusted upside
- **Hold**: -10% to 15%
- **Sell**: -25% to -10%
- **Strong Sell**: < -25%

### Sector margin benchmarks
The `SECTOR_MARGINS` dict (`src/research/config.py`) provides gross, operating,
and net margin benchmarks per sector. Financial analysis compares a company's
margins to these benchmarks to generate strengths/concerns.

### DCF sensitivity matrix
Every DCF valuation includes a sensitivity matrix varying WACC (+/- 2%) and
terminal growth rate (+/- 1%). This helps assess valuation range under
different assumptions.

### Weighted fair value
The blended fair value uses: DCF (50%), Comparable (35%), DDM (15%).
If comparable or DDM data is unavailable, weights are renormalized.
Confidence is derived from valuation dispersion (coefficient of variation).
