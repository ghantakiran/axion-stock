# PRD-08: Portfolio Optimization & Construction

**Priority**: P0 | **Phase**: 2 | **Status**: Draft

---

## Problem Statement

Axion's portfolio construction is basic: select top N stocks by composite score, allocate proportional to score, cap at 25%. Professional portfolio construction requires mean-variance optimization, risk parity, tax-aware rebalancing, and constraint-aware allocation. The gap between "top picks" and "optimal portfolio" is where real performance lives.

---

## Goals

1. **Mean-variance optimization** with Black-Litterman views
2. **Risk parity** portfolio construction
3. **Tax-aware rebalancing** with tax-loss harvesting
4. **Transaction cost optimization** (minimize turnover)
5. **Multi-strategy portfolio** (combine factor strategies)
6. **Custom constraints** (ESG, sector, country, etc.)

---

## Detailed Requirements

### R1: Optimization Methods

#### R1.1: Mean-Variance Optimization (Markowitz)
```python
class MeanVarianceOptimizer:
    def optimize(self,
                 expected_returns: pd.Series,
                 cov_matrix: pd.DataFrame,
                 target_return: float = None,
                 target_risk: float = None,
                 constraints: list[Constraint] = None) -> Weights:
        """
        Minimize portfolio variance subject to:
        - Target return (or maximize Sharpe)
        - Weight constraints (0 <= w <= max_weight)
        - Sector constraints
        - Turnover constraints
        """
        n = len(expected_returns)

        # Objective: minimize w' * Sigma * w
        def portfolio_variance(w):
            return w @ cov_matrix.values @ w

        # Constraints
        cons = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Fully invested
        ]
        if target_return:
            cons.append({
                'type': 'ineq',
                'fun': lambda w: w @ expected_returns.values - target_return
            })
        if constraints:
            cons.extend(self._build_constraints(constraints))

        # Bounds
        bounds = [(0, self.max_weight)] * n

        result = minimize(
            portfolio_variance,
            x0=np.ones(n) / n,  # Equal weight start
            method='SLSQP',
            bounds=bounds,
            constraints=cons,
        )

        return Weights(dict(zip(expected_returns.index, result.x)))
```

#### R1.2: Black-Litterman Model
```python
class BlackLitterman:
    """Combine market equilibrium with factor model views."""

    def compute_posterior(self,
                          cov_matrix: pd.DataFrame,
                          market_weights: pd.Series,
                          views: list[View],
                          tau: float = 0.05) -> pd.Series:
        """
        Views from factor model:
        - "AAPL will outperform by 2% monthly" (confidence: 80%)
        - "Tech sector will underperform Energy by 1%" (confidence: 60%)
        """
        # Implied equilibrium returns
        pi = self.risk_aversion * cov_matrix @ market_weights

        # View matrix (P) and view returns (Q)
        P, Q, Omega = self._build_view_matrices(views, cov_matrix)

        # Posterior expected returns
        Sigma = cov_matrix.values
        tau_Sigma = tau * Sigma

        M = np.linalg.inv(
            np.linalg.inv(tau_Sigma) + P.T @ np.linalg.inv(Omega) @ P
        )
        posterior = M @ (
            np.linalg.inv(tau_Sigma) @ pi.values +
            P.T @ np.linalg.inv(Omega) @ Q
        )

        return pd.Series(posterior, index=cov_matrix.index)
```

#### R1.3: Risk Parity
```python
class RiskParityOptimizer:
    """Equal risk contribution from each asset."""

    def optimize(self, cov_matrix: pd.DataFrame) -> Weights:
        n = len(cov_matrix)

        def risk_contribution_error(w):
            port_vol = np.sqrt(w @ cov_matrix.values @ w)
            marginal_contrib = cov_matrix.values @ w
            risk_contrib = w * marginal_contrib / port_vol
            target = port_vol / n  # Equal contribution
            return np.sum((risk_contrib - target) ** 2)

        result = minimize(
            risk_contribution_error,
            x0=np.ones(n) / n,
            method='SLSQP',
            bounds=[(0.01, 0.30)] * n,
            constraints=[{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}],
        )

        return Weights(dict(zip(cov_matrix.index, result.x)))
```

#### R1.4: Minimum Variance
```python
class MinimumVarianceOptimizer:
    """Lowest possible portfolio volatility."""

    def optimize(self, cov_matrix: pd.DataFrame) -> Weights:
        # Special case of MVO with no return target
        return self.mvo.optimize(
            expected_returns=pd.Series(0, index=cov_matrix.index),
            cov_matrix=cov_matrix,
        )
```

#### R1.5: Hierarchical Risk Parity (HRP)
```python
class HRPOptimizer:
    """Correlation-based hierarchical clustering + risk parity.
    More stable than MVO, no matrix inversion needed."""

    def optimize(self, returns: pd.DataFrame) -> Weights:
        # 1. Tree clustering based on correlation distance
        dist = self._correlation_distance(returns)
        link = linkage(dist, method='single')
        sort_ix = self._quasi_diag(link)

        # 2. Recursive bisection
        weights = self._recursive_bisection(
            returns.iloc[:, sort_ix].cov(),
            sort_ix
        )

        return Weights(weights)
```

### R2: Constraint Framework

#### R2.1: Available Constraints
```python
class ConstraintEngine:
    available_constraints = {
        # Position limits
        'min_weight': PositionConstraint(min_pct=0.01),
        'max_weight': PositionConstraint(max_pct=0.15),
        'max_positions': CountConstraint(max_n=30),
        'min_positions': CountConstraint(min_n=10),

        # Sector limits
        'max_sector': SectorConstraint(max_pct=0.35),
        'min_sectors': DiversificationConstraint(min_sectors=5),

        # Factor limits
        'min_quality': FactorConstraint(factor='quality', min_score=0.40),
        'max_beta': RiskConstraint(metric='beta', max_value=1.3),
        'max_volatility': RiskConstraint(metric='volatility', max_value=0.20),

        # Turnover limits
        'max_turnover': TurnoverConstraint(max_one_way=0.30),

        # ESG filters
        'esg_min': ESGConstraint(min_score=50),
        'exclude_sectors': ExclusionConstraint(sectors=['Energy', 'Tobacco']),

        # Liquidity
        'min_market_cap': LiquidityConstraint(min_cap=1e9),
        'min_adv': LiquidityConstraint(min_adv=1e6),
    }
```

#### R2.2: Custom Constraint Builder
Users can define custom constraints via UI:
```
Portfolio Constraints
├── Position Size:    1% - 15%
├── Number of Stocks: 15 - 30
├── Max Sector:       35%
├── Min Sectors:      5
├── Max Beta:         1.3
├── Min Quality:      40th percentile
├── Max Turnover:     30% monthly
├── ESG Filter:       Exclude fossil fuels
└── Min Market Cap:   $1B
```

### R3: Tax-Aware Portfolio Management

#### R3.1: Tax-Loss Harvesting
```python
class TaxLossHarvester:
    def identify_harvest_candidates(self,
                                     positions: list[Position],
                                     min_loss: float = 500) -> list[HarvestCandidate]:
        """Find positions with unrealized losses for tax harvesting."""
        candidates = []
        for pos in positions:
            if pos.unrealized_pnl < -min_loss:
                # Find replacement (similar factor profile, different ticker)
                replacement = self._find_replacement(pos)
                tax_savings = abs(pos.unrealized_pnl) * self.tax_rate

                candidates.append(HarvestCandidate(
                    position=pos,
                    unrealized_loss=pos.unrealized_pnl,
                    estimated_tax_savings=tax_savings,
                    replacement=replacement,
                    wash_sale_risk=self._check_wash_sale(pos),
                ))

        return sorted(candidates, key=lambda x: x.estimated_tax_savings,
                       reverse=True)

    def _find_replacement(self, position: Position) -> str:
        """Find a similar stock that avoids wash sale rule."""
        # Same sector, similar factor profile, different company
        sector_peers = self.universe.get_sector_peers(position.symbol)
        factor_profile = self.factors.get_scores(position.symbol)

        best_match = None
        best_similarity = 0
        for peer in sector_peers:
            peer_profile = self.factors.get_scores(peer)
            similarity = self._cosine_similarity(factor_profile, peer_profile)
            if similarity > best_similarity and peer != position.symbol:
                best_match = peer
                best_similarity = similarity

        return best_match
```

#### R3.2: Tax-Aware Rebalancing
- Prefer selling losers (harvest losses) over winners
- Track short-term vs long-term holding periods
- Defer gains within 30 days of long-term threshold (1 year)
- Estimate tax impact of each rebalance trade
- Show after-tax vs pre-tax returns

### R4: Portfolio Templates

#### R4.1: Pre-Built Strategies
| Template | Description | Holdings | Rebalance |
|----------|-------------|----------|-----------|
| **Aggressive Alpha** | Top factor scores, concentrated | 10-15 | Monthly |
| **Balanced Factor** | Equal factor exposure, diversified | 25-30 | Monthly |
| **Quality Income** | High quality + dividend yield | 20-25 | Quarterly |
| **Momentum Rider** | Top momentum with trend filters | 10-15 | Bi-weekly |
| **Value Contrarian** | Deep value with quality floor | 15-20 | Monthly |
| **Low Volatility** | Min-variance with quality tilt | 25-30 | Quarterly |
| **Risk Parity** | Equal risk from each position | 20-30 | Monthly |
| **All-Weather** | Multi-asset (stocks + bonds + gold) | 10-20 | Quarterly |

#### R4.2: Strategy Blending
```python
class StrategyBlender:
    def blend(self, strategies: list[tuple[str, float]]) -> Portfolio:
        """
        Combine multiple strategies with custom weights.
        Example: 60% Balanced Factor + 30% Quality Income + 10% Momentum
        """
        combined_weights = {}
        for strategy_name, allocation in strategies:
            strategy = self.templates[strategy_name]
            portfolio = strategy.construct()
            for symbol, weight in portfolio.weights.items():
                if symbol not in combined_weights:
                    combined_weights[symbol] = 0
                combined_weights[symbol] += weight * allocation

        # Re-normalize
        total = sum(combined_weights.values())
        return Portfolio({s: w / total for s, w in combined_weights.items()})
```

### R5: Portfolio Analytics

#### R5.1: Efficient Frontier Visualization
- Plot efficient frontier with current portfolio marked
- Show tangency portfolio (max Sharpe)
- Show minimum variance portfolio
- Allow user to click on frontier to see composition

#### R5.2: Portfolio X-Ray
```
PORTFOLIO X-RAY
═══════════════════════════════════════════
Positions: 22 stocks  |  Cash: 2.1%

SECTOR ALLOCATION           FACTOR EXPOSURE
Technology:   28.3% ████    Value:      0.62 ████████
Healthcare:   18.1% ███     Momentum:   0.71 █████████
Financials:   14.2% ██      Quality:    0.78 ██████████
Consumer:     12.8% ██      Growth:     0.55 ███████
Industrials:  11.4% ██      Volatility: 0.48 ██████
Energy:        7.1% █       Sentiment:  0.64 ████████
Other:         6.0% █

RISK METRICS                 PERFORMANCE (YTD)
Beta:           1.08         Return:    +8.4%
Volatility:     14.2%        Benchmark: +6.1%
Sharpe:         1.67         Alpha:     +2.3%
Max Drawdown:  -6.2%         IR:        0.82
VaR (95%):     -1.8%         Win Rate:  62%

CONCENTRATION
Top 5:          41.2%        Avg Correlation: 0.38
HHI:            612          Effective N:     16.3
```

#### R5.3: What-If Analysis
```python
class WhatIfAnalyzer:
    def analyze(self, portfolio: Portfolio,
                changes: dict[str, float]) -> WhatIfResult:
        """
        "What if I add 5% NVDA and reduce AAPL by 5%?"
        """
        new_portfolio = portfolio.copy()
        for symbol, delta in changes.items():
            new_portfolio.adjust(symbol, delta)

        return WhatIfResult(
            risk_change=new_portfolio.risk - portfolio.risk,
            return_change=new_portfolio.expected_return - portfolio.expected_return,
            sharpe_change=new_portfolio.sharpe - portfolio.sharpe,
            sector_impact=self._sector_delta(portfolio, new_portfolio),
            factor_impact=self._factor_delta(portfolio, new_portfolio),
            trades_required=self._compute_trades(portfolio, new_portfolio),
            estimated_cost=self._estimate_cost(portfolio, new_portfolio),
        )
```

---

## Claude Integration

```
User: "Build me a 20-stock portfolio with $100K that maximizes Sharpe ratio,
       no more than 30% in tech, and minimum quality score of 50th percentile"

Claude: Here's your optimized portfolio:

Optimization: Mean-Variance (Max Sharpe)
Constraints: 20 stocks, tech ≤30%, quality ≥50th pctile, pos ≤10%

Expected Annual Return: 14.2%
Expected Volatility: 12.8%
Sharpe Ratio: 1.11
Portfolio Beta: 0.95

[Shows allocation table, sector breakdown, factor exposure radar]

Top Holdings:
1. NVDA  8.2% ($8,200) - Momentum + Quality leader
2. UNH   7.1% ($7,100) - Quality + Value healthcare
3. JPM   6.8% ($6,800) - Value + Quality financials
...

Shall I execute this portfolio in paper trading?
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Optimizer solve time | <5 seconds for 30-stock portfolio |
| Sharpe improvement vs equal-weight | >0.3 |
| Tax-loss harvest savings (annual) | >$2,000 per $100K |
| Constraint satisfaction | 100% (no violations) |
| Turnover reduction vs naive | >30% lower |

---

## Dependencies

- PRD-02 (Factor Engine) for expected returns and scores
- PRD-03 (Execution System) for rebalancing execution
- PRD-04 (Risk Management) for risk constraints
- scipy, cvxpy for optimization solvers

---

*Owner: Quantitative Engineering Lead*
*Last Updated: January 2026*
