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

    # Store v2 config (if available)
    original_v2 = getattr(config, "FACTOR_ENGINE_V2", False)
    original_adaptive = getattr(config, "FACTOR_ENGINE_ADAPTIVE_WEIGHTS", True)
    original_sector = getattr(config, "FACTOR_ENGINE_SECTOR_RELATIVE", True)

    yield

    # Restore after test
    config.FACTOR_WEIGHTS = original_weights
    config.TOP_N_STOCKS = original_top_n
    config.MIN_PERCENTILE = original_min_pct

    # Restore v2 config
    if hasattr(config, "FACTOR_ENGINE_V2"):
        config.FACTOR_ENGINE_V2 = original_v2
    if hasattr(config, "FACTOR_ENGINE_ADAPTIVE_WEIGHTS"):
        config.FACTOR_ENGINE_ADAPTIVE_WEIGHTS = original_adaptive
    if hasattr(config, "FACTOR_ENGINE_SECTOR_RELATIVE"):
        config.FACTOR_ENGINE_SECTOR_RELATIVE = original_sector
