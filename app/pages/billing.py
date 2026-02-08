"""PRD-125: Cost & Usage Metering + Billing Dashboard."""

import streamlit as st
from datetime import datetime, timezone, timedelta

from src.billing import (
    MeterType,
    InvoiceStatus,
    BillingPeriod,
    PricingTier,
    BillingConfig,
    UsageMeter,
    BillingEngine,
    InvoiceManager,
    CostAnalytics,
)


def _create_sample_data():
    """Generate sample billing data for display."""
    config = BillingConfig(tax_rate=0.08)
    meter = UsageMeter()
    engine = BillingEngine(meter, config)
    inv_mgr = InvoiceManager(config)
    analytics = CostAnalytics(meter, engine)

    # Define meters
    api_meter = meter.define_meter(
        "API Calls", MeterType.API_CALL, "calls", 0.001,
        description="Per-call API metering",
    )
    data_meter = meter.define_meter(
        "Data Feed", MeterType.DATA_FEED, "feeds", 5.0,
        description="Real-time data feed subscription",
    )
    backtest_meter = meter.define_meter(
        "Backtest Runs", MeterType.BACKTEST_RUN, "runs", 0.50,
        description="Per-backtest execution charge",
    )
    training_meter = meter.define_meter(
        "Model Training", MeterType.MODEL_TRAINING, "hours", 2.0,
        description="ML model training compute hours",
    )
    storage_meter = meter.define_meter(
        "Storage", MeterType.STORAGE_GB, "GB", 0.10,
        description="Storage consumption per GB-month",
    )

    # Record usage for workspaces
    now = datetime.now(timezone.utc)
    workspaces = ["ws-alpha", "ws-beta", "ws-gamma"]
    for ws in workspaces:
        meter.record_usage(api_meter.meter_id, ws, 15000,
                           timestamp=now - timedelta(days=15))
        meter.record_usage(data_meter.meter_id, ws, 3,
                           timestamp=now - timedelta(days=10))
        meter.record_usage(backtest_meter.meter_id, ws, 50,
                           timestamp=now - timedelta(days=5))
        meter.record_usage(training_meter.meter_id, ws, 8,
                           timestamp=now - timedelta(days=3))
        meter.record_usage(storage_meter.meter_id, ws, 120,
                           timestamp=now - timedelta(days=1))

    # Generate bills
    period_start = now - timedelta(days=30)
    period_end = now
    bills = []
    for ws in workspaces:
        bill = engine.generate_bill(ws, period_start, period_end)
        bills.append(bill)

    # Create invoices
    invoices = []
    for bill in bills:
        inv = inv_mgr.create_invoice(bill.bill_id, bill.workspace_id, bill.total)
        invoices.append(inv)

    return meter, engine, inv_mgr, analytics, config, workspaces


def render():
    st.set_page_config(page_title="Billing & Metering", layout="wide")
    st.title("Cost & Usage Metering + Billing")

    meter, engine, inv_mgr, analytics, config, workspaces = _create_sample_data()

    tabs = st.tabs(["Usage Overview", "Invoices", "Cost Analytics", "Billing Config"])

    # ── Tab 1: Usage Overview ─────────────────────────────────────────
    with tabs[0]:
        st.subheader("Usage Overview")
        stats = meter.get_statistics()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records", stats["total_records"])
        col2.metric("Total Cost", f"${stats['total_cost']:,.2f}")
        col3.metric("Active Meters", stats["active_meters"])
        col4.metric("Workspaces", stats["unique_workspaces"])

        st.subheader("Defined Meters")
        meter_data = []
        for m in meter.list_meters():
            meter_data.append({
                "Name": m.name,
                "Type": m.meter_type.value,
                "Unit": m.unit,
                "Price/Unit": f"${m.price_per_unit:.4f}",
            })
        st.dataframe(meter_data, use_container_width=True)

        st.subheader("Per-Workspace Usage")
        selected_ws = st.selectbox("Workspace", workspaces, key="usage_ws")
        if selected_ws:
            summary = meter.get_cost_summary(selected_ws)
            cost_data = [
                {"Meter Type": k, "Cost": f"${v:,.4f}"}
                for k, v in summary.items()
            ]
            st.dataframe(cost_data, use_container_width=True)

    # ── Tab 2: Invoices ───────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Invoices")
        inv_stats = inv_mgr.get_statistics()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Invoices", inv_stats["total_invoices"])
        col2.metric("Total Amount", f"${inv_stats['total_amount']:,.2f}")
        col3.metric("Outstanding", f"${inv_stats['total_outstanding']:,.2f}")

        st.subheader("All Invoices")
        inv_data = []
        for inv in inv_mgr.list_invoices():
            inv_data.append({
                "Invoice ID": inv.invoice_id,
                "Workspace": inv.workspace_id,
                "Amount": f"${inv.amount:,.2f}",
                "Status": inv.status.value.upper(),
                "Due Date": inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "N/A",
            })
        st.dataframe(inv_data, use_container_width=True)

        st.subheader("Bills")
        bills = engine.list_bills()
        bill_data = []
        for b in bills:
            bill_data.append({
                "Bill ID": b.bill_id,
                "Workspace": b.workspace_id,
                "Subtotal": f"${b.subtotal:,.2f}",
                "Tax": f"${b.tax:,.2f}",
                "Total": f"${b.total:,.2f}",
                "Status": b.status.value.upper(),
                "Items": len(b.line_items),
            })
        st.dataframe(bill_data, use_container_width=True)

    # ── Tab 3: Cost Analytics ─────────────────────────────────────────
    with tabs[2]:
        st.subheader("Cost Analytics")
        analytics_ws = st.selectbox("Workspace", workspaces, key="analytics_ws")

        if analytics_ws:
            breakdown = analytics.get_workspace_costs(analytics_ws)
            st.write(f"**Total Cost:** ${breakdown.total:,.4f}")
            st.write(f"**Period:** {breakdown.period}")

            cost_by_meter = [
                {"Meter": k, "Cost": f"${v:,.4f}"}
                for k, v in breakdown.by_meter.items()
            ]
            st.dataframe(cost_by_meter, use_container_width=True)

            # Budget status
            st.subheader("Budget Status")
            budget_input = st.number_input("Monthly Budget ($)", value=200.0, step=50.0)
            budget = analytics.get_budget_status(analytics_ws, budget_input)
            bcol1, bcol2, bcol3 = st.columns(3)
            bcol1.metric("Spent", f"${budget['spent']:,.2f}")
            bcol2.metric("Remaining", f"${budget['remaining']:,.2f}")
            bcol3.metric("Utilization", f"{budget['utilization_pct']:.1f}%")
            if budget["is_over_budget"]:
                st.error("Budget exceeded!")
            elif budget["status"] == "critical":
                st.warning("Budget usage is critical (>90%)")

            # Recommendations
            st.subheader("Optimization Recommendations")
            recs = analytics.get_optimization_recommendations(analytics_ws)
            for rec in recs:
                st.info(f"**{rec['type'].upper()}**: {rec['message']}")

        # Top consumers
        st.subheader("Top Consumers")
        top = analytics.get_top_consumers(limit=5)
        top_data = [
            {
                "Rank": t["rank"],
                "Workspace": t["workspace_id"],
                "Total Cost": f"${t['total_cost']:,.4f}",
                "Usage Count": t["usage_count"],
            }
            for t in top
        ]
        st.dataframe(top_data, use_container_width=True)

    # ── Tab 4: Billing Config ─────────────────────────────────────────
    with tabs[3]:
        st.subheader("Billing Configuration")

        st.write("**Current Settings:**")
        cfg_data = {
            "Default Period": config.default_period.value,
            "Tax Rate": f"{config.tax_rate:.1%}",
            "Currency": config.currency,
            "Grace Period": f"{config.grace_period_days} days",
            "Invoice Prefix": config.invoice_prefix,
            "Auto Finalize": config.auto_finalize,
            "Send Reminders": config.send_reminders,
            "Reminder Days Before Due": config.reminder_days_before_due,
            "Overdue Penalty Rate": f"{config.overdue_penalty_rate:.1%}",
            "Max Credit Balance": f"${config.max_credit_balance:,.2f}",
        }
        for key, val in cfg_data.items():
            st.write(f"- **{key}:** {val}")

        st.subheader("Pricing Tiers")
        tier_info = {
            PricingTier.FREE: {"price": "$0/mo", "limits": "100 API calls, 1 backtest/day"},
            PricingTier.STARTER: {"price": "$29/mo", "limits": "10K API calls, 50 backtests/day"},
            PricingTier.PROFESSIONAL: {"price": "$99/mo", "limits": "100K API calls, unlimited backtests"},
            PricingTier.ENTERPRISE: {"price": "Custom", "limits": "Unlimited, dedicated support"},
        }
        tier_data = [
            {"Tier": t.value.title(), "Price": info["price"], "Limits": info["limits"]}
            for t, info in tier_info.items()
        ]
        st.dataframe(tier_data, use_container_width=True)

        st.subheader("Meter Types")
        mt_data = [
            {"Type": mt.value, "Description": mt.name.replace("_", " ").title()}
            for mt in MeterType
        ]
        st.dataframe(mt_data, use_container_width=True)

        st.subheader("Revenue Summary")
        rev = engine.get_revenue_summary()
        rcol1, rcol2, rcol3 = st.columns(3)
        rcol1.metric("Total Revenue", f"${rev['total_revenue']:,.2f}")
        rcol2.metric("Total Bills", rev["bill_count"])
        rcol3.metric("Avg Bill", f"${rev['avg_bill_amount']:,.2f}")


if __name__ == "__main__":
    render()
