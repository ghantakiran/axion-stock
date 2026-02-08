"""PRD-98: Smart Order Router Dashboard."""

import streamlit as st

from src.smart_router import (
    SmartRouter,
    VenueManager,
    RouteScorer,
    CostOptimizer,
    RoutingConfig,
    RoutingStrategy,
)


def render():
    st.title("Smart Order Router")

    tabs = st.tabs(["Route Order", "Venues", "Cost Analysis", "Audit Log"])

    # ── Tab 1: Route Order ───────────────────────────────────────────
    with tabs[0]:
        st.subheader("Route an Order")

        col1, col2 = st.columns(2)
        with col1:
            symbol = st.text_input("Symbol", "AAPL")
            side = st.selectbox("Side", ["buy", "sell"])
            quantity = st.number_input("Quantity", value=5000, step=100)

        with col2:
            price = st.number_input("Price ($)", value=175.0, step=1.0)
            adv = st.number_input("ADV", value=25_000_000, step=1_000_000)
            strategy = st.selectbox("Strategy",
                                     [s.value for s in RoutingStrategy],
                                     index=4)

        if st.button("Route Order"):
            config = RoutingConfig(strategy=RoutingStrategy(strategy))
            router = SmartRouter(config=config)
            decision = router.route_order("UI-001", symbol, side, quantity, price, adv)

            col1, col2, col3 = st.columns(3)
            col1.metric("Venues Used", decision.n_venues)
            col2.metric("Dark Pool %", f"{decision.dark_pool_pct:.0%}")
            col3.metric("Est. Total Cost", f"${decision.total_estimated_cost:.2f}")

            st.subheader("Route Splits")
            split_data = []
            for s in decision.splits:
                split_data.append({
                    "Venue": s.venue_id,
                    "Quantity": s.quantity,
                    "Hidden": "Yes" if s.is_hidden else "No",
                    "Midpoint": "Yes" if s.is_midpoint else "No",
                    "Fill Prob": f"{s.fill_probability:.1%}",
                    "Est. Cost": f"${s.estimated_cost:.2f}",
                })
            st.dataframe(split_data, use_container_width=True)

            st.subheader("Venue Scores")
            score_data = []
            for s in decision.scores:
                score_data.append({
                    "Rank": s.rank,
                    "Venue": s.venue_id,
                    "Fill": f"{s.fill_score:.3f}",
                    "Cost": f"{s.cost_score:.3f}",
                    "Latency": f"{s.latency_score:.3f}",
                    "Price Imp": f"{s.price_improvement_score:.3f}",
                    "Composite": f"{s.composite_score:.3f}",
                })
            st.dataframe(score_data, use_container_width=True)

    # ── Tab 2: Venues ────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Trading Venues")
        mgr = VenueManager.create_default_venues()

        venue_data = []
        for v in mgr.list_venues():
            venue_data.append({
                "ID": v.venue_id,
                "Name": v.name,
                "Type": v.venue_type,
                "Maker Fee": f"${v.maker_fee:.4f}",
                "Taker Fee": f"${v.taker_fee:.4f}",
                "Latency (ms)": f"{v.avg_latency_ms:.1f}",
                "Fill Rate": f"{v.fill_rate:.0%}",
            })
        st.dataframe(venue_data, use_container_width=True)

        st.subheader("Rankings")
        ranking_by = st.selectbox("Rank By", ["fill_rate", "latency", "cost"])
        ranked = mgr.rank_venues(by=ranking_by)
        rank_data = [{"Rank": i + 1, "Venue": v.venue_id, "Name": v.name}
                     for i, v in enumerate(ranked)]
        st.dataframe(rank_data, use_container_width=True)

    # ── Tab 3: Cost Analysis ─────────────────────────────────────────
    with tabs[2]:
        st.subheader("Venue Cost Comparison")
        mgr = VenueManager.create_default_venues()
        opt = CostOptimizer()

        qty = st.number_input("Order Size", value=1000, step=100, key="cost_qty")
        px = st.number_input("Price ($)", value=150.0, step=5.0, key="cost_px")

        venues = mgr.list_venues()
        compared = opt.compare_venues(venues, qty, px)

        cost_data = []
        for est in compared:
            cost_data.append({
                "Venue": est.venue_id,
                "Exchange Fee": f"${est.exchange_fee:.2f}",
                "Spread": f"${est.spread_cost:.2f}",
                "Impact": f"${est.impact_cost:.2f}",
                "Rebate": f"${est.rebate:.2f}",
                "Net Cost": f"${est.net_cost:.2f}",
            })
        st.dataframe(cost_data, use_container_width=True)

    # ── Tab 4: Audit Log ─────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Routing Audit Trail")

        router = SmartRouter()
        # Generate sample audits
        for sym in ["AAPL", "MSFT", "GOOG"]:
            router.route_order(f"DEMO-{sym}", sym, "buy", 2000, 150.0, 10_000_000)

        audits = router.get_audit_log()
        audit_data = []
        for a in audits:
            audit_data.append({
                "Order": a.order_id,
                "Symbol": a.symbol,
                "Side": a.side,
                "Qty": a.quantity,
                "Venues Considered": a.venues_considered,
                "Venues Selected": a.venues_selected,
                "Reg NMS": "Yes" if a.reg_nms_compliant else "No",
                "Time": a.decided_at.strftime("%H:%M:%S"),
            })
        st.dataframe(audit_data, use_container_width=True)


if __name__ == "__main__":
    render()
