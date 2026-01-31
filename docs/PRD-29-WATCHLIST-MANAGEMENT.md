# PRD-29: Watchlist Management

**Priority**: P1 | **Phase**: 18 | **Status**: Draft

---

## Problem Statement

Investors need to track stocks they're interested in but don't yet own. A basic watchlist is insufficient for serious investors who want to set price targets, add notes, receive alerts, organize by themes, and share ideas with others. A comprehensive watchlist management system helps investors stay organized and ready to act when opportunities arise.

---

## Goals

1. **Multiple Watchlists** - Create and organize multiple themed watchlists
2. **Custom Columns** - Configure display with relevant metrics
3. **Price Targets** - Set buy/sell targets with alerts
4. **Notes & Tags** - Add research notes and categorize with tags
5. **Smart Alerts** - Alert on price, volume, technical signals
6. **Sharing** - Share watchlists and collaborate with others

---

## Detailed Requirements

### R1: Watchlist Structure

#### R1.1: Watchlist Model
```python
@dataclass
class Watchlist:
    watchlist_id: str
    name: str
    description: Optional[str] = None
    
    # Items
    items: list[WatchlistItem]
    
    # Organization
    is_default: bool = False
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    
    # Sharing
    is_public: bool = False
    shared_with: list[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    created_by: str
```

#### R1.2: Watchlist Item
```python
@dataclass
class WatchlistItem:
    item_id: str
    symbol: str
    
    # Targets
    buy_target: Optional[float] = None
    sell_target: Optional[float] = None
    stop_loss: Optional[float] = None
    
    # Notes
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    
    # Rating
    conviction: Optional[int] = None  # 1-5
    
    # Alerts
    alerts_enabled: bool = True
    
    # Tracking
    added_at: datetime
    added_price: float
    current_price: float
```

### R2: Custom Columns

#### R2.1: Available Columns
| Category | Columns |
|----------|---------|
| **Price** | Last, Change, Change %, Open, High, Low, 52W High/Low |
| **Volume** | Volume, Avg Volume, Volume Ratio |
| **Valuation** | P/E, Forward P/E, P/S, P/B, EV/EBITDA |
| **Fundamentals** | Market Cap, Revenue, EPS, Dividend Yield |
| **Technical** | RSI, MACD, SMA 50/200, Distance from MA |
| **Performance** | 1D, 1W, 1M, 3M, YTD, 1Y Return |
| **Custom** | Target %, Notes, Tags, Conviction |

#### R2.2: Column Configuration
```python
@dataclass
class ColumnConfig:
    column_id: str
    name: str
    category: str
    data_type: str  # number, percent, currency, text
    width: int = 100
    alignment: str = "right"
    format: Optional[str] = None
    is_visible: bool = True
    sort_order: int = 0
```

### R3: Price Targets & Alerts

#### R3.1: Target Types
| Target | Description |
|--------|-------------|
| **Buy Target** | Price to consider buying |
| **Sell Target** | Price to consider selling |
| **Stop Loss** | Risk management level |
| **Alert Price** | Custom alert trigger |

#### R3.2: Alert Model
```python
@dataclass
class WatchlistAlert:
    alert_id: str
    watchlist_id: str
    symbol: str
    
    # Condition
    alert_type: AlertType  # price_above, price_below, pct_change, volume_spike
    threshold: float
    
    # Status
    is_active: bool = True
    triggered_at: Optional[datetime] = None
    
    # Notification
    notify_email: bool = True
    notify_push: bool = True
```

### R4: Notes & Tags

#### R4.1: Notes System
```python
@dataclass
class WatchlistNote:
    note_id: str
    symbol: str
    
    # Content
    title: str
    content: str
    
    # Classification
    note_type: NoteType  # research, thesis, earnings, news
    tags: list[str]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
```

#### R4.2: Tag System
- User-defined tags
- Color-coded tags
- Tag filtering and search
- Tag suggestions based on usage

### R5: Smart Features

#### R5.1: Smart Alerts
| Alert Type | Trigger |
|------------|---------|
| **Price Target** | Hits buy/sell target |
| **% Change** | Daily change exceeds threshold |
| **Volume Spike** | Volume exceeds 2x average |
| **Technical Signal** | RSI oversold/overbought, MA cross |
| **Earnings** | Upcoming earnings in X days |
| **News** | Breaking news for symbol |

#### R5.2: Performance Tracking
```python
@dataclass
class WatchlistPerformance:
    watchlist_id: str
    
    # If bought at add price
    hypothetical_return: float
    hypothetical_value: float
    
    # Best/worst performers
    top_performers: list[str]
    worst_performers: list[str]
    
    # Hit rate
    targets_hit: int
    targets_missed: int
```

### R6: Sharing & Collaboration

#### R6.1: Sharing Options
| Option | Description |
|--------|-------------|
| **Private** | Only owner can view |
| **Shared** | Specific users can view |
| **Public** | Anyone with link can view |
| **Collaborative** | Others can add/edit |

#### R6.2: Share Model
```python
@dataclass
class WatchlistShare:
    share_id: str
    watchlist_id: str
    
    # Access
    shared_with: str  # user_id or "public"
    permission: Permission  # view, edit, admin
    
    # Tracking
    shared_at: datetime
    shared_by: str
    
    # Link sharing
    share_link: Optional[str] = None
    link_expires: Optional[datetime] = None
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Watchlists per user | 3+ average |
| Items per watchlist | 15+ average |
| Alert engagement | 60%+ set alerts |
| Sharing adoption | 20%+ share watchlists |

---

## Dependencies

- Market data (PRD-01)
- Alerting system (PRD-13)
- User authentication (PRD-10)
- Screener (PRD-24)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
