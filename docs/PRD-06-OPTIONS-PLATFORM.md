# PRD-06: Advanced Options Trading Platform

**Priority**: P1 | **Phase**: 3 | **Status**: Draft

---

## Problem Statement

Axion has basic options chain viewing and simple strategy recommendations, but lacks Greeks calculation, probability analysis, strategy backtesting, volatility surface modeling, and risk graphing. Options are where sophisticated investors generate outsized returns—and where they need the most analytical support.

---

## Goals

1. **Full Greeks computation** (Delta, Gamma, Theta, Vega, Rho)
2. **Volatility surface** modeling (smile, skew, term structure)
3. **Strategy builder** with risk/reward visualization
4. **Probability of profit** calculation for every strategy
5. **Options backtesting** with historical IV data
6. **Unusual options activity** detection and alerting

---

## Detailed Requirements

### R1: Options Pricing Engine

#### R1.1: Greeks Calculator
```python
class OptionsGreeks:
    def black_scholes(self, S, K, T, r, sigma, option_type='call'):
        """Black-Scholes pricing with all Greeks."""
        d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)

        if option_type == 'call':
            price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
            delta = norm.cdf(d1)
        else:
            price = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
            delta = norm.cdf(d1) - 1

        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        theta = (-S*norm.pdf(d1)*sigma/(2*np.sqrt(T))
                 - r*K*np.exp(-r*T)*norm.cdf(d2)) / 365
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        rho = K * T * np.exp(-r*T) * norm.cdf(d2) / 100

        return OptionPrice(
            price=price, delta=delta, gamma=gamma,
            theta=theta, vega=vega, rho=rho
        )

    def implied_volatility(self, market_price, S, K, T, r, option_type):
        """Newton-Raphson IV solver."""
        sigma = 0.30  # initial guess
        for _ in range(100):
            price = self.black_scholes(S, K, T, r, sigma, option_type).price
            vega = self.black_scholes(S, K, T, r, sigma, option_type).vega * 100
            if abs(vega) < 1e-10:
                break
            sigma -= (price - market_price) / vega
            if sigma < 0.001:
                sigma = 0.001
        return sigma
```

#### R1.2: Advanced Pricing Models
| Model | Use Case |
|-------|----------|
| Black-Scholes | European options (baseline) |
| Binomial Tree | American options (early exercise) |
| Monte Carlo | Exotic payoffs, path-dependent |
| SABR | Volatility surface calibration |
| Heston | Stochastic volatility pricing |

### R2: Volatility Surface

#### R2.1: IV Surface Construction
```python
class VolatilitySurface:
    def build(self, symbol: str) -> Surface:
        """Build 3D volatility surface from options chain."""
        chains = self.data.get_options_chains(symbol)

        # Extract IVs for all strikes and expirations
        points = []
        for expiry in chains:
            for strike, option in expiry.items():
                iv = self.greeks.implied_volatility(
                    option.mid_price, option.underlying_price,
                    strike, option.dte / 365, self.risk_free_rate,
                    option.type
                )
                points.append({
                    'moneyness': strike / option.underlying_price,
                    'dte': option.dte,
                    'iv': iv
                })

        # Interpolate surface using SVI parametrization
        return self._fit_svi_surface(points)
```

#### R2.2: Volatility Analytics
| Metric | Description |
|--------|-------------|
| ATM IV | At-the-money implied volatility |
| IV Skew | 25-delta put IV - 25-delta call IV |
| IV Term Structure | IV across expirations at ATM |
| IV Percentile | Current IV vs 1-year history |
| IV Rank | (Current - 52w Low) / (52w High - 52w Low) |
| HV-IV Spread | Historical vol - Implied vol |
| Realized Vol Cone | Distribution of realized vol by timeframe |

### R3: Strategy Builder

#### R3.1: Pre-Built Strategies
| Strategy | Legs | Outlook | Max Profit | Max Loss |
|----------|------|---------|------------|----------|
| Long Call | 1 | Bullish | Unlimited | Premium |
| Long Put | 1 | Bearish | Strike - Premium | Premium |
| Covered Call | 2 | Neutral-Bull | Premium + upside | Downside |
| Cash-Secured Put | 2 | Neutral-Bull | Premium | Strike - Premium |
| Bull Call Spread | 2 | Bullish | Width - Debit | Debit |
| Bear Put Spread | 2 | Bearish | Width - Debit | Debit |
| Iron Condor | 4 | Neutral | Credit | Width - Credit |
| Iron Butterfly | 4 | Neutral | Credit | Width - Credit |
| Straddle | 2 | Vol expansion | Unlimited | Premium |
| Strangle | 2 | Vol expansion | Unlimited | Premium |
| Calendar Spread | 2 | Neutral/Vol | Varies | Debit |
| Diagonal Spread | 2 | Directional | Varies | Debit |
| Jade Lizard | 3 | Neutral-Bull | Credit | Downside |
| Ratio Spread | 2+ | Directional | Varies | Varies |

#### R3.2: Strategy Analyzer
```python
class StrategyAnalyzer:
    def analyze(self, legs: list[OptionLeg]) -> StrategyAnalysis:
        return StrategyAnalysis(
            max_profit=self._calc_max_profit(legs),
            max_loss=self._calc_max_loss(legs),
            breakeven_points=self._calc_breakevens(legs),
            probability_of_profit=self._calc_pop(legs),
            expected_value=self._calc_expected_value(legs),
            risk_reward_ratio=max_profit / abs(max_loss),
            net_greeks=self._aggregate_greeks(legs),
            margin_requirement=self._calc_margin(legs),
            capital_required=self._calc_capital(legs),
            annualized_return=self._calc_annualized(legs),
        )

    def payoff_diagram(self, legs: list[OptionLeg],
                       price_range: tuple) -> PayoffCurve:
        """Generate P&L at expiration across price range."""
        prices = np.linspace(price_range[0], price_range[1], 200)
        pnl = np.zeros_like(prices)

        for leg in legs:
            if leg.type == 'call':
                intrinsic = np.maximum(prices - leg.strike, 0)
            else:
                intrinsic = np.maximum(leg.strike - prices, 0)

            leg_pnl = (intrinsic - leg.premium) * leg.quantity * 100
            pnl += leg_pnl

        return PayoffCurve(prices=prices, pnl=pnl)
```

#### R3.3: Probability of Profit (PoP)
```python
def probability_of_profit(self, legs, underlying_price, iv, dte):
    """Monte Carlo probability of profit estimation."""
    n_simulations = 100_000
    dt = dte / 365

    # Simulate underlying price at expiration (GBM)
    z = np.random.standard_normal(n_simulations)
    ST = underlying_price * np.exp(
        (-0.5 * iv**2) * dt + iv * np.sqrt(dt) * z
    )

    # Calculate P&L for each simulation
    pnl = np.zeros(n_simulations)
    for leg in legs:
        if leg.type == 'call':
            intrinsic = np.maximum(ST - leg.strike, 0)
        else:
            intrinsic = np.maximum(leg.strike - ST, 0)
        pnl += (intrinsic - leg.premium) * leg.quantity * 100

    return (pnl > 0).mean()  # % of simulations profitable
```

### R4: Risk Visualization

#### R4.1: P&L Diagrams
- **At Expiration**: Classic hockey-stick payoff diagram
- **Before Expiration**: 3D surface showing P&L vs price vs time
- **Greeks Profile**: Delta, gamma, theta, vega across price range
- **Scenario Analysis**: P&L at various IV levels (+/- 10%, 20%, 30%)

#### R4.2: Strategy Comparison
Side-by-side comparison of strategies:
```
Strategy Comparison: AAPL ($178)
═══════════════════════════════════════════════════════
                    Bull Call    Iron Condor   Covered Call
                    Spread
Max Profit          $320        $180          $450
Max Loss           -$180       -$320         -$17,350
Breakeven           $181.80     $176.20/$183.80  $173.50
PoP                 45%         62%           68%
Risk/Reward         1.78:1      0.56:1        0.03:1
Capital Required    $180        $320          $17,800
Ann. Return (max)   213%        67%           30%
Net Delta           0.45        0.02          0.55
Net Theta          -$2.10      +$3.40        +$1.80
```

### R5: Unusual Options Activity

#### R5.1: Detection Criteria
| Signal | Threshold | Interpretation |
|--------|-----------|---------------|
| Volume Spike | >5x avg daily volume | Unusual interest |
| OI Surge | >3x avg OI change | New large positions |
| IV Spike | IV rank >80th percentile | Anticipated move |
| Large Block | >1000 contracts single trade | Institutional flow |
| Sweep Order | Multiple exchanges hit rapidly | Aggressive buyer |
| Put/Call Skew | P/C ratio >2x or <0.3x | Directional bet |
| Near-Expiry Volume | >10x avg in weekly options | Short-term catalyst |

#### R5.2: Flow Dashboard
```
UNUSUAL OPTIONS ACTIVITY - Real Time
═══════════════════════════════════════════════
Symbol  Type   Strike  Exp      Volume  OI    Premium   Signal
NVDA    CALL   $140    Feb 21   45,200  8,100 $12.5M   SWEEP
AAPL    PUT    $170    Feb 14   22,100  3,400 $4.2M    BLOCK
TSLA    CALL   $280    Mar 21   18,700  5,200 $8.1M    VOL SPIKE
META    CALL   $600    Feb 21   15,400  2,100 $6.8M    OI SURGE
```

### R6: Options Backtesting

#### R6.1: Historical IV Data
- Store historical IV surfaces (daily snapshots)
- At minimum: ATM IV for all expirations
- Ideally: Full surface (strikes x expirations)
- Source: CBOE, iVolatility, or reconstructed from EOD options prices

#### R6.2: Strategy Backtester
```python
class OptionsBacktester:
    def backtest_strategy(self,
                          strategy: StrategyTemplate,
                          underlying: str,
                          start: date,
                          end: date,
                          entry_rules: EntryRules,
                          exit_rules: ExitRules) -> BacktestResult:
        """
        Example: Backtest selling 30-delta puts on SPY
        when IV rank > 50%, held to 50% profit or 21 DTE.
        """
        trades = []
        for entry_date in self._get_entry_dates(start, end, entry_rules):
            chain = self._get_historical_chain(underlying, entry_date)
            legs = strategy.select_legs(chain, entry_date)

            exit_date, exit_pnl = self._simulate_to_exit(
                legs, entry_date, exit_rules
            )
            trades.append(Trade(entry_date, exit_date, legs, exit_pnl))

        return BacktestResult(
            trades=trades,
            total_pnl=sum(t.pnl for t in trades),
            win_rate=sum(1 for t in trades if t.pnl > 0) / len(trades),
            avg_trade=np.mean([t.pnl for t in trades]),
            max_drawdown=self._calc_drawdown(trades),
            sharpe=self._calc_sharpe(trades),
        )
```

---

## Claude Integration

```
User: "Build me an iron condor on SPY with 80% PoP"

Claude: Here's an iron condor on SPY ($502.30) targeting ~80% probability
of profit:

Strategy: Iron Condor
├── Sell $490 Put  (Feb 21)  → +$1.85
├── Buy  $485 Put  (Feb 21)  → -$1.20
├── Sell $515 Call (Feb 21)  → +$1.45
├── Buy  $520 Call (Feb 21)  → -$0.90
├── Net Credit: $1.20 ($120 per contract)
├── Max Loss: $3.80 ($380 per contract)
├── Breakevens: $488.80 / $516.20
├── PoP: 78.4%
├── IV Rank: 62 (favorable for selling)
└── Expected Value: +$42 per contract

[Shows payoff diagram and Greeks profile]

Shall I place this trade in paper or live?
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Greeks accuracy vs market | <2% deviation |
| IV surface calibration error | <1% RMSE |
| PoP prediction accuracy | Within 5% of realized |
| Strategy backtester speed | <10s for 5-year test |
| Unusual activity detection | >80% of major moves caught |

---

## Dependencies

- PRD-01 (Data Infrastructure) for real-time options data
- PRD-03 (Execution System) for options order execution
- PRD-04 (Risk Management) for portfolio-level options risk
- Historical IV data source (CBOE, iVolatility)

---

*Owner: Derivatives Engineering Lead*
*Last Updated: January 2026*
