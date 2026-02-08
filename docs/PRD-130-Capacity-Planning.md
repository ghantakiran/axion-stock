# PRD-130: Capacity Planning & Auto-Scaling

## Overview
Capacity planning system that monitors resource utilization, forecasts demand, recommends scaling actions, and manages auto-scaling policies. Ensures the platform can handle peak trading loads with optimal resource allocation.

## Goals
1. Resource utilization tracking (CPU, memory, disk, network, connections)
2. Demand forecasting using historical patterns and market calendars
3. Auto-scaling policies with configurable thresholds
4. Capacity recommendations based on growth trends
5. Cost optimization through right-sizing analysis

## Components

### 1. Capacity Config (`config.py`)
- ResourceType enum: CPU, MEMORY, DISK, NETWORK, CONNECTIONS, QUEUE_DEPTH, API_CALLS
- ScalingDirection enum: SCALE_UP, SCALE_DOWN, SCALE_OUT, SCALE_IN, NO_ACTION
- ScalingPolicy enum: THRESHOLD, PREDICTIVE, SCHEDULED, MANUAL
- CapacityStatus enum: HEALTHY, WARNING, CRITICAL, OVER_PROVISIONED, UNDER_PROVISIONED
- ResourceThreshold dataclass (warning_pct, critical_pct, scale_up_pct, scale_down_pct, cooldown_seconds)
- CapacityConfig dataclass (thresholds, forecast_horizon_hours, check_interval_seconds, enable_auto_scaling)

### 2. Resource Monitor (`monitor.py`)
- ResourceMetric dataclass (resource_type, current_value, capacity, utilization_pct, timestamp, service)
- ResourceSnapshot dataclass (snapshot_id, timestamp, metrics, overall_health)
- ResourceMonitor class:
  - record_metric(metric) -> None
  - get_current_utilization(resource_type, service) -> ResourceMetric
  - get_utilization_history(resource_type, service, hours) -> list
  - take_snapshot() -> ResourceSnapshot
  - get_health_status() -> CapacityStatus
  - top_utilized_resources(limit) -> list
  - resource_summary() -> dict

### 3. Demand Forecaster (`forecaster.py`)
- ForecastPoint dataclass (timestamp, predicted_value, confidence_lower, confidence_upper)
- DemandForecast dataclass (forecast_id, resource_type, service, horizon_hours, points, model_used)
- DemandForecaster class:
  - forecast(resource_type, service, horizon_hours) -> DemandForecast
  - forecast_with_moving_average(history, horizon, window) -> list of ForecastPoint
  - forecast_with_exponential_smoothing(history, horizon, alpha) -> list of ForecastPoint
  - detect_seasonality(history) -> (bool, period)
  - predict_peak(resource_type, service) -> (timestamp, value)
  - forecast_accuracy(forecast_id) -> float

### 4. Scaling Manager (`scaling.py`)
- ScalingRule dataclass (rule_id, resource_type, service, policy, thresholds, min_instances, max_instances)
- ScalingAction dataclass (action_id, rule_id, direction, from_value, to_value, reason, timestamp)
- ScalingManager class:
  - add_rule(rule) -> rule_id
  - evaluate_rules() -> list of ScalingAction
  - execute_action(action) -> bool
  - get_scaling_history(service, hours) -> list of ScalingAction
  - set_cooldown(rule_id, seconds) -> None
  - get_active_rules() -> list
  - simulate_scaling(rule, metrics) -> ScalingAction

### 5. Cost Analyzer (`cost.py`)
- ResourceCost dataclass (resource_type, service, hourly_cost, monthly_cost, utilization_pct)
- CostReport dataclass (report_id, period, total_cost, by_service, by_resource, savings_opportunities)
- SavingsOpportunity dataclass (resource, service, current_cost, recommended_cost, savings_pct, action)
- CostAnalyzer class:
  - calculate_costs(period) -> CostReport
  - find_savings(threshold_pct) -> list of SavingsOpportunity
  - right_size_recommendations() -> list
  - cost_forecast(months) -> list of projected costs
  - cost_per_trade() -> float
  - efficiency_score() -> float

## Database Tables
- `capacity_metrics`: Resource utilization metrics
- `scaling_events`: Scaling action history

## Dashboard (4 tabs)
1. Resource Overview — utilization gauges, health status, metrics
2. Demand Forecast — predicted load, seasonal patterns, peak times
3. Scaling Policies — active rules, scaling history, cooldowns
4. Cost Analysis — resource costs, savings opportunities, trends

## Test Coverage
- Resource monitor tests
- Forecasting algorithm tests (moving average, exponential smoothing)
- Scaling rule evaluation tests
- Cost analysis and right-sizing tests
- ~80+ tests
