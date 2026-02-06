"""Trade Journal Service - CRUD operations for journal entries and reviews.

Provides:
- Create, read, update, delete for journal entries
- Strategy and setup management
- Daily/periodic review management
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.db.models import (
    JournalEntry,
    DailyReview,
    PeriodicReview,
    TradeSetup,
    TradingStrategy,
)

logger = logging.getLogger(__name__)


# Default setups
DEFAULT_SETUPS = [
    ("breakout", "Breakout", "Price breaks key level with volume confirmation"),
    ("pullback", "Pullback", "Entry on retracement to support/resistance"),
    ("reversal", "Reversal", "Counter-trend entry at exhaustion point"),
    ("momentum", "Momentum", "Following strong directional move"),
    ("mean_reversion", "Mean Reversion", "Fading extreme moves back to mean"),
    ("gap_play", "Gap Play", "Trading gap fills or gap continuations"),
    ("earnings", "Earnings", "Trades around earnings announcements"),
    ("news", "News Catalyst", "News-driven trade opportunities"),
]


class JournalService:
    """Service for managing trade journal entries and reviews."""

    def __init__(self, session: Session):
        """Initialize service with database session."""
        self.session = session

    # =========================================================================
    # Setup Management
    # =========================================================================

    def initialize_default_setups(self) -> list[TradeSetup]:
        """Create default trade setups if they don't exist.

        Returns:
            List of created/existing TradeSetup records.
        """
        results = []
        for setup_id, name, description in DEFAULT_SETUPS:
            existing = self.session.query(TradeSetup).filter(
                TradeSetup.setup_id == setup_id
            ).first()

            if not existing:
                setup = TradeSetup(
                    setup_id=setup_id,
                    name=name,
                    category=setup_id,
                    description=description,
                    is_active=True,
                )
                self.session.add(setup)
                results.append(setup)
            else:
                results.append(existing)

        self.session.commit()
        return results

    def get_setups(self, active_only: bool = True) -> list[TradeSetup]:
        """Get all trade setups.

        Args:
            active_only: Only return active setups.

        Returns:
            List of TradeSetup records.
        """
        query = self.session.query(TradeSetup)
        if active_only:
            query = query.filter(TradeSetup.is_active == True)
        return query.order_by(TradeSetup.name).all()

    def create_setup(
        self,
        name: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TradeSetup:
        """Create a new trade setup.

        Args:
            name: Setup name.
            category: Setup category.
            description: Setup description.

        Returns:
            Created TradeSetup record.
        """
        setup_id = name.lower().replace(" ", "_")

        setup = TradeSetup(
            setup_id=setup_id,
            name=name,
            category=category or setup_id,
            description=description,
            is_active=True,
        )
        self.session.add(setup)
        self.session.commit()
        return setup

    # =========================================================================
    # Strategy Management
    # =========================================================================

    def get_strategies(self, active_only: bool = True) -> list[TradingStrategy]:
        """Get all trading strategies.

        Args:
            active_only: Only return active strategies.

        Returns:
            List of TradingStrategy records.
        """
        query = self.session.query(TradingStrategy)
        if active_only:
            query = query.filter(TradingStrategy.is_active == True)
        return query.order_by(TradingStrategy.name).all()

    def create_strategy(
        self,
        name: str,
        description: Optional[str] = None,
        entry_rules: Optional[list[str]] = None,
        exit_rules: Optional[list[str]] = None,
        max_risk_per_trade: float = 0.02,
        target_risk_reward: float = 2.0,
    ) -> TradingStrategy:
        """Create a new trading strategy.

        Args:
            name: Strategy name.
            description: Strategy description.
            entry_rules: List of entry rules.
            exit_rules: List of exit rules.
            max_risk_per_trade: Max risk per trade as decimal.
            target_risk_reward: Target risk/reward ratio.

        Returns:
            Created TradingStrategy record.
        """
        strategy_id = str(uuid.uuid4())[:8]

        strategy = TradingStrategy(
            strategy_id=strategy_id,
            name=name,
            description=description,
            entry_rules=json.dumps(entry_rules) if entry_rules else None,
            exit_rules=json.dumps(exit_rules) if exit_rules else None,
            max_risk_per_trade=max_risk_per_trade,
            target_risk_reward=target_risk_reward,
            is_active=True,
        )
        self.session.add(strategy)
        self.session.commit()
        return strategy

    def update_strategy(
        self,
        strategy_id: str,
        **kwargs,
    ) -> Optional[TradingStrategy]:
        """Update a trading strategy.

        Args:
            strategy_id: Strategy ID to update.
            **kwargs: Fields to update.

        Returns:
            Updated TradingStrategy or None if not found.
        """
        strategy = self.session.query(TradingStrategy).filter(
            TradingStrategy.strategy_id == strategy_id
        ).first()

        if not strategy:
            return None

        for key, value in kwargs.items():
            if hasattr(strategy, key):
                if key in ("entry_rules", "exit_rules") and isinstance(value, list):
                    value = json.dumps(value)
                setattr(strategy, key, value)

        self.session.commit()
        return strategy

    # =========================================================================
    # Journal Entry Management
    # =========================================================================

    def create_entry(
        self,
        symbol: str,
        direction: str,
        entry_date: datetime,
        entry_price: float,
        entry_quantity: float,
        trade_type: Optional[str] = None,
        entry_reason: Optional[str] = None,
        setup_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        timeframe: Optional[str] = None,
        tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
        pre_trade_emotion: Optional[str] = None,
        initial_stop: Optional[float] = None,
        initial_target: Optional[float] = None,
        screenshots: Optional[list[str]] = None,
    ) -> JournalEntry:
        """Create a new journal entry.

        Args:
            symbol: Ticker symbol.
            direction: 'long' or 'short'.
            entry_date: Entry datetime.
            entry_price: Entry price.
            entry_quantity: Position size.
            trade_type: Trade type (scalp, day, swing, position).
            entry_reason: Reason for entering.
            setup_id: Associated setup ID.
            strategy_id: Associated strategy ID.
            timeframe: Trading timeframe.
            tags: List of tags.
            notes: Trade notes.
            pre_trade_emotion: Emotional state before trade.
            initial_stop: Initial stop loss price.
            initial_target: Initial target price.
            screenshots: List of screenshot paths/URLs.

        Returns:
            Created JournalEntry record.
        """
        entry_id = str(uuid.uuid4())[:12]

        # Calculate planned R:R if stop and target provided
        risk_reward_planned = None
        if initial_stop and initial_target:
            if direction == "long":
                risk = entry_price - initial_stop
                reward = initial_target - entry_price
            else:
                risk = initial_stop - entry_price
                reward = entry_price - initial_target

            if risk > 0:
                risk_reward_planned = reward / risk

        entry = JournalEntry(
            entry_id=entry_id,
            symbol=symbol.upper(),
            direction=direction,
            trade_type=trade_type,
            entry_date=entry_date,
            entry_price=entry_price,
            entry_quantity=entry_quantity,
            entry_reason=entry_reason,
            setup_id=setup_id,
            strategy_id=strategy_id,
            timeframe=timeframe,
            tags=json.dumps(tags) if tags else None,
            notes=notes,
            pre_trade_emotion=pre_trade_emotion,
            initial_stop=initial_stop,
            initial_target=initial_target,
            risk_reward_planned=risk_reward_planned,
            screenshots=json.dumps(screenshots) if screenshots else None,
        )

        self.session.add(entry)
        self.session.commit()

        logger.info("Created journal entry %s: %s %s %s @ %.2f",
                    entry_id, direction, entry_quantity, symbol, entry_price)

        return entry

    def close_entry(
        self,
        entry_id: str,
        exit_date: datetime,
        exit_price: float,
        exit_reason: Optional[str] = None,
        fees: float = 0,
        during_trade_emotion: Optional[str] = None,
        post_trade_emotion: Optional[str] = None,
        lessons_learned: Optional[str] = None,
    ) -> Optional[JournalEntry]:
        """Close an open journal entry.

        Args:
            entry_id: Entry ID to close.
            exit_date: Exit datetime.
            exit_price: Exit price.
            exit_reason: Reason for exit.
            fees: Total fees/commissions.
            during_trade_emotion: Emotion during trade.
            post_trade_emotion: Emotion after trade.
            lessons_learned: Lessons from this trade.

        Returns:
            Updated JournalEntry or None if not found.
        """
        entry = self.session.query(JournalEntry).filter(
            JournalEntry.entry_id == entry_id
        ).first()

        if not entry:
            logger.warning("Entry %s not found", entry_id)
            return None

        # Calculate P&L
        if entry.direction == "long":
            realized_pnl = (exit_price - entry.entry_price) * entry.entry_quantity - fees
        else:
            realized_pnl = (entry.entry_price - exit_price) * entry.entry_quantity - fees

        realized_pnl_pct = realized_pnl / (entry.entry_price * entry.entry_quantity)

        # Calculate actual R:R
        risk_reward_actual = None
        if entry.initial_stop:
            if entry.direction == "long":
                risk = entry.entry_price - entry.initial_stop
                reward = exit_price - entry.entry_price
            else:
                risk = entry.initial_stop - entry.entry_price
                reward = entry.entry_price - exit_price

            if risk > 0:
                risk_reward_actual = reward / risk

        entry.exit_date = exit_date
        entry.exit_price = exit_price
        entry.exit_reason = exit_reason
        entry.realized_pnl = realized_pnl
        entry.realized_pnl_pct = realized_pnl_pct
        entry.fees = fees
        entry.during_trade_emotion = during_trade_emotion
        entry.post_trade_emotion = post_trade_emotion
        entry.lessons_learned = lessons_learned
        entry.risk_reward_actual = risk_reward_actual

        self.session.commit()

        logger.info("Closed entry %s: P&L $%.2f (%.2f%%)",
                    entry_id, realized_pnl, realized_pnl_pct * 100)

        return entry

    def update_entry(self, entry_id: str, **kwargs) -> Optional[JournalEntry]:
        """Update a journal entry.

        Args:
            entry_id: Entry ID to update.
            **kwargs: Fields to update.

        Returns:
            Updated JournalEntry or None if not found.
        """
        entry = self.session.query(JournalEntry).filter(
            JournalEntry.entry_id == entry_id
        ).first()

        if not entry:
            return None

        for key, value in kwargs.items():
            if hasattr(entry, key):
                if key in ("tags", "screenshots") and isinstance(value, list):
                    value = json.dumps(value)
                setattr(entry, key, value)

        self.session.commit()
        return entry

    def get_entry(self, entry_id: str) -> Optional[JournalEntry]:
        """Get a journal entry by ID.

        Args:
            entry_id: Entry ID.

        Returns:
            JournalEntry or None if not found.
        """
        return self.session.query(JournalEntry).filter(
            JournalEntry.entry_id == entry_id
        ).first()

    def get_entries(
        self,
        symbol: Optional[str] = None,
        setup_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        open_only: bool = False,
        limit: int = 100,
    ) -> list[JournalEntry]:
        """Query journal entries with filters.

        Args:
            symbol: Filter by symbol.
            setup_id: Filter by setup.
            strategy_id: Filter by strategy.
            start_date: Filter entries after this date.
            end_date: Filter entries before this date.
            open_only: Only return open trades.
            limit: Maximum number of results.

        Returns:
            List of JournalEntry records.
        """
        query = self.session.query(JournalEntry)

        if symbol:
            query = query.filter(JournalEntry.symbol == symbol.upper())
        if setup_id:
            query = query.filter(JournalEntry.setup_id == setup_id)
        if strategy_id:
            query = query.filter(JournalEntry.strategy_id == strategy_id)
        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)
        if open_only:
            query = query.filter(JournalEntry.exit_date.is_(None))

        return query.order_by(JournalEntry.entry_date.desc()).limit(limit).all()

    def get_open_positions(self) -> list[JournalEntry]:
        """Get all open journal entries.

        Returns:
            List of open JournalEntry records.
        """
        return self.get_entries(open_only=True, limit=1000)

    # =========================================================================
    # Daily Review Management
    # =========================================================================

    def create_daily_review(
        self,
        review_date: date,
        followed_plan: bool = True,
        mistakes_made: Optional[list[str]] = None,
        did_well: Optional[list[str]] = None,
        tomorrow_focus: Optional[str] = None,
        overall_rating: int = 3,
        notes: Optional[str] = None,
    ) -> DailyReview:
        """Create or update a daily review.

        Args:
            review_date: Date of the review.
            followed_plan: Did you follow your trading plan?
            mistakes_made: List of mistakes.
            did_well: List of things done well.
            tomorrow_focus: Focus for next trading day.
            overall_rating: Rating from 1-5.
            notes: Additional notes.

        Returns:
            Created/updated DailyReview record.
        """
        # Calculate stats from entries
        entries = self.get_entries(
            start_date=review_date,
            end_date=review_date + timedelta(days=1),
            limit=1000,
        )

        closed = [e for e in entries if e.exit_date is not None]
        trades_taken = len(entries)
        gross_pnl = sum(e.realized_pnl or 0 for e in closed)
        net_pnl = gross_pnl - sum(e.fees or 0 for e in closed)
        winners = [e for e in closed if (e.realized_pnl or 0) > 0]
        win_rate = len(winners) / len(closed) if closed else 0

        # Check for existing review
        existing = self.session.query(DailyReview).filter(
            DailyReview.review_date == review_date
        ).first()

        if existing:
            review = existing
        else:
            review = DailyReview(review_date=review_date)

        review.trades_taken = trades_taken
        review.gross_pnl = gross_pnl
        review.net_pnl = net_pnl
        review.win_rate = win_rate
        review.followed_plan = followed_plan
        review.mistakes_made = json.dumps(mistakes_made) if mistakes_made else None
        review.did_well = json.dumps(did_well) if did_well else None
        review.tomorrow_focus = tomorrow_focus
        review.overall_rating = max(1, min(5, overall_rating))
        review.notes = notes

        if not existing:
            self.session.add(review)

        self.session.commit()
        return review

    def get_daily_review(self, review_date: date) -> Optional[DailyReview]:
        """Get daily review for a specific date.

        Args:
            review_date: Date of the review.

        Returns:
            DailyReview or None if not found.
        """
        return self.session.query(DailyReview).filter(
            DailyReview.review_date == review_date
        ).first()

    def get_recent_reviews(self, days: int = 30) -> list[DailyReview]:
        """Get recent daily reviews.

        Args:
            days: Number of days to look back.

        Returns:
            List of DailyReview records.
        """
        cutoff = date.today() - timedelta(days=days)
        return self.session.query(DailyReview).filter(
            DailyReview.review_date >= cutoff
        ).order_by(DailyReview.review_date.desc()).all()

    # =========================================================================
    # Periodic Review Management
    # =========================================================================

    def create_periodic_review(
        self,
        review_type: str,
        period_start: date,
        period_end: date,
        key_learnings: Optional[list[str]] = None,
        action_items: Optional[list[str]] = None,
        strategy_adjustments: Optional[str] = None,
        next_period_goals: Optional[list[str]] = None,
    ) -> PeriodicReview:
        """Create a weekly or monthly review.

        Args:
            review_type: 'weekly' or 'monthly'.
            period_start: Start of review period.
            period_end: End of review period.
            key_learnings: Key lessons from period.
            action_items: Action items for next period.
            strategy_adjustments: Strategy changes.
            next_period_goals: Goals for next period.

        Returns:
            Created PeriodicReview record.
        """
        # Calculate stats from entries
        entries = self.get_entries(
            start_date=period_start,
            end_date=period_end,
            limit=10000,
        )

        closed = [e for e in entries if e.exit_date is not None]
        total_trades = len(closed)
        winners = [e for e in closed if (e.realized_pnl or 0) > 0]
        losers = [e for e in closed if (e.realized_pnl or 0) < 0]

        win_rate = len(winners) / len(closed) if closed else 0
        total_profit = sum(e.realized_pnl for e in winners)
        total_loss = abs(sum(e.realized_pnl for e in losers))
        profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")
        net_pnl = sum(e.realized_pnl or 0 for e in closed)

        # Find best/worst setups
        from collections import defaultdict

        by_setup = defaultdict(list)
        for e in closed:
            if e.setup_id:
                by_setup[e.setup_id].append(e)

        best_setups = []
        worst_setups = []

        for setup_id, setup_entries in by_setup.items():
            setup_winners = [e for e in setup_entries if (e.realized_pnl or 0) > 0]
            setup_wr = len(setup_winners) / len(setup_entries) if setup_entries else 0
            setup_pnl = sum(e.realized_pnl or 0 for e in setup_entries)

            if setup_wr >= 0.5 and setup_pnl > 0:
                best_setups.append({"setup": setup_id, "win_rate": setup_wr, "pnl": setup_pnl})
            elif setup_wr < 0.5 or setup_pnl < 0:
                worst_setups.append({"setup": setup_id, "win_rate": setup_wr, "pnl": setup_pnl})

        review = PeriodicReview(
            review_type=review_type,
            period_start=period_start,
            period_end=period_end,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor if profit_factor != float("inf") else None,
            net_pnl=net_pnl,
            best_setups=json.dumps(best_setups[:5]) if best_setups else None,
            worst_setups=json.dumps(worst_setups[:5]) if worst_setups else None,
            key_learnings=json.dumps(key_learnings) if key_learnings else None,
            action_items=json.dumps(action_items) if action_items else None,
            strategy_adjustments=strategy_adjustments,
            next_period_goals=json.dumps(next_period_goals) if next_period_goals else None,
        )

        self.session.add(review)
        self.session.commit()
        return review

    def get_periodic_reviews(
        self,
        review_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[PeriodicReview]:
        """Get periodic reviews.

        Args:
            review_type: Filter by 'weekly' or 'monthly'.
            limit: Maximum number of results.

        Returns:
            List of PeriodicReview records.
        """
        query = self.session.query(PeriodicReview)

        if review_type:
            query = query.filter(PeriodicReview.review_type == review_type)

        return query.order_by(PeriodicReview.period_end.desc()).limit(limit).all()
