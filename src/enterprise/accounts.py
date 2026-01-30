"""Multi-Account Management System.

Handles multiple trading accounts, household view, and cross-account analytics.
"""

import logging
from datetime import datetime, date
from typing import Optional, List
from dataclasses import dataclass, field

from src.enterprise.config import (
    AccountType, TaxStatus, BrokerType, SubscriptionTier, SUBSCRIPTION_LIMITS,
)
from src.enterprise.models import Account, AccountSnapshot, User, generate_uuid

logger = logging.getLogger(__name__)


@dataclass
class AccountSummary:
    """Summary of an account's current state."""

    account_id: str
    name: str
    account_type: AccountType
    total_value: float
    cash_balance: float
    positions_value: float
    day_pnl: float
    day_pnl_pct: float
    ytd_return: float
    total_return: float
    strategy_name: Optional[str] = None
    n_positions: int = 0


@dataclass
class HouseholdSummary:
    """Aggregated view across all accounts."""

    user_id: str
    total_value: float
    total_cash: float
    total_positions_value: float
    day_pnl: float
    day_pnl_pct: float
    ytd_return: float
    accounts: List[AccountSummary] = field(default_factory=list)

    # Asset location (by tax status)
    taxable_value: float = 0.0
    tax_deferred_value: float = 0.0
    tax_free_value: float = 0.0

    # Allocation analysis
    total_equity_allocation: float = 0.0
    total_fixed_income_allocation: float = 0.0
    total_cash_allocation: float = 0.0


class AccountManager:
    """Manages multiple trading accounts for users.

    Features:
    - Create/update/delete accounts
    - Track account performance
    - Household aggregation
    - Tax-optimized asset location
    - Cross-account rebalancing
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._accounts: dict[str, Account] = {}
        self._snapshots: dict[str, List[AccountSnapshot]] = {}

    def create_account(
        self,
        user: User,
        name: str,
        account_type: AccountType,
        broker: BrokerType = BrokerType.PAPER,
        initial_value: float = 0.0,
        tax_status: Optional[TaxStatus] = None,
        strategy_name: Optional[str] = None,
        benchmark: str = "SPY",
    ) -> tuple[Optional[Account], Optional[str]]:
        """Create a new account.

        Args:
            user: Account owner.
            name: Account name.
            account_type: Type of account.
            broker: Broker for the account.
            initial_value: Starting value.
            tax_status: Tax treatment.
            strategy_name: Assigned strategy.
            benchmark: Performance benchmark.

        Returns:
            Tuple of (Account, error_message).
        """
        # Check subscription limits
        limits = SUBSCRIPTION_LIMITS.get(user.subscription, {})
        max_accounts = limits.get("max_accounts", 1)

        user_accounts = self.get_user_accounts(user.id)
        if len(user_accounts) >= max_accounts:
            return None, f"Account limit reached ({max_accounts}). Upgrade to add more accounts."

        # Check allowed account types
        allowed_types = limits.get("account_types", [AccountType.PAPER])
        if account_type not in allowed_types:
            return None, f"Account type {account_type.value} not available on your plan"

        # Determine tax status if not provided
        if tax_status is None:
            tax_status = self._infer_tax_status(account_type)

        # Create account
        account = Account(
            owner_id=user.id,
            name=name,
            account_type=account_type,
            broker=broker,
            cash_balance=initial_value,
            total_value=initial_value,
            tax_status=tax_status,
            strategy_name=strategy_name,
            benchmark=benchmark,
            is_primary=len(user_accounts) == 0,  # First account is primary
        )

        self._accounts[account.id] = account
        self._snapshots[account.id] = []

        # Record initial snapshot
        self._record_snapshot(account)

        logger.info(f"Account created: {account.name} for user {user.id}")
        return account, None

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self._accounts.get(account_id)

    def get_user_accounts(self, user_id: str) -> List[Account]:
        """Get all accounts for a user."""
        return [
            acc for acc in self._accounts.values()
            if acc.owner_id == user_id and acc.is_active
        ]

    def update_account(
        self,
        account_id: str,
        user_id: str,
        **kwargs,
    ) -> tuple[Optional[Account], Optional[str]]:
        """Update account fields.

        Args:
            account_id: Account to update.
            user_id: User making the update.
            **kwargs: Fields to update.

        Returns:
            Tuple of (Account, error_message).
        """
        account = self._accounts.get(account_id)
        if not account:
            return None, "Account not found"

        if account.owner_id != user_id:
            return None, "Not authorized"

        for key, value in kwargs.items():
            if hasattr(account, key) and key not in ["id", "owner_id", "created_at"]:
                setattr(account, key, value)

        account.updated_at = datetime.utcnow()
        return account, None

    def delete_account(self, account_id: str, user_id: str) -> tuple[bool, Optional[str]]:
        """Soft-delete an account.

        Args:
            account_id: Account to delete.
            user_id: User making the deletion.

        Returns:
            Tuple of (success, error_message).
        """
        account = self._accounts.get(account_id)
        if not account:
            return False, "Account not found"

        if account.owner_id != user_id:
            return False, "Not authorized"

        account.is_active = False
        account.updated_at = datetime.utcnow()

        logger.info(f"Account deleted: {account.name}")
        return True, None

    def update_account_value(
        self,
        account_id: str,
        total_value: float,
        cash_balance: float,
        positions: Optional[dict] = None,
    ):
        """Update account values and record snapshot.

        Args:
            account_id: Account to update.
            total_value: New total value.
            cash_balance: New cash balance.
            positions: Optional position details.
        """
        account = self._accounts.get(account_id)
        if not account:
            return

        account.total_value = total_value
        account.cash_balance = cash_balance
        account.updated_at = datetime.utcnow()

        self._record_snapshot(account, positions)

    def get_account_summary(self, account_id: str) -> Optional[AccountSummary]:
        """Get summary for an account.

        Args:
            account_id: Account ID.

        Returns:
            AccountSummary or None.
        """
        account = self._accounts.get(account_id)
        if not account:
            return None

        snapshots = self._snapshots.get(account_id, [])

        # Calculate day P&L
        day_pnl = 0.0
        day_pnl_pct = 0.0
        if len(snapshots) >= 2:
            prev = snapshots[-2]
            curr = snapshots[-1]
            day_pnl = curr.total_value - prev.total_value
            if prev.total_value > 0:
                day_pnl_pct = day_pnl / prev.total_value

        # Calculate YTD return
        ytd_return = self._calculate_ytd_return(account_id)

        # Calculate total return
        total_return = 0.0
        if snapshots and account.cost_basis > 0:
            total_return = (account.total_value - account.cost_basis) / account.cost_basis

        return AccountSummary(
            account_id=account.id,
            name=account.name,
            account_type=account.account_type,
            total_value=account.total_value,
            cash_balance=account.cash_balance,
            positions_value=account.total_value - account.cash_balance,
            day_pnl=day_pnl,
            day_pnl_pct=day_pnl_pct,
            ytd_return=ytd_return,
            total_return=total_return,
            strategy_name=account.strategy_name,
        )

    def get_household_summary(self, user_id: str) -> HouseholdSummary:
        """Get aggregated view across all user accounts.

        Args:
            user_id: User ID.

        Returns:
            HouseholdSummary.
        """
        accounts = self.get_user_accounts(user_id)

        summaries = []
        total_value = 0.0
        total_cash = 0.0
        total_positions = 0.0
        total_day_pnl = 0.0
        prev_total_value = 0.0

        taxable_value = 0.0
        tax_deferred_value = 0.0
        tax_free_value = 0.0

        for account in accounts:
            summary = self.get_account_summary(account.id)
            if summary:
                summaries.append(summary)
                total_value += summary.total_value
                total_cash += summary.cash_balance
                total_positions += summary.positions_value
                total_day_pnl += summary.day_pnl

                # Track previous value for day P&L %
                snapshots = self._snapshots.get(account.id, [])
                if len(snapshots) >= 2:
                    prev_total_value += snapshots[-2].total_value

                # Asset location by tax status
                if account.tax_status == TaxStatus.TAXABLE:
                    taxable_value += account.total_value
                elif account.tax_status == TaxStatus.TAX_DEFERRED:
                    tax_deferred_value += account.total_value
                elif account.tax_status == TaxStatus.TAX_FREE:
                    tax_free_value += account.total_value

        day_pnl_pct = total_day_pnl / prev_total_value if prev_total_value > 0 else 0

        # Calculate overall YTD
        ytd_return = self._calculate_household_ytd(user_id)

        return HouseholdSummary(
            user_id=user_id,
            total_value=total_value,
            total_cash=total_cash,
            total_positions_value=total_positions,
            day_pnl=total_day_pnl,
            day_pnl_pct=day_pnl_pct,
            ytd_return=ytd_return,
            accounts=summaries,
            taxable_value=taxable_value,
            tax_deferred_value=tax_deferred_value,
            tax_free_value=tax_free_value,
            total_cash_allocation=total_cash / total_value if total_value > 0 else 0,
        )

    def get_performance_history(
        self,
        account_id: str,
        days: int = 365,
    ) -> List[AccountSnapshot]:
        """Get historical snapshots for an account.

        Args:
            account_id: Account ID.
            days: Number of days of history.

        Returns:
            List of AccountSnapshots.
        """
        snapshots = self._snapshots.get(account_id, [])
        cutoff = datetime.utcnow().timestamp() - (days * 86400)

        return [
            s for s in snapshots
            if s.timestamp.timestamp() > cutoff
        ]

    def suggest_asset_location(self, user_id: str) -> dict:
        """Suggest optimal asset location across accounts.

        Tax-efficient asset location places:
        - High-tax assets (bonds, REITs) in tax-deferred accounts
        - Tax-efficient assets (index funds) in taxable accounts
        - High-growth assets in tax-free accounts (Roth)

        Args:
            user_id: User ID.

        Returns:
            Suggestions dictionary.
        """
        accounts = self.get_user_accounts(user_id)

        taxable_accounts = [a for a in accounts if a.tax_status == TaxStatus.TAXABLE]
        deferred_accounts = [a for a in accounts if a.tax_status == TaxStatus.TAX_DEFERRED]
        free_accounts = [a for a in accounts if a.tax_status == TaxStatus.TAX_FREE]

        suggestions = {
            "taxable": {
                "accounts": [a.name for a in taxable_accounts],
                "recommended_assets": [
                    "Total market index funds",
                    "Tax-managed funds",
                    "Municipal bonds",
                    "Growth stocks (long-term holds)",
                ],
            },
            "tax_deferred": {
                "accounts": [a.name for a in deferred_accounts],
                "recommended_assets": [
                    "Bond funds",
                    "REITs",
                    "High-dividend stocks",
                    "Actively managed funds",
                ],
            },
            "tax_free": {
                "accounts": [a.name for a in free_accounts],
                "recommended_assets": [
                    "High-growth stocks",
                    "Small-cap funds",
                    "Aggressive growth strategies",
                    "Assets expected to appreciate significantly",
                ],
            },
        }

        return suggestions

    def _record_snapshot(self, account: Account, positions: Optional[dict] = None):
        """Record a point-in-time snapshot."""
        snapshot = AccountSnapshot(
            account_id=account.id,
            timestamp=datetime.utcnow(),
            total_value=account.total_value,
            cash_balance=account.cash_balance,
            positions_value=account.total_value - account.cash_balance,
            positions=positions or {},
        )

        if account.id not in self._snapshots:
            self._snapshots[account.id] = []

        self._snapshots[account.id].append(snapshot)

    def _calculate_ytd_return(self, account_id: str) -> float:
        """Calculate year-to-date return for an account."""
        snapshots = self._snapshots.get(account_id, [])
        if not snapshots:
            return 0.0

        # Find first snapshot of the year
        current_year = datetime.utcnow().year
        year_start_value = None

        for s in snapshots:
            if s.timestamp.year == current_year:
                year_start_value = s.total_value
                break

        if year_start_value is None or year_start_value == 0:
            return 0.0

        current_value = snapshots[-1].total_value
        return (current_value - year_start_value) / year_start_value

    def _calculate_household_ytd(self, user_id: str) -> float:
        """Calculate aggregate YTD return across all accounts."""
        accounts = self.get_user_accounts(user_id)

        total_start = 0.0
        total_current = 0.0

        for account in accounts:
            snapshots = self._snapshots.get(account.id, [])
            if snapshots:
                current_year = datetime.utcnow().year
                for s in snapshots:
                    if s.timestamp.year == current_year:
                        total_start += s.total_value
                        break
                total_current += snapshots[-1].total_value

        if total_start == 0:
            return 0.0

        return (total_current - total_start) / total_start

    def _infer_tax_status(self, account_type: AccountType) -> TaxStatus:
        """Infer tax status from account type."""
        if account_type in [AccountType.IRA_TRADITIONAL]:
            return TaxStatus.TAX_DEFERRED
        elif account_type in [AccountType.IRA_ROTH]:
            return TaxStatus.TAX_FREE
        else:
            return TaxStatus.TAXABLE
