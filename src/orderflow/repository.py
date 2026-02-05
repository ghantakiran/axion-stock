"""Order Flow persistence (PRD-42).

Saves and loads orderflow data to/from the database tables:
orderbook_snapshots, block_trades, flow_pressure, smart_money_signals.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.db.engine import get_sync_session_factory
from src.db.models import (
    BlockTradeRecord,
    FlowPressureRecord,
    OrderbookSnapshotRecord,
    SmartMoneySignalRecord,
)
from src.orderflow.models import (
    BlockTrade,
    FlowPressure,
    OrderBookSnapshot,
    SmartMoneySignal,
)


def save_orderbook_snapshot(session: Session, snapshot: OrderBookSnapshot) -> int:
    """Persist an order book snapshot. Returns record id."""
    rec = OrderbookSnapshotRecord(
        symbol=snapshot.symbol,
        bid_volume=snapshot.bid_volume,
        ask_volume=snapshot.ask_volume,
        imbalance_ratio=snapshot.imbalance_ratio,
        imbalance_type=snapshot.imbalance_type.value if hasattr(snapshot.imbalance_type, "value") else str(snapshot.imbalance_type),
        signal=snapshot.signal.value if hasattr(snapshot.signal, "value") else str(snapshot.signal),
        timestamp=snapshot.timestamp or datetime.now(),
    )
    session.add(rec)
    session.flush()
    return rec.id


def save_block_trades(session: Session, trades: list[BlockTrade], symbol: str) -> None:
    """Persist block trades for a symbol."""
    now = datetime.now()
    for t in trades:
        rec = BlockTradeRecord(
            symbol=symbol or t.symbol,
            size=t.size,
            price=t.price,
            side=t.side,
            dollar_value=t.dollar_value,
            block_size=t.block_size.value if hasattr(t.block_size, "value") else str(t.block_size),
            timestamp=t.timestamp or now,
        )
        session.add(rec)


def save_flow_pressure(session: Session, pressure: FlowPressure) -> int:
    """Persist a flow pressure record. Returns record id."""
    rec = FlowPressureRecord(
        symbol=pressure.symbol,
        buy_volume=pressure.buy_volume,
        sell_volume=pressure.sell_volume,
        net_flow=pressure.net_flow,
        pressure_ratio=pressure.pressure_ratio,
        direction=pressure.direction.value if hasattr(pressure.direction, "value") else str(pressure.direction),
        cumulative_delta=pressure.cumulative_delta,
        date=pressure.date or date.today(),
    )
    session.add(rec)
    session.flush()
    return rec.id


def save_smart_money_signal(session: Session, signal: SmartMoneySignal) -> int:
    """Persist a smart money signal. Returns record id."""
    rec = SmartMoneySignalRecord(
        symbol=signal.symbol,
        signal=signal.signal.value if hasattr(signal.signal, "value") else str(signal.signal),
        confidence=signal.confidence,
        block_ratio=signal.block_ratio,
        institutional_net_flow=signal.institutional_net_flow,
        institutional_buy_pct=signal.institutional_buy_pct,
        date=signal.date or date.today(),
    )
    session.add(rec)
    session.flush()
    return rec.id


def get_orderbook_history(
    session: Session,
    symbol: str,
    limit: int = 100,
) -> list[dict]:
    """Load order book snapshot history for a symbol (newest first)."""
    rows = (
        session.query(OrderbookSnapshotRecord)
        .filter(OrderbookSnapshotRecord.symbol == symbol)
        .order_by(OrderbookSnapshotRecord.timestamp.desc().nullslast(), OrderbookSnapshotRecord.computed_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "symbol": r.symbol,
            "bid_volume": r.bid_volume,
            "ask_volume": r.ask_volume,
            "imbalance_ratio": r.imbalance_ratio,
            "imbalance_type": r.imbalance_type or "balanced",
            "signal": r.signal or "neutral",
            "timestamp": r.timestamp,
            "computed_at": r.computed_at,
        })
    return out


def get_block_trades(
    session: Session,
    symbol: str,
    limit: int = 100,
) -> list[dict]:
    """Load block trades for a symbol (newest first)."""
    rows = (
        session.query(BlockTradeRecord)
        .filter(BlockTradeRecord.symbol == symbol)
        .order_by(BlockTradeRecord.timestamp.desc().nullslast(), BlockTradeRecord.computed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "size": r.size,
            "price": r.price,
            "side": r.side,
            "dollar_value": r.dollar_value,
            "block_size": r.block_size,
            "timestamp": r.timestamp,
            "computed_at": r.computed_at,
        }
        for r in rows
    ]


def get_flow_pressure_history(
    session: Session,
    symbol: str,
    limit: int = 100,
) -> list[dict]:
    """Load flow pressure history for a symbol (newest first)."""
    rows = (
        session.query(FlowPressureRecord)
        .filter(FlowPressureRecord.symbol == symbol)
        .order_by(FlowPressureRecord.date.desc().nullslast(), FlowPressureRecord.computed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "buy_volume": r.buy_volume,
            "sell_volume": r.sell_volume,
            "net_flow": r.net_flow,
            "pressure_ratio": r.pressure_ratio,
            "direction": r.direction or "neutral",
            "cumulative_delta": r.cumulative_delta,
            "date": r.date,
            "computed_at": r.computed_at,
        }
        for r in rows
    ]


def get_smart_money_history(
    session: Session,
    symbol: str,
    limit: int = 100,
) -> list[dict]:
    """Load smart money signal history for a symbol (newest first)."""
    rows = (
        session.query(SmartMoneySignalRecord)
        .filter(SmartMoneySignalRecord.symbol == symbol)
        .order_by(SmartMoneySignalRecord.date.desc().nullslast(), SmartMoneySignalRecord.computed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "signal": r.signal or "neutral",
            "confidence": r.confidence,
            "block_ratio": r.block_ratio,
            "institutional_net_flow": r.institutional_net_flow,
            "institutional_buy_pct": r.institutional_buy_pct,
            "date": r.date,
            "computed_at": r.computed_at,
        }
        for r in rows
    ]


def get_session() -> Session:
    """Return a new sync session (caller must close/commit)."""
    factory = get_sync_session_factory()
    return factory()
