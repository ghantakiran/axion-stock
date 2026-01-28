"""Convert price_bars to TimescaleDB hypertable with compression.

Revision ID: 002
Revises: 001
Create Date: 2026-01-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert price_bars to a TimescaleDB hypertable
    # chunk_time_interval of 1 month for efficient range queries
    op.execute("""
        SELECT create_hypertable(
            'price_bars', 'time',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
    """)

    # Enable compression for data older than 6 months
    op.execute("""
        ALTER TABLE price_bars SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'instrument_id',
            timescaledb.compress_orderby = 'time DESC'
        );
    """)
    op.execute("""
        SELECT add_compression_policy('price_bars', INTERVAL '6 months',
                                       if_not_exists => TRUE);
    """)

    # Retention policy: drop raw data older than 25 years
    op.execute("""
        SELECT add_retention_policy('price_bars', INTERVAL '25 years',
                                     if_not_exists => TRUE);
    """)


def downgrade() -> None:
    op.execute("SELECT remove_retention_policy('price_bars', if_exists => TRUE);")
    op.execute("SELECT remove_compression_policy('price_bars', if_exists => TRUE);")
    # Cannot easily revert from hypertable to regular table
