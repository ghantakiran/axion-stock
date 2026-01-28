# PRD-12: Crypto & Futures Expansion

**Priority**: P2 | **Phase**: 6 | **Status**: Draft

---

## Problem Statement

Axion supports only US equities. Modern traders diversify across asset classes — crypto for high growth, futures for hedging and leverage, international equities for diversification. A world-class platform must be multi-asset, enabling cross-asset portfolio optimization and unified risk management.

---

## Goals

1. **Cryptocurrency trading** (BTC, ETH, top 50 by market cap)
2. **Futures trading** (equity index, commodity, treasury)
3. **International equities** (UK, EU, Asian markets)
4. **Cross-asset portfolio optimization**
5. **Unified risk management** across all asset classes

---

## Detailed Requirements

### R1: Cryptocurrency Integration

#### R1.1: Supported Instruments
- **Major**: BTC, ETH, SOL, ADA, DOT, AVAX, LINK, MATIC
- **DeFi**: UNI, AAVE, MKR, CRV, SNX
- **Layer 2**: ARB, OP, MATIC
- **Stablecoins**: USDC, USDT (for pairs)
- **Total**: Top 50 by market cap

#### R1.2: Data Sources
| Source | Type | Coverage |
|--------|------|----------|
| CoinGecko | REST | Prices, market cap, fundamentals |
| Binance | WebSocket | Real-time orderbook, trades |
| Coinbase | REST + WS | US-regulated exchange data |
| Glassnode | REST | On-chain metrics |
| DeFi Llama | REST | TVL, protocol data |

#### R1.3: Crypto Factor Model
| Factor | Metrics | Rationale |
|--------|---------|-----------|
| Value | NVT ratio, MVRV, Stock-to-Flow | On-chain valuation |
| Momentum | 30d/90d/180d returns | Trend following |
| Quality | Developer activity, TVL, transaction count | Network health |
| Sentiment | Social dominance, fear/greed index | Market psychology |
| Network | Active addresses, hash rate, staking ratio | Adoption metrics |

#### R1.4: Crypto Execution
- **Primary**: Alpaca Crypto (commission-free, API compatible)
- **Secondary**: Coinbase Advanced Trade API
- **Features**: Limit orders, stop-loss, DCA scheduling
- **Settlement**: T+0 (instant), 24/7 trading

### R2: Futures Integration

#### R2.1: Supported Contracts
| Category | Contracts |
|----------|-----------|
| **Equity Index** | ES (S&P 500), NQ (Nasdaq), YM (Dow), RTY (Russell) |
| **Treasury** | ZN (10Y Note), ZB (30Y Bond), ZF (5Y Note) |
| **Commodity** | CL (Crude Oil), GC (Gold), SI (Silver), NG (Natural Gas) |
| **Currency** | 6E (EUR), 6J (JPY), 6B (GBP) |
| **Volatility** | VX (VIX Futures) |

#### R2.2: Futures-Specific Features
```python
class FuturesManager:
    def get_contract_specs(self, symbol: str) -> ContractSpec:
        return ContractSpec(
            symbol=symbol,
            multiplier=50,          # ES: $50 per point
            tick_size=0.25,         # Minimum price increment
            tick_value=12.50,       # $ value per tick
            margin_initial=12_650,  # Initial margin requirement
            margin_maintenance=11_500,
            trading_hours="Sun 6pm - Fri 5pm ET",
            expiration_months=['H', 'M', 'U', 'Z'],  # Mar, Jun, Sep, Dec
            settlement='cash',
        )

    def roll_contract(self, position: FuturesPosition) -> RollOrder:
        """Auto-roll expiring contracts to next month."""
        days_to_expiry = (position.expiry - date.today()).days
        if days_to_expiry <= self.roll_threshold:  # Default: 5 days
            next_contract = self._get_next_contract(position.root)
            return RollOrder(
                close_leg=Order(position.symbol, 'sell', position.qty),
                open_leg=Order(next_contract, 'buy', position.qty),
            )
```

#### R2.3: Futures Execution
- **Broker**: Interactive Brokers (primary for futures)
- **Margin tracking**: Real-time margin utilization
- **Roll management**: Auto-roll before expiration
- **Spread trading**: Calendar spreads, inter-commodity spreads

### R3: International Equities

#### R3.1: Market Coverage
| Market | Exchange | Currency | Trading Hours (ET) |
|--------|----------|----------|-------------------|
| UK | LSE | GBP | 3:00 - 11:30 AM |
| Germany | XETRA | EUR | 3:00 - 11:30 AM |
| France | Euronext | EUR | 3:00 - 11:30 AM |
| Japan | TSE | JPY | 7:00 PM - 1:00 AM |
| Hong Kong | HKEX | HKD | 9:30 PM - 4:00 AM |
| Australia | ASX | AUD | 7:00 PM - 1:00 AM |
| Canada | TSX | CAD | 9:30 AM - 4:00 PM |

#### R3.2: FX Considerations
- Real-time FX rates for portfolio valuation
- Currency-hedged returns calculation
- FX risk contribution analysis
- Option to hedge currency exposure

### R4: Cross-Asset Portfolio

#### R4.1: Multi-Asset Optimizer
```python
class CrossAssetOptimizer:
    def optimize(self,
                 assets: dict[str, AssetClass],
                 total_capital: float,
                 constraints: CrossAssetConstraints) -> Portfolio:
        """
        Optimize across equities, crypto, futures, and fixed income.

        Example allocation:
        - US Equities: 50% (factor-optimized)
        - International: 15% (diversification)
        - Crypto: 10% (growth)
        - Gold/Commodities: 10% (inflation hedge)
        - Treasuries: 10% (safety)
        - Cash: 5% (buffer)
        """
        # Estimate cross-asset covariance matrix
        cov = self._build_cross_asset_covariance(assets)

        # Expected returns from factor models + views
        returns = self._get_expected_returns(assets)

        # Optimize with asset-class-specific constraints
        weights = self.optimizer.optimize(
            returns, cov,
            constraints=[
                MaxAssetClass('crypto', 0.15),
                MaxAssetClass('futures_notional', 0.50),
                MinAssetClass('equities', 0.30),
                MaxDrawdown(0.20),
            ]
        )

        return Portfolio(weights)
```

#### R4.2: All-Weather Portfolio Templates
| Template | Equities | Bonds | Gold | Crypto | Commodities | Cash |
|----------|----------|-------|------|--------|-------------|------|
| Conservative | 40% | 40% | 10% | 0% | 5% | 5% |
| Balanced | 50% | 25% | 10% | 5% | 5% | 5% |
| Growth | 60% | 10% | 5% | 15% | 5% | 5% |
| Aggressive | 50% | 0% | 5% | 25% | 10% | 10% |
| Ray Dalio | 30% | 55% | 7.5% | 0% | 7.5% | 0% |

### R5: Unified Risk Management

#### R5.1: Cross-Asset Risk
```python
class UnifiedRiskManager:
    def portfolio_risk(self, portfolio: MultiAssetPortfolio) -> RiskReport:
        # Normalize all positions to USD
        usd_exposures = self._convert_to_usd(portfolio)

        # Cross-asset VaR
        var = self._cross_asset_var(usd_exposures, confidence=0.95)

        # Asset class contribution to risk
        risk_contrib = self._risk_contribution_by_asset_class(usd_exposures)

        # Correlation regime (are correlations breaking down?)
        corr_regime = self._detect_correlation_regime(usd_exposures)

        return RiskReport(
            total_var=var,
            risk_by_asset_class=risk_contrib,
            currency_risk=self._fx_risk(portfolio),
            leverage_ratio=self._calc_leverage(portfolio),
            margin_utilization=self._margin_util(portfolio),
            correlation_regime=corr_regime,
        )
```

#### R5.2: Margin Management
- Real-time margin tracking for futures positions
- Margin call alerts at 80%, 90%, 100% utilization
- Auto-liquidation at 110% to prevent negative balance
- Cross-margining where supported (CME portfolio margin)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Crypto data latency | <500ms |
| Futures contract coverage | Top 15 most liquid |
| International market coverage | 7 major markets |
| Cross-asset optimization time | <15 seconds |
| FX rate accuracy | <1bps from mid-market |

---

## Dependencies

- All previous PRDs for core platform
- Interactive Brokers for futures access
- Alpaca Crypto or Coinbase for crypto execution
- CoinGecko/Glassnode for crypto data
- FX data provider (Open Exchange Rates)

---

*Owner: Multi-Asset Engineering Lead*
*Last Updated: January 2026*
