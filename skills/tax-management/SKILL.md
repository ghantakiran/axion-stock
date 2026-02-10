---
name: tax-management
description: Tax lot management, wash sale detection, tax-loss harvesting, and IRS form generation for the Axion platform. Covers TaxLotManager (FIFO/LIFO/MinTax/HighCost/MaxLoss/SpecID lot selection), WashSaleTracker (30-day rule, substantially identical securities), TaxLossHarvester (automatic opportunities with substitute ETFs), TaxEstimator (federal/state/NIIT liability), and TaxReportGenerator (Form 8949, Schedule D, annual summaries).
metadata:
  author: axion-platform
  version: "1.0"
---

# Tax Management

## When to use this skill

Use this skill when you need to:
- Track cost basis via tax lots across multiple accounts
- Select specific lots for sales to minimize tax impact
- Detect and handle IRS wash sale rules (30-day window)
- Find tax-loss harvesting opportunities with substitute securities
- Estimate federal, state, and NIIT tax liability
- Generate Form 8949, Schedule D, and annual tax summaries
- Compare tax scenarios (sell now vs. hold for long-term treatment)
- Track pending repurchase dates after harvesting

## Step-by-step instructions

### 1. Set up tax lot tracking

```python
from src.tax import (
    TaxLotManager, TaxConfig, DEFAULT_TAX_CONFIG,
    LotSelectionMethod, AcquisitionType, HoldingPeriod,
)
from datetime import date

# Create a lot manager with default config
lot_manager = TaxLotManager()

# Or with custom config
config = TaxConfig(
    tax_year=2026,
    lot_selection=LotSelectionConfig(
        default_method=LotSelectionMethod.MIN_TAX,
    ),
)
lot_manager = TaxLotManager(config=config)

# Add lots from purchases
lot1 = lot_manager.create_lot(
    account_id="acct_001",
    symbol="AAPL",
    shares=100,
    cost_per_share=150.00,
    acquisition_date=date(2025, 3, 15),
    acquisition_type=AcquisitionType.BUY,
)

lot2 = lot_manager.create_lot(
    account_id="acct_001",
    symbol="AAPL",
    shares=50,
    cost_per_share=180.00,
    acquisition_date=date(2025, 11, 20),
)

# Query lots
lots = lot_manager.get_lots("AAPL")
total_shares = lot_manager.get_total_shares("AAPL")       # 150
avg_cost = lot_manager.get_average_cost("AAPL")            # ~160.00
total_basis = lot_manager.get_total_cost_basis("AAPL")     # 24,000.00
```

### 2. Select lots for a sale

```python
# Select lots using different methods
from src.tax import LotSelectionMethod

# FIFO: sell oldest lots first
result = lot_manager.select_lots(
    symbol="AAPL",
    shares_to_sell=75,
    method=LotSelectionMethod.FIFO,
    current_price=195.00,
)
print(f"Total shares: {result.total_shares}")
print(f"Cost basis: ${result.total_cost_basis:.2f}")
print(f"Short-term: {result.short_term_shares}, Long-term: {result.long_term_shares}")
print(f"Estimated gain/loss: ${result.estimated_gain_loss:.2f}")

# MIN_TAX: minimize tax liability (losses first, then LT gains, then ST gains)
result = lot_manager.select_lots(
    symbol="AAPL",
    shares_to_sell=75,
    method=LotSelectionMethod.MIN_TAX,
    current_price=195.00,
)

# Specific lot ID selection
result = lot_manager.select_lots(
    symbol="AAPL",
    shares_to_sell=50,
    method=LotSelectionMethod.SPEC_ID,
    target_lot_ids=[lot2.lot_id],
)
```

Available lot selection methods:
- `FIFO` -- First In, First Out (oldest lots first)
- `LIFO` -- Last In, First Out (newest lots first)
- `HIGH_COST` -- Highest cost per share first (maximize basis)
- `MAX_LOSS` -- Maximize losses first
- `MIN_TAX` -- Minimize total tax impact (losses -> LT gains -> ST gains)
- `SPEC_ID` -- Specific lot identification by lot_id

### 3. Execute a sale with realized gain tracking

```python
# Execute and record realized gains
realized_gains = lot_manager.execute_sale(
    symbol="AAPL",
    shares=75,
    proceeds=14_625.00,          # 75 * $195.00
    sale_date=date(2026, 2, 9),
    method=LotSelectionMethod.MIN_TAX,
)

for gain in realized_gains:
    print(f"Lot {gain.lot_id}: {gain.shares} shares")
    print(f"  Proceeds: ${gain.proceeds:.2f}")
    print(f"  Cost basis: ${gain.cost_basis:.2f}")
    print(f"  Gain/Loss: ${gain.gain_loss:.2f}")
    print(f"  Holding period: {gain.holding_period.value}")
```

### 4. Detect wash sales

```python
from src.tax import WashSaleTracker, Transaction
from datetime import date, timedelta

wash_tracker = WashSaleTracker()

# Record transactions for tracking
wash_tracker.add_transaction(Transaction(
    symbol="AAPL",
    shares=100,
    date=date(2026, 1, 15),
    is_purchase=False,     # This was a sale at a loss
    price=140.00,
))

wash_tracker.add_transaction(Transaction(
    symbol="AAPL",
    shares=50,
    date=date(2026, 1, 25),  # Within 30 days of the loss sale
    is_purchase=True,          # This is a replacement purchase
    lot_id="lot_replacement",
    price=142.00,
))

# Check if a loss sale triggered a wash sale
result = wash_tracker.check_wash_sale(
    symbol="AAPL",
    sale_date=date(2026, 1, 15),
    loss_amount=-1000.00,
    shares_sold=100,
)

if result.is_wash_sale:
    print(f"WASH SALE: {result.reason}")
    print(f"  Disallowed loss: ${result.disallowed_loss:.2f}")
    print(f"  Wash sale shares: {result.wash_sale_shares}")
    print(f"  Basis adjustment: ${result.basis_adjustment:.2f}")
    print(f"  Replacement lot: {result.replacement_lot_id}")

# Mark substantially identical securities (e.g., SPY and IVV)
wash_tracker.add_substantially_identical("SPY", "IVV")
wash_tracker.add_substantially_identical("SPY", "VOO")

# Check if buying now would trigger wash sale
risk = wash_tracker.check_potential_wash_sale("AAPL", date.today())
if risk.is_wash_sale:
    print("WARNING: Buying AAPL now would trigger wash sale!")

# Check if symbol is in a wash sale window
if wash_tracker.is_symbol_in_wash_window("AAPL"):
    print("AAPL is currently in a wash sale window")

# Get safe repurchase dates (31 days after each loss sale)
safe_dates = wash_tracker.get_pending_repurchase_dates("AAPL")
for d in safe_dates:
    print(f"Safe to buy AAPL after: {d}")
```

### 5. Find tax-loss harvesting opportunities

```python
from src.tax import TaxLossHarvester, Position, ETF_SUBSTITUTES

harvester = TaxLossHarvester(
    lot_manager=lot_manager,
    wash_sale_tracker=wash_tracker,
)

# Define current positions
positions = [
    Position(symbol="SPY", shares=200, current_price=450.00, sector="Index"),
    Position(symbol="QQQ", shares=100, current_price=370.00, sector="Tech"),
    Position(symbol="AAPL", shares=50, current_price=175.00, sector="Tech"),
]

# Find opportunities (sorted by estimated tax savings, highest first)
opportunities = harvester.find_opportunities(positions)

for opp in opportunities:
    print(f"{opp.symbol}: {opp.shares} shares")
    print(f"  Unrealized loss: ${opp.unrealized_loss:.2f}")
    print(f"  Estimated tax savings: ${opp.estimated_tax_savings:.2f}")
    print(f"  Wash sale risk: {opp.wash_sale_risk}")
    print(f"  Substitutes: {opp.substitute_symbols}")
    print(f"  Holding period: {opp.holding_period.value}")
    print(f"  Days held: {opp.days_held}")

# Execute a harvest
if opportunities:
    result = harvester.execute_harvest(
        opportunities[0],
        buy_substitute=True,
    )
    print(f"Harvested: ${abs(result.loss_realized):.2f} loss")
    print(f"Tax savings: ${result.tax_savings:.2f}")
    print(f"Replacement: {result.replacement_symbol}")
    print(f"Repurchase eligible: {result.repurchase_eligible_date}")

# Get harvest summary for the year
summary = harvester.get_harvest_summary(year=2026)
print(f"Total harvests: {summary['total_harvests']}")
print(f"Total losses harvested: ${summary['total_losses_harvested']:.2f}")
print(f"Total tax savings: ${summary['total_tax_savings']:.2f}")

# Get repurchase calendar
calendar = harvester.get_repurchase_calendar()
for entry in calendar:
    print(f"{entry['symbol']}: eligible {entry['eligible_date']}")

# Year-end harvesting -- offset realized gains
year_end_opps = harvester.should_harvest_before_year_end(
    positions=positions,
    realized_gains_ytd=15_000.00,
)
```

Built-in ETF substitutes (from `src/tax/harvesting.py`):

| Symbol | Substitutes |
|--------|------------|
| SPY | IVV, VOO, SPLG |
| QQQ | QQQM, ONEQ |
| VTI | ITOT, SPTM, SCHB |
| IWM | IJR, VB, SCHA |
| VEA | IEFA, SCHF, EFA |
| VWO | IEMG, EEM, SCHE |
| BND | AGG, SCHZ |

### 6. Estimate tax liability

```python
from src.tax import TaxEstimator, FilingStatus

estimator = TaxEstimator()

# Estimate total liability
estimate = estimator.estimate_liability(
    ordinary_income=120_000,
    short_term_gains=8_000,
    long_term_gains=25_000,
    filing_status=FilingStatus.SINGLE,
    state="CA",
    deductions=14_600,     # Standard deduction
)

print(f"Total taxable income: ${estimate.total_taxable_income:,.2f}")
print(f"Federal ordinary tax: ${estimate.federal_ordinary_tax:,.2f}")
print(f"Federal STCG tax: ${estimate.federal_stcg_tax:,.2f}")
print(f"Federal LTCG tax: ${estimate.federal_ltcg_tax:,.2f}")
print(f"Federal NIIT: ${estimate.federal_niit:,.2f}")
print(f"Total federal: ${estimate.total_federal_tax:,.2f}")
print(f"State tax ({estimate.state}): ${estimate.state_tax:,.2f}")
print(f"Total tax: ${estimate.total_tax:,.2f}")
print(f"Effective rate: {estimate.effective_rate:.1%}")
print(f"Marginal rate: {estimate.marginal_rate:.1%}")

# Compare scenarios
scenarios = [
    {"name": "Sell all winners now", "short_term": 15000, "long_term": 0},
    {"name": "Hold for long-term", "short_term": 0, "long_term": 15000},
    {"name": "Harvest losses first", "short_term": 15000 - 5000, "long_term": 0},
]

projections = estimator.compare_scenarios(
    base_income=120_000,
    scenarios=scenarios,
    filing_status=FilingStatus.SINGLE,
    state="CA",
)

for proj in projections:
    print(f"{proj.action}: Tax ${proj.projected_tax:,.2f} (savings: ${proj.tax_savings:,.2f})")

# Should you wait for long-term treatment?
result = estimator.calculate_breakeven_hold_days(
    unrealized_gain=10_000,
    days_held=300,
    ordinary_income=120_000,
)
print(result["recommendation"])
# "Waiting 66 days saves $1,500.00"
```

### 7. Generate IRS tax forms

```python
from src.tax import TaxReportGenerator

generator = TaxReportGenerator()

# Generate Form 8949
form = generator.generate_form_8949(
    realized_gains=realized_gains,
    tax_year=2026,
    name="John Doe",
    ssn="***-**-1234",
)

# Print human-readable version
print(generator.format_form_8949_text(form))

# Access form data
for entry in form.short_term_entries:
    print(f"{entry.description}: {entry.date_acquired} -> {entry.date_sold}")
    print(f"  Proceeds: ${entry.proceeds:,.2f}, Basis: ${entry.cost_basis:,.2f}")
    print(f"  Gain/Loss: ${entry.gain_loss:,.2f}")
    if entry.adjustment_code:
        print(f"  Adjustment: {entry.adjustment_code} ${entry.adjustment_amount:,.2f}")

# Generate Schedule D from Form 8949
schedule = generator.generate_schedule_d(
    form_8949=form,
    short_term_carryover=-2_000,   # Prior year carryover
    long_term_carryover=0,
)
print(generator.format_schedule_d_text(schedule))

# Generate comprehensive gain/loss report
gain_loss_report = generator.generate_gain_loss_report(
    realized_gains=realized_gains,
    lots=lot_manager.get_lots("AAPL", include_empty=True),
    current_prices={"AAPL": 195.00},
)

# Generate annual tax summary
summary = generator.generate_tax_summary(
    account_id="acct_001",
    realized_gains=realized_gains,
    wash_sales=wash_tracker.get_wash_sales(year=2026),
    harvest_count=3,
    harvested_losses=5_000.00,
    dividends_qualified=1_200.00,
    dividends_ordinary=800.00,
    tax_year=2026,
)
print(generator.format_summary_text(summary))
```

## Key classes and methods

### `TaxLotManager` (src/tax/lots.py)
- `create_lot(account_id, symbol, shares, cost_per_share, acquisition_date, acquisition_type) -> TaxLot`
- `add_lot(lot) -> TaxLot` / `get_lot(lot_id) -> Optional[TaxLot]`
- `get_lots(symbol, include_empty) -> list[TaxLot]`
- `get_total_shares(symbol) -> float` / `get_average_cost(symbol) -> float`
- `get_total_cost_basis(symbol) -> float`
- `select_lots(symbol, shares_to_sell, method, current_price, target_lot_ids) -> LotSelectionResult`
- `execute_sale(symbol, shares, proceeds, sale_date, method, target_lot_ids) -> list[RealizedGain]`
- `adjust_lot_basis(lot_id, adjustment, reason)` -- for wash sale adjustments
- `get_unrealized_gains(symbol, current_price) -> dict` -- by holding period
- `get_lots_approaching_long_term(days_threshold) -> list[TaxLot]`

### `WashSaleTracker` (src/tax/wash_sales.py)
- `add_transaction(txn: Transaction)` -- record buy/sell for tracking
- `add_substantially_identical(symbol, related)` -- mark related securities
- `check_wash_sale(symbol, sale_date, loss_amount, shares_sold) -> WashSaleCheckResult`
- `check_potential_wash_sale(symbol, purchase_date) -> WashSaleCheckResult`
- `record_wash_sale(loss_sale, replacement_lot, disallowed_loss) -> WashSale`
- `is_symbol_in_wash_window(symbol) -> bool`
- `get_pending_repurchase_dates(symbol) -> list[date]`
- `get_wash_sales(symbol, year) -> list[WashSale]`
- `get_total_disallowed(year) -> float`

### `TaxLossHarvester` (src/tax/harvesting.py)
- `find_opportunities(positions, prices) -> list[HarvestOpportunity]`
- `execute_harvest(opportunity, execute_trade, buy_substitute) -> HarvestResult`
- `get_harvest_summary(year) -> dict`
- `get_repurchase_calendar() -> list[dict]`
- `should_harvest_before_year_end(positions, realized_gains_ytd) -> list[HarvestOpportunity]`

### `TaxEstimator` (src/tax/estimator.py)
- `estimate_liability(ordinary_income, short_term_gains, long_term_gains, filing_status, state, deductions) -> TaxEstimate`
- `compare_scenarios(base_income, scenarios, filing_status, state) -> list[TaxSavingsProjection]`
- `estimate_from_gain_loss_report(report, ordinary_income) -> TaxEstimate`
- `calculate_breakeven_hold_days(unrealized_gain, days_held, ordinary_income) -> dict`

### `TaxReportGenerator` (src/tax/reports.py)
- `generate_form_8949(realized_gains, tax_year, name, ssn) -> Form8949`
- `generate_schedule_d(form_8949, short_term_carryover, long_term_carryover, k1_short_term, k1_long_term) -> ScheduleD`
- `generate_gain_loss_report(realized_gains, lots, current_prices, start_date, end_date) -> GainLossReport`
- `generate_tax_summary(account_id, realized_gains, wash_sales, ...) -> TaxSummaryReport`
- `format_form_8949_text(form) -> str`
- `format_schedule_d_text(schedule) -> str`
- `format_summary_text(summary) -> str`

### Key enums (src/tax/config.py)
- `FilingStatus`: SINGLE, MARRIED_FILING_JOINTLY, MARRIED_FILING_SEPARATELY, HEAD_OF_HOUSEHOLD
- `HoldingPeriod`: SHORT_TERM, LONG_TERM
- `LotSelectionMethod`: FIFO, LIFO, HIGH_COST, MAX_LOSS, MIN_TAX, SPEC_ID
- `AcquisitionType`: BUY, REINVESTMENT, GIFT, INHERITANCE, TRANSFER
- `AdjustmentCode`: W (wash sale), B (basis reported), D (market discount)

## Common patterns

### Wash sale prevention workflow

```python
# Before placing a buy order, check wash sale risk
risk = wash_tracker.check_potential_wash_sale("AAPL", date.today())
if risk.is_wash_sale:
    # Warn user or use a substitute ETF
    substitutes = ETF_SUBSTITUTES.get("AAPL", [])
    if substitutes:
        print(f"Buy {substitutes[0]} instead to avoid wash sale")
```

### End-of-year tax optimization

```python
# 1. Find lots approaching long-term status
approaching = lot_manager.get_lots_approaching_long_term(days_threshold=30)
for lot in approaching:
    print(f"{lot.symbol}: {lot.days_to_long_term} days to long-term treatment")

# 2. Find harvesting opportunities to offset gains
opps = harvester.should_harvest_before_year_end(positions, realized_gains_ytd=20_000)

# 3. Compare holding vs. selling
for lot in approaching:
    analysis = estimator.calculate_breakeven_hold_days(
        unrealized_gain=lot.remaining_shares * (current_price - lot.adjusted_cost_per_share),
        days_held=lot.days_held,
        ordinary_income=120_000,
    )
```

### Capital loss limitation

Net capital losses exceeding $3,000 per year are limited. The excess carries forward:
- The `TaxEstimator.estimate_from_gain_loss_report()` method handles this automatically
- `ScheduleD.capital_loss_carryover` reports the carryover amount

### Source files

- `src/tax/__init__.py` -- public API exports (all classes and constants)
- `src/tax/config.py` -- enums, brackets, rates, TaxConfig, TaxProfile
- `src/tax/models.py` -- TaxLot, RealizedGain, WashSale, HarvestOpportunity, Form8949, etc.
- `src/tax/lots.py` -- TaxLotManager, LotSelectionResult
- `src/tax/wash_sales.py` -- WashSaleTracker, WashSaleCheckResult, Transaction
- `src/tax/harvesting.py` -- TaxLossHarvester, Position, ETF_SUBSTITUTES
- `src/tax/estimator.py` -- TaxEstimator
- `src/tax/reports.py` -- TaxReportGenerator
