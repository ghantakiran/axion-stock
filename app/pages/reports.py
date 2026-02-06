"""Professional Reporting Dashboard - PRD-70.

Report generation and management:
- Generate PDF/Excel/HTML reports
- Report templates with customization
- Scheduled report automation
- White-label branding
- Distribution management
"""

import sys
import os
from datetime import datetime, date, timedelta
import random
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Reports", page_icon="📊", layout="wide")

# Try to import enterprise modules
try:
    from src.enterprise.reporting import ReportGenerator, ReportData, PerformanceMetrics
    REPORTING_AVAILABLE = True
except ImportError:
    REPORTING_AVAILABLE = False


def init_session_state():
    """Initialize session state."""
    if "demo_reports" not in st.session_state:
        st.session_state.demo_reports = generate_demo_reports()
    if "demo_templates" not in st.session_state:
        st.session_state.demo_templates = generate_demo_templates()
    if "demo_schedules" not in st.session_state:
        st.session_state.demo_schedules = generate_demo_schedules()
    if "demo_branding" not in st.session_state:
        st.session_state.demo_branding = generate_demo_branding()


def generate_demo_reports():
    """Generate demo report data."""
    reports = [
        {
            "id": "rpt-001",
            "title": "Q4 2025 Performance Report",
            "report_type": "performance",
            "format": "pdf",
            "account": "Personal Brokerage",
            "period_start": date(2025, 10, 1),
            "period_end": date(2025, 12, 31),
            "status": "completed",
            "file_size": 245000,
            "created_at": datetime(2026, 1, 5, 9, 30),
            "metrics": {
                "period_return": 0.084,
                "benchmark_return": 0.062,
                "alpha": 0.022,
                "sharpe": 1.67,
                "max_drawdown": -0.038,
            },
        },
        {
            "id": "rpt-002",
            "title": "December 2025 Holdings Report",
            "report_type": "holdings",
            "format": "excel",
            "account": "Personal Brokerage",
            "period_start": date(2025, 12, 1),
            "period_end": date(2025, 12, 31),
            "status": "completed",
            "file_size": 128000,
            "created_at": datetime(2026, 1, 2, 14, 15),
            "metrics": {
                "total_positions": 12,
                "total_value": 142300,
                "cash_pct": 8.7,
            },
        },
        {
            "id": "rpt-003",
            "title": "2025 Annual Performance Report",
            "report_type": "performance",
            "format": "pdf",
            "account": "All Accounts",
            "period_start": date(2025, 1, 1),
            "period_end": date(2025, 12, 31),
            "status": "completed",
            "file_size": 412000,
            "created_at": datetime(2026, 1, 3, 10, 0),
            "metrics": {
                "period_return": 0.186,
                "benchmark_return": 0.142,
                "alpha": 0.044,
                "sharpe": 1.82,
                "max_drawdown": -0.112,
            },
        },
        {
            "id": "rpt-004",
            "title": "Trade Activity Report - January 2026",
            "report_type": "trade_activity",
            "format": "pdf",
            "account": "Roth IRA",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "status": "generating",
            "file_size": None,
            "created_at": datetime(2026, 2, 1, 8, 0),
            "metrics": {},
        },
    ]
    return reports


def generate_demo_templates():
    """Generate demo template data."""
    templates = [
        {
            "id": "tpl-001",
            "name": "Quarterly Performance",
            "description": "Standard quarterly performance report with attribution analysis",
            "report_type": "performance",
            "is_default": True,
            "sections": ["Executive Summary", "Performance Attribution", "Holdings", "Risk Analysis", "Trade Activity"],
            "created_at": datetime(2024, 6, 1),
        },
        {
            "id": "tpl-002",
            "name": "Monthly Holdings",
            "description": "Monthly holdings snapshot with sector breakdown",
            "report_type": "holdings",
            "is_default": False,
            "sections": ["Holdings Summary", "Sector Allocation", "Top Performers", "Watchlist"],
            "created_at": datetime(2024, 7, 15),
        },
        {
            "id": "tpl-003",
            "name": "Risk Dashboard",
            "description": "Risk metrics and exposure analysis",
            "report_type": "risk",
            "is_default": False,
            "sections": ["Risk Summary", "VaR Analysis", "Factor Exposures", "Stress Tests"],
            "created_at": datetime(2024, 8, 1),
        },
    ]
    return templates


def generate_demo_schedules():
    """Generate demo schedule data."""
    schedules = [
        {
            "id": "sch-001",
            "name": "Weekly Performance Digest",
            "template": "Quarterly Performance",
            "frequency": "weekly",
            "day_of_week": 0,  # Monday
            "time": "08:00",
            "format": "pdf",
            "recipients": ["john@example.com", "advisor@example.com"],
            "is_active": True,
            "last_run": datetime(2026, 2, 3, 8, 0),
            "next_run": datetime(2026, 2, 10, 8, 0),
            "run_count": 52,
        },
        {
            "id": "sch-002",
            "name": "Monthly Holdings Export",
            "template": "Monthly Holdings",
            "frequency": "monthly",
            "day_of_month": 1,
            "time": "09:00",
            "format": "excel",
            "recipients": ["john@example.com"],
            "is_active": True,
            "last_run": datetime(2026, 2, 1, 9, 0),
            "next_run": datetime(2026, 3, 1, 9, 0),
            "run_count": 8,
        },
        {
            "id": "sch-003",
            "name": "Quarterly Client Report",
            "template": "Quarterly Performance",
            "frequency": "quarterly",
            "day_of_month": 5,
            "time": "10:00",
            "format": "pdf",
            "recipients": ["john@example.com", "client@example.com"],
            "is_active": False,
            "last_run": datetime(2026, 1, 5, 10, 0),
            "next_run": datetime(2026, 4, 5, 10, 0),
            "run_count": 4,
        },
    ]
    return schedules


def generate_demo_branding():
    """Generate demo branding data."""
    return {
        "company_name": "Alpha Capital Management",
        "logo_url": None,
        "primary_color": "#1a5f7a",
        "secondary_color": "#57837b",
        "accent_color": "#c38e70",
        "header_text": "Professional Investment Management",
        "footer_text": "This report is for informational purposes only.",
        "disclaimer": "Past performance is not indicative of future results. Investment involves risk.",
        "contact_email": "info@alphacapital.com",
        "contact_phone": "(555) 123-4567",
        "website": "www.alphacapital.com",
    }


def render_reports_list():
    """Render list of generated reports."""
    st.subheader("Generated Reports")

    reports = st.session_state.demo_reports

    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        type_filter = st.selectbox(
            "Report Type",
            ["All", "Performance", "Holdings", "Trade Activity", "Risk"],
            label_visibility="collapsed",
        )
    with col2:
        format_filter = st.selectbox(
            "Format",
            ["All", "PDF", "Excel", "HTML"],
            label_visibility="collapsed",
        )
    with col3:
        if st.button("Generate New", type="primary", use_container_width=True):
            st.session_state.show_generate_form = True

    # Filter reports
    filtered = reports
    if type_filter != "All":
        filtered = [r for r in filtered if r['report_type'].lower() == type_filter.lower()]
    if format_filter != "All":
        filtered = [r for r in filtered if r['format'].upper() == format_filter.upper()]

    if not filtered:
        st.info("No reports found matching your criteria.")
        return

    # Reports table
    for report in filtered:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 1.5, 1.5, 1, 1])

            with col1:
                status_icons = {
                    "completed": "✅",
                    "generating": "⏳",
                    "failed": "❌",
                    "pending": "🕐",
                }
                icon = status_icons.get(report['status'], "📄")
                st.markdown(f"{icon} **{report['title']}**")
                st.caption(f"{report['account']} | {report['period_start']} to {report['period_end']}")

            with col2:
                st.text(report['report_type'].replace("_", " ").title())

            with col3:
                st.text(report['format'].upper())
                if report['file_size']:
                    st.caption(f"{report['file_size']/1000:.0f} KB")

            with col4:
                st.text(report['created_at'].strftime("%b %d"))

            with col5:
                if report['status'] == 'completed':
                    st.button("Download", key=f"dl_{report['id']}", use_container_width=True)
                elif report['status'] == 'generating':
                    st.button("Cancel", key=f"cancel_{report['id']}", use_container_width=True, disabled=True)

            # Show metrics for completed reports
            if report['status'] == 'completed' and report.get('metrics'):
                with st.expander("View Metrics"):
                    metrics = report['metrics']
                    cols = st.columns(5)
                    for i, (key, value) in enumerate(metrics.items()):
                        with cols[i % 5]:
                            if isinstance(value, float):
                                if 'pct' in key or 'return' in key or 'alpha' in key or 'drawdown' in key:
                                    st.metric(key.replace("_", " ").title(), f"{value*100:.1f}%")
                                else:
                                    st.metric(key.replace("_", " ").title(), f"{value:.2f}")
                            else:
                                st.metric(key.replace("_", " ").title(), value)

            st.divider()


def render_generate_report():
    """Render report generation form."""
    st.subheader("Generate New Report")

    with st.form("generate_report"):
        col1, col2 = st.columns(2)

        with col1:
            report_type = st.selectbox(
                "Report Type",
                ["Performance", "Holdings", "Trade Activity", "Attribution", "Risk", "Custom"],
            )
            template = st.selectbox(
                "Template",
                ["Default Template"] + [t['name'] for t in st.session_state.demo_templates],
            )
            account = st.selectbox(
                "Account",
                ["All Accounts", "Personal Brokerage", "Roth IRA", "Traditional IRA"],
            )

        with col2:
            format = st.selectbox("Format", ["PDF", "Excel", "HTML"])
            period = st.selectbox(
                "Period",
                ["Last Month", "Last Quarter", "Year to Date", "Last Year", "Custom"],
            )

            if period == "Custom":
                date_col1, date_col2 = st.columns(2)
                with date_col1:
                    start_date = st.date_input("Start Date", date.today() - timedelta(days=90))
                with date_col2:
                    end_date = st.date_input("End Date", date.today())
            else:
                start_date = date.today() - timedelta(days=30)
                end_date = date.today()

        title = st.text_input("Report Title", value=f"{report_type} Report - {date.today().strftime('%B %Y')}")

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Generate Report", type="primary", use_container_width=True)
        with col2:
            st.form_submit_button("Cancel", use_container_width=True)

        if submitted:
            new_report = {
                "id": f"rpt-{uuid.uuid4().hex[:8]}",
                "title": title,
                "report_type": report_type.lower().replace(" ", "_"),
                "format": format.lower(),
                "account": account,
                "period_start": start_date,
                "period_end": end_date,
                "status": "generating",
                "file_size": None,
                "created_at": datetime.now(),
                "metrics": {},
            }
            st.session_state.demo_reports.insert(0, new_report)
            st.success(f"Report '{title}' is being generated...")
            st.rerun()


def render_templates():
    """Render report templates management."""
    st.subheader("Report Templates")

    templates = st.session_state.demo_templates

    for template in templates:
        with st.container():
            col1, col2, col3 = st.columns([4, 1, 1])

            with col1:
                default_badge = " (Default)" if template['is_default'] else ""
                st.markdown(f"**{template['name']}**{default_badge}")
                st.caption(template['description'])

                # Show sections
                sections_str = " → ".join(template['sections'][:4])
                if len(template['sections']) > 4:
                    sections_str += f" + {len(template['sections']) - 4} more"
                st.text(f"Sections: {sections_str}")

            with col2:
                st.text(template['report_type'].title())

            with col3:
                st.button("Edit", key=f"edit_{template['id']}", use_container_width=True)

            st.divider()

    # Create new template
    with st.expander("Create New Template"):
        with st.form("create_template"):
            name = st.text_input("Template Name")
            description = st.text_area("Description")

            report_type = st.selectbox(
                "Report Type",
                ["Performance", "Holdings", "Trade Activity", "Attribution", "Risk"],
            )

            st.multiselect(
                "Sections",
                [
                    "Executive Summary", "Performance Chart", "Monthly Returns",
                    "Holdings Table", "Sector Allocation", "Performance Attribution",
                    "Risk Analysis", "Trade Activity", "Factor Exposures",
                ],
                default=["Executive Summary", "Performance Chart", "Holdings Table"],
            )

            if st.form_submit_button("Create Template", type="primary"):
                if name:
                    new_template = {
                        "id": f"tpl-{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "description": description,
                        "report_type": report_type.lower(),
                        "is_default": False,
                        "sections": ["Executive Summary", "Performance Chart", "Holdings Table"],
                        "created_at": datetime.now(),
                    }
                    st.session_state.demo_templates.append(new_template)
                    st.success(f"Template '{name}' created!")
                    st.rerun()


def render_schedules():
    """Render scheduled reports management."""
    st.subheader("Scheduled Reports")

    schedules = st.session_state.demo_schedules

    for schedule in schedules:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 1.5, 1.5, 1.5, 1])

            with col1:
                status_icon = "🟢" if schedule['is_active'] else "⏸️"
                st.markdown(f"{status_icon} **{schedule['name']}**")
                st.caption(f"Template: {schedule['template']} | {schedule['format'].upper()}")

            with col2:
                freq_display = {
                    "daily": "Daily",
                    "weekly": f"Weekly (Mon)" if schedule.get('day_of_week') == 0 else "Weekly",
                    "monthly": f"Monthly (Day {schedule.get('day_of_month', 1)})",
                    "quarterly": "Quarterly",
                }
                st.text(freq_display.get(schedule['frequency'], schedule['frequency'].title()))
                st.caption(f"@ {schedule['time']}")

            with col3:
                st.text(f"{len(schedule['recipients'])} recipients")
                st.caption(f"Run {schedule['run_count']} times")

            with col4:
                if schedule['next_run']:
                    st.text(f"Next: {schedule['next_run'].strftime('%b %d')}")
                if schedule['last_run']:
                    st.caption(f"Last: {schedule['last_run'].strftime('%b %d')}")

            with col5:
                if schedule['is_active']:
                    if st.button("Pause", key=f"pause_{schedule['id']}", use_container_width=True):
                        schedule['is_active'] = False
                        st.rerun()
                else:
                    if st.button("Resume", key=f"resume_{schedule['id']}", use_container_width=True):
                        schedule['is_active'] = True
                        st.rerun()

            st.divider()

    # Create new schedule
    with st.expander("Create New Schedule"):
        with st.form("create_schedule"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Schedule Name")
                template = st.selectbox(
                    "Template",
                    [t['name'] for t in st.session_state.demo_templates],
                )
                frequency = st.selectbox(
                    "Frequency",
                    ["Daily", "Weekly", "Monthly", "Quarterly"],
                )

            with col2:
                format = st.selectbox("Format", ["PDF", "Excel", "HTML"])
                time_of_day = st.time_input("Time", value=datetime.strptime("08:00", "%H:%M").time())
                recipients = st.text_input("Recipients (comma-separated)", placeholder="email1@example.com, email2@example.com")

            if st.form_submit_button("Create Schedule", type="primary"):
                if name and recipients:
                    recipient_list = [r.strip() for r in recipients.split(",")]
                    new_schedule = {
                        "id": f"sch-{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "template": template,
                        "frequency": frequency.lower(),
                        "time": time_of_day.strftime("%H:%M"),
                        "format": format.lower(),
                        "recipients": recipient_list,
                        "is_active": True,
                        "last_run": None,
                        "next_run": datetime.now() + timedelta(days=1),
                        "run_count": 0,
                    }
                    st.session_state.demo_schedules.append(new_schedule)
                    st.success(f"Schedule '{name}' created!")
                    st.rerun()


def render_branding():
    """Render white-label branding settings."""
    st.subheader("White-Label Branding")

    branding = st.session_state.demo_branding

    with st.form("branding_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Company Information**")
            company_name = st.text_input("Company Name", value=branding['company_name'])
            header_text = st.text_input("Header Text", value=branding['header_text'])
            contact_email = st.text_input("Contact Email", value=branding['contact_email'])
            contact_phone = st.text_input("Contact Phone", value=branding['contact_phone'])
            website = st.text_input("Website", value=branding['website'])

        with col2:
            st.markdown("**Colors & Branding**")
            primary_color = st.color_picker("Primary Color", value=branding['primary_color'])
            secondary_color = st.color_picker("Secondary Color", value=branding['secondary_color'])
            accent_color = st.color_picker("Accent Color", value=branding['accent_color'])

            st.markdown("**Logo**")
            st.file_uploader("Upload Logo", type=['png', 'jpg', 'svg'])

        st.markdown("**Legal Text**")
        footer_text = st.text_input("Footer Text", value=branding['footer_text'])
        disclaimer = st.text_area("Disclaimer", value=branding['disclaimer'])

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Save Branding", type="primary", use_container_width=True):
                st.session_state.demo_branding = {
                    "company_name": company_name,
                    "logo_url": branding['logo_url'],
                    "primary_color": primary_color,
                    "secondary_color": secondary_color,
                    "accent_color": accent_color,
                    "header_text": header_text,
                    "footer_text": footer_text,
                    "disclaimer": disclaimer,
                    "contact_email": contact_email,
                    "contact_phone": contact_phone,
                    "website": website,
                }
                st.success("Branding settings saved!")
        with col2:
            st.form_submit_button("Preview Report", use_container_width=True)

    # Preview
    st.subheader("Branding Preview")

    preview_html = f"""
    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 20px; background: white;">
        <div style="border-bottom: 3px solid {branding['primary_color']}; padding-bottom: 15px; margin-bottom: 15px;">
            <h2 style="color: {branding['primary_color']}; margin: 0;">{branding['company_name']}</h2>
            <p style="color: {branding['secondary_color']}; margin: 5px 0 0 0; font-size: 14px;">{branding['header_text']}</p>
        </div>
        <div style="min-height: 100px; padding: 10px;">
            <p style="color: #333;">Sample report content would appear here...</p>
            <div style="background: {branding['accent_color']}20; padding: 10px; border-radius: 4px; margin-top: 10px;">
                <strong style="color: {branding['accent_color']};">+12.4%</strong>
                <span style="color: #666;"> YTD Return</span>
            </div>
        </div>
        <div style="border-top: 1px solid #ddd; padding-top: 15px; margin-top: 15px; font-size: 12px; color: #666;">
            <p>{branding['footer_text']}</p>
            <p style="font-style: italic;">{branding['disclaimer'][:100]}...</p>
            <p>{branding['contact_email']} | {branding['contact_phone']} | {branding['website']}</p>
        </div>
    </div>
    """
    st.markdown(preview_html, unsafe_allow_html=True)


def render_report_preview():
    """Render a sample report preview."""
    st.subheader("Sample Report Preview")

    # Generate sample data
    dates = pd.date_range(start='2025-01-01', periods=365, freq='D')
    base_value = 100000

    values = [base_value]
    for _ in range(364):
        change = random.gauss(0.0003, 0.01)
        values.append(values[-1] * (1 + change))

    # Performance chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        name="Portfolio",
        line=dict(color="#1a5f7a", width=2),
        fill='tozeroy',
        fillcolor='rgba(26, 95, 122, 0.1)',
    ))

    # Add benchmark
    benchmark = [base_value]
    for _ in range(364):
        change = random.gauss(0.00025, 0.008)
        benchmark.append(benchmark[-1] * (1 + change))

    fig.add_trace(go.Scatter(
        x=dates,
        y=benchmark,
        name="S&P 500",
        line=dict(color="#999", width=1, dash='dash'),
    ))

    fig.update_layout(
        title="Portfolio Performance",
        xaxis_title="Date",
        yaxis_title="Value ($)",
        height=400,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        final_return = (values[-1] - base_value) / base_value
        st.metric("Total Return", f"{final_return*100:.1f}%")
    with col2:
        st.metric("Sharpe Ratio", "1.67")
    with col3:
        st.metric("Max Drawdown", "-8.4%")
    with col4:
        st.metric("Alpha", "+2.2%")
    with col5:
        st.metric("Win Rate", "58%")


def main():
    """Main application."""
    init_session_state()

    st.title("📊 Professional Reports")
    st.caption("Generate, schedule, and distribute professional performance reports")

    # Check if enterprise features available
    if not REPORTING_AVAILABLE:
        st.warning("Professional Reporting requires Pro or Enterprise subscription. Using demo mode.")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Generated Reports",
        "Generate New",
        "Templates",
        "Schedules",
        "Branding",
    ])

    with tab1:
        render_reports_list()

    with tab2:
        render_generate_report()
        st.divider()
        render_report_preview()

    with tab3:
        render_templates()

    with tab4:
        render_schedules()

    with tab5:
        render_branding()

    # Sidebar stats
    with st.sidebar:
        st.subheader("Report Stats")

        total_reports = len(st.session_state.demo_reports)
        completed = len([r for r in st.session_state.demo_reports if r['status'] == 'completed'])
        active_schedules = len([s for s in st.session_state.demo_schedules if s['is_active']])

        st.metric("Total Reports", total_reports)
        st.metric("Completed", completed)
        st.metric("Active Schedules", active_schedules)

        st.divider()

        st.subheader("Quick Actions")
        if st.button("Generate Performance Report", use_container_width=True):
            st.info("Navigate to 'Generate New' tab")

        if st.button("View Latest Report", use_container_width=True):
            if st.session_state.demo_reports:
                st.info(f"Latest: {st.session_state.demo_reports[0]['title']}")


if __name__ == "__main__":
    main()
