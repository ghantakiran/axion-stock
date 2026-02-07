"""Tests for Tax Optimization System."""

import pytest
from datetime import date, timedelta

from src.tax import (
    # Config
    FilingStatus,
    HoldingPeriod,
    LotSelectionMethod,
    AcquisitionType,
    TaxProfile,
    TaxConfig,
    DEFAULT_TAX_CONFIG,
    # Models
    TaxLot,
    RealizedGain,
    WashSale,
    HarvestOpportunity,
    GainLossReport,
    TaxEstimate,
    Form8949,
    Form8949Entry,
    ScheduleD,
    # Core
    TaxLotManager,
    WashSaleTracker,
    WashSaleCheckResult,
    Transaction,
    TaxLossHarvester,
    Position,
    TaxEstimator,
    TaxReportGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def lot_manager():
    """Create a TaxLotManager with sample lots."""
    manager = TaxLotManager()
    
    # Add some lots at different prices and dates
    manager.create_lot("acct1", "AAPL", 100, 150.0, date(2023, 1, 15))
    manager.create_lot("acct1", "AAPL", 50, 170.0, date(2023, 6, 1))
    manager.create_lot("acct1", "AAPL", 75, 140.0, date(2024, 3, 1))
    
    manager.create_lot("acct1", "MSFT", 50, 300.0, date(2023, 2, 1))
    manager.create_lot("acct1", "MSFT", 30, 320.0, date(2024, 1, 15))
    
    return manager


@pytest.fixture
def wash_tracker():
    """Create a WashSaleTracker."""
    return WashSaleTracker()


@pytest.fixture
def tax_estimator():
    """Create a TaxEstimator."""
    return TaxEstimator()


@pytest.fixture
def report_generator():
    """Create a TaxReportGenerator."""
    return TaxReportGenerator()


# =============================================================================
# Test Tax Lot Management
# =============================================================================

class TestTaxLotManager:
    """Tests for TaxLotManager."""
    
    def test_create_lot(self, lot_manager):
        """Test creating a tax lot."""
        lot = lot_manager.create_lot(
            account_id="acct1",
            symbol="GOOGL",
            shares=25,
            cost_per_share=140.0,
            acquisition_date=date(2024, 5, 1),
        )
        
        assert lot.symbol == "GOOGL"
        assert lot.shares == 25
        assert lot.cost_basis == 3500.0
        assert lot.remaining_shares == 25
    
    def test_get_lots(self, lot_manager):
        """Test getting lots for a symbol."""
        lots = lot_manager.get_lots("AAPL")
        assert len(lots) == 3
    
    def test_get_total_shares(self, lot_manager):
        """Test total share count."""
        total = lot_manager.get_total_shares("AAPL")
        assert total == 225  # 100 + 50 + 75
    
    def test_get_average_cost(self, lot_manager):
        """Test average cost calculation."""
        avg = lot_manager.get_average_cost("AAPL")
        # (100*150 + 50*170 + 75*140) / 225 = 34000 / 225 = 151.11
        assert abs(avg - 151.11) < 0.1
    
    def test_select_lots_fifo(self, lot_manager):
        """Test FIFO lot selection."""
        result = lot_manager.select_lots(
            "AAPL", 120, LotSelectionMethod.FIFO, current_price=160.0
        )
        
        # Should use first lot (100 shares) + part of second (20 shares)
        assert result.total_shares == 120
        assert len(result.lots_used) == 2
    
    def test_select_lots_lifo(self, lot_manager):
        """Test LIFO lot selection."""
        result = lot_manager.select_lots(
            "AAPL", 80, LotSelectionMethod.LIFO, current_price=160.0
        )
        
        # Should use most recent lot (75 shares) + part of second newest (5 shares)
        assert result.total_shares == 80
        first_lot = result.lots_used[0][0]
        assert first_lot.acquisition_date == date(2024, 3, 1)
    
    def test_select_lots_high_cost(self, lot_manager):
        """Test highest cost first selection."""
        result = lot_manager.select_lots(
            "AAPL", 50, LotSelectionMethod.HIGH_COST, current_price=160.0
        )
        
        # Should start with $170 lot
        first_lot = result.lots_used[0][0]
        assert first_lot.cost_per_share == 170.0
    
    def test_execute_sale(self, lot_manager):
        """Test executing a sale."""
        realized = lot_manager.execute_sale(
            symbol="AAPL",
            shares=50,
            proceeds=8000.0,
            sale_date=date(2024, 6, 1),
            method=LotSelectionMethod.FIFO,
        )
        
        assert len(realized) == 1
        assert realized[0].shares == 50
        assert realized[0].proceeds == 8000.0
        # Cost basis from first lot at $150
        assert realized[0].cost_basis == 7500.0
        assert realized[0].gain_loss == 500.0
        
        # Check remaining shares updated
        assert lot_manager.get_total_shares("AAPL") == 175  # 225 - 50
    
    def test_holding_period_classification(self):
        """Test short-term vs long-term classification."""
        # Short-term lot (less than 1 year ago)
        st_lot = TaxLot(
            symbol="TEST",
            shares=100,
            cost_basis=10000,
            acquisition_date=date.today() - timedelta(days=100),
        )
        assert st_lot.holding_period == HoldingPeriod.SHORT_TERM
        
        # Long-term lot (more than 1 year ago)
        lt_lot = TaxLot(
            symbol="TEST",
            shares=100,
            cost_basis=10000,
            acquisition_date=date.today() - timedelta(days=400),
        )
        assert lt_lot.holding_period == HoldingPeriod.LONG_TERM


# =============================================================================
# Test Wash Sale Tracking
# =============================================================================

class TestWashSaleTracker:
    """Tests for WashSaleTracker."""
    
    def test_no_wash_sale_no_replacement(self, wash_tracker):
        """Test no wash sale when no replacement purchase."""
        result = wash_tracker.check_wash_sale(
            symbol="AAPL",
            sale_date=date(2024, 6, 1),
            loss_amount=-1000.0,
            shares_sold=10,
        )
        
        assert not result.is_wash_sale
    
    def test_wash_sale_with_prior_purchase(self, wash_tracker):
        """Test wash sale detection with prior purchase."""
        # Record a purchase within 30 days before the sale
        wash_tracker.add_transaction(Transaction(
            symbol="AAPL",
            shares=10,
            date=date(2024, 5, 20),
            is_purchase=True,
            lot_id="lot1",
        ))
        
        result = wash_tracker.check_wash_sale(
            symbol="AAPL",
            sale_date=date(2024, 6, 1),
            loss_amount=-1000.0,
            shares_sold=10,
        )
        
        assert result.is_wash_sale
        assert result.disallowed_loss == 1000.0
    
    def test_wash_sale_with_subsequent_purchase(self, wash_tracker):
        """Test wash sale with purchase after sale."""
        # Record the loss sale
        wash_tracker.add_transaction(Transaction(
            symbol="AAPL",
            shares=10,
            date=date(2024, 6, 1),
            is_purchase=False,
        ))
        
        # Record a purchase within 30 days after
        wash_tracker.add_transaction(Transaction(
            symbol="AAPL",
            shares=10,
            date=date(2024, 6, 15),
            is_purchase=True,
            lot_id="lot2",
        ))
        
        result = wash_tracker.check_wash_sale(
            symbol="AAPL",
            sale_date=date(2024, 6, 1),
            loss_amount=-1000.0,
            shares_sold=10,
        )
        
        assert result.is_wash_sale
    
    def test_no_wash_sale_for_gain(self, wash_tracker):
        """Test that gains don't trigger wash sale."""
        wash_tracker.add_transaction(Transaction(
            symbol="AAPL",
            shares=10,
            date=date(2024, 5, 20),
            is_purchase=True,
        ))
        
        result = wash_tracker.check_wash_sale(
            symbol="AAPL",
            sale_date=date(2024, 6, 1),
            loss_amount=500.0,  # Gain, not loss
            shares_sold=10,
        )
        
        assert not result.is_wash_sale
    
    def test_substantially_identical(self, wash_tracker):
        """Test substantially identical security matching."""
        wash_tracker.add_substantially_identical("SPY", "IVV")
        
        identical = wash_tracker.get_substantially_identical("SPY")
        assert "IVV" in identical
        assert "SPY" in identical
    
    def test_partial_wash_sale(self, wash_tracker):
        """Test partial wash sale (fewer replacement shares)."""
        # Purchase only 5 shares as replacement
        wash_tracker.add_transaction(Transaction(
            symbol="AAPL",
            shares=5,
            date=date(2024, 5, 25),
            is_purchase=True,
            lot_id="lot1",
        ))
        
        result = wash_tracker.check_wash_sale(
            symbol="AAPL",
            sale_date=date(2024, 6, 1),
            loss_amount=-1000.0,
            shares_sold=10,
        )
        
        assert result.is_wash_sale
        # Only 5 of 10 shares are wash sale
        assert result.wash_sale_shares == 5
        # Disallowed is proportional
        assert result.disallowed_loss == 500.0


# =============================================================================
# Test Tax-Loss Harvesting
# =============================================================================

class TestTaxLossHarvester:
    """Tests for TaxLossHarvester."""
    
    def test_find_opportunities(self, lot_manager, wash_tracker):
        """Test finding harvesting opportunities."""
        harvester = TaxLossHarvester(lot_manager, wash_tracker)
        
        # Create positions with current prices
        positions = [
            Position(symbol="AAPL", shares=225, current_price=130.0),  # Loss
            Position(symbol="MSFT", shares=80, current_price=350.0),   # Gain
        ]
        
        opportunities = harvester.find_opportunities(positions)
        
        # Should find AAPL opportunities (losing positions)
        aapl_opps = [o for o in opportunities if o.symbol == "AAPL"]
        assert len(aapl_opps) > 0
        
        # Should not include MSFT (it's a gain)
        msft_opps = [o for o in opportunities if o.symbol == "MSFT"]
        assert len(msft_opps) == 0
    
    def test_opportunity_tax_savings(self, lot_manager, wash_tracker):
        """Test tax savings calculation."""
        config = TaxConfig(
            tax_profile=TaxProfile(
                filing_status=FilingStatus.SINGLE,
                estimated_ordinary_income=100000,
                state="CA",
            )
        )
        harvester = TaxLossHarvester(lot_manager, wash_tracker, config)
        
        positions = [
            Position(symbol="AAPL", shares=225, current_price=100.0),
        ]
        
        opportunities = harvester.find_opportunities(positions)
        
        # Should have positive tax savings for losses
        for opp in opportunities:
            assert opp.estimated_tax_savings > 0
    
    def test_harvest_summary(self, lot_manager, wash_tracker):
        """Test harvest summary generation."""
        harvester = TaxLossHarvester(lot_manager, wash_tracker)
        
        summary = harvester.get_harvest_summary()
        
        assert "year" in summary
        assert "total_harvests" in summary
        assert "total_losses_harvested" in summary


# =============================================================================
# Test Tax Estimation
# =============================================================================

class TestTaxEstimator:
    """Tests for TaxEstimator."""
    
    def test_basic_estimate(self, tax_estimator):
        """Test basic tax estimation."""
        estimate = tax_estimator.estimate_liability(
            ordinary_income=100000,
            short_term_gains=5000,
            long_term_gains=10000,
        )
        
        assert estimate.total_tax > 0
        assert estimate.federal_ordinary_tax > 0
        assert estimate.federal_ltcg_tax > 0
        assert 0 < estimate.effective_rate < 1
    
    def test_no_income_state(self, tax_estimator):
        """Test estimation for no-income-tax state."""
        estimate = tax_estimator.estimate_liability(
            ordinary_income=100000,
            short_term_gains=5000,
            long_term_gains=10000,
            state="TX",
        )
        
        assert estimate.state_tax == 0
    
    def test_high_income_niit(self, tax_estimator):
        """Test NIIT applies to high income."""
        estimate = tax_estimator.estimate_liability(
            ordinary_income=250000,
            short_term_gains=50000,
            long_term_gains=100000,
            filing_status=FilingStatus.SINGLE,
        )
        
        # NIIT should apply (income > $200k threshold)
        assert estimate.federal_niit > 0
    
    def test_low_income_no_niit(self, tax_estimator):
        """Test NIIT doesn't apply to lower income."""
        estimate = tax_estimator.estimate_liability(
            ordinary_income=100000,
            short_term_gains=5000,
            long_term_gains=10000,
            filing_status=FilingStatus.SINGLE,
        )
        
        # NIIT should not apply (income < $200k)
        assert estimate.federal_niit == 0
    
    def test_filing_status_impact(self, tax_estimator):
        """Test different filing statuses."""
        single = tax_estimator.estimate_liability(
            ordinary_income=100000,
            filing_status=FilingStatus.SINGLE,
        )
        
        mfj = tax_estimator.estimate_liability(
            ordinary_income=100000,
            filing_status=FilingStatus.MARRIED_JOINT,
        )
        
        # Married filing jointly should have lower tax
        assert mfj.total_tax < single.total_tax
    
    def test_long_term_vs_short_term_rates(self, tax_estimator):
        """Test LTCG gets better rate than STCG."""
        # All gains as short-term
        st_estimate = tax_estimator.estimate_liability(
            ordinary_income=100000,
            short_term_gains=50000,
            long_term_gains=0,
        )
        
        # All gains as long-term
        lt_estimate = tax_estimator.estimate_liability(
            ordinary_income=100000,
            short_term_gains=0,
            long_term_gains=50000,
        )
        
        # Long-term should result in lower tax
        assert lt_estimate.total_tax < st_estimate.total_tax
    
    def test_breakeven_hold_days(self, tax_estimator):
        """Test breakeven hold days calculation."""
        result = tax_estimator.calculate_breakeven_hold_days(
            unrealized_gain=10000,
            days_held=200,
            ordinary_income=100000,
        )
        
        assert "days_to_long_term" in result
        assert "tax_savings" in result
        assert result["days_to_long_term"] > 0


# =============================================================================
# Test Tax Reports
# =============================================================================

class TestTaxReportGenerator:
    """Tests for TaxReportGenerator."""
    
    def test_generate_form_8949(self, report_generator):
        """Test Form 8949 generation."""
        realized_gains = [
            RealizedGain(
                symbol="AAPL",
                shares=100,
                proceeds=16000,
                cost_basis=15000,
                gain_loss=1000,
                holding_period=HoldingPeriod.SHORT_TERM,
                sale_date=date(2024, 3, 15),
                acquisition_date=date(2024, 1, 10),
            ),
            RealizedGain(
                symbol="MSFT",
                shares=50,
                proceeds=15000,
                cost_basis=12000,
                gain_loss=3000,
                holding_period=HoldingPeriod.LONG_TERM,
                sale_date=date(2024, 6, 1),
                acquisition_date=date(2022, 3, 1),
            ),
        ]
        
        form = report_generator.generate_form_8949(
            realized_gains, tax_year=2024, name="Test User"
        )
        
        assert form.tax_year == 2024
        assert len(form.short_term_entries) == 1
        assert len(form.long_term_entries) == 1
        assert form.short_term_gain_loss == 1000
        assert form.long_term_gain_loss == 3000
    
    def test_form_8949_wash_sale(self, report_generator):
        """Test Form 8949 with wash sale adjustment."""
        realized_gains = [
            RealizedGain(
                symbol="AAPL",
                shares=100,
                proceeds=14000,
                cost_basis=15000,
                gain_loss=-1000,
                holding_period=HoldingPeriod.SHORT_TERM,
                sale_date=date(2024, 3, 15),
                acquisition_date=date(2024, 1, 10),
                is_wash_sale=True,
                disallowed_loss=500,
            ),
        ]
        
        form = report_generator.generate_form_8949(realized_gains, tax_year=2024)
        
        entry = form.short_term_entries[0]
        assert entry.adjustment_code == "W"
        assert entry.adjustment_amount == 500
        # Reported gain/loss should be adjusted
        assert entry.gain_loss == -500  # -1000 + 500
    
    def test_generate_schedule_d(self, report_generator):
        """Test Schedule D generation."""
        form = Form8949(tax_year=2024)
        form.short_term_entries = [
            Form8949Entry(gain_loss=1000),
            Form8949Entry(gain_loss=-500),
        ]
        form.long_term_entries = [
            Form8949Entry(gain_loss=3000),
        ]
        
        schedule = report_generator.generate_schedule_d(
            form, short_term_carryover=-1000
        )
        
        assert schedule.short_term_from_8949 == 500
        assert schedule.long_term_from_8949 == 3000
        assert schedule.short_term_carryover == -1000
        assert schedule.net_short_term == -500  # 500 - 1000
        assert schedule.net_long_term == 3000
    
    def test_format_form_8949_text(self, report_generator):
        """Test text formatting of Form 8949."""
        form = Form8949(tax_year=2024, name="Test User")
        form.short_term_entries = [
            Form8949Entry(
                description="100 sh AAPL",
                date_acquired=date(2024, 1, 10),
                date_sold=date(2024, 3, 15),
                proceeds=16000,
                cost_basis=15000,
                gain_loss=1000,
            ),
        ]
        
        text = report_generator.format_form_8949_text(form)
        
        assert "Form 8949" in text
        assert "SHORT-TERM" in text
        assert "AAPL" in text
        assert "2024" in text
    
    def test_generate_tax_summary(self, report_generator):
        """Test tax summary report generation."""
        realized_gains = [
            RealizedGain(
                symbol="AAPL",
                shares=100,
                proceeds=16000,
                cost_basis=15000,
                gain_loss=1000,
                holding_period=HoldingPeriod.SHORT_TERM,
                sale_date=date(2024, 3, 15),
            ),
        ]
        
        summary = report_generator.generate_tax_summary(
            account_id="acct1",
            realized_gains=realized_gains,
            wash_sales=[],
            tax_year=2024,
        )
        
        assert summary.tax_year == 2024
        assert summary.total_proceeds == 16000
        assert summary.short_term_gain_loss == 1000
        assert summary.estimated_tax_liability > 0


# =============================================================================
# Test GainLossReport
# =============================================================================

class TestGainLossReport:
    """Tests for GainLossReport model."""
    
    def test_net_calculations(self):
        """Test net gain/loss calculations."""
        report = GainLossReport(
            short_term_realized_gains=5000,
            short_term_realized_losses=-2000,
            long_term_realized_gains=10000,
            long_term_realized_losses=-3000,
        )
        
        assert report.net_short_term_realized == 3000
        assert report.net_long_term_realized == 7000
        assert report.total_realized == 10000
    
    def test_unrealized_totals(self):
        """Test unrealized gain/loss totals."""
        report = GainLossReport(
            short_term_unrealized_gains=2000,
            short_term_unrealized_losses=-500,
            long_term_unrealized_gains=8000,
            long_term_unrealized_losses=-1000,
        )
        
        assert report.net_short_term_unrealized == 1500
        assert report.net_long_term_unrealized == 7000
        assert report.total_unrealized == 8500


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_full_harvest_workflow(self):
        """Test complete harvesting workflow."""
        # Setup
        lot_manager = TaxLotManager()
        wash_tracker = WashSaleTracker()
        harvester = TaxLossHarvester(lot_manager, wash_tracker)
        
        # Create a losing position
        lot_manager.create_lot(
            "acct1", "AAPL", 100, 180.0,
            date.today() - timedelta(days=60)
        )
        
        # Current price is lower
        positions = [Position("AAPL", 100, 150.0)]
        
        # Find opportunities
        opportunities = harvester.find_opportunities(positions)
        assert len(opportunities) > 0
        
        # Execute harvest
        opp = opportunities[0]
        result = harvester.execute_harvest(opp, buy_substitute=False)
        
        assert result.status == "completed"
        assert result.loss_realized < 0
        
        # Verify lot updated
        assert lot_manager.get_total_shares("AAPL") == 0
    
    def test_wash_sale_prevention(self):
        """Test wash sale prevention in harvesting."""
        lot_manager = TaxLotManager()
        wash_tracker = WashSaleTracker()

        # Record a recent sale at a loss (creates wash sale risk for repurchase)
        wash_tracker.add_transaction(Transaction(
            symbol="AAPL",
            shares=50,
            date=date.today() - timedelta(days=10),
            is_purchase=False,  # This is a sale
        ))

        # Create the lot
        lot_manager.create_lot(
            "acct1", "AAPL", 100, 180.0,
            date.today() - timedelta(days=60)
        )

        harvester = TaxLossHarvester(lot_manager, wash_tracker)
        positions = [Position("AAPL", 100, 150.0)]

        opportunities = harvester.find_opportunities(positions)

        # Opportunity should be flagged with wash sale risk (recent sale in window)
        aapl_opp = [o for o in opportunities if o.symbol == "AAPL"][0]
        assert aapl_opp.wash_sale_risk is True
