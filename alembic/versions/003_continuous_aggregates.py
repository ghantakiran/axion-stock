"""Add continuous aggregates for weekly OHLCV rollup.

Revision ID: 003
Revises: 002
Create Date: 2026-01-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Weekly OHLCV continuous aggregate from daily bars
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS weekly_ohlcv
        WITH (timescaledb.continuous) AS
        SELECT
            instrument_id,
            time_bucket('1 week', time) AS bucket,
            first(open, time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, time) AS close,
            sum(volume) AS volume,
            last(adj_close, time) AS adj_close
        FROM price_bars
        GROUP BY instrument_id, time_bucket('1 week', time)
        WITH NO DATA;
    """)

    # Refresh policy: refresh weekly data every day
    op.execute("""
        SELECT add_continuous_aggregate_policy('weekly_ohlcv',
            start_offset => INTERVAL '2 weeks',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    """)

    # Monthly OHLCV continuous aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_ohlcv
        WITH (timescaledb.continuous) AS
        SELECT
            instrument_id,
            time_bucket('1 month', time) AS bucket,
            first(open, time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, time) AS close,
            sum(volume) AS volume,
            last(adj_close, time) AS adj_close
        FROM price_bars
        GROUP BY instrument_id, time_bucket('1 month', time)
        WITH NO DATA;
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('monthly_ohlcv',
            start_offset => INTERVAL '3 months',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS monthly_ohlcv CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS weekly_ohlcv CASCADE;")
