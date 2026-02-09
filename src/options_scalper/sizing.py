"""Position sizing for options scalps.

Risk-controlled sizing with conviction adjustments.
Max risk = 2% of equity per scalp, max loss = 50% of premium.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ScalpSizer:
    """Position sizing for options scalps.

    Rules:
    - Max risk per scalp: 2% of account equity
    - Max premium at risk: entry_price * contracts * 100
    - Assume max loss = 50% of premium (hard stop)
    - So: max_contracts = (equity * 0.02) / (premium * 100 * 0.50)
    - Conviction adjustment:
      - High (75+): full contracts
      - Medium (50-74): half contracts (min 1)
    - Max 3 concurrent scalp positions
    """

    def __init__(self, config):
        self.config = config

    def calculate(
        self,
        premium: float,
        conviction: int,
        account_equity: float,
    ) -> int:
        """Calculate number of contracts for a scalp trade."""
        if premium <= 0 or account_equity <= 0:
            return 0

        risk_budget = account_equity * self.config.max_risk_per_scalp
        max_loss_per_contract = premium * 100 * self.config.max_loss_pct
        if max_loss_per_contract <= 0:
            return 0

        raw_contracts = risk_budget / max_loss_per_contract

        # Conviction multiplier
        if conviction >= 75:
            mult = 1.0
        else:
            mult = 0.5

        contracts = int(raw_contracts * mult)
        return max(contracts, 1) if raw_contracts >= 0.5 else 0
