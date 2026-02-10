"""Multi-Account Dashboard - PRD-68.

Comprehensive account management with:
- Account list and creation
- Household aggregate view
- Performance comparison across accounts
- Tax-optimized asset location
- Cross-account positions view
"""

import sys
import os
from datetime import datetime, date, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

try:
    st.set_page_config(page_title="Accounts", page_icon="🏦", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()


# Try to import enterprise modules
try:
    from src.enterprise.accounts import AccountManager
    from src.enterprise.config import AccountType, TaxStatus, BrokerType
    ACCOUNTS_AVAILABLE = True
except ImportError:
    ACCOUNTS_AVAILABLE = False


def init_session_state():
    """Initialize session state."""
    if "demo_accounts" not in st.session_state:
        st.session_state.demo_accounts = generate_demo_accounts()
    if "selected_account_id" not in st.session_state:
        st.session_state.selected_account_id = None


def generate_demo_accounts():
    """Generate demo accounts."""
    accounts = [
        {
            "id": "acc-001",
            "name": "Personal Brokerage",
            "account_type": "individual",
            "broker": "alpaca",
            "tax_status": "taxable",
            "total_value": 142300,
            "cash_balance": 12500,
            "cost_basis": 125000,
            "ytd_return": 0.084,
            "total_return": 0.138,
            "strategy_name": "Balanced Factor",
            "benchmark": "SPY",
            "is_primary": True,
            "inception_date": date(2023, 1, 15),
            "positions": [
                {"symbol": "AAPL", "qty": 50, "value": 9500, "pnl": 1200, "weight": 0.073},
                {"symbol": "MSFT", "qty": 30, "value": 12600, "pnl": 2100, "weight": 0.097},
                {"symbol": "NVDA", "qty": 20, "value": 15800, "pnl": 4500, "weight": 0.122},
                {"symbol": "GOOGL", "qty": 25, "value": 4250, "pnl": 350, "weight": 0.033},
                {"symbol": "VTI", "qty": 200, "value": 48000, "pnl": 5200, "weight": 0.370},
                {"symbol": "BND", "qty": 150, "value": 11250, "pnl": -300, "weight": 0.087},
            ],
        },
        {
            "id": "acc-002",
            "name": "Roth IRA",
            "account_type": "ira_roth",
            "broker": "alpaca",
            "tax_status": "tax_free",
            "total_value": 68200,
            "cash_balance": 5200,
            "cost_basis": 55000,
            "ytd_return": 0.121,
            "total_return": 0.24,
            "strategy_name": "Aggressive Alpha",
            "benchmark": "QQQ",
            "is_primary": False,
            "inception_date": date(2022, 3, 1),
            "positions": [
                {"symbol": "NVDA", "qty": 40, "value": 31600, "pnl": 12000, "weight": 0.50},
                {"symbol": "AMD", "qty": 100, "value": 16500, "pnl": 3500, "weight": 0.26},
                {"symbol": "TSLA", "qty": 30, "value": 7500, "pnl": -1200, "weight": 0.12},
            ],
        },
        {
            "id": "acc-003",
            "name": "Traditional IRA",
            "account_type": "ira_traditional",
            "broker": "ibkr",
            "tax_status": "tax_deferred",
            "total_value": 52100,
            "cash_balance": 8100,
            "cost_basis": 48000,
            "ytd_return": 0.078,
            "total_return": 0.085,
            "strategy_name": "Quality Income",
            "benchmark": "VYM",
            "is_primary": False,
            "inception_date": date(2021, 6, 15),
            "positions": [
                {"symbol": "JNJ", "qty": 50, "value": 7800, "pnl": 400, "weight": 0.18},
                {"symbol": "PG", "qty": 40, "value": 6400, "pnl": 300, "weight": 0.15},
                {"symbol": "KO", "qty": 80, "value": 4800, "pnl": 200, "weight": 0.11},
                {"symbol": "VYM", "qty": 100, "value": 11000, "pnl": 800, "weight": 0.25},
                {"symbol": "SCHD", "qty": 80, "value": 6000, "pnl": 500, "weight": 0.14},
            ],
        },
        {
            "id": "acc-004",
            "name": "Paper Trading",
            "account_type": "paper",
            "broker": "paper",
            "tax_status": "taxable",
            "total_value": 100000,
            "cash_balance": 25000,
            "cost_basis": 100000,
            "ytd_return": 0.032,
            "total_return": 0.0,
            "strategy_name": "Momentum Rider",
            "benchmark": "SPY",
            "is_primary": False,
            "inception_date": date(2026, 1, 1),
            "positions": [
                {"symbol": "SPY", "qty": 100, "value": 50000, "pnl": 2000, "weight": 0.67},
                {"symbol": "QQQ", "qty": 50, "value": 25000, "pnl": 1200, "weight": 0.33},
            ],
        },
    ]

    # Generate performance history
    for acc in accounts:
        acc["history"] = generate_performance_history(
            acc["total_value"],
            acc["ytd_return"],
            90,
        )

    return accounts


def generate_performance_history(current_value, ytd_return, days):
    """Generate synthetic performance history."""
    history = []
    base_value = current_value / (1 + ytd_return)

    for i in range(days):
        day = date.today() - timedelta(days=days - i)
        # Random walk with drift toward current value
        progress = i / days
        value = base_value + (current_value - base_value) * progress
        value *= (1 + random.gauss(0, 0.01))  # Add noise
        history.append({"date": day, "value": value})

    return history


def calculate_household_summary(accounts):
    """Calculate aggregate household metrics."""
    total_value = sum(a["total_value"] for a in accounts)
    total_cash = sum(a["cash_balance"] for a in accounts)
    total_cost_basis = sum(a["cost_basis"] for a in accounts)

    # Weighted YTD return
    if total_cost_basis > 0:
        weighted_ytd = sum(a["ytd_return"] * a["total_value"] for a in accounts) / total_value
    else:
        weighted_ytd = 0

    # By tax status
    taxable = sum(a["total_value"] for a in accounts if a["tax_status"] == "taxable")
    tax_deferred = sum(a["total_value"] for a in accounts if a["tax_status"] == "tax_deferred")
    tax_free = sum(a["total_value"] for a in accounts if a["tax_status"] == "tax_free")

    return {
        "total_value": total_value,
        "total_cash": total_cash,
        "total_cost_basis": total_cost_basis,
        "total_pnl": total_value - total_cost_basis,
        "ytd_return": weighted_ytd,
        "taxable_value": taxable,
        "tax_deferred_value": tax_deferred,
        "tax_free_value": tax_free,
        "num_accounts": len(accounts),
    }


def render_household_summary():
    """Render household aggregate view."""
    accounts = st.session_state.demo_accounts
    summary = calculate_household_summary(accounts)

    st.subheader("Household Summary")

    # Top metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Total Value",
        f"${summary['total_value']:,.0f}",
        f"{summary['ytd_return']:.1%} YTD",
    )
    col2.metric(
        "Total P&L",
        f"${summary['total_pnl']:,.0f}",
        f"{summary['total_pnl']/summary['total_cost_basis']:.1%}" if summary['total_cost_basis'] > 0 else "0%",
    )
    col3.metric(
        "Cash",
        f"${summary['total_cash']:,.0f}",
        f"{summary['total_cash']/summary['total_value']:.1%} of total",
    )
    col4.metric("Accounts", summary["num_accounts"])
    col5.metric(
        "Positions",
        sum(len(a.get("positions", [])) for a in accounts),
    )

    st.markdown("---")

    # Account breakdown
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### Accounts")
        df = pd.DataFrame([{
            "Account": a["name"],
            "Type": a["account_type"].replace("_", " ").title(),
            "Value": a["total_value"],
            "YTD": a["ytd_return"],
            "Strategy": a["strategy_name"],
        } for a in accounts])

        st.dataframe(
            df.style.format({
                "Value": "${:,.0f}",
                "YTD": "{:.1%}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    with col2:
        # Tax status pie chart
        st.markdown("#### Asset Location")
        fig = go.Figure(data=[go.Pie(
            labels=["Taxable", "Tax-Deferred", "Tax-Free"],
            values=[
                summary["taxable_value"],
                summary["tax_deferred_value"],
                summary["tax_free_value"],
            ],
            hole=0.4,
            marker_colors=["#FF6B6B", "#4ECDC4", "#45B7D1"],
        )])
        fig.update_layout(
            height=250,
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=True,
            legend=dict(orientation="h", y=-0.1),
        )
        st.plotly_chart(fig, use_container_width=True)


def render_performance_comparison():
    """Render performance comparison across accounts."""
    accounts = st.session_state.demo_accounts

    st.subheader("Performance Comparison")

    # Combined performance chart
    fig = go.Figure()

    for acc in accounts:
        history = acc.get("history", [])
        if history:
            dates = [h["date"] for h in history]
            values = [h["value"] for h in history]
            # Normalize to 100
            base = values[0]
            normalized = [v / base * 100 for v in values]

            fig.add_trace(go.Scatter(
                x=dates,
                y=normalized,
                name=acc["name"],
                mode="lines",
                hovertemplate="%{x}<br>%{y:.1f}<extra></extra>",
            ))

    fig.update_layout(
        title="Normalized Performance (Base = 100)",
        xaxis_title="Date",
        yaxis_title="Value",
        height=400,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Metrics comparison table
    st.markdown("#### Metrics Comparison")

    metrics_data = []
    for acc in accounts:
        metrics_data.append({
            "Account": acc["name"],
            "Total Value": acc["total_value"],
            "YTD Return": acc["ytd_return"],
            "Total Return": acc["total_return"],
            "Positions": len(acc.get("positions", [])),
            "Cash %": acc["cash_balance"] / acc["total_value"] if acc["total_value"] > 0 else 0,
        })

    df = pd.DataFrame(metrics_data)
    st.dataframe(
        df.style.format({
            "Total Value": "${:,.0f}",
            "YTD Return": "{:.1%}",
            "Total Return": "{:.1%}",
            "Cash %": "{:.1%}",
        }).background_gradient(subset=["YTD Return"], cmap="RdYlGn"),
        use_container_width=True,
        hide_index=True,
    )


def render_account_detail(account):
    """Render detailed view for a single account."""
    st.subheader(f"📊 {account['name']}")

    # Account info
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Value", f"${account['total_value']:,.0f}")
    col2.metric("Cash", f"${account['cash_balance']:,.0f}")
    col3.metric("YTD Return", f"{account['ytd_return']:.1%}")
    col4.metric("Total Return", f"{account['total_return']:.1%}")

    col5, col6, col7, col8 = st.columns(4)
    col5.markdown(f"**Type:** {account['account_type'].replace('_', ' ').title()}")
    col6.markdown(f"**Broker:** {account['broker'].upper()}")
    col7.markdown(f"**Tax Status:** {account['tax_status'].replace('_', ' ').title()}")
    col8.markdown(f"**Strategy:** {account['strategy_name']}")

    st.markdown("---")

    # Positions
    st.markdown("#### Positions")
    positions = account.get("positions", [])

    if positions:
        df = pd.DataFrame(positions)
        df = df.rename(columns={
            "symbol": "Symbol",
            "qty": "Qty",
            "value": "Value",
            "pnl": "P&L",
            "weight": "Weight",
        })

        st.dataframe(
            df.style.format({
                "Value": "${:,.0f}",
                "P&L": "${:,.0f}",
                "Weight": "{:.1%}",
            }).applymap(
                lambda x: "color: green" if isinstance(x, (int, float)) and x > 0 else "color: red" if isinstance(x, (int, float)) and x < 0 else "",
                subset=["P&L"]
            ),
            use_container_width=True,
            hide_index=True,
        )

        # Position weights chart
        col1, col2 = st.columns(2)

        with col1:
            fig = px.pie(
                pd.DataFrame(positions),
                values="value",
                names="symbol",
                title="Position Weights",
                hole=0.4,
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Performance chart
            history = account.get("history", [])
            if history:
                df_hist = pd.DataFrame(history)
                fig = go.Figure(go.Scatter(
                    x=df_hist["date"],
                    y=df_hist["value"],
                    mode="lines",
                    fill="tozeroy",
                    fillcolor="rgba(0, 200, 83, 0.1)",
                    line=dict(color="#00C853"),
                ))
                fig.update_layout(
                    title="Account Value",
                    height=300,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No positions in this account.")


def render_create_account_form():
    """Render form to create new account."""
    st.subheader("Create New Account")

    with st.form("create_account_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Account Name", placeholder="My Trading Account")
            account_type = st.selectbox(
                "Account Type",
                ["individual", "ira_traditional", "ira_roth", "joint", "trust", "paper"],
                format_func=lambda x: x.replace("_", " ").title(),
            )
            broker = st.selectbox(
                "Broker",
                ["paper", "alpaca", "ibkr"],
                format_func=lambda x: x.upper() if x != "paper" else "Paper Trading",
            )

        with col2:
            initial_value = st.number_input("Initial Value ($)", min_value=0, value=10000, step=1000)
            strategy = st.selectbox(
                "Strategy",
                ["Balanced Factor", "Aggressive Alpha", "Quality Income", "Momentum Rider", "Custom"],
            )
            benchmark = st.selectbox("Benchmark", ["SPY", "QQQ", "VTI", "IWM", "VYM"])

        submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)

        if submitted:
            if not name:
                st.error("Please enter an account name")
            else:
                # Create new account
                new_account = {
                    "id": f"acc-{len(st.session_state.demo_accounts)+1:03d}",
                    "name": name,
                    "account_type": account_type,
                    "broker": broker,
                    "tax_status": "tax_free" if "roth" in account_type else "tax_deferred" if "ira" in account_type else "taxable",
                    "total_value": initial_value,
                    "cash_balance": initial_value,
                    "cost_basis": initial_value,
                    "ytd_return": 0,
                    "total_return": 0,
                    "strategy_name": strategy,
                    "benchmark": benchmark,
                    "is_primary": False,
                    "inception_date": date.today(),
                    "positions": [],
                    "history": [{"date": date.today(), "value": initial_value}],
                }
                st.session_state.demo_accounts.append(new_account)
                st.success(f"Account '{name}' created successfully!")
                st.rerun()


def render_asset_location():
    """Render asset location recommendations."""
    accounts = st.session_state.demo_accounts

    st.subheader("Tax-Optimized Asset Location")

    st.info("""
    **Asset Location Strategy**: Place assets in the most tax-efficient account type:
    - **Taxable accounts**: Tax-efficient assets (index funds, muni bonds, long-term holds)
    - **Tax-deferred accounts**: High-tax assets (bonds, REITs, high-dividend stocks)
    - **Tax-free accounts (Roth)**: High-growth assets (growth stocks, small caps)
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Taxable Accounts")
        taxable = [a for a in accounts if a["tax_status"] == "taxable"]
        for acc in taxable:
            st.markdown(f"**{acc['name']}**: ${acc['total_value']:,.0f}")

        st.markdown("##### Recommended Assets")
        st.markdown("""
        - Total market index funds (VTI, ITOT)
        - Tax-managed funds
        - Municipal bonds
        - Growth stocks (long-term holds)
        """)

    with col2:
        st.markdown("#### Tax-Deferred Accounts")
        deferred = [a for a in accounts if a["tax_status"] == "tax_deferred"]
        for acc in deferred:
            st.markdown(f"**{acc['name']}**: ${acc['total_value']:,.0f}")

        st.markdown("##### Recommended Assets")
        st.markdown("""
        - Bond funds (BND, AGG)
        - REITs (VNQ, SCHH)
        - High-dividend stocks
        - Actively managed funds
        """)

    with col3:
        st.markdown("#### Tax-Free Accounts (Roth)")
        tax_free = [a for a in accounts if a["tax_status"] == "tax_free"]
        for acc in tax_free:
            st.markdown(f"**{acc['name']}**: ${acc['total_value']:,.0f}")

        st.markdown("##### Recommended Assets")
        st.markdown("""
        - High-growth stocks
        - Small-cap funds (VB, IJR)
        - Aggressive growth ETFs
        - Assets expected to appreciate
        """)


def render_cross_account_positions():
    """Render consolidated positions across all accounts."""
    accounts = st.session_state.demo_accounts

    st.subheader("Consolidated Positions")

    # Aggregate positions across accounts
    all_positions = {}

    for acc in accounts:
        for pos in acc.get("positions", []):
            symbol = pos["symbol"]
            if symbol not in all_positions:
                all_positions[symbol] = {
                    "symbol": symbol,
                    "total_qty": 0,
                    "total_value": 0,
                    "total_pnl": 0,
                    "accounts": [],
                }
            all_positions[symbol]["total_qty"] += pos["qty"]
            all_positions[symbol]["total_value"] += pos["value"]
            all_positions[symbol]["total_pnl"] += pos.get("pnl", 0)
            all_positions[symbol]["accounts"].append(acc["name"])

    # Convert to list and sort
    positions_list = sorted(all_positions.values(), key=lambda x: x["total_value"], reverse=True)

    if positions_list:
        total_value = sum(p["total_value"] for p in positions_list)

        df = pd.DataFrame([{
            "Symbol": p["symbol"],
            "Total Qty": p["total_qty"],
            "Total Value": p["total_value"],
            "Total P&L": p["total_pnl"],
            "Weight": p["total_value"] / total_value if total_value > 0 else 0,
            "# Accounts": len(set(p["accounts"])),
            "Accounts": ", ".join(set(p["accounts"])),
        } for p in positions_list])

        st.dataframe(
            df.style.format({
                "Total Value": "${:,.0f}",
                "Total P&L": "${:,.0f}",
                "Weight": "{:.1%}",
            }),
            use_container_width=True,
            hide_index=True,
        )

        # Sector/asset allocation would go here
        col1, col2 = st.columns(2)

        with col1:
            # Top holdings chart
            top_10 = positions_list[:10]
            fig = go.Figure(go.Bar(
                x=[p["symbol"] for p in top_10],
                y=[p["total_value"] for p in top_10],
                marker_color="#4CAF50",
                text=[f"${p['total_value']:,.0f}" for p in top_10],
                textposition="auto",
            ))
            fig.update_layout(
                title="Top 10 Holdings",
                xaxis_title="Symbol",
                yaxis_title="Value ($)",
                height=350,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Concentration chart
            fig = px.pie(
                pd.DataFrame(positions_list[:8]),
                values="total_value",
                names="symbol",
                title="Position Concentration",
                hole=0.4,
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No positions across accounts.")


def main():
    st.title("🏦 Multi-Account Management")

    init_session_state()

    # Sidebar - Account selector
    st.sidebar.header("Accounts")

    accounts = st.session_state.demo_accounts
    summary = calculate_household_summary(accounts)

    st.sidebar.metric("Total Value", f"${summary['total_value']:,.0f}")
    st.sidebar.metric("YTD Return", f"{summary['ytd_return']:.1%}")

    st.sidebar.markdown("---")

    for acc in accounts:
        if st.sidebar.button(
            f"{acc['name']}\n${acc['total_value']:,.0f}",
            key=f"acc_{acc['id']}",
            use_container_width=True,
        ):
            st.session_state.selected_account_id = acc["id"]
            st.rerun()

    if st.sidebar.button("➕ New Account", use_container_width=True, type="primary"):
        st.session_state.selected_account_id = "new"
        st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 Household View", use_container_width=True):
        st.session_state.selected_account_id = None
        st.rerun()

    # Main content
    selected_id = st.session_state.selected_account_id

    if selected_id == "new":
        render_create_account_form()
    elif selected_id:
        account = next((a for a in accounts if a["id"] == selected_id), None)
        if account:
            render_account_detail(account)
        else:
            st.error("Account not found")
    else:
        # Household view
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Summary",
            "📈 Performance",
            "💼 Positions",
            "🏛️ Asset Location",
        ])

        with tab1:
            render_household_summary()

        with tab2:
            render_performance_comparison()

        with tab3:
            render_cross_account_positions()

        with tab4:
            render_asset_location()



main()
