# PRD-32: Insider Trading Tracker

**Priority**: P1 | **Phase**: 21 | **Status**: Draft

---

## Problem Statement

Insider trading activity provides valuable signals about company prospects. Corporate insiders (executives, directors, large shareholders) must disclose their trades via SEC Form 4 filings. Tracking these transactions, especially cluster buying patterns, can help investors identify potential opportunities before they're widely known. A comprehensive insider trading tracker aggregates this data and highlights significant activity.

---

## Goals

1. **Transaction Tracking** - Monitor insider buys/sells across all companies
2. **Form 4 Analysis** - Parse and analyze SEC Form 4 filings
3. **Cluster Detection** - Identify multiple insiders buying simultaneously
4. **Institutional Holdings** - Track 13F filings and ownership changes
5. **Insider Profiles** - Track individual insider trading history
6. **Signals & Alerts** - Generate actionable signals from insider activity

---

## Detailed Requirements

### R1: Insider Transaction Model

#### R1.1: Transaction Structure
```python
@dataclass
class InsiderTransaction:
    transaction_id: str
    symbol: str
    company_name: str
    
    # Insider info
    insider_name: str
    insider_title: str
    insider_type: InsiderType  # officer, director, 10% owner
    
    # Transaction details
    transaction_type: TransactionType  # buy, sell, gift, exercise
    transaction_date: date
    shares: int
    price: float
    value: float
    
    # Post-transaction
    shares_owned: int
    ownership_change_pct: float
    
    # Filing info
    filing_date: date
    form_type: str  # Form 4, Form 144
    sec_url: Optional[str] = None
```

#### R1.2: Insider Types
| Type | Description |
|------|-------------|
| **CEO** | Chief Executive Officer |
| **CFO** | Chief Financial Officer |
| **COO** | Chief Operating Officer |
| **Director** | Board member |
| **10% Owner** | Beneficial owner of 10%+ |
| **Officer** | Other corporate officers |

### R2: Form 4 Analysis

#### R2.1: Filing Parser
- Extract transaction details from Form 4
- Handle multiple transactions per filing
- Track derivative securities (options)
- Calculate total value and ownership changes

#### R2.2: Transaction Types
| Code | Type | Signal |
|------|------|--------|
| **P** | Open market purchase | Bullish |
| **S** | Open market sale | Varies |
| **A** | Grant/Award | Neutral |
| **M** | Option exercise | Neutral |
| **G** | Gift | Neutral |
| **F** | Tax withholding | Neutral |

### R3: Cluster Buying Detection

#### R3.1: Cluster Definition
```python
@dataclass
class InsiderCluster:
    cluster_id: str
    symbol: str
    
    # Cluster details
    start_date: date
    end_date: date
    
    # Participants
    insider_count: int
    transactions: list[InsiderTransaction]
    
    # Totals
    total_shares: int
    total_value: float
    
    # Scoring
    cluster_score: float  # 0-100
    signal_strength: str  # weak, moderate, strong
```

#### R3.2: Detection Criteria
| Criterion | Threshold |
|-----------|-----------|
| **Time Window** | 14 days |
| **Min Insiders** | 2+ |
| **Min Value** | $100K total |
| **Transaction Type** | Open market buys only |

### R4: Institutional Holdings (13F)

#### R4.1: Holding Model
```python
@dataclass
class InstitutionalHolding:
    holding_id: str
    institution_name: str
    institution_type: str  # hedge fund, mutual fund, etc.
    
    # Position
    symbol: str
    shares: int
    value: float
    portfolio_pct: float
    
    # Changes
    shares_change: int
    shares_change_pct: float
    is_new_position: bool
    is_sold_out: bool
    
    # Filing
    report_date: date
    filing_date: date
```

#### R4.2: Tracking Features
| Feature | Description |
|---------|-------------|
| **New Positions** | Institutions initiating new positions |
| **Increases** | Significant position increases |
| **Decreases** | Significant position decreases |
| **Sold Out** | Complete position exits |
| **Top Holders** | Largest institutional holders |

### R5: Insider Profiles

#### R5.1: Profile Model
```python
@dataclass
class InsiderProfile:
    insider_id: str
    name: str
    
    # Current positions
    companies: list[str]
    titles: list[str]
    
    # Trading history
    total_transactions: int
    total_buys: int
    total_sells: int
    total_buy_value: float
    total_sell_value: float
    
    # Performance (if tracked)
    avg_return_after_buy: float
    avg_return_after_sell: float
    success_rate: float
```

#### R5.2: Profile Features
- Transaction history by company
- Buy/sell patterns over time
- Performance tracking (optional)
- Notable transactions

### R6: Signals & Alerts

#### R6.1: Signal Types
| Signal | Trigger | Strength |
|--------|---------|----------|
| **Large Buy** | Single buy > $500K | Moderate |
| **Cluster Buy** | 3+ insiders buying | Strong |
| **CEO Buy** | CEO open market purchase | Strong |
| **Unusual Activity** | Volume spike in filings | Moderate |
| **Sector Activity** | Multiple companies in sector | Moderate |

#### R6.2: Alert Configuration
```python
@dataclass
class InsiderAlert:
    alert_id: str
    name: str
    
    # Criteria
    min_value: float = 100000
    transaction_types: list[TransactionType]
    insider_types: list[InsiderType]
    
    # Filters
    symbols: list[str]  # Empty = all
    sectors: list[str]
    
    # Notification
    is_active: bool = True
```

---

## Key Metrics

### Insider Activity Summary
| Metric | Description |
|--------|-------------|
| **Buy/Sell Ratio** | Ratio of buy to sell transactions |
| **Net Insider Value** | Total buys minus sells ($) |
| **Active Insiders** | Count of insiders trading |
| **Cluster Count** | Number of cluster events |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Filing coverage | 99%+ Form 4s |
| Processing delay | < 1 hour from filing |
| Cluster detection | 95% accuracy |
| Signal quality | 60%+ positive returns |

---

## Dependencies

- SEC EDGAR API
- Market data (PRD-01)
- Alerting system (PRD-13)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
