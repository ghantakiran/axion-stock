# PRD-04: Enterprise Risk Management System

**Priority**: P0 | **Phase**: 2 | **Status**: Draft

---

## Problem Statement

Axion has minimal risk management: a 25% position cap and a 40% sector limit (not enforced). Professional algo platforms require comprehensive risk frameworks covering portfolio risk, position-level risk, drawdown protection, stress testing, and real-time monitoring. Without this, any trading platform is a liability.

---

## Goals

1. **Real-time risk monitoring** with automatic breach alerts
2. **Pre-trade risk checks** that block dangerous orders
3. **Portfolio-level risk metrics** (VaR, CVaR, Sharpe, drawdown)
4. **Stress testing** against historical and hypothetical scenarios
5. **Automatic de-risking** when drawdown limits are breached
6. **Risk-adjusted performance attribution**

---

## Detailed Requirements

### R1: Risk Metrics Engine

#### R1.1: Portfolio Risk Metrics (Real-Time)
| Metric | Formula | Update Freq |
|--------|---------|-------------|
| Portfolio Beta | Weighted avg beta vs SPY | Real-time |
| Portfolio Volatility | Annualized stddev of portfolio returns | Daily |
| Sharpe Ratio | (Return - Rf) / Volatility | Daily |
| Sortino Ratio | (Return - Rf) / Downside Vol | Daily |
| Calmar Ratio | CAGR / Max Drawdown | Daily |
| Information Ratio | Active Return / Tracking Error | Daily |
| Value at Risk (95%) | 5th percentile of return distribution | Daily |
| CVaR / Expected Shortfall | Avg return below VaR | Daily |
| Max Drawdown (current) | Peak-to-current decline | Real-time |
| Correlation to SPY | Rolling 60-day correlation | Daily |
| Tracking Error | StdDev of active returns | Daily |
| Active Share | % of portfolio differing from benchmark | Daily |

#### R1.2: Position Risk Metrics
| Metric | Description |
|--------|-------------|
| Position P&L | Unrealized gain/loss per position |
| Position Drawdown | Max peak-to-current per position |
| Days Held | Holding period tracking |
| Distance to Stop | Current price vs stop-loss level |
| Risk Contribution | % of portfolio risk from this position |
| Marginal VaR | Portfolio VaR change if position removed |
| Beta-Adjusted Exposure | Position size × beta |

#### R1.3: Concentration Metrics
| Metric | Limit | Action |
|--------|-------|--------|
| Single Position | 15% of portfolio | Block new buys |
| Top 5 Positions | 60% of portfolio | Warning alert |
| Single Sector (GICS) | 35% of portfolio | Block same-sector buys |
| Single Industry | 20% of portfolio | Warning alert |
| Correlation Cluster | 3+ positions >0.8 corr | Diversification alert |
| Long/Short Ratio | Configurable | Warning alert |

### R2: VaR & Stress Testing

#### R2.1: Value at Risk Models
```python
class VaRCalculator:
    def historical_var(self, returns: pd.Series,
                       confidence: float = 0.95) -> float:
        """Historical simulation VaR."""
        return -np.percentile(returns, (1 - confidence) * 100)

    def parametric_var(self, portfolio_value: float,
                       volatility: float,
                       confidence: float = 0.95) -> float:
        """Variance-covariance VaR (assumes normal)."""
        z_score = norm.ppf(confidence)
        return portfolio_value * volatility * z_score

    def monte_carlo_var(self, portfolio: Portfolio,
                        n_simulations: int = 10_000,
                        horizon_days: int = 1,
                        confidence: float = 0.95) -> float:
        """Monte Carlo VaR with correlated returns."""
        cov_matrix = self._get_covariance_matrix(portfolio)
        simulated_returns = np.random.multivariate_normal(
            mean=np.zeros(len(portfolio.positions)),
            cov=cov_matrix,
            size=n_simulations
        )
        portfolio_returns = simulated_returns @ portfolio.weights
        return -np.percentile(portfolio_returns, (1 - confidence) * 100)

    def expected_shortfall(self, returns: pd.Series,
                           confidence: float = 0.95) -> float:
        """CVaR: average loss beyond VaR."""
        var = self.historical_var(returns, confidence)
        return -returns[returns <= -var].mean()
```

#### R2.2: Historical Stress Tests
| Scenario | Period | SPY Decline | Description |
|----------|--------|-------------|-------------|
| COVID Crash | Feb-Mar 2020 | -34% | Pandemic shock |
| 2022 Bear Market | Jan-Oct 2022 | -25% | Rate hikes |
| Volmageddon | Feb 2018 | -10% | VIX spike |
| Trade War | May-Dec 2018 | -20% | Tariff escalation |
| GFC | Sep 2008-Mar 2009 | -57% | Financial crisis |
| Dot-Com Bust | Mar 2000-Oct 2002 | -49% | Tech bubble pop |
| Flash Crash | May 6, 2010 | -9% (intraday) | Liquidity vacuum |
| 2011 Downgrade | Aug 2011 | -19% | US debt downgrade |

**For each scenario**: Apply historical factor returns to current portfolio and show estimated P&L impact.

#### R2.3: Hypothetical Stress Tests
| Scenario | Parameters |
|----------|------------|
| Rate Shock +200bps | Interest rates rise 2%, affect duration-sensitive |
| Oil Spike +50% | Energy up, consumer/transport down |
| Tech Correction -30% | Tech/growth factor crash |
| Credit Crisis | HY spreads +500bps, quality flight |
| Dollar Surge +15% | USD strength, multinational earnings hit |
| Inflation Spike +3% | CPI acceleration, Fed response |

### R3: Drawdown Protection System

#### R3.1: Drawdown Rules Engine
```python
class DrawdownProtection:
    rules = [
        DrawdownRule(
            name='portfolio_warning',
            threshold=-0.05,  # -5%
            action='alert',
            message='Portfolio down 5% from peak'
        ),
        DrawdownRule(
            name='portfolio_reduce',
            threshold=-0.10,  # -10%
            action='reduce_exposure',
            target_cash=0.30,  # Move to 30% cash
            message='Portfolio down 10% - reducing to 70% invested'
        ),
        DrawdownRule(
            name='portfolio_emergency',
            threshold=-0.15,  # -15%
            action='liquidate_to_cash',
            target_cash=0.50,  # Move to 50% cash
            message='Portfolio down 15% - emergency de-risk to 50% cash'
        ),
        DrawdownRule(
            name='position_stop',
            threshold=-0.15,  # -15% per position
            action='close_position',
            message='Position stop-loss triggered at -15%'
        ),
        DrawdownRule(
            name='daily_loss_limit',
            threshold=-0.03,  # -3% daily
            action='halt_trading',
            cooldown_hours=24,
            message='Daily loss limit hit - trading halted 24h'
        ),
    ]
```

#### R3.2: Recovery Protocol
After a drawdown de-risk event:
1. **Cooldown Period**: No new buys for 24-48 hours
2. **Gradual Re-Entry**: Scale back in over 5 trading days
3. **Reduced Size**: New positions at 50% normal size for 2 weeks
4. **Enhanced Monitoring**: Alert thresholds tightened by 50%

### R4: Pre-Trade Risk Checks

#### R4.1: Order Validation Pipeline
```python
class PreTradeRiskCheck:
    async def validate(self, order: OrderRequest,
                       portfolio: Portfolio) -> ValidationResult:
        checks = [
            self._check_buying_power(order, portfolio),
            self._check_position_limit(order, portfolio),
            self._check_sector_limit(order, portfolio),
            self._check_concentration(order, portfolio),
            self._check_drawdown_state(portfolio),
            self._check_daily_loss_limit(portfolio),
            self._check_pdt_rule(order, portfolio),
            self._check_liquidity(order),
            self._check_volatility(order),
            self._check_correlation(order, portfolio),
        ]

        results = await asyncio.gather(*checks)
        failures = [r for r in results if not r.passed]

        if any(f.severity == 'block' for f in failures):
            return ValidationResult(approved=False, reasons=failures)
        elif failures:
            return ValidationResult(approved=True, warnings=failures)
        return ValidationResult(approved=True)

    async def _check_liquidity(self, order: OrderRequest) -> CheckResult:
        """Ensure order <5% of average daily volume."""
        adv = await self.data.get_avg_volume(order.symbol, days=20)
        participation = order.qty / adv
        if participation > 0.05:
            return CheckResult(
                passed=False,
                severity='block',
                message=f'Order is {participation:.1%} of ADV (limit: 5%)'
            )
        return CheckResult(passed=True)
```

### R5: Risk Dashboard

#### R5.1: Real-Time Risk Monitor
```
┌─────────────────────────────────────────────────────┐
│  RISK DASHBOARD                          🟢 Normal  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Portfolio VaR (95%, 1-day): $1,247 (1.25%)        │
│  CVaR / Expected Shortfall: $1,892 (1.89%)         │
│  Max Drawdown (current):    -3.2%                  │
│  Portfolio Beta:             1.12                   │
│  Sharpe Ratio (ann.):       1.84                   │
│  Sortino Ratio:             2.31                   │
│                                                     │
│  CONCENTRATION                                      │
│  ├─ Largest Position:  NVDA  12.3% ████████████░   │
│  ├─ Top 5:                   48.7% ████████████░   │
│  ├─ Largest Sector:   Tech  28.1% ████████████░   │
│  └─ Avg Correlation:        0.42   ████████░░░░   │
│                                                     │
│  DRAWDOWN STATUS                                    │
│  ├─ Portfolio:   -3.2%  [░░░░░░░░░░░▓▓░░] -15%   │
│  ├─ Daily P&L:  -0.8%  [░░░░░░░░░▓░░░░░] -3%    │
│  └─ Worst Pos:  -7.1%  [░░░░░░▓▓▓░░░░░░] -15%   │
│                                                     │
│  STRESS TESTS                                       │
│  ├─ COVID Repeat:     -$18,400 (-18.4%)            │
│  ├─ Rate Shock +2%:   -$8,200  (-8.2%)             │
│  └─ Tech Crash -30%:  -$14,100 (-14.1%)            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### R5.2: Alert System
| Alert Level | Condition | Notification |
|-------------|-----------|--------------|
| Info | New position opened | Dashboard update |
| Warning | Position >10% of portfolio | Dashboard + in-app |
| Critical | Drawdown >5% | Dashboard + email + SMS |
| Emergency | Drawdown >10% | Auto de-risk + all channels |

### R6: Risk-Adjusted Performance Attribution

#### R6.1: Brinson Attribution
Decompose portfolio returns into:
- **Allocation Effect**: Return from sector weight decisions
- **Selection Effect**: Return from stock picking within sectors
- **Interaction Effect**: Combined allocation + selection
- **Total Active Return**: Sum of all effects

#### R6.2: Factor Attribution
Decompose returns by factor contribution:
```
Total Return: +12.4%
├── Market (Beta):      +8.2%  (66%)
├── Value Factor:       +1.1%  (9%)
├── Momentum Factor:    +2.3%  (19%)
├── Quality Factor:     +0.5%  (4%)
├── Growth Factor:      +0.8%  (6%)
├── Residual (Alpha):   -0.5%  (-4%)
```

---

## Configuration Defaults

```python
DEFAULT_RISK_CONFIG = {
    'max_position_pct': 0.15,
    'max_sector_pct': 0.35,
    'max_top5_pct': 0.60,
    'max_correlation': 0.85,
    'position_stop_loss': -0.15,
    'portfolio_drawdown_warning': -0.05,
    'portfolio_drawdown_reduce': -0.10,
    'portfolio_drawdown_emergency': -0.15,
    'daily_loss_limit': -0.03,
    'max_portfolio_beta': 1.5,
    'var_confidence': 0.95,
    'var_horizon_days': 1,
    'min_cash_pct': 0.02,
    'max_adv_participation': 0.05,
}
```

All limits are user-configurable with minimum floors (cannot disable stop-loss below -25%).

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Pre-trade check latency | <100ms |
| Risk metric update frequency | Every 1 minute |
| Stress test execution | <30 seconds for all scenarios |
| False positive rate (blocked good trades) | <5% |
| Drawdown protection activation accuracy | >90% |

---

## Dependencies

- PRD-01 (Data Infrastructure) for real-time data and covariance calculation
- PRD-02 (Factor Engine) for factor attribution
- PRD-03 (Execution System) for pre-trade checks and auto de-risking

---

*Owner: Risk Engineering Lead*
*Last Updated: January 2026*
