# PRD-09: Professional Backtesting Engine

**Priority**: P0 | **Phase**: 1 | **Status**: Draft

---

## Problem Statement

Axion's backtester supports monthly rebalancing with no transaction costs, no parameter optimization, no multi-timeframe testing, and no robust out-of-sample validation. Professional backtesting requires minute-level granularity, realistic cost modeling, walk-forward optimization, and Monte Carlo analysis to distinguish real alpha from luck.

---

## Goals

1. **Multi-timeframe** backtesting (minute to monthly bars)
2. **Realistic execution modeling** (slippage, commissions, market impact)
3. **Walk-forward optimization** to prevent overfitting
4. **Monte Carlo analysis** for statistical significance
5. **Strategy comparison** framework with proper benchmarking
6. **Visual reporting** with tear sheets and trade analysis

---

## Detailed Requirements

### R1: Backtest Engine Core

#### R1.1: Event-Driven Architecture
```python
class BacktestEngine:
    """Event-driven backtesting framework."""

    def __init__(self, config: BacktestConfig):
        self.data_handler = HistoricalDataHandler(config)
        self.strategy = config.strategy
        self.portfolio = SimulatedPortfolio(config.initial_capital)
        self.execution = SimulatedExecution(config.cost_model)
        self.risk_manager = BacktestRiskManager(config.risk_rules)

    async def run(self) -> BacktestResult:
        """Main backtest loop."""
        for event in self.data_handler.stream_bars():
            # 1. Update market data
            self.portfolio.update_market_data(event)

            # 2. Generate signals
            signals = self.strategy.on_bar(event)

            # 3. Risk check
            approved_signals = self.risk_manager.validate(signals, self.portfolio)

            # 4. Execute orders
            for signal in approved_signals:
                fill = self.execution.simulate_fill(signal, event)
                self.portfolio.process_fill(fill)

            # 5. Record state
            self.portfolio.record_snapshot()

        return self._compile_results()
```

#### R1.2: Configuration
```python
@dataclass
class BacktestConfig:
    # Time range
    start_date: date
    end_date: date
    bar_type: str = '1d'  # '1m', '5m', '15m', '1h', '1d'

    # Capital
    initial_capital: float = 100_000
    currency: str = 'USD'

    # Strategy
    strategy: Strategy = None
    universe: str = 'sp500'

    # Execution model
    cost_model: CostModel = RealisticCostModel()
    fill_model: FillModel = VolumeParticipationFill()

    # Risk rules (same as live trading)
    risk_rules: RiskConfig = DEFAULT_RISK_CONFIG

    # Rebalancing
    rebalance_frequency: str = 'monthly'  # daily, weekly, monthly
    rebalance_day: int = 1  # Day of period

    # Data
    adjust_for_splits: bool = True
    adjust_for_dividends: bool = True
    survivorship_bias_free: bool = True
```

### R2: Realistic Execution Modeling

#### R2.1: Cost Models
```python
class RealisticCostModel:
    """Model real-world trading costs."""

    def __init__(self,
                 commission_per_share: float = 0.0,     # Commission-free era
                 sec_fee_rate: float = 0.0000278,       # SEC fee
                 taf_fee: float = 0.000166,             # FINRA TAF
                 min_spread_bps: float = 1.0,           # Min half-spread
                 market_impact_bps_per_pct_adv: float = 10.0):
        self.config = {
            'commission': commission_per_share,
            'sec_fee': sec_fee_rate,
            'taf_fee': taf_fee,
            'spread': min_spread_bps,
            'impact': market_impact_bps_per_pct_adv,
        }

    def estimate_cost(self, order: Order, market_data: BarData) -> float:
        """Total cost = commission + spread + market impact + fees."""
        notional = order.qty * market_data.close

        # Commission
        commission = order.qty * self.config['commission']

        # Half-spread cost (always pay the spread)
        spread_cost = notional * self.config['spread'] / 10_000

        # Market impact (linear in participation rate)
        adv = market_data.volume * market_data.close
        participation = notional / adv
        impact_cost = notional * participation * self.config['impact'] / 10_000

        # Regulatory fees (sells only)
        sec_fee = notional * self.config['sec_fee'] if order.side == 'sell' else 0
        taf_fee = order.qty * self.config['taf_fee'] if order.side == 'sell' else 0

        return commission + spread_cost + impact_cost + sec_fee + taf_fee
```

#### R2.2: Fill Models
| Model | Description | Use Case |
|-------|-------------|----------|
| Immediate | Fill at bar close price | Baseline (optimistic) |
| VWAP | Fill at volume-weighted price | Realistic daily |
| Volume Participation | Fill proportional to volume | Large orders |
| Slippage | Close + random spread | Conservative |
| Limit Order | Fill only if price touches limit | Passive execution |

### R3: Walk-Forward Optimization

#### R3.1: Framework
```python
class WalkForwardOptimizer:
    def run(self,
            strategy_class: type,
            param_grid: dict,
            data: pd.DataFrame,
            in_sample_pct: float = 0.70,
            n_windows: int = 5) -> WalkForwardResult:
        """
        For each window:
        1. Optimize params on in-sample data
        2. Test on out-of-sample data
        3. Combine out-of-sample results

        This prevents overfitting by never testing on training data.
        """
        windows = self._generate_windows(data, n_windows, in_sample_pct)
        oos_results = []

        for window in windows:
            # In-sample optimization
            best_params = self._optimize_insample(
                strategy_class, param_grid,
                window.in_sample_data
            )

            # Out-of-sample test
            strategy = strategy_class(**best_params)
            oos_result = self._backtest(strategy, window.out_of_sample_data)
            oos_results.append(oos_result)

        # Combine out-of-sample periods
        combined = self._combine_results(oos_results)

        return WalkForwardResult(
            in_sample_sharpe=np.mean([w.is_sharpe for w in windows]),
            out_of_sample_sharpe=combined.sharpe,
            efficiency_ratio=combined.sharpe / np.mean([w.is_sharpe for w in windows]),
            oos_equity_curve=combined.equity_curve,
            param_stability=self._assess_param_stability(windows),
        )
```

#### R3.2: Efficiency Ratio
The walk-forward efficiency ratio measures how well in-sample performance translates to out-of-sample:
- **>0.5**: Good — strategy is robust
- **0.3-0.5**: Acceptable — some overfitting
- **<0.3**: Poor — likely overfit, do not deploy

### R4: Monte Carlo Analysis

#### R4.1: Bootstrapped Confidence Intervals
```python
class MonteCarloAnalyzer:
    def bootstrap_analysis(self,
                           trades: list[Trade],
                           n_simulations: int = 10_000) -> MCResult:
        """Bootstrap trade sequences to assess statistical significance."""
        sharpe_dist = []
        cagr_dist = []
        max_dd_dist = []

        for _ in range(n_simulations):
            # Resample trades with replacement
            sample = np.random.choice(trades, size=len(trades), replace=True)

            # Compute metrics on resampled sequence
            equity = self._build_equity_curve(sample)
            sharpe_dist.append(self._calc_sharpe(equity))
            cagr_dist.append(self._calc_cagr(equity))
            max_dd_dist.append(self._calc_max_drawdown(equity))

        return MCResult(
            sharpe_mean=np.mean(sharpe_dist),
            sharpe_95ci=(np.percentile(sharpe_dist, 2.5),
                        np.percentile(sharpe_dist, 97.5)),
            cagr_mean=np.mean(cagr_dist),
            cagr_95ci=(np.percentile(cagr_dist, 2.5),
                      np.percentile(cagr_dist, 97.5)),
            max_dd_mean=np.mean(max_dd_dist),
            max_dd_95ci=(np.percentile(max_dd_dist, 2.5),
                        np.percentile(max_dd_dist, 97.5)),
            pct_profitable=np.mean(np.array(cagr_dist) > 0),
            pct_beats_benchmark=np.mean(np.array(sharpe_dist) > 0),
        )
```

#### R4.2: Randomized Strategy Testing
```python
def is_strategy_significant(self, strategy_sharpe: float,
                            n_random: int = 1000) -> bool:
    """Compare strategy against N random strategies to assess significance.
    Corrects for multiple testing (data snooping)."""
    random_sharpes = []
    for _ in range(n_random):
        random_weights = np.random.dirichlet(np.ones(30))
        random_sharpe = self._backtest_random(random_weights)
        random_sharpes.append(random_sharpe)

    # Strategy must beat 95th percentile of random strategies
    threshold = np.percentile(random_sharpes, 95)
    return strategy_sharpe > threshold
```

### R5: Comprehensive Tear Sheet

#### R5.1: Performance Summary
```
STRATEGY TEAR SHEET: Balanced Factor v2
═══════════════════════════════════════════════════════
Period: Jan 2016 - Jan 2026 (10 years)
Initial Capital: $100,000 → Final: $312,400

RETURNS                          RISK
Annual Return:    12.1%          Volatility:     13.8%
Benchmark (SPY):  10.2%         Downside Vol:    9.1%
Alpha:             1.9%         Max Drawdown:   -18.2%
Best Month:       +8.4%         Avg Drawdown:    -4.1%
Worst Month:      -9.1%         Drawdown Duration: 42 days (avg)
Win Rate:         58.3%         Recovery Time:   31 days (avg)

RISK-ADJUSTED                    COSTS
Sharpe Ratio:     0.88          Total Commissions: $0
Sortino Ratio:    1.33          Total Slippage:    $4,200
Calmar Ratio:     0.67          Total Turnover:    340%
Information Ratio: 0.62         Avg Monthly Turn:  2.8%

STATISTICAL SIGNIFICANCE
Monte Carlo 95% CI (Sharpe): [0.52, 1.24]
Walk-Forward Efficiency:      0.61
Strategy Significant (p<0.05): YES

MONTHLY RETURNS HEATMAP
     Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
2026 +1.2
2025 +2.1  -0.8  +1.4  +3.2  -1.1  +0.8  +2.4  -2.1  +1.6  +0.4  +2.8  +1.1
2024 +0.8  +1.6  +2.1  -0.4  +1.8  -1.2  +3.1  +0.2  -0.8  +2.4  +1.2  +0.6
...
```

#### R5.2: Trade Analysis
```
TRADE ANALYSIS
═══════════════════════════════════════════
Total Trades:       2,847
Profitable:         1,661 (58.3%)
Avg Win:            +3.2%
Avg Loss:           -2.8%
Win/Loss Ratio:     1.14
Profit Factor:      1.60
Avg Hold Period:    22 days

BY SECTOR                    BY FACTOR
Tech:     +$48K (best)       Momentum: +$62K (best)
Energy:   -$3K  (worst)      Value:    +$28K
Healthcare: +$22K            Quality:  +$34K
Financials: +$18K            Growth:   +$21K

LARGEST TRADES
+$4,200  NVDA (held 45 days, momentum signal)
+$3,800  UNH (held 62 days, quality signal)
-$2,900  META (held 18 days, stopped out)
-$2,400  PYPL (held 32 days, factor degradation)
```

### R6: Strategy Comparison Framework

#### R6.1: Head-to-Head Comparison
```python
class StrategyComparator:
    def compare(self, strategies: list[Strategy],
                benchmark: str = 'SPY') -> ComparisonReport:
        """Run all strategies on same data and compare."""
        results = {}
        for strategy in strategies:
            results[strategy.name] = self.engine.backtest(strategy)

        return ComparisonReport(
            returns_table=self._build_returns_table(results),
            risk_table=self._build_risk_table(results),
            correlation_matrix=self._strategy_correlations(results),
            rolling_sharpe=self._rolling_sharpe_comparison(results),
            drawdown_comparison=self._drawdown_comparison(results),
            winner_by_metric={
                'sharpe': max(results, key=lambda s: results[s].sharpe),
                'cagr': max(results, key=lambda s: results[s].cagr),
                'max_dd': min(results, key=lambda s: abs(results[s].max_dd)),
                'win_rate': max(results, key=lambda s: results[s].win_rate),
            }
        )
```

### R7: Survivorship Bias Handling

- Include delisted stocks in historical universe
- Use point-in-time S&P 500 constituents (not current list)
- Handle mergers: convert to acquiring company or close position
- Handle bankruptcies: mark position as $0
- Source: Historical S&P 500 constituent lists from Siblis Research or similar

---

## Performance Targets

| Scenario | Target Speed |
|----------|-------------|
| 10-year daily backtest (30 stocks) | <10 seconds |
| 10-year daily backtest (500 stocks) | <60 seconds |
| 5-year minute backtest (1 stock) | <30 seconds |
| Walk-forward (5 windows, 100 params) | <10 minutes |
| Monte Carlo (10,000 simulations) | <60 seconds |

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Backtest granularity | Monthly | Minute-level |
| Cost modeling | None | Full (spread + impact + fees) |
| Walk-forward capability | None | 5-window standard |
| Statistical testing | None | Monte Carlo + significance |
| Survivorship bias | Present | Eliminated |

---

## Dependencies

- PRD-01 (Data Infrastructure) for historical data depth
- PRD-02 (Factor Engine) for factor score history
- PRD-04 (Risk Management) for backtest risk rules

---

*Owner: Quant Engineering Lead*
*Last Updated: January 2026*
