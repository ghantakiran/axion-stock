# PRD-54: Liquidity Risk Management

## Overview
Extends the existing liquidity module (PRD-25) with redemption risk modeling
and liquidity-adjusted VaR for portfolio-level liquidity risk management.

## New Components

### 1. Redemption Risk Modeler (`redemption.py`)
- Redemption probability estimation from flow patterns
- Liquidity buffer computation (cash needed for redemptions)
- Liquidity coverage ratio (liquid assets / expected redemptions)
- Stress scenario modeling (normal, stressed, crisis)
- Days-to-liquidate estimation per position
- Portfolio liquidation schedule

### 2. Liquidity-Adjusted VaR (`lavar.py`)
- Standard VaR computation (historical, parametric)
- Liquidity cost component (bid-ask spread + market impact)
- Holding period adjustment (sqrt-T scaling)
- Liquidity-adjusted VaR = VaR + Liquidity Cost
- Position-level LaVaR decomposition
- Confidence level configuration (95%, 99%)

## Data Models
- RedemptionScenario: scenario parameters and results
- LiquidityBuffer: required buffer with coverage ratio
- LiquidationSchedule: per-position liquidation timeline
- LaVaR: liquidity-adjusted VaR with components

## Technical Details
- Extends existing src/liquidity/ module
- NumPy/SciPy for VaR computation
- Dataclass-based models
- Integration with existing LiquidityScorer
