"""PRD-123: Feature Store & ML Feature Management."""

import streamlit as st
from datetime import datetime, timedelta, timezone

from src.feature_store import (
    FeatureType,
    FeatureStatus,
    EntityType,
    ComputeMode,
    FeatureStoreConfig,
    FeatureDefinition,
    FeatureCatalog,
    FeatureValue,
    OfflineFeatureStore,
    CacheEntry,
    OnlineFeatureStore,
    LineageNode,
    LineageEdge,
    FeatureLineage,
)


def _build_sample_catalog() -> FeatureCatalog:
    """Build a sample catalog for dashboard display."""
    catalog = FeatureCatalog()
    features = [
        FeatureDefinition(
            name="momentum_30d", description="30-day price momentum",
            feature_type=FeatureType.NUMERIC, entity_type=EntityType.STOCK,
            owner="quant_team", tags=["momentum", "factor"],
            freshness_sla_minutes=30,
        ),
        FeatureDefinition(
            name="avg_volume_10d", description="10-day average volume",
            feature_type=FeatureType.NUMERIC, entity_type=EntityType.STOCK,
            owner="quant_team", tags=["volume", "factor"],
            freshness_sla_minutes=15,
        ),
        FeatureDefinition(
            name="sector_code", description="GICS sector classification",
            feature_type=FeatureType.CATEGORICAL, entity_type=EntityType.STOCK,
            owner="data_team", tags=["sector", "classification"],
            freshness_sla_minutes=1440,
        ),
        FeatureDefinition(
            name="is_sp500", description="S&P 500 membership flag",
            feature_type=FeatureType.BOOLEAN, entity_type=EntityType.STOCK,
            owner="data_team", tags=["index", "membership"],
            freshness_sla_minutes=1440,
        ),
        FeatureDefinition(
            name="volatility_60d", description="60-day realized volatility",
            feature_type=FeatureType.NUMERIC, entity_type=EntityType.STOCK,
            owner="risk_team", tags=["volatility", "risk"],
            freshness_sla_minutes=60,
        ),
        FeatureDefinition(
            name="sentiment_score", description="NLP sentiment from news",
            feature_type=FeatureType.NUMERIC, entity_type=EntityType.STOCK,
            owner="ml_team", tags=["sentiment", "nlp"],
            freshness_sla_minutes=15, status=FeatureStatus.EXPERIMENTAL,
        ),
        FeatureDefinition(
            name="old_rsi_14d", description="Legacy RSI indicator (deprecated)",
            feature_type=FeatureType.NUMERIC, entity_type=EntityType.STOCK,
            owner="quant_team", tags=["technical"], status=FeatureStatus.DEPRECATED,
        ),
    ]
    for f in features:
        catalog.register(f)
    return catalog


def _build_sample_online_store() -> OnlineFeatureStore:
    """Build a sample online store with cached entries."""
    store = OnlineFeatureStore(default_ttl_seconds=300)
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM"]
    features = ["momentum_30d", "avg_volume_10d", "volatility_60d", "sentiment_score"]

    import random
    random.seed(42)
    for ticker in tickers:
        for feat in features:
            store.put(feat, ticker, round(random.uniform(-0.5, 1.5), 4))

    # Simulate some cache lookups
    for _ in range(50):
        t = random.choice(tickers)
        f = random.choice(features)
        store.get(f, t)

    return store


def _build_sample_offline_store() -> OfflineFeatureStore:
    """Build a sample offline store with historical data."""
    store = OfflineFeatureStore()
    now = datetime.now(timezone.utc)

    import random
    random.seed(42)
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    for ticker in tickers:
        for day in range(30):
            dt = now - timedelta(days=29 - day)
            store.store(FeatureValue(
                feature_id="momentum_30d", entity_id=ticker,
                value=round(random.uniform(-0.3, 0.5), 4), as_of_date=dt,
            ))
            store.store(FeatureValue(
                feature_id="avg_volume_10d", entity_id=ticker,
                value=random.randint(1000000, 50000000), as_of_date=dt,
            ))
    return store


def _build_sample_lineage() -> FeatureLineage:
    """Build a sample lineage graph."""
    lineage = FeatureLineage()

    # Sources
    nodes = [
        LineageNode(node_id="src_yahoo", name="Yahoo Finance", node_type="source"),
        LineageNode(node_id="src_polygon", name="Polygon.io", node_type="source"),
        LineageNode(node_id="src_news", name="News API", node_type="source"),
        # Features
        LineageNode(node_id="feat_momentum", name="momentum_30d", node_type="feature"),
        LineageNode(node_id="feat_volume", name="avg_volume_10d", node_type="feature"),
        LineageNode(node_id="feat_volatility", name="volatility_60d", node_type="feature"),
        LineageNode(node_id="feat_sentiment", name="sentiment_score", node_type="feature"),
        # Models
        LineageNode(node_id="model_ranker", name="Stock Ranker", node_type="model"),
        LineageNode(node_id="model_risk", name="Risk Model", node_type="model"),
    ]
    for n in nodes:
        lineage.add_node(n)

    edges = [
        LineageEdge(source_id="src_yahoo", target_id="feat_momentum"),
        LineageEdge(source_id="src_yahoo", target_id="feat_volume"),
        LineageEdge(source_id="src_polygon", target_id="feat_volatility"),
        LineageEdge(source_id="src_news", target_id="feat_sentiment"),
        LineageEdge(source_id="feat_momentum", target_id="model_ranker"),
        LineageEdge(source_id="feat_volume", target_id="model_ranker"),
        LineageEdge(source_id="feat_sentiment", target_id="model_ranker"),
        LineageEdge(source_id="feat_volatility", target_id="model_risk"),
        LineageEdge(source_id="feat_momentum", target_id="model_risk"),
    ]
    for e in edges:
        lineage.add_edge(e)

    return lineage


def render():
    try:
        st.set_page_config(page_title="Feature Store", layout="wide")
    except st.errors.StreamlitAPIException:
        pass
    st.title("Feature Store & ML Feature Management")

    tabs = st.tabs(["Feature Catalog", "Online/Offline Status", "Lineage", "Monitoring"])

    catalog = _build_sample_catalog()
    online = _build_sample_online_store()
    offline = _build_sample_offline_store()
    lineage = _build_sample_lineage()

    # ── Tab 1: Feature Catalog ────────────────────────────────────────
    with tabs[0]:
        st.subheader("Feature Registry")

        stats = catalog.get_statistics()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Features", stats["total_features"])
        col2.metric("Active", stats["total_active"])
        col3.metric("Deprecated", stats["total_deprecated"])
        col4.metric("Owners", len(stats["by_owner"]))

        # Search
        query = st.text_input("Search features", placeholder="e.g. momentum, volume...")
        type_filter = st.selectbox(
            "Filter by type",
            ["All"] + [t.value for t in FeatureType],
        )
        status_filter = st.selectbox(
            "Filter by status",
            ["All"] + [s.value for s in FeatureStatus],
        )

        ft = FeatureType(type_filter) if type_filter != "All" else None
        sf = FeatureStatus(status_filter) if status_filter != "All" else None
        results = catalog.search(query=query, feature_type=ft, status=sf)

        feature_data = []
        for f in results:
            feature_data.append({
                "Name": f.name,
                "Type": f.feature_type.value,
                "Entity": f.entity_type.value,
                "Owner": f.owner,
                "Status": f.status.value.upper(),
                "SLA (min)": f.freshness_sla_minutes,
                "Version": f.version,
                "Tags": ", ".join(f.tags),
            })
        st.dataframe(feature_data, use_container_width=True)

    # ── Tab 2: Online/Offline Status ──────────────────────────────────
    with tabs[1]:
        st.subheader("Store Status")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Online Store (Cache)")
            cache_stats = online.get_cache_stats()
            c1, c2 = st.columns(2)
            c1.metric("Cached Entries", cache_stats["total_entries"])
            c2.metric("Hit Rate", f"{cache_stats['hit_rate']:.1%}")

            c3, c4 = st.columns(2)
            c3.metric("Total Hits", cache_stats["total_hits"])
            c4.metric("Total Misses", cache_stats["total_misses"])

            st.metric("Utilization", f"{cache_stats['utilization']:.4%}")

        with col2:
            st.markdown("### Offline Store")
            offline_stats = offline.get_statistics()
            c1, c2 = st.columns(2)
            c1.metric("Total Values", offline_stats["total_values"])
            c2.metric("Unique Features", offline_stats["unique_features"])

            c3, c4 = st.columns(2)
            c3.metric("Unique Entities", offline_stats["unique_entities"])
            c4.metric("Total Keys", offline_stats["total_keys"])

            if offline_stats["oldest_value"]:
                st.text(f"Oldest value: {offline_stats['oldest_value'].strftime('%Y-%m-%d %H:%M')}")
            if offline_stats["newest_value"]:
                st.text(f"Newest value: {offline_stats['newest_value'].strftime('%Y-%m-%d %H:%M')}")

    # ── Tab 3: Lineage ────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Feature Lineage Graph")

        lineage_stats = lineage.get_statistics()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Nodes", lineage_stats["total_nodes"])
        col2.metric("Edges", lineage_stats["total_edges"])
        col3.metric("Root Sources", lineage_stats["root_count"])
        col4.metric("Leaf Models", lineage_stats["leaf_count"])

        # Node type breakdown
        st.markdown("#### Node Types")
        type_data = [
            {"Type": k.capitalize(), "Count": v}
            for k, v in lineage_stats["by_type"].items()
        ]
        st.dataframe(type_data, use_container_width=True)

        # Impact analysis
        st.markdown("#### Impact Analysis")
        graph = lineage.get_lineage_graph()
        node_names = {n["node_id"]: n["name"] for n in graph["nodes"]}
        selected_node = st.selectbox(
            "Select node for impact analysis",
            options=[n["node_id"] for n in graph["nodes"]],
            format_func=lambda x: f"{node_names.get(x, x)} ({x})",
        )
        if selected_node:
            impact = lineage.get_impact(selected_node)
            st.write(f"**Total affected downstream:** {impact['total_affected']}")
            st.write(f"**Affected features:** {impact['feature_count']}")
            st.write(f"**Affected models:** {impact['model_count']}")

        # Full graph view
        st.markdown("#### Graph Edges")
        edge_data = []
        for e in graph["edges"]:
            edge_data.append({
                "Source": node_names.get(e["source_id"], e["source_id"]),
                "Target": node_names.get(e["target_id"], e["target_id"]),
                "Relationship": e["relationship"],
            })
        st.dataframe(edge_data, use_container_width=True)

    # ── Tab 4: Monitoring ─────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Feature Store Monitoring")

        cfg = FeatureStoreConfig()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Cache TTL", f"{cfg.cache_ttl_seconds}s")
        col2.metric("Freshness Interval", f"{cfg.freshness_check_interval}s")
        col3.metric("Max Versions", cfg.max_feature_versions)
        col4.metric("Max Cache Entries", f"{cfg.online_cache_max_entries:,}")

        # Feature freshness
        st.markdown("#### Feature Freshness")
        all_features = catalog.list_features()
        freshness_data = []
        for f in all_features:
            is_fresh = f.status == FeatureStatus.ACTIVE
            freshness_data.append({
                "Feature": f.name,
                "SLA (min)": f.freshness_sla_minutes,
                "Status": f.status.value.upper(),
                "Fresh": "Yes" if is_fresh else "No",
                "Owner": f.owner,
            })
        st.dataframe(freshness_data, use_container_width=True)

        # Cache performance
        st.markdown("#### Cache Performance")
        cache_stats = online.get_cache_stats()
        perf_data = {
            "Metric": ["Hit Rate", "Active Entries", "Expired Entries", "Utilization"],
            "Value": [
                f"{cache_stats['hit_rate']:.1%}",
                str(cache_stats["active_entries"]),
                str(cache_stats["expired_entries"]),
                f"{cache_stats['utilization']:.4%}",
            ],
        }
        st.dataframe(perf_data, use_container_width=True)

        # Offline store health
        st.markdown("#### Offline Store Health")
        offline_stats = offline.get_statistics()
        health_data = {
            "Metric": ["Total Values", "Unique Features", "Unique Entities", "Total Keys"],
            "Value": [
                str(offline_stats["total_values"]),
                str(offline_stats["unique_features"]),
                str(offline_stats["unique_entities"]),
                str(offline_stats["total_keys"]),
            ],
        }
        st.dataframe(health_data, use_container_width=True)



render()
