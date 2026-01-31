"""Goal-Based Planning.

Investment goal tracking and projection.
"""

from datetime import date, datetime, timezone
from dateutil.relativedelta import relativedelta
from typing import Optional
import logging
import math
import random

from src.scenarios.config import (
    GoalConfig,
    DEFAULT_GOAL_CONFIG,
    GoalType,
)
from src.scenarios.models import (
    InvestmentGoal,
    GoalProjection,
)

logger = logging.getLogger(__name__)


class GoalPlanner:
    """Plans and tracks investment goals.
    
    Provides projections, Monte Carlo simulations, and
    required contribution/return calculations.
    
    Example:
        planner = GoalPlanner()
        
        goal = InvestmentGoal(
            name="Retirement",
            target_amount=1_000_000,
            target_date=date(2045, 1, 1),
            current_amount=100_000,
            monthly_contribution=1000,
        )
        
        projection = planner.project_goal(goal)
        print(f"Probability of success: {goal.probability_of_success:.0%}")
    """
    
    def __init__(self, config: Optional[GoalConfig] = None):
        self.config = config or DEFAULT_GOAL_CONFIG
    
    def project_goal(
        self,
        goal: InvestmentGoal,
        monte_carlo: bool = True,
    ) -> GoalProjection:
        """Project goal progress over time.
        
        Args:
            goal: Investment goal.
            monte_carlo: Run Monte Carlo simulation for probability.
            
        Returns:
            GoalProjection with time series.
        """
        if not goal.target_date:
            goal.target_date = date.today() + relativedelta(years=10)
        
        # Calculate months to goal
        today = date.today()
        months_to_goal = (
            (goal.target_date.year - today.year) * 12 +
            (goal.target_date.month - today.month)
        )
        months_to_goal = max(1, months_to_goal)
        goal.months_to_goal = months_to_goal
        
        # Monthly return rate
        monthly_return = (1 + goal.expected_return) ** (1/12) - 1
        
        # Deterministic projection
        projection = GoalProjection(
            goal_id=goal.goal_id,
            target_amount=goal.target_amount,
            target_month=months_to_goal,
        )
        
        value = goal.current_amount
        projection.months = list(range(months_to_goal + 1))
        projection.projected_values = [value]
        projection.contributions = [0]
        
        for month in range(1, months_to_goal + 1):
            # Add contribution
            value += goal.monthly_contribution
            # Apply return
            value *= (1 + monthly_return)
            
            projection.projected_values.append(value)
            projection.contributions.append(goal.monthly_contribution * month)
        
        goal.projected_value = value
        
        # Monte Carlo simulation
        if monte_carlo:
            self._run_monte_carlo(goal, projection)
        else:
            # Simple deterministic probability
            goal.probability_of_success = 1.0 if value >= goal.target_amount else 0.0
        
        # Calculate shortfall
        goal.shortfall = max(0, goal.target_amount - goal.projected_value)
        
        # Calculate required monthly contribution
        goal.required_monthly = self.required_contribution(
            goal.current_amount,
            goal.target_amount,
            months_to_goal,
            goal.expected_return,
        )
        
        return projection
    
    def _run_monte_carlo(
        self,
        goal: InvestmentGoal,
        projection: GoalProjection,
    ) -> None:
        """Run Monte Carlo simulation for probability of success."""
        num_runs = self.config.monte_carlo_runs
        months = goal.months_to_goal
        monthly_return = (1 + goal.expected_return) ** (1/12) - 1
        monthly_vol = goal.volatility / math.sqrt(12)
        
        final_values = []
        p10_paths = []
        p50_paths = []
        p90_paths = []
        
        for _ in range(num_runs):
            value = goal.current_amount
            path = [value]
            
            for _ in range(months):
                # Random return
                ret = random.gauss(monthly_return, monthly_vol)
                value += goal.monthly_contribution
                value *= (1 + ret)
                value = max(0, value)  # Can't go negative
                path.append(value)
            
            final_values.append(value)
        
        # Calculate probability of success
        successes = sum(1 for v in final_values if v >= goal.target_amount)
        goal.probability_of_success = successes / num_runs
        
        # Calculate percentile paths
        # Run more simulations to get percentiles
        all_paths = []
        for _ in range(min(1000, num_runs)):
            value = goal.current_amount
            path = [value]
            for _ in range(months):
                ret = random.gauss(monthly_return, monthly_vol)
                value += goal.monthly_contribution
                value *= (1 + ret)
                value = max(0, value)
                path.append(value)
            all_paths.append(path)
        
        # Extract percentiles at each time point
        projection.p10_values = []
        projection.p50_values = []
        projection.p90_values = []
        
        for t in range(months + 1):
            values_at_t = sorted([path[t] for path in all_paths])
            n = len(values_at_t)
            projection.p10_values.append(values_at_t[int(n * 0.10)])
            projection.p50_values.append(values_at_t[int(n * 0.50)])
            projection.p90_values.append(values_at_t[int(n * 0.90)])
        
        # Find expected achievement month
        for t, val in enumerate(projection.p50_values):
            if val >= goal.target_amount:
                projection.expected_achievement_month = t
                break
    
    def required_contribution(
        self,
        current_amount: float,
        target_amount: float,
        months: int,
        annual_return: float,
    ) -> float:
        """Calculate required monthly contribution to reach goal.
        
        Uses future value of annuity formula.
        
        Args:
            current_amount: Current portfolio value.
            target_amount: Target amount.
            months: Months to goal.
            annual_return: Expected annual return.
            
        Returns:
            Required monthly contribution.
        """
        if months <= 0:
            return target_amount - current_amount
        
        r = (1 + annual_return) ** (1/12) - 1  # Monthly rate
        
        # Future value of current amount
        fv_current = current_amount * ((1 + r) ** months)
        
        # Amount needed from contributions
        needed = target_amount - fv_current
        
        if needed <= 0:
            return 0
        
        # PMT formula
        if r == 0:
            return needed / months
        
        pmt = needed * r / (((1 + r) ** months) - 1)
        return max(0, pmt)
    
    def required_return(
        self,
        current_amount: float,
        target_amount: float,
        months: int,
        monthly_contribution: float,
    ) -> float:
        """Calculate required annual return to reach goal.
        
        Uses numerical approximation.
        
        Args:
            current_amount: Current portfolio value.
            target_amount: Target amount.
            months: Months to goal.
            monthly_contribution: Monthly contribution.
            
        Returns:
            Required annual return.
        """
        if months <= 0:
            return 0
        
        # Binary search for rate
        low, high = -0.5, 1.0
        
        for _ in range(50):  # Iterations
            mid = (low + high) / 2
            r = (1 + mid) ** (1/12) - 1  # Monthly
            
            # Calculate future value
            fv = current_amount * ((1 + r) ** months)
            if r != 0:
                fv += monthly_contribution * (((1 + r) ** months - 1) / r)
            else:
                fv += monthly_contribution * months
            
            if abs(fv - target_amount) < 1:
                return mid
            elif fv < target_amount:
                low = mid
            else:
                high = mid
        
        return (low + high) / 2
    
    def time_to_goal(
        self,
        current_amount: float,
        target_amount: float,
        monthly_contribution: float,
        annual_return: float,
    ) -> int:
        """Calculate months to reach goal.
        
        Args:
            current_amount: Current portfolio value.
            target_amount: Target amount.
            monthly_contribution: Monthly contribution.
            annual_return: Expected annual return.
            
        Returns:
            Months to reach goal.
        """
        if current_amount >= target_amount:
            return 0
        
        r = (1 + annual_return) ** (1/12) - 1
        value = current_amount
        months = 0
        max_months = 12 * 100  # 100 years max
        
        while value < target_amount and months < max_months:
            value += monthly_contribution
            value *= (1 + r)
            months += 1
        
        return months if months < max_months else -1
    
    def inflation_adjusted_target(
        self,
        target_amount: float,
        years: int,
        inflation_rate: float = None,
    ) -> float:
        """Calculate inflation-adjusted target amount.
        
        Args:
            target_amount: Target in today's dollars.
            years: Years until goal.
            inflation_rate: Annual inflation rate.
            
        Returns:
            Inflation-adjusted target.
        """
        rate = inflation_rate or self.config.inflation_rate
        return target_amount * ((1 + rate) ** years)
    
    def create_retirement_goal(
        self,
        current_age: int,
        retirement_age: int,
        current_savings: float,
        monthly_contribution: float,
        annual_expenses: float,
        withdrawal_rate: float = 0.04,
    ) -> InvestmentGoal:
        """Create a retirement goal.
        
        Args:
            current_age: Current age.
            retirement_age: Target retirement age.
            current_savings: Current retirement savings.
            monthly_contribution: Monthly contribution.
            annual_expenses: Expected annual expenses in retirement.
            withdrawal_rate: Safe withdrawal rate (default 4%).
            
        Returns:
            Retirement InvestmentGoal.
        """
        years_to_retirement = retirement_age - current_age
        
        # Target = annual expenses / withdrawal rate
        target = annual_expenses / withdrawal_rate
        
        # Adjust for inflation
        inflation_adjusted_target = self.inflation_adjusted_target(
            target, years_to_retirement
        )
        
        target_date = date.today() + relativedelta(years=years_to_retirement)
        
        return InvestmentGoal(
            name="Retirement",
            goal_type=GoalType.RETIREMENT,
            target_amount=inflation_adjusted_target,
            target_date=target_date,
            current_amount=current_savings,
            monthly_contribution=monthly_contribution,
            expected_return=self.config.expected_return,
            volatility=self.config.volatility,
            inflation_rate=self.config.inflation_rate,
        )
