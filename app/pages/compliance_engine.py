"""PRD-99: Compliance Engine Dashboard."""

import streamlit as st
from datetime import date, timedelta

from src.compliance_engine import (
    SurveillanceEngine,
    BlackoutManager,
    BestExecutionMonitor,
    RegulatoryReporter,
    SurveillanceConfig,
    BlackoutConfig,
    ComplianceSummary,
)


def render():
    st.title("Compliance Engine")

    tabs = st.tabs(["Surveillance", "Blackout Windows", "Best Execution", "Reports"])

    # ── Tab 1: Trade Surveillance ────────────────────────────────────
    with tabs[0]:
        st.subheader("Trade Surveillance")

        engine = SurveillanceEngine()

        # Demo trades with violations
        demo_trades = [
            {"symbol": "AAPL", "side": "buy", "price": 175.0, "timestamp": 1000},
            {"symbol": "AAPL", "side": "sell", "price": 175.0, "timestamp": 1100},
            {"symbol": "MSFT", "status": "cancelled"},
            {"symbol": "MSFT", "status": "cancelled"},
            {"symbol": "MSFT", "status": "cancelled"},
            {"symbol": "MSFT", "status": "filled"},
            {"symbol": "GOOG", "side": "buy", "quantity": 5000, "minutes_to_close": 2},
        ]

        alerts = engine.scan_trades(demo_trades, "DEMO-ACC")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Alerts", len(alerts))
        col2.metric("Unresolved", len([a for a in alerts if not a.is_resolved]))
        col3.metric("Critical", len([a for a in alerts if a.severity == "critical"]))

        for alert in alerts:
            severity_color = {"critical": "red", "high": "orange", "medium": "blue", "low": "gray"}
            st.markdown(
                f"**{alert.alert_type.upper()}** | :{severity_color.get(alert.severity, 'gray')}[{alert.severity}] | "
                f"{alert.symbol} | {alert.description}"
            )

    # ── Tab 2: Blackout Windows ──────────────────────────────────────
    with tabs[1]:
        st.subheader("Insider Trading Blackout Windows")

        mgr = BlackoutManager()
        today = date.today()
        mgr.create_earnings_blackout("AAPL", today + timedelta(days=10))
        mgr.create_earnings_blackout("MSFT", today + timedelta(days=20))
        mgr.create_blackout("TSLA", "Material Event", today - timedelta(days=2), today + timedelta(days=5))

        active = mgr.get_active_blackouts()
        st.metric("Active Blackout Windows", len(active))

        window_data = []
        for w in mgr.list_all_windows():
            window_data.append({
                "Symbol": w.symbol,
                "Reason": w.reason,
                "Start": w.start_date.isoformat(),
                "End": w.end_date.isoformat(),
                "Active": "Yes" if w.is_in_blackout(today) else "No",
            })
        st.dataframe(window_data, use_container_width=True)

        st.subheader("Pre-Clearance Requests")
        req = mgr.submit_pre_clearance("trader_1", "AAPL", "buy", 200, 35000, "Portfolio rebalance")
        st.write(f"**Pending:** {len(mgr.get_pending_requests())} requests")

    # ── Tab 3: Best Execution ────────────────────────────────────────
    with tabs[2]:
        st.subheader("Best Execution Monitoring")

        monitor = BestExecutionMonitor()
        today = date.today()

        # Generate sample executions
        import random
        random.seed(42)
        for i in range(20):
            slip = random.gauss(3, 4)
            fill = 175.0 + slip * 0.0175
            venue = random.choice(["NYSE", "NASDAQ", "IEX", "ARCA"])
            monitor.record_execution(
                f"O{i:03d}", "AAPL", "buy", 100 + i * 10,
                176.0, fill, 175.0, venue,
            )

        report = monitor.generate_report(today - timedelta(days=1), today + timedelta(days=1))

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Orders", report.total_orders)
        col2.metric("Avg Slippage", f"{report.avg_slippage_bps:.1f} bps")
        col3.metric("Quality", report.overall_quality.upper())
        col4.metric("Cost Saved", f"${report.total_cost_saved:.2f}")

        st.subheader("Quality Distribution")
        dist_data = {
            "Excellent": f"{report.excellent_pct:.0%}",
            "Good": f"{report.good_pct:.0%}",
            "Poor": f"{report.poor_pct:.0%}",
            "Failed": f"{report.failed_pct:.0%}",
        }
        st.write(dist_data)

        st.subheader("Venue Ranking")
        ranking = monitor.get_venue_ranking()
        st.dataframe(ranking, use_container_width=True)

    # ── Tab 4: Regulatory Reports ────────────────────────────────────
    with tabs[3]:
        st.subheader("Regulatory Reports")

        reporter = RegulatoryReporter()
        filing = reporter.generate_daily_compliance(date.today(), [])

        summary = reporter.generate_compliance_summary(
            "Today", [], blackout_violations=0,
        )

        status_color = "green" if summary.overall_status == "compliant" else "red"
        st.markdown(f"**Status:** :{status_color}[{summary.overall_status.upper()}]")

        col1, col2, col3 = st.columns(3)
        col1.metric("Alerts", summary.surveillance_alerts)
        col2.metric("Unresolved", summary.unresolved_alerts)
        col3.metric("Filings Due", summary.filings_due)

        st.subheader("Recent Filings")
        filings = reporter.get_filings()
        for f in filings:
            st.write(f"**{f.title}** — {'Filed' if f.filed else 'Pending'}")


if __name__ == "__main__":
    render()
