# PRD-20: Tax Optimization System

**Priority**: P1 | **Phase**: 10 | **Status**: Draft

---

## Problem Statement

Traders and investors lose significant returns to taxes through suboptimal tax management. Without proper tools, users miss tax-loss harvesting opportunities, trigger wash sales inadvertently, select suboptimal tax lots, and lack visibility into their tax liability. A comprehensive tax optimization system can meaningfully improve after-tax returns.

---

## Goals

1. **Tax-Loss Harvesting** - Identify and execute opportunities to realize losses
2. **Wash Sale Prevention** - Track and prevent wash sale violations
3. **Tax Lot Selection** - Optimize lot selection for sales (FIFO, LIFO, SpecID, MinTax)
4. **Gain/Loss Tracking** - Real-time realized and unrealized gain/loss by holding period
5. **Tax Liability Estimation** - Project current-year tax liability with rate schedules
6. **Tax Reports** - Generate Schedule D, Form 8949, and summary reports

---

## Detailed Requirements

### R1: Tax-Loss Harvesting Engine

#### R1.1: Opportunity Detection
```python
class TaxLossHarvester:
    def find_opportunities(
        self,
        positions: list[Position],
        min_loss: float = 100.0,
        wash_sale_window: int = 30,
    ) -> list[HarvestOpportunity]:
        """
        Find positions with unrealized losses suitable for harvesting.
        
        Criteria:
        - Unrealized loss exceeds min_loss threshold
        - No wash sale risk (haven't bought in last 30 days)
        - Long-term vs short-term classification
        - Estimated tax savings calculation
        """
```

#### R1.2: Substitute Securities
- Identify correlated replacement securities to maintain exposure
- Correlation threshold (default: 0.85+)
- Same sector/industry preference
- ETF substitutes for individual stocks
- 31-day waiting period tracking for repurchase

#### R1.3: Harvesting Constraints
- Daily/annual harvesting limits
- Wash sale avoidance (30-day lookback and look-forward)
- Minimum holding period options
- Account type awareness (taxable vs tax-advantaged)

### R2: Wash Sale Tracking

#### R2.1: Wash Sale Detection
```python
class WashSaleTracker:
    def check_wash_sale(
        self,
        symbol: str,
        sale_date: date,
        transactions: list[Transaction],
    ) -> WashSaleResult:
        """
        Detect wash sales by checking for substantially identical
        securities purchased within 30 days before or after a loss sale.
        
        Returns:
        - is_wash_sale: bool
        - disallowed_loss: float
        - adjusted_basis: float (for replacement shares)
        - wash_sale_shares: int
        """
```

#### R2.2: Substantially Identical Rules
- Same security (exact match)
- Options on same underlying
- Convertible securities
- Related ETFs (configurable similarity threshold)

#### R2.3: Wash Sale Adjustments
- Disallowed loss calculation
- Basis adjustment for replacement shares
- Holding period adjustment
- Carryforward tracking

### R3: Tax Lot Management

#### R3.1: Lot Selection Methods
| Method | Description | Best For |
|--------|-------------|----------|
| FIFO | First In, First Out | Default, simplest |
| LIFO | Last In, First Out | Rising cost basis |
| SpecID | Specific Identification | Maximum control |
| MinTax | Minimize Tax | Optimal tax outcome |
| MaxLoss | Maximize Loss | Tax-loss harvesting |
| HighCost | Highest Cost First | Minimize gains |

#### R3.2: Lot Tracking
```python
@dataclass
class TaxLot:
    lot_id: str
    symbol: str
    shares: float
    cost_basis: float
    acquisition_date: date
    acquisition_type: str  # 'buy', 'dividend_reinvest', 'transfer'
    holding_period: str  # 'short_term', 'long_term'
    adjusted_basis: float  # After wash sale adjustments
    wash_sale_adjustment: float
```

#### R3.3: Lot Selection Optimization
- Project tax impact for each lot
- Consider short-term vs long-term rates
- Factor in state tax rates
- Net investment income tax (NIIT) consideration

### R4: Gain/Loss Tracking

#### R4.1: Real-Time Tracking
```python
@dataclass
class GainLossReport:
    # Realized gains/losses (YTD)
    short_term_realized_gains: float
    short_term_realized_losses: float
    long_term_realized_gains: float
    long_term_realized_losses: float
    
    # Unrealized gains/losses
    short_term_unrealized_gains: float
    short_term_unrealized_losses: float
    long_term_unrealized_gains: float
    long_term_unrealized_losses: float
    
    # Net positions
    net_short_term: float
    net_long_term: float
    total_realized: float
    total_unrealized: float
    
    # Wash sale impact
    disallowed_losses: float
    pending_adjustments: float
```

#### R4.2: Holding Period Classification
- Short-term: held ≤ 1 year
- Long-term: held > 1 year
- Automatic reclassification at 1-year mark
- Wash sale holding period adjustments

### R5: Tax Liability Estimation

#### R5.1: Tax Rate Schedules (2024)
```python
FEDERAL_RATES_2024 = {
    'single': [
        (11_600, 0.10),
        (47_150, 0.12),
        (100_525, 0.22),
        (191_950, 0.24),
        (243_725, 0.32),
        (609_350, 0.35),
        (float('inf'), 0.37),
    ],
    'married_joint': [
        (23_200, 0.10),
        (94_300, 0.12),
        # ... etc
    ],
}

CAPITAL_GAINS_RATES = {
    'short_term': 'ordinary_income',  # Taxed as ordinary income
    'long_term': {
        'single': [(47_025, 0.0), (518_900, 0.15), (float('inf'), 0.20)],
        'married_joint': [(94_050, 0.0), (583_750, 0.15), (float('inf'), 0.20)],
    },
}

NIIT_THRESHOLD = {
    'single': 200_000,
    'married_joint': 250_000,
}
NIIT_RATE = 0.038  # 3.8% Net Investment Income Tax
```

#### R5.2: State Tax Integration
- Support for all 50 states + DC
- State-specific capital gains treatment
- No state tax states (FL, TX, NV, etc.)

#### R5.3: Tax Projection
```python
class TaxEstimator:
    def estimate_liability(
        self,
        filing_status: str,
        ordinary_income: float,
        short_term_gains: float,
        long_term_gains: float,
        state: str,
    ) -> TaxEstimate:
        """
        Project total tax liability including:
        - Federal income tax
        - Federal capital gains tax
        - Net Investment Income Tax (NIIT)
        - State income tax
        - Effective tax rate
        """
```

### R6: Tax Reports

#### R6.1: Form 8949 Generation
- Part I: Short-term transactions
- Part II: Long-term transactions
- Adjustment codes (W for wash sales, etc.)
- Basis reporting categories (A, B, C, D, E, F)

#### R6.2: Schedule D Summary
- Short-term totals
- Long-term totals
- Net capital gain/loss
- Carryover calculations

#### R6.3: Additional Reports
- Year-end tax summary
- Estimated quarterly payments
- Tax-loss harvesting activity log
- Wash sale audit trail

### R7: Database Tables

```sql
-- Tax lots for cost basis tracking
CREATE TABLE tax_lots (
    lot_id UUID PRIMARY KEY,
    account_id UUID REFERENCES accounts(id),
    symbol VARCHAR(20) NOT NULL,
    shares DECIMAL(18,8) NOT NULL,
    cost_basis DECIMAL(18,4) NOT NULL,
    adjusted_basis DECIMAL(18,4) NOT NULL,
    acquisition_date DATE NOT NULL,
    acquisition_type VARCHAR(20),
    wash_sale_adjustment DECIMAL(18,4) DEFAULT 0,
    remaining_shares DECIMAL(18,8),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Realized gains/losses
CREATE TABLE realized_gains (
    id UUID PRIMARY KEY,
    account_id UUID REFERENCES accounts(id),
    lot_id UUID REFERENCES tax_lots(lot_id),
    symbol VARCHAR(20) NOT NULL,
    shares DECIMAL(18,8) NOT NULL,
    proceeds DECIMAL(18,4) NOT NULL,
    cost_basis DECIMAL(18,4) NOT NULL,
    gain_loss DECIMAL(18,4) NOT NULL,
    holding_period VARCHAR(20),
    sale_date DATE NOT NULL,
    is_wash_sale BOOLEAN DEFAULT FALSE,
    disallowed_loss DECIMAL(18,4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Wash sale tracking
CREATE TABLE wash_sales (
    id UUID PRIMARY KEY,
    account_id UUID REFERENCES accounts(id),
    loss_sale_id UUID REFERENCES realized_gains(id),
    replacement_lot_id UUID REFERENCES tax_lots(lot_id),
    symbol VARCHAR(20) NOT NULL,
    disallowed_loss DECIMAL(18,4) NOT NULL,
    basis_adjustment DECIMAL(18,4) NOT NULL,
    wash_sale_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Harvest opportunities log
CREATE TABLE harvest_log (
    id UUID PRIMARY KEY,
    account_id UUID REFERENCES accounts(id),
    symbol VARCHAR(20) NOT NULL,
    shares DECIMAL(18,8) NOT NULL,
    loss_amount DECIMAL(18,4) NOT NULL,
    tax_savings DECIMAL(18,4),
    replacement_symbol VARCHAR(20),
    harvest_date DATE NOT NULL,
    status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Tax-loss opportunity detection | <5s for 500-position portfolio |
| Wash sale check | <100ms per transaction |
| Tax estimate accuracy | Within 5% of actual |
| Form 8949 generation | <10s for 1000 transactions |
| After-tax return improvement | +0.5% annually (estimated) |

---

## Dependencies

- Position and transaction data from execution system
- Market data for current prices
- Account type information (taxable vs IRA)
- User tax profile (filing status, state, income estimate)

---

*Owner: Tax Engineering Lead*
*Last Updated: January 2026*
