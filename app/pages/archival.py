"""PRD-118: Data Archival & GDPR Compliance Dashboard."""

import streamlit as st
from datetime import datetime, timedelta

from src.archival import (
    StorageTier,
    ArchivalFormat,
    GDPRRequestType,
    GDPRRequestStatus,
    ArchivalConfig,
    ArchivalEngine,
    RetentionPolicy,
    RetentionManager,
    GDPRRequest,
    GDPRManager,
    TierStats,
    DataLifecycleManager,
)

st.set_page_config(page_title="Data Archival", page_icon="\U0001F4E6", layout="wide")


def render():
    st.title("\U0001F4E6 Data Archival & GDPR Compliance")

    tabs = st.tabs(["Storage Tiers", "Archival Jobs", "GDPR Requests", "Policies"])

    # Initialize sample data
    lifecycle = DataLifecycleManager()
    lifecycle.record_tier_stats(StorageTier.HOT, 2_500_000, 85 * (1024 ** 3), 12)
    lifecycle.record_tier_stats(StorageTier.WARM, 8_000_000, 210 * (1024 ** 3), 10)
    lifecycle.record_tier_stats(StorageTier.COLD, 15_000_000, 520 * (1024 ** 3), 8)
    lifecycle.record_tier_stats(StorageTier.ARCHIVE, 30_000_000, 1200 * (1024 ** 3), 6)

    engine = ArchivalEngine()
    tables = ["price_bars", "trade_orders", "trade_executions", "portfolio_snapshots", "factor_scores"]
    for i, table in enumerate(tables):
        start = datetime(2023, 1 + i, 1)
        end = datetime(2023, 3 + i, 28)
        job = engine.create_job(table, start, end)
        if i < 3:
            engine.execute_job(job.job_id)

    retention_mgr = RetentionManager()
    retention_mgr.add_policy("price_bars", hot_days=30, warm_days=180, cold_days=1095, description="High-frequency price data")
    retention_mgr.add_policy("trade_orders", hot_days=90, warm_days=365, cold_days=2555, delete_after=3650, description="Trade order history")
    retention_mgr.add_policy("trade_executions", hot_days=90, warm_days=365, cold_days=2555, description="Execution records")
    retention_mgr.add_policy("portfolio_snapshots", hot_days=60, warm_days=365, cold_days=2555, description="Daily portfolio snapshots")
    retention_mgr.add_policy("factor_scores", hot_days=30, warm_days=180, cold_days=730, delete_after=1095, description="Pre-computed factor scores")
    retention_mgr.set_legal_hold("trade_executions", "Regulatory audit 2024")

    gdpr_mgr = GDPRManager()
    req1 = gdpr_mgr.submit_request("user-101", GDPRRequestType.ACCESS, notes="Customer data access request")
    req2 = gdpr_mgr.submit_request("user-202", GDPRRequestType.DELETION, notes="Account closure")
    req3 = gdpr_mgr.submit_request("user-303", GDPRRequestType.EXPORT, notes="Data portability")
    req4 = gdpr_mgr.submit_request("user-404", GDPRRequestType.RECTIFICATION, notes="Address correction")
    gdpr_mgr.process_request(req1.request_id)
    gdpr_mgr.process_request(req2.request_id)
    gdpr_mgr.reject_request(req4.request_id, "Duplicate request")

    # ── Tab 1: Storage Tiers ──────────────────────────────────────────
    with tabs[0]:
        st.subheader("Storage Tier Distribution")

        summary = lifecycle.get_storage_summary()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records", f"{summary['total_records']:,}")
        col2.metric("Total Storage", f"{summary['total_bytes'] / (1024**3):.1f} GB")
        col3.metric("Monthly Cost", f"${summary['total_monthly_cost']:.2f}")
        col4.metric("Active Tiers", summary["tier_count"])

        st.subheader("Tier Breakdown")
        tier_data = []
        costs = lifecycle.get_cost_by_tier()
        for tier_name, info in summary["tier_breakdown"].items():
            cost_info = costs.get(tier_name, {})
            tier_data.append({
                "Tier": tier_name.upper(),
                "Records": f"{info['records']:,}",
                "Storage (GB)": f"{info['bytes'] / (1024**3):.1f}",
                "Tables": info["tables"],
                "Cost/GB/Month": f"${info['cost_per_gb_month']:.5f}",
                "Monthly Cost": f"${cost_info.get('monthly_cost', 0):.2f}",
            })
        st.dataframe(tier_data, use_container_width=True)

        st.subheader("Optimization Recommendations")
        recs = lifecycle.get_optimization_recommendations()
        for rec in recs:
            priority_color = {"high": "red", "medium": "orange", "low": "blue", "info": "green"}
            color = priority_color.get(rec["priority"], "gray")
            st.markdown(
                f":{color}[**{rec['priority'].upper()}**] {rec['recommendation']} "
                f"| Savings: **${rec['savings']:.2f}/mo**"
            )

    # ── Tab 2: Archival Jobs ──────────────────────────────────────────
    with tabs[1]:
        st.subheader("Archival Jobs")

        stats = engine.get_storage_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Jobs", stats["total_jobs"])
        col2.metric("Completed", stats["completed_jobs"])
        col3.metric("Archived Records", f"{stats['total_records']:,}")
        col4.metric("Archived Size", f"{stats['total_bytes'] / (1024**2):.1f} MB")

        st.subheader("Job List")
        job_data = []
        for job in engine.list_jobs():
            status_icon = {"pending": "\u23F3", "running": "\u25B6\uFE0F", "completed": "\u2705", "failed": "\u274C"}
            job_data.append({
                "Status": f"{status_icon.get(job.status, '')} {job.status.upper()}",
                "Table": job.table_name,
                "Date Range": f"{job.date_range_start.strftime('%Y-%m-%d')} to {job.date_range_end.strftime('%Y-%m-%d')}",
                "Format": job.format.value.upper(),
                "Records": f"{job.records_archived:,}" if job.records_archived > 0 else "-",
                "Size": f"{job.bytes_written / (1024**2):.1f} MB" if job.bytes_written > 0 else "-",
            })
        st.dataframe(job_data, use_container_width=True)

    # ── Tab 3: GDPR Requests ─────────────────────────────────────────
    with tabs[2]:
        st.subheader("GDPR Data Subject Requests")

        report = gdpr_mgr.generate_compliance_report()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Requests", report["total_requests"])
        col2.metric("Completed", report["by_status"].get("completed", 0))
        col3.metric("Pending", report["by_status"].get("pending", 0))
        col4.metric("Records Affected", f"{report['total_records_affected']:,}")

        st.subheader("Request Breakdown by Type")
        type_data = []
        for rtype, count in report["by_type"].items():
            type_data.append({"Type": rtype.upper(), "Count": count})
        st.dataframe(type_data, use_container_width=True)

        st.subheader("Request Log")
        request_data = []
        for req in gdpr_mgr.list_requests():
            status_color = {
                "pending": "\u23F3",
                "processing": "\u25B6\uFE0F",
                "completed": "\u2705",
                "failed": "\u274C",
                "rejected": "\U0001F6AB",
            }
            request_data.append({
                "Status": f"{status_color.get(req.status.value, '')} {req.status.value.upper()}",
                "User": req.user_id,
                "Type": req.request_type.value.upper(),
                "Tables": len(req.tables_affected),
                "Records": f"{req.records_affected:,}" if req.records_affected > 0 else "-",
                "Submitted": req.submitted_at.strftime("%Y-%m-%d %H:%M"),
                "Notes": req.notes[:50] + "..." if len(req.notes) > 50 else req.notes,
            })
        st.dataframe(request_data, use_container_width=True)

        st.subheader("Deletion Audit Log")
        del_log = gdpr_mgr.get_deletion_log()
        if del_log:
            del_data = []
            for entry in del_log:
                del_data.append({
                    "User": entry["user_id"],
                    "Tables": len(entry["tables"]),
                    "Records Deleted": f"{entry['records_deleted']:,}",
                    "Audit Proof": entry["audit_proof"],
                    "Deleted At": entry["deleted_at"],
                })
            st.dataframe(del_data, use_container_width=True)
        else:
            st.info("No deletion records.")

    # ── Tab 4: Policies ───────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Retention Policies")

        policies = retention_mgr.get_policies()
        holds = retention_mgr.get_holds()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Policies", len(policies))
        col2.metric("Legal Holds", len(holds))
        col3.metric("Tables with Deletion", sum(1 for p in policies if p.delete_after_days is not None))

        policy_data = []
        for p in policies:
            hold_status = "\U0001F512 HELD" if p.legal_hold else "\u2705 Normal"
            policy_data.append({
                "Table": p.table_name,
                "Hot (days)": p.hot_days,
                "Warm (days)": p.warm_days,
                "Cold (days)": p.cold_days,
                "Delete After": f"{p.delete_after_days} days" if p.delete_after_days else "Never",
                "Legal Hold": hold_status,
                "Description": p.description,
            })
        st.dataframe(policy_data, use_container_width=True)

        st.subheader("Tier Evaluation (Sample Ages)")
        eval_data = []
        sample_ages = [30, 100, 400, 1000, 3000]
        for p in policies:
            for age in sample_ages:
                result = retention_mgr.evaluate_table(p.table_name, age)
                eval_data.append({
                    "Table": p.table_name,
                    "Data Age (days)": age,
                    "Current Tier": result["current_tier"].upper(),
                    "Action Needed": result["action_needed"],
                })
        st.dataframe(eval_data, use_container_width=True)

        if holds:
            st.subheader("Active Legal Holds")
            for table in holds:
                st.warning(f"\U0001F512 **{table}** is under legal hold - deletion suspended")


if __name__ == "__main__":
    render()
