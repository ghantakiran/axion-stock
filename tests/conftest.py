"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to defaults before each test."""
    import config

    # Store original values
    original_weights = config.FACTOR_WEIGHTS.copy()
    original_top_n = config.TOP_N_STOCKS
    original_min_pct = config.MIN_PERCENTILE

    yield

    # Restore after test
    config.FACTOR_WEIGHTS = original_weights
    config.TOP_N_STOCKS = original_top_n
    config.MIN_PERCENTILE = original_min_pct
