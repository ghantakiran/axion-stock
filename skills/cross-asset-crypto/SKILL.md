---
name: cross-asset-crypto
description: >
  Analyze cross-asset relationships, crypto derivatives, blockchain settlement,
  credit risk, and ESG scoring on the Axion trading platform. Covers blockchain
  settlement with atomic swaps (src/blockchain/), crypto option pricing with
  Black-76 and Greeks (src/crypto_options/), intermarket correlation and lead-lag
  signal generation (src/crossasset/), multi-asset portfolio optimization with
  crypto factors and futures management (src/multi_asset/), credit spread
  analysis and default estimation (src/credit/), and ESG scoring with impact
  tracking (src/esg/). Use this skill for cross-asset signals, crypto trading,
  or alternative investment analysis.
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# Cross-Asset Crypto & Alternative Investments

## When to use this skill

- Analyzing intermarket correlations and detecting correlation regime shifts
- Identifying lead-lag relationships between asset classes for predictive signals
- Computing cross-asset momentum and mean-reversion signals
- Pricing crypto options with Black-76 and computing Greeks
- Analyzing crypto derivatives: funding rates, basis spreads, put/call ratios, max pain
- Settling trades on blockchain with atomic swap support
- Managing crypto portfolios with 5-factor models (value, momentum, quality, sentiment, network)
- Trading futures with contract specs, auto-roll detection, margin monitoring
- Optimizing multi-asset portfolios across equities, crypto, futures, and FX
- Computing cross-asset VaR, risk contributions, and correlation regime detection
- Analyzing credit spreads, default probabilities, and debt structures
- Scoring securities on ESG dimensions with screening and portfolio aggregation

## Step-by-step instructions

### 1. Analyze intermarket relationships

Use `IntermarketAnalyzer` for rolling correlations, relative strength, divergence detection, and correlation matrices.

```python
from src.crossasset import IntermarketAnalyzer, IntermarketConfig, AssetPairCorrelation

analyzer = IntermarketAnalyzer(IntermarketConfig(
    correlation_window=60, long_window=252, divergence_threshold=2.0,
))

# Rolling correlation between two return series
corr: AssetPairCorrelation = analyzer.rolling_correlation(
    equity_returns, bond_returns, asset_a="SPY", asset_b="TLT",
)
# Returns: .correlation, .long_term_correlation, .z_score, .regime, .beta

# Relative strength ranking
rankings = analyzer.relative_strength(
    prices={"SPY": spy_px, "TLT": tlt_px, "GLD": gld_px}, benchmark="SPY", window=63,
)
# Returns: list[RelativeStrength] with .rank, .ratio, .trend

# Detect correlation divergence
div = analyzer.detect_divergence(equity_ret, bond_ret, "SPY", "TLT")
# Returns: {"is_diverging": bool, "direction": str, "z_score": float}

# Full correlation matrix
matrix = analyzer.correlation_matrix(returns={"SPY": spy_ret, "TLT": tlt_ret}, window=60)
```

### 2. Detect lead-lag relationships

Use `LeadLagDetector` to find predictive relationships via cross-correlation.

```python
from src.crossasset import LeadLagDetector, LeadLagConfig, LeadLagResult

detector = LeadLagDetector(LeadLagConfig(max_lag=10, min_correlation=0.15))

result: LeadLagResult = detector.detect(vix_ret, spy_ret, "VIX", "SPY")
# Returns: .leader, .lagger, .optimal_lag, .correlation_at_lag, .is_significant, .stability

# All pairwise relationships (returns only significant pairs, sorted by correlation)
all_results = detector.detect_all_pairs({"VIX": vix_ret, "SPY": spy_ret, "TLT": tlt_ret})

# Extract directional signal from leader for use in downstream models
signal = detector.extract_signal(leader_returns=vix_ret, lag=3)
```

### 3. Compute cross-asset momentum signals

Use `CrossAssetMomentum` for time-series momentum, cross-sectional ranking, and mean-reversion detection.

```python
from src.crossasset import CrossAssetMomentum, MomentumConfig, MomentumSignal

momentum = CrossAssetMomentum(MomentumConfig(
    lookback_short=21, lookback_long=126, zscore_window=63,
    mean_reversion_threshold=2.0, trend_strength_threshold=1.5,
))

# Single asset time-series momentum
sig: MomentumSignal = momentum.time_series_momentum(btc_ret, asset="BTC", asset_class="crypto")
# Returns: .ts_momentum, .z_score, .trend_strength, .signal, .is_mean_reverting

# Cross-sectional ranked momentum
returns_dict = {"BTC": btc_ret, "ETH": eth_ret, "SPY": spy_ret, "GLD": gld_ret}
ranked = momentum.cross_sectional_momentum(returns_dict, {"BTC": "crypto", "SPY": "equity"})
# Each signal gets .xs_rank (0-1, higher=better)

# Filter helpers
mr_signals = momentum.mean_reversion_signals(returns_dict)  # |z_score| > threshold
trend_signals = momentum.trend_signals(returns_dict)         # |trend_strength| > threshold
```

### 4. Generate composite cross-asset signals

Use `CrossAssetSignalGenerator` to combine momentum, lead-lag, and intermarket into a single signal.

```python
from src.crossasset import CrossAssetSignalGenerator, SignalConfig, CrossAssetSignal

generator = CrossAssetSignalGenerator(SignalConfig(
    momentum_weight=0.4, mean_reversion_weight=0.2,
    leadlag_weight=0.2, intermarket_weight=0.2,
))

signal: CrossAssetSignal = generator.generate(
    asset="SPY", momentum=spy_mom, lead_lag=vix_spy_ll,
    lead_lag_signal=0.003, correlations=[spy_tlt_corr],
)
# Returns: .direction (bullish/bearish/neutral), .strength (strong/moderate/weak/none),
#          .score, .confidence, .momentum_component, .leadlag_component

# Batch generation for all assets
all_signals = generator.generate_all(
    momentum_signals=ranked, lead_lag_results=ll_results,
    lead_lag_signals={"SPY": 0.003}, correlation_map={"SPY": [spy_tlt_corr]},
)
```

### 5. Price crypto options and compute Greeks

Use `CryptoOptionPricer` for Black-76 pricing, Greeks, implied vol, and vol surfaces.

```python
from src.crypto_options import (
    CryptoOptionPricer, CryptoOptionsConfig, CryptoOptionContract,
    CryptoOptionQuote, CryptoOptionGreeks, CryptoOptionType,
)

pricer = CryptoOptionPricer(CryptoOptionsConfig(default_risk_free_rate=0.05))

contract = CryptoOptionContract(
    underlying="BTC", strike=50000.0, expiry_date="2025-06-30",
    option_type=CryptoOptionType.CALL,
)

# Price with Black-76 (returns quote with .mark, .greeks.delta/gamma/theta/vega)
quote: CryptoOptionQuote = pricer.price(contract, spot=48000.0, vol=0.80)

# Solve for implied volatility via Newton-Raphson
iv = pricer.implied_vol(contract, spot=48000.0, market_price=5200.0)

# Build volatility surface from market quotes: dict[(strike, tte)] -> iv
surface = pricer.build_vol_surface("BTC", spot=48000.0, quotes=market_quotes)
```

### 6. Analyze crypto derivatives markets

Use `CryptoDerivativesAnalyzer` for funding rates, basis, PCR, and max pain.

```python
from src.crypto_options import CryptoDerivativesAnalyzer, CryptoExchange

analyzer = CryptoDerivativesAnalyzer()

# Track and query funding rates
analyzer.record_funding_rate("BTC", CryptoExchange.DERIBIT, rate=0.0001)
avg = analyzer.average_funding_rate("BTC", CryptoExchange.DERIBIT, periods=30)

# Spot-futures basis spread
basis = analyzer.compute_basis("BTC", spot_price=48000.0, futures_price=49200.0,
                               perp_price=48050.0, days_to_expiry=30)

# Put/call ratio and max pain from option quotes
pcr = analyzer.put_call_ratio(option_quotes)
max_pain_strike = analyzer.max_pain(option_quotes, spot=48000.0)
```

### 7. Settle trades on blockchain

Use `SettlementEngine` for settlement lifecycle and `TransactionMonitor` for confirmations.

```python
from src.blockchain import (
    SettlementEngine, BlockchainConfig, BlockchainNetwork,
    TransactionMonitor, SettlementRecord, AtomicSwap,
)

engine = SettlementEngine(BlockchainConfig(
    default_network=BlockchainNetwork.ETHEREUM, max_retries=3,
))

# Settlement lifecycle: initiate -> submit -> confirm
record = engine.initiate_settlement(
    trade_id="TRADE-001", amount=1.5, asset_symbol="ETH",
    sender="0xSender...", receiver="0xReceiver...",
)
engine.submit_settlement(record.id)
engine.confirm_settlement(record.id, tx_hash="0xabc...", block_number=18500000, gas_cost=0.003)

# Atomic swap (cross-chain)
swap = engine.initiate_atomic_swap(
    initiator="0xAlice...", participant="0xBob...",
    send_asset="ETH", send_amount=10.0, receive_asset="BTC", receive_amount=0.5,
)
engine.complete_swap(swap.id)

# Gas estimation and summary
gas = engine.estimate_gas(BlockchainNetwork.ETHEREUM)  # estimated_cost_eth, estimated_time_seconds
summary = engine.get_summary()  # .success_rate, .total_volume, .avg_settlement_time

# Transaction monitoring
monitor = TransactionMonitor()
monitor.watch(tx)
monitor.update_confirmations(tx.id, confirmations=6, block_number=18500001)
```

### 8. Build crypto factor models and manage futures

Use `CryptoFactorModel` for 5-factor scoring and `FuturesManager` for contracts and margin.

```python
from src.multi_asset import (
    CryptoFactorModel, CryptoDataProvider, CryptoAsset, OnChainMetrics,
    FuturesManager, FuturesConfig, MarginStatus,
)

# Crypto factor model: value, momentum, quality, sentiment, network
provider = CryptoDataProvider()
provider.register_asset(CryptoAsset(symbol="BTC", name="Bitcoin"))
provider.set_on_chain_metrics(OnChainMetrics(
    symbol="BTC", nvt_ratio=35.0, mvrv_ratio=1.8,
    active_addresses_24h=900000, stock_to_flow=56.0,
    developer_commits_30d=150, tvl=5e9, transaction_count_24h=350000,
))
provider.set_price_history("BTC", btc_price_series)

model = CryptoFactorModel(data_provider=provider)
scores = model.compute_scores("BTC")  # .value, .momentum, .quality, .network, .composite
top = model.rank_universe(symbols=["BTC", "ETH", "SOL"], factor="composite", top_n=5)

# Futures: specs, front month, auto-roll, margin
futures = FuturesManager(FuturesConfig(roll_threshold_days=5))
spec = futures.get_contract_spec("ES")
front = futures.get_front_month("ES")  # e.g. "ESH25"
roll = futures.check_roll(position)    # returns RollOrder or None
futures.set_margin_available(500_000.0)
futures.add_position(es_position)
margin: MarginStatus = futures.get_margin_status()
spread = futures.build_calendar_spread("ES", front_month="H25", back_month="M25")
```

### 9. Optimize cross-asset portfolios and monitor risk

Use `CrossAssetOptimizer` for allocation and `UnifiedRiskManager` for VaR and risk decomposition.

```python
from src.multi_asset import (
    CrossAssetOptimizer, UnifiedRiskManager, AssetClass,
    MultiAssetPortfolio, CrossAssetRiskReport,
)

optimizer = CrossAssetOptimizer()

# Build from template: conservative, balanced, growth, aggressive, crypto_native
portfolio = optimizer.from_template("balanced", symbols_by_class={
    AssetClass.US_EQUITY: ["SPY", "QQQ"], AssetClass.CRYPTO: ["BTC", "ETH"],
    AssetClass.FIXED_INCOME: ["TLT"], AssetClass.COMMODITY: ["GLD"],
}, total_capital=100_000)

# Build covariance and do risk-parity allocation
cov = optimizer.build_covariance(returns_by_asset={"SPY": spy_ret, "BTC": btc_ret})
weights = optimizer.risk_budget_allocation(cov, risk_budgets={"SPY": 0.4, "BTC": 0.6})

# Cross-asset risk analysis
risk_mgr = UnifiedRiskManager()
report = risk_mgr.compute_portfolio_risk(portfolio, returns=returns_df, covariance=cov)
# .total_var_95, .total_var_99, .max_drawdown, .correlation_regime, .risk_by_asset_class

# Margin monitoring with alert levels (warning/critical/margin_call/liquidation)
margin = risk_mgr.check_margin(total_required=150_000, total_available=500_000)
alerts = risk_mgr.get_margin_alerts()
```

### 10. Analyze credit risk

Use `SpreadAnalyzer` for credit spread tracking with Z-scores and relative value.

```python
from src.credit import SpreadAnalyzer, CreditSpread, SpreadSummary

spreads = SpreadAnalyzer()
spreads.add_spread(CreditSpread(symbol="AAPL", spread_bps=75.0, term=5.0))
spreads.add_spread(CreditSpread(symbol="AAPL", spread_bps=78.0, term=5.0))
spreads.add_spread(CreditSpread(symbol="AAPL", spread_bps=82.0, term=5.0))

summary: SpreadSummary = spreads.analyze("AAPL")
# .current_spread, .avg_spread, .z_score, .percentile, .trend

term_struct = spreads.term_structure("AAPL")      # [{term, spread_bps}]
rv = spreads.relative_value(["AAPL", "MSFT"])     # sorted by z_score desc
```

### 11. Score and screen securities on ESG

Use `ESGScorer` for scoring/screening and `ImpactTracker` for impact measurement.

```python
from src.esg import (
    ESGScorer, ESGConfig, ESGScore, ESGScreenResult, ESGPortfolioSummary,
    ImpactTracker, ImpactCategory,
)

scorer = ESGScorer(ESGConfig(
    environmental_weight=0.4, social_weight=0.3, governance_weight=0.3,
    controversy_penalty=5.0, exclude_sin_stocks=True, exclude_fossil_fuels=True,
))

# Score a security (0-100 per pillar, composite with weighted average, AAA-CCC rating)
score: ESGScore = scorer.score_security(
    "AAPL", environmental=72.0, social=68.0, governance=80.0,
    controversies=["supply_chain_labor"], sector="technology",
)

# Screen against exclusion criteria
screen = scorer.screen_security("XOM", industry="oil_gas", min_score=50.0)
# .passed, .excluded_reasons

# Portfolio aggregation and sector ranking
summary = scorer.portfolio_summary({"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4})
tech_ranked = scorer.rank_by_sector("technology")

# Impact tracking against benchmarks
tracker = ImpactTracker()
tracker.record_metric("AAPL", ImpactCategory.CARBON_FOOTPRINT, 85.0, trend="improving")
impact = tracker.portfolio_impact({"AAPL": 0.5, "MSFT": 0.5})
# Returns: dict[ImpactCategory, ImpactMetric] with .value and .benchmark
```

## Key classes and methods

| Module | Class | Key Methods | Description |
|--------|-------|-------------|-------------|
| `src.crossasset.intermarket` | `IntermarketAnalyzer` | `rolling_correlation()`, `relative_strength()`, `detect_divergence()`, `correlation_matrix()` | Intermarket correlation, relative strength, divergence |
| `src.crossasset.leadlag` | `LeadLagDetector` | `detect()`, `detect_all_pairs()`, `extract_signal()` | Cross-correlation lead-lag with stability |
| `src.crossasset.momentum` | `CrossAssetMomentum` | `time_series_momentum()`, `cross_sectional_momentum()`, `mean_reversion_signals()`, `trend_signals()` | Momentum/mean-reversion with Z-score |
| `src.crossasset.signals` | `CrossAssetSignalGenerator` | `generate()`, `generate_all()` | Composite signal from all components |
| `src.crypto_options.pricing` | `CryptoOptionPricer` | `price()`, `implied_vol()`, `build_vol_surface()` | Black-76, Greeks, Newton-Raphson IV |
| `src.crypto_options.analytics` | `CryptoDerivativesAnalyzer` | `record_funding_rate()`, `compute_basis()`, `put_call_ratio()`, `max_pain()` | Funding, basis, PCR, max pain |
| `src.blockchain.settlement` | `SettlementEngine` | `initiate_settlement()`, `submit_settlement()`, `confirm_settlement()`, `initiate_atomic_swap()` | Blockchain settlement lifecycle |
| `src.blockchain.monitor` | `TransactionMonitor` | `watch()`, `update_confirmations()`, `mark_reverted()` | Tx confirmation tracking |
| `src.multi_asset.crypto` | `CryptoFactorModel` | `compute_scores()`, `rank_universe()` | 5-factor crypto scoring |
| `src.multi_asset.crypto` | `CryptoDataProvider` | `register_asset()`, `set_on_chain_metrics()`, `get_returns()` | Crypto data provider |
| `src.multi_asset.futures` | `FuturesManager` | `get_contract_spec()`, `get_front_month()`, `check_roll()`, `build_calendar_spread()` | Futures, auto-roll, margin |
| `src.multi_asset.cross_asset` | `CrossAssetOptimizer` | `optimize()`, `from_template()`, `build_covariance()`, `risk_budget_allocation()` | Multi-asset allocation |
| `src.multi_asset.risk` | `UnifiedRiskManager` | `compute_portfolio_risk()`, `check_margin()`, `get_margin_alerts()` | Cross-asset VaR and risk |
| `src.credit.spreads` | `SpreadAnalyzer` | `add_spread()`, `analyze()`, `term_structure()`, `relative_value()` | Credit spread Z-scores |
| `src.credit.default` | `DefaultEstimator` | Default probability estimation | Merton/reduced-form models |
| `src.credit.rating` | `RatingTracker` | Rating migration tracking | Credit rating changes |
| `src.credit.structure` | `DebtAnalyzer` | Debt structure analysis | Maturity profile |
| `src.esg.scoring` | `ESGScorer` | `score_security()`, `screen_security()`, `portfolio_summary()`, `rank_by_sector()` | ESG scoring and screening |
| `src.esg.impact` | `ImpactTracker` | `record_metric()`, `portfolio_impact()` | Impact vs benchmarks |

## Common patterns

### End-to-end cross-asset signal pipeline

```python
from src.crossasset import (
    IntermarketAnalyzer, LeadLagDetector, CrossAssetMomentum, CrossAssetSignalGenerator,
)

returns = {"SPY": spy_ret, "TLT": tlt_ret, "GLD": gld_ret, "BTC": btc_ret}

# 1. Momentum  2. Lead-lag  3. Correlations  4. Composite signals
mom_signals = CrossAssetMomentum().cross_sectional_momentum(returns)
ll_results = LeadLagDetector().detect_all_pairs(returns)
ll_signals = {r.lagger: LeadLagDetector().extract_signal(returns[r.leader], r.optimal_lag)
              for r in ll_results}

im = IntermarketAnalyzer()
corr_map = {a: [im.rolling_correlation(returns[a], returns[b], a, b)
                for b in returns if b != a] for a in returns}

signals = CrossAssetSignalGenerator().generate_all(
    mom_signals, ll_results, ll_signals, corr_map,
)
```

### Crypto options trading workflow

```python
from src.crypto_options import CryptoOptionPricer, CryptoDerivativesAnalyzer, CryptoExchange

pricer = CryptoOptionPricer()
analyzer = CryptoDerivativesAnalyzer()

avg_funding = analyzer.average_funding_rate("BTC", CryptoExchange.DERIBIT, 30)
quote = pricer.price(contract, spot=48000.0, vol=0.80)
surface = pricer.build_vol_surface("BTC", 48000.0, market_quotes)
max_pain_strike = analyzer.max_pain(market_quotes, spot=48000.0)
```

### Multi-asset portfolio with risk monitoring

```python
from src.multi_asset import CrossAssetOptimizer, UnifiedRiskManager, AssetClass

portfolio = CrossAssetOptimizer().from_template("balanced", symbols_by_class, 1_000_000)
report = UnifiedRiskManager().compute_portfolio_risk(portfolio, returns=daily_ret, covariance=cov)
if report.correlation_regime == "stress":
    print("ALERT: Correlation stress -- consider de-risking")
```

### ESG-integrated portfolio construction

```python
from src.esg import ESGScorer, ImpactTracker, ImpactCategory

scorer = ESGScorer()
for sym in symbols:
    scorer.score_security(sym, environmental=e[sym], social=s[sym], governance=g[sym])

screened = [sym for sym in symbols if scorer.screen_security(sym, industries[sym], 40).passed]
summary = scorer.portfolio_summary({s: w[s] for s in screened})
tracker = ImpactTracker()
for sym in screened:
    tracker.record_metric(sym, ImpactCategory.CARBON_FOOTPRINT, carbon[sym])
impact = tracker.portfolio_impact({s: w[s] for s in screened})
```
