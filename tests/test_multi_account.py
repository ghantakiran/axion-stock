"""Unit tests for PRD-68: Multi-Account Management.

Tests cover:
- AccountManager CRUD operations
- Subscription limit enforcement
- Household aggregation
- Performance tracking
- Tax-optimized asset location
- Account snapshots
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch

from src.enterprise.accounts import (
    AccountManager,
    AccountSummary,
    HouseholdSummary,
)
from src.enterprise.models import User, Account, AccountSnapshot, generate_uuid
from src.enterprise.config import (
    AccountType,
    TaxStatus,
    BrokerType,
    SubscriptionTier,
    UserRole,
    SUBSCRIPTION_LIMITS,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def account_manager():
    """Create a fresh AccountManager instance."""
    return AccountManager()


@pytest.fixture
def free_user():
    """Create a free tier user."""
    return User(
        id=generate_uuid(),
        email="free@example.com",
        name="Free User",
        role=UserRole.TRADER,
        subscription=SubscriptionTier.FREE,
    )


@pytest.fixture
def pro_user():
    """Create a pro tier user."""
    return User(
        id=generate_uuid(),
        email="pro@example.com",
        name="Pro User",
        role=UserRole.TRADER,
        subscription=SubscriptionTier.PRO,
    )


@pytest.fixture
def enterprise_user():
    """Create an enterprise tier user."""
    return User(
        id=generate_uuid(),
        email="enterprise@example.com",
        name="Enterprise User",
        role=UserRole.ADMIN,
        subscription=SubscriptionTier.ENTERPRISE,
    )


# =============================================================================
# Account Creation Tests
# =============================================================================


class TestAccountCreation:
    """Tests for account creation."""

    def test_create_paper_account(self, account_manager, free_user):
        """Free users can create paper accounts."""
        account, error = account_manager.create_account(
            user=free_user,
            name="Paper Trading",
            account_type=AccountType.PAPER,
            broker=BrokerType.PAPER,
            initial_value=100000.0,
        )

        assert error is None
        assert account is not None
        assert account.name == "Paper Trading"
        assert account.account_type == AccountType.PAPER
        assert account.total_value == 100000.0
        assert account.is_primary is True  # First account is primary

    def test_create_account_generates_id(self, account_manager, free_user):
        """Account gets a valid UUID on creation."""
        account, _ = account_manager.create_account(
            user=free_user,
            name="Test Account",
            account_type=AccountType.PAPER,
        )

        assert account is not None
        assert len(account.id) == 36  # UUID length

    def test_free_user_cannot_create_live_account(self, account_manager, free_user):
        """Free users cannot create live trading accounts."""
        account, error = account_manager.create_account(
            user=free_user,
            name="Live Trading",
            account_type=AccountType.INDIVIDUAL,
            broker=BrokerType.ALPACA,
        )

        assert account is None
        assert "not available on your plan" in error

    def test_pro_user_can_create_ira(self, account_manager, pro_user):
        """Pro users can create IRA accounts."""
        account, error = account_manager.create_account(
            user=pro_user,
            name="My IRA",
            account_type=AccountType.IRA_ROTH,
            broker=BrokerType.ALPACA,
        )

        assert error is None
        assert account is not None
        assert account.account_type == AccountType.IRA_ROTH

    def test_free_user_account_limit(self, account_manager, free_user):
        """Free users limited to 1 account."""
        # Create first account
        account1, _ = account_manager.create_account(
            user=free_user,
            name="First Account",
            account_type=AccountType.PAPER,
        )
        assert account1 is not None

        # Try to create second account
        account2, error = account_manager.create_account(
            user=free_user,
            name="Second Account",
            account_type=AccountType.PAPER,
        )

        assert account2 is None
        assert "Account limit reached" in error

    def test_pro_user_can_create_multiple_accounts(self, account_manager, pro_user):
        """Pro users can create up to 3 accounts."""
        for i in range(3):
            account, error = account_manager.create_account(
                user=pro_user,
                name=f"Account {i+1}",
                account_type=AccountType.INDIVIDUAL,
            )
            assert account is not None
            assert error is None

        # Fourth should fail
        account4, error = account_manager.create_account(
            user=pro_user,
            name="Account 4",
            account_type=AccountType.INDIVIDUAL,
        )
        assert account4 is None
        assert "Account limit reached" in error

    def test_enterprise_user_unlimited_accounts(self, account_manager, enterprise_user):
        """Enterprise users can create many accounts."""
        for i in range(10):
            account, error = account_manager.create_account(
                user=enterprise_user,
                name=f"Account {i+1}",
                account_type=AccountType.INDIVIDUAL,
            )
            assert account is not None
            assert error is None

    def test_first_account_is_primary(self, account_manager, pro_user):
        """First account created is marked as primary."""
        account1, _ = account_manager.create_account(
            user=pro_user,
            name="First",
            account_type=AccountType.INDIVIDUAL,
        )
        assert account1.is_primary is True

        account2, _ = account_manager.create_account(
            user=pro_user,
            name="Second",
            account_type=AccountType.IRA_TRADITIONAL,
        )
        assert account2.is_primary is False


# =============================================================================
# Account Retrieval Tests
# =============================================================================


class TestAccountRetrieval:
    """Tests for getting accounts."""

    def test_get_account_by_id(self, account_manager, pro_user):
        """Can retrieve account by ID."""
        created, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
        )

        retrieved = account_manager.get_account(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test Account"

    def test_get_nonexistent_account(self, account_manager):
        """Returns None for nonexistent account."""
        account = account_manager.get_account("nonexistent-id")
        assert account is None

    def test_get_user_accounts(self, account_manager, pro_user):
        """Get all accounts for a user."""
        account_manager.create_account(
            user=pro_user,
            name="Account 1",
            account_type=AccountType.INDIVIDUAL,
        )
        account_manager.create_account(
            user=pro_user,
            name="Account 2",
            account_type=AccountType.IRA_ROTH,
        )

        accounts = account_manager.get_user_accounts(pro_user.id)
        assert len(accounts) == 2
        names = [a.name for a in accounts]
        assert "Account 1" in names
        assert "Account 2" in names

    def test_get_user_accounts_excludes_inactive(self, account_manager, pro_user):
        """Inactive accounts not returned in user accounts."""
        account1, _ = account_manager.create_account(
            user=pro_user,
            name="Active",
            account_type=AccountType.INDIVIDUAL,
        )
        account2, _ = account_manager.create_account(
            user=pro_user,
            name="Inactive",
            account_type=AccountType.IRA_ROTH,
        )

        # Delete (soft-delete) second account
        account_manager.delete_account(account2.id, pro_user.id)

        accounts = account_manager.get_user_accounts(pro_user.id)
        assert len(accounts) == 1
        assert accounts[0].name == "Active"


# =============================================================================
# Account Update Tests
# =============================================================================


class TestAccountUpdate:
    """Tests for updating accounts."""

    def test_update_account_name(self, account_manager, pro_user):
        """Can update account name."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Original Name",
            account_type=AccountType.INDIVIDUAL,
        )

        updated, error = account_manager.update_account(
            account_id=account.id,
            user_id=pro_user.id,
            name="New Name",
        )

        assert error is None
        assert updated.name == "New Name"

    def test_update_account_strategy(self, account_manager, pro_user):
        """Can assign strategy to account."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
        )

        updated, _ = account_manager.update_account(
            account_id=account.id,
            user_id=pro_user.id,
            strategy_name="Growth Strategy",
        )

        assert updated.strategy_name == "Growth Strategy"

    def test_update_account_benchmark(self, account_manager, pro_user):
        """Can update account benchmark."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
        )

        updated, _ = account_manager.update_account(
            account_id=account.id,
            user_id=pro_user.id,
            benchmark="QQQ",
        )

        assert updated.benchmark == "QQQ"

    def test_update_nonexistent_account(self, account_manager, pro_user):
        """Returns error for nonexistent account."""
        updated, error = account_manager.update_account(
            account_id="nonexistent",
            user_id=pro_user.id,
            name="New Name",
        )

        assert updated is None
        assert "not found" in error

    def test_update_account_unauthorized(self, account_manager, pro_user, free_user):
        """Cannot update another user's account."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Pro Account",
            account_type=AccountType.INDIVIDUAL,
        )

        # Free user tries to update pro user's account
        updated, error = account_manager.update_account(
            account_id=account.id,
            user_id=free_user.id,
            name="Hacked Name",
        )

        assert updated is None
        assert "Not authorized" in error

    def test_cannot_update_immutable_fields(self, account_manager, pro_user):
        """Cannot update id, owner_id, or created_at."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
        )

        original_id = account.id
        original_owner = account.owner_id
        original_created = account.created_at

        updated, _ = account_manager.update_account(
            account_id=account.id,
            user_id=pro_user.id,
            id="new-id",
            owner_id="new-owner",
            created_at=datetime.utcnow(),
        )

        assert updated.id == original_id
        assert updated.owner_id == original_owner
        assert updated.created_at == original_created


# =============================================================================
# Account Deletion Tests
# =============================================================================


class TestAccountDeletion:
    """Tests for deleting accounts."""

    def test_delete_account(self, account_manager, pro_user):
        """Can soft-delete an account."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="To Delete",
            account_type=AccountType.INDIVIDUAL,
        )

        success, error = account_manager.delete_account(account.id, pro_user.id)

        assert success is True
        assert error is None

        # Account still exists but inactive
        deleted = account_manager.get_account(account.id)
        assert deleted is not None
        assert deleted.is_active is False

    def test_delete_nonexistent_account(self, account_manager, pro_user):
        """Returns error for nonexistent account."""
        success, error = account_manager.delete_account("nonexistent", pro_user.id)

        assert success is False
        assert "not found" in error

    def test_delete_account_unauthorized(self, account_manager, pro_user, free_user):
        """Cannot delete another user's account."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Pro Account",
            account_type=AccountType.INDIVIDUAL,
        )

        success, error = account_manager.delete_account(account.id, free_user.id)

        assert success is False
        assert "Not authorized" in error


# =============================================================================
# Account Value Updates Tests
# =============================================================================


class TestAccountValueUpdates:
    """Tests for updating account values."""

    def test_update_account_value(self, account_manager, pro_user):
        """Can update account value and cash balance."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )

        account_manager.update_account_value(
            account_id=account.id,
            total_value=110000.0,
            cash_balance=20000.0,
        )

        updated = account_manager.get_account(account.id)
        assert updated.total_value == 110000.0
        assert updated.cash_balance == 20000.0

    def test_update_creates_snapshot(self, account_manager, pro_user):
        """Value updates create snapshots."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )

        # Update value
        account_manager.update_account_value(
            account_id=account.id,
            total_value=110000.0,
            cash_balance=20000.0,
        )

        snapshots = account_manager.get_performance_history(account.id)
        assert len(snapshots) >= 2  # Initial + update


# =============================================================================
# Account Summary Tests
# =============================================================================


class TestAccountSummary:
    """Tests for account summary generation."""

    def test_get_account_summary(self, account_manager, pro_user):
        """Can get account summary."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Growth Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
            strategy_name="Momentum Strategy",
        )

        summary = account_manager.get_account_summary(account.id)

        assert summary is not None
        assert summary.name == "Growth Account"
        assert summary.total_value == 100000.0
        assert summary.strategy_name == "Momentum Strategy"

    def test_account_summary_calculates_positions_value(self, account_manager, pro_user):
        """Summary calculates positions value correctly."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )

        # Update with cash and positions
        account_manager.update_account_value(
            account_id=account.id,
            total_value=100000.0,
            cash_balance=30000.0,
        )

        summary = account_manager.get_account_summary(account.id)
        assert summary.positions_value == 70000.0  # 100k - 30k cash

    def test_account_summary_nonexistent(self, account_manager):
        """Returns None for nonexistent account."""
        summary = account_manager.get_account_summary("nonexistent")
        assert summary is None

    def test_account_summary_day_pnl(self, account_manager, pro_user):
        """Summary calculates day P&L correctly."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )

        # Simulate next day with gain
        account_manager.update_account_value(
            account_id=account.id,
            total_value=102000.0,
            cash_balance=20000.0,
        )

        summary = account_manager.get_account_summary(account.id)
        assert summary.day_pnl == 2000.0
        assert round(summary.day_pnl_pct, 4) == 0.02  # 2% gain


# =============================================================================
# Household Summary Tests
# =============================================================================


class TestHouseholdSummary:
    """Tests for household aggregation."""

    def test_household_summary_aggregates_values(self, account_manager, pro_user):
        """Household summary aggregates all account values."""
        account_manager.create_account(
            user=pro_user,
            name="Taxable Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )
        account_manager.create_account(
            user=pro_user,
            name="IRA Account",
            account_type=AccountType.IRA_TRADITIONAL,
            initial_value=50000.0,
        )

        summary = account_manager.get_household_summary(pro_user.id)

        assert summary.total_value == 150000.0
        assert len(summary.accounts) == 2

    def test_household_summary_tax_location(self, account_manager, enterprise_user):
        """Household summary tracks values by tax status."""
        # Create taxable account
        account_manager.create_account(
            user=enterprise_user,
            name="Taxable",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
            tax_status=TaxStatus.TAXABLE,
        )
        # Create tax-deferred (Traditional IRA)
        account_manager.create_account(
            user=enterprise_user,
            name="Traditional IRA",
            account_type=AccountType.IRA_TRADITIONAL,
            initial_value=50000.0,
            tax_status=TaxStatus.TAX_DEFERRED,
        )
        # Create tax-free (Roth IRA)
        account_manager.create_account(
            user=enterprise_user,
            name="Roth IRA",
            account_type=AccountType.IRA_ROTH,
            initial_value=30000.0,
            tax_status=TaxStatus.TAX_FREE,
        )

        summary = account_manager.get_household_summary(enterprise_user.id)

        assert summary.taxable_value == 100000.0
        assert summary.tax_deferred_value == 50000.0
        assert summary.tax_free_value == 30000.0

    def test_household_summary_cash_allocation(self, account_manager, pro_user):
        """Household summary calculates cash allocation."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )

        # Set cash balance
        account_manager.update_account_value(
            account_id=account.id,
            total_value=100000.0,
            cash_balance=25000.0,
        )

        summary = account_manager.get_household_summary(pro_user.id)
        assert summary.total_cash_allocation == 0.25  # 25% cash


# =============================================================================
# Tax Status Inference Tests
# =============================================================================


class TestTaxStatusInference:
    """Tests for automatic tax status inference."""

    def test_individual_account_is_taxable(self, account_manager, pro_user):
        """Individual accounts default to taxable."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Individual",
            account_type=AccountType.INDIVIDUAL,
        )

        assert account.tax_status == TaxStatus.TAXABLE

    def test_traditional_ira_is_tax_deferred(self, account_manager, pro_user):
        """Traditional IRA defaults to tax-deferred."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Traditional IRA",
            account_type=AccountType.IRA_TRADITIONAL,
        )

        assert account.tax_status == TaxStatus.TAX_DEFERRED

    def test_roth_ira_is_tax_free(self, account_manager, pro_user):
        """Roth IRA defaults to tax-free."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Roth IRA",
            account_type=AccountType.IRA_ROTH,
        )

        assert account.tax_status == TaxStatus.TAX_FREE

    def test_explicit_tax_status_overrides_inference(self, account_manager, pro_user):
        """Explicit tax status overrides inference."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Special Account",
            account_type=AccountType.INDIVIDUAL,
            tax_status=TaxStatus.TAX_FREE,  # Override
        )

        assert account.tax_status == TaxStatus.TAX_FREE


# =============================================================================
# Asset Location Suggestions Tests
# =============================================================================


class TestAssetLocationSuggestions:
    """Tests for tax-optimized asset location."""

    def test_asset_location_suggestions_structure(self, account_manager, enterprise_user):
        """Suggestions include all tax status categories."""
        # Create accounts of different types
        account_manager.create_account(
            user=enterprise_user,
            name="Taxable",
            account_type=AccountType.INDIVIDUAL,
        )
        account_manager.create_account(
            user=enterprise_user,
            name="IRA",
            account_type=AccountType.IRA_TRADITIONAL,
        )
        account_manager.create_account(
            user=enterprise_user,
            name="Roth",
            account_type=AccountType.IRA_ROTH,
        )

        suggestions = account_manager.suggest_asset_location(enterprise_user.id)

        assert "taxable" in suggestions
        assert "tax_deferred" in suggestions
        assert "tax_free" in suggestions

    def test_asset_location_lists_accounts(self, account_manager, enterprise_user):
        """Suggestions list accounts by category."""
        account_manager.create_account(
            user=enterprise_user,
            name="My Taxable",
            account_type=AccountType.INDIVIDUAL,
        )

        suggestions = account_manager.suggest_asset_location(enterprise_user.id)

        assert "My Taxable" in suggestions["taxable"]["accounts"]

    def test_asset_location_recommends_assets(self, account_manager, enterprise_user):
        """Suggestions include recommended asset types."""
        account_manager.create_account(
            user=enterprise_user,
            name="Traditional IRA",
            account_type=AccountType.IRA_TRADITIONAL,
        )

        suggestions = account_manager.suggest_asset_location(enterprise_user.id)

        # Tax-deferred should recommend bonds, REITs
        recommended = suggestions["tax_deferred"]["recommended_assets"]
        assert any("Bond" in asset for asset in recommended)
        assert any("REIT" in asset for asset in recommended)


# =============================================================================
# Performance History Tests
# =============================================================================


class TestPerformanceHistory:
    """Tests for performance history tracking."""

    def test_get_performance_history(self, account_manager, pro_user):
        """Can retrieve performance history."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )

        # Add some value updates
        for i in range(5):
            account_manager.update_account_value(
                account_id=account.id,
                total_value=100000.0 + (i * 1000),
                cash_balance=20000.0,
            )

        history = account_manager.get_performance_history(account.id)
        assert len(history) >= 5

    def test_performance_history_tracks_values(self, account_manager, pro_user):
        """History snapshots track correct values."""
        account, _ = account_manager.create_account(
            user=pro_user,
            name="Test Account",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000.0,
        )

        account_manager.update_account_value(
            account_id=account.id,
            total_value=110000.0,
            cash_balance=25000.0,
        )

        history = account_manager.get_performance_history(account.id)
        latest = history[-1]

        assert latest.total_value == 110000.0
        assert latest.cash_balance == 25000.0
        assert latest.positions_value == 85000.0


# =============================================================================
# Subscription Limits Tests
# =============================================================================


class TestSubscriptionLimits:
    """Tests for subscription tier limits."""

    def test_free_tier_limits(self):
        """Free tier has correct limits."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.FREE]

        assert limits["max_accounts"] == 1
        assert limits["live_trading"] is False
        assert AccountType.PAPER in limits["account_types"]
        assert limits["api_requests_daily"] == 0

    def test_pro_tier_limits(self):
        """Pro tier has correct limits."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.PRO]

        assert limits["max_accounts"] == 3
        assert limits["live_trading"] is True
        assert AccountType.INDIVIDUAL in limits["account_types"]
        assert AccountType.IRA_ROTH in limits["account_types"]
        assert limits["api_requests_daily"] == 1000

    def test_enterprise_tier_limits(self):
        """Enterprise tier has generous limits."""
        limits = SUBSCRIPTION_LIMITS[SubscriptionTier.ENTERPRISE]

        assert limits["max_accounts"] >= 100  # Effectively unlimited
        assert limits["live_trading"] is True
        assert limits["team_workspace"] is True
        assert limits["white_label"] is True


# =============================================================================
# ORM Model Tests
# =============================================================================


class TestORMModels:
    """Tests for ORM model definitions."""

    def test_trading_account_model(self):
        """TradingAccount model has required fields."""
        from src.db.models import TradingAccount

        # Check required columns exist
        columns = {c.name for c in TradingAccount.__table__.columns}
        assert "id" in columns
        assert "owner_id" in columns
        assert "name" in columns
        assert "account_type" in columns
        assert "broker" in columns
        assert "tax_status" in columns
        assert "total_value" in columns
        assert "cash_balance" in columns

    def test_account_snapshot_model(self):
        """AccountSnapshotRecord model has required fields."""
        from src.db.models import AccountSnapshotRecord

        columns = {c.name for c in AccountSnapshotRecord.__table__.columns}
        assert "id" in columns
        assert "account_id" in columns
        assert "snapshot_date" in columns
        assert "total_value" in columns
        assert "day_pnl" in columns
        assert "positions" in columns

    def test_account_position_model(self):
        """AccountPositionRecord model has required fields."""
        from src.db.models import AccountPositionRecord

        columns = {c.name for c in AccountPositionRecord.__table__.columns}
        assert "id" in columns
        assert "account_id" in columns
        assert "symbol" in columns
        assert "quantity" in columns
        assert "avg_cost" in columns
        assert "market_value" in columns
        assert "unrealized_pnl" in columns

    def test_account_link_model(self):
        """AccountLink model has required fields."""
        from src.db.models import AccountLink

        columns = {c.name for c in AccountLink.__table__.columns}
        assert "id" in columns
        assert "primary_user_id" in columns
        assert "linked_account_id" in columns
        assert "relationship" in columns
        assert "access_level" in columns

    def test_rebalancing_history_model(self):
        """RebalancingHistory model has required fields."""
        from src.db.models import RebalancingHistory

        columns = {c.name for c in RebalancingHistory.__table__.columns}
        assert "id" in columns
        assert "account_id" in columns
        assert "rebalance_date" in columns
        assert "rebalance_type" in columns
        assert "pre_allocation" in columns
        assert "post_allocation" in columns
        assert "status" in columns


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum definitions."""

    def test_account_type_enum(self):
        """AccountTypeEnum has all expected values."""
        from src.db.models import AccountTypeEnum

        values = {e.value for e in AccountTypeEnum}
        assert "individual" in values
        assert "ira_traditional" in values
        assert "ira_roth" in values
        assert "paper" in values

    def test_tax_status_enum(self):
        """TaxStatusEnum has all expected values."""
        from src.db.models import TaxStatusEnum

        values = {e.value for e in TaxStatusEnum}
        assert "taxable" in values
        assert "tax_deferred" in values
        assert "tax_free" in values

    def test_broker_enum(self):
        """BrokerEnum has all expected values."""
        from src.db.models import BrokerEnum

        values = {e.value for e in BrokerEnum}
        assert "paper" in values
        assert "alpaca" in values
        assert "ibkr" in values
