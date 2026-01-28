# PRD-10: Enterprise & Multi-Account Platform

**Priority**: P2 | **Phase**: 5 | **Status**: Draft

---

## Problem Statement

Axion is a single-user, single-session application with no authentication, no persistence between sessions, and no collaboration features. To become the best platform in the world, it must support multi-user environments, team workspaces, compliance requirements, and professional reporting — serving individual investors, RIAs, and institutional desks.

---

## Goals

1. **User authentication** with role-based access control
2. **Multi-account management** (personal, IRA, trust, etc.)
3. **Team workspaces** with shared strategies and portfolios
4. **Performance reporting** with PDF/Excel export
5. **Compliance & audit logging** for regulated entities
6. **Subscription tiers** (Free, Pro, Enterprise)

---

## Detailed Requirements

### R1: Authentication & User Management

#### R1.1: Auth System
- OAuth 2.0 with Google, Apple, GitHub sign-in
- Email/password with bcrypt hashing
- Two-factor authentication (TOTP)
- Session management with JWT tokens (1-hour access, 30-day refresh)
- Rate limiting: 100 requests/min per user

#### R1.2: Role-Based Access Control
| Role | Permissions |
|------|------------|
| **Viewer** | View portfolios, reports, dashboards |
| **Trader** | Viewer + execute trades, rebalance |
| **Manager** | Trader + create strategies, manage accounts |
| **Admin** | Manager + manage users, billing, compliance |
| **API** | Programmatic access with scoped tokens |

### R2: Multi-Account Management

#### R2.1: Account Types
```python
class Account:
    id: str
    name: str
    type: str          # 'individual', 'ira_traditional', 'ira_roth',
                       # 'joint', 'trust', 'corporate', 'paper'
    broker: str        # 'alpaca', 'ibkr', 'paper'
    strategy: str      # Strategy template assigned
    target_allocation: dict[str, float]
    cash_balance: float
    total_value: float
    tax_status: str    # 'taxable', 'tax_deferred', 'tax_free'
    benchmark: str     # 'SPY', 'QQQ', 'custom'
    inception_date: date
    owner_id: str
    permissions: list[str]
```

#### R2.2: Account Dashboard
```
MY ACCOUNTS
═══════════════════════════════════════════════════════
Account          Type       Value      YTD     Strategy
Personal         Taxable    $142,300   +8.4%   Balanced Factor
Roth IRA         Tax-Free   $68,200    +12.1%  Aggressive Alpha
Wife's IRA       Tax-Defer  $52,100    +7.8%   Quality Income
Paper Testing    Paper      $100,000   +3.2%   Momentum Rider
─────────────────────────────────────────────────────
Total                       $362,600   +9.1%
```

#### R2.3: Household View
- Aggregate view across all accounts
- Tax-optimized asset location (high-tax assets in tax-deferred)
- Unified risk monitoring across accounts
- Cross-account rebalancing

### R3: Team Workspaces

#### R3.1: Workspace Features
- Shared strategy library (team-created strategies)
- Shared watchlists
- Research notes and annotations
- Strategy performance leaderboard
- Activity feed (trades, signals, alerts)

#### R3.2: Collaboration
```
TEAM: Alpha Capital Research
═══════════════════════════════════════════
Members: 5 | Strategies: 12 | AUM: $2.4M

ACTIVITY FEED
├── John created strategy "Earnings Momentum v3" (2h ago)
├── Sarah executed rebalance on "Quality Growth" (4h ago)
├── Mike shared research note on NVDA earnings (6h ago)
└── Lisa's "Deep Value" strategy hit new high watermark

STRATEGY LEADERBOARD (YTD)
1. Sarah's Quality Growth    +14.2%  Sharpe: 1.82
2. John's Earnings Momentum  +11.8%  Sharpe: 1.45
3. Mike's Tech Alpha         +10.4%  Sharpe: 1.21
4. Lisa's Deep Value         +9.1%   Sharpe: 1.08
```

### R4: Professional Reporting

#### R4.1: Client Reports (PDF)
```
QUARTERLY PERFORMANCE REPORT
Q4 2025 | Prepared for: John Smith

EXECUTIVE SUMMARY
Portfolio returned +4.2% vs benchmark +3.1% (alpha: +1.1%)
Sharpe ratio: 1.67 | Max drawdown: -3.8%

PERFORMANCE ATTRIBUTION
├── Sector Allocation:  +0.4%
├── Stock Selection:    +0.6%
└── Interaction:        +0.1%

HOLDINGS (as of Dec 31, 2025)
[Table of all positions with weights, returns, factor scores]

RISK ANALYSIS
[VaR, drawdown chart, factor exposures]

TRADE ACTIVITY
[Summary of all trades executed during the quarter]
```

#### R4.2: Report Generation
- Automated quarterly/annual reports
- PDF and Excel export
- Custom report builder (drag-and-drop sections)
- White-label support (custom logo, branding)
- Email distribution lists

### R5: Compliance & Audit

#### R5.1: Audit Trail
Every action logged:
```python
class AuditLog:
    timestamp: datetime
    user_id: str
    action: str          # 'order_submit', 'strategy_change', 'login', etc.
    resource_type: str   # 'order', 'portfolio', 'strategy', 'account'
    resource_id: str
    details: dict        # Full action details
    ip_address: str
    user_agent: str
```

#### R5.2: Compliance Features
- Pre-trade compliance checks (restricted lists, position limits)
- Best execution reporting
- Trade error correction workflow
- Regulatory filing support (Form ADV, 13F for large accounts)
- Data retention policies (7-year minimum)
- SOC 2 Type II compliance readiness

### R6: Subscription Tiers

| Feature | Free | Pro ($29/mo) | Enterprise ($99/mo) |
|---------|------|-------------|-------------------|
| Paper Trading | Yes | Yes | Yes |
| Live Trading | No | Yes | Yes |
| Accounts | 1 paper | 3 accounts | Unlimited |
| Strategies | 2 | Unlimited | Unlimited |
| Backtesting | 1-year | 10-year | 20-year |
| ML Predictions | No | Yes | Yes |
| Options Analytics | Basic | Full | Full |
| Sentiment Data | No | Yes | Yes |
| API Access | No | 1,000 req/day | Unlimited |
| Team Workspace | No | No | Yes (10 seats) |
| Priority Support | No | Email | Dedicated |
| Custom Reports | No | Basic | Full |
| White Label | No | No | Yes |

---

## Technical Architecture

### Database Schema (New Tables)
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    name TEXT,
    role TEXT DEFAULT 'trader',
    subscription TEXT DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE accounts (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name TEXT,
    account_type TEXT,
    broker TEXT,
    strategy_id UUID,
    inception_date DATE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE workspaces (
    id UUID PRIMARY KEY,
    name TEXT,
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE workspace_members (
    workspace_id UUID REFERENCES workspaces(id),
    user_id UUID REFERENCES users(id),
    role TEXT DEFAULT 'member',
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details JSONB,
    ip_address INET
);
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| User registration → first trade | <10 minutes |
| Free → Pro conversion | >5% |
| Pro → Enterprise conversion | >15% |
| Monthly churn (Pro) | <5% |
| Report generation time | <30 seconds |
| Audit log query time | <1 second |

---

## Dependencies

- All previous PRDs (complete platform required)
- Stripe for payment processing
- SendGrid for email
- Auth0 or custom auth service
- PDF generation library (WeasyPrint or ReportLab)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*
