"""PRD-97: GIPS Performance Report Dashboard."""

import streamlit as st
from datetime import date

from src.performance_report import (
    CompositeManager,
    GIPSCalculator,
    DispersionCalculator,
    ComplianceValidator,
    GIPSReportGenerator,
    GIPSConfig,
    CompositeConfig,
    DispersionMethod,
    PerformanceRecord,
    CompositePeriod,
)


def render():
    st.title("GIPS Performance Reporting")

    tabs = st.tabs(["Composites", "Performance", "Compliance", "Presentation"])

    # ── Tab 1: Composite Management ──────────────────────────────────
    with tabs[0]:
        st.subheader("Composite Management")

        mgr = CompositeManager.generate_sample_composite()
        composites = mgr.list_composites()

        if composites:
            comp = composites[0]
            col1, col2, col3 = st.columns(3)
            col1.metric("Composite", comp.name)
            col2.metric("Active Portfolios", comp.n_portfolios)
            col3.metric("Strategy", comp.strategy)

            st.write(f"**Benchmark:** {comp.benchmark_name}")
            st.write(f"**Inception:** {comp.inception_date}")
            st.write(f"**Currency:** {comp.currency}")

            st.subheader("Portfolio Assignments")
            data = []
            for p in comp.portfolios:
                data.append({
                    "Portfolio ID": p.portfolio_id,
                    "Join Date": p.join_date.isoformat(),
                    "Market Value": f"${p.market_value:,.0f}",
                    "Active": "Yes" if p.is_active else "No",
                })
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No composites defined. Create one to get started.")

    # ── Tab 2: Performance Calculation ───────────────────────────────
    with tabs[1]:
        st.subheader("Return Calculations")

        calc = GIPSCalculator()
        returns = GIPSCalculator.generate_sample_returns(7)
        periods = calc.build_annual_periods(returns)

        # Annual returns table
        table_data = []
        for p in periods:
            table_data.append({
                "Year": p.year,
                "Gross Return": f"{p.gross_return:.2%}",
                "Net Return": f"{p.net_return:.2%}",
                "Benchmark": f"{p.benchmark_return:.2%}",
                "Excess (Gross)": f"{p.gross_return - p.benchmark_return:.2%}",
                "# Portfolios": p.n_portfolios,
                "Composite Assets": f"${p.composite_assets:,.0f}",
            })
        st.dataframe(table_data, use_container_width=True)

        # Calculator tools
        st.subheader("Return Calculator")
        col1, col2 = st.columns(2)
        with col1:
            bv = st.number_input("Beginning Value ($)", value=1_000_000, step=100_000)
            ev = st.number_input("Ending Value ($)", value=1_120_000, step=100_000)

        with col2:
            cf = st.number_input("Cash Flow ($)", value=0, step=10_000)
            fee_rate = st.number_input("Annual Fee Rate (%)", value=1.0, step=0.25) / 100

        if bv > 0:
            gross = (ev - bv - cf) / (bv + cf) if (bv + cf) > 0 else 0
            net = calc.gross_to_net(gross, fee_rate)
            c1, c2 = st.columns(2)
            c1.metric("Gross Return", f"{gross:.2%}")
            c2.metric("Net Return", f"{net:.2%}")

    # ── Tab 3: Compliance Validation ─────────────────────────────────
    with tabs[2]:
        st.subheader("GIPS Compliance Check")

        config = GIPSConfig(firm_name="Demo Investment Firm")
        validator = ComplianceValidator(config)

        mgr = CompositeManager.generate_sample_composite()
        comp = mgr.list_composites()[0]
        calc = GIPSCalculator()
        returns = GIPSCalculator.generate_sample_returns(7)
        periods = calc.build_annual_periods(returns)

        report = validator.validate_composite(comp, periods)

        status_color = "green" if report.overall_compliant else "red"
        st.markdown(f"**Overall Status:** :{status_color}[{'COMPLIANT' if report.overall_compliant else 'NON-COMPLIANT'}]")
        st.metric("Pass Rate", f"{report.pass_rate:.0%}")

        for check in report.checks:
            icon = ":white_check_mark:" if check.passed else ":x:" if check.severity == "error" else ":warning:"
            st.markdown(f"{icon} **{check.rule_id}**: {check.description}")
            if not check.passed:
                st.caption(f"   Details: {check.details}")

    # ── Tab 4: GIPS Presentation ─────────────────────────────────────
    with tabs[3]:
        st.subheader("GIPS-Compliant Presentation")

        config = GIPSConfig(firm_name="Demo Investment Firm")
        gen = GIPSReportGenerator(config)

        mgr = CompositeManager.generate_sample_composite()
        comp = mgr.list_composites()[0]
        calc = GIPSCalculator()
        returns = GIPSCalculator.generate_sample_returns(7)
        periods = calc.build_annual_periods(returns)

        pres = gen.generate_presentation(comp, periods)

        # Summary metrics
        summary = gen.generate_summary(pres)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Years of History", summary["years"])
        col2.metric("Cumulative Gross", f"{summary['cumulative_gross']:.2%}")
        col3.metric("Cumulative Benchmark", f"{summary['cumulative_benchmark']:.2%}")
        col4.metric("Status", summary["status"])

        # Formatted report
        st.subheader("Full Presentation")
        table_text = gen.format_presentation_table(pres)
        st.code(table_text, language="text")

        # Disclosures
        st.subheader("Required Disclosures")
        for d in pres.disclosures:
            with st.expander(d.category.replace("_", " ").title()):
                st.write(d.text)


if __name__ == "__main__":
    render()
