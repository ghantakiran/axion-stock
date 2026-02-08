# PRD-125: Cost & Usage Metering + Billing

## Overview
Usage-based billing with real-time metering of API calls, data subscriptions, and
compute resources. Bill generation, invoicing, and payment processor integration
for SaaS monetization of the Axion platform.

## Problem
API usage is logged but not metered for billing. No cost attribution per workspace
or feature. No invoice generation. Cannot monetize the platform as SaaS. No
visibility into per-customer resource consumption.

## Components

### 1. Usage Meter (`src/billing/meter.py`)
- Real-time event aggregation of billable actions
- Configurable meters (API calls, data feeds, backtest runs, model training)
- Cost calculation with tiered pricing
- Meter rollup by period (hourly, daily, monthly)
- Usage threshold alerts

### 2. Billing Engine (`src/billing/engine.py`)
- Monthly bill generation from aggregated usage
- Tier-based discount application
- Promotional credit and coupon management
- Overage charge calculation
- Bill preview before finalization

### 3. Invoice Manager (`src/billing/invoices.py`)
- Invoice generation with line items
- Invoice status tracking (draft, sent, paid, overdue)
- Payment recording and reconciliation
- Credit note generation for refunds
- Invoice template rendering

### 4. Cost Analytics (`src/billing/analytics.py`)
- Per-workspace cost breakdown
- Per-feature cost attribution
- Cost trend analysis and forecasting
- Budget alerts and spending limits
- Cost optimization recommendations

## Database
- `billing_meters` table for meter definitions and state
- `invoices` table for generated invoices

## Dashboard
4-tab Streamlit dashboard: Usage Overview, Invoices, Cost Analytics, Billing Config
