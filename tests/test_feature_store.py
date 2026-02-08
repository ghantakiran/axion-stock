"""Tests for PRD-123: Feature Store & ML Feature Management."""

from datetime import datetime, timedelta, timezone

import pytest

from src.feature_store.config import (
    FeatureType,
    FeatureStatus,
    EntityType,
    ComputeMode,
    FeatureStoreConfig,
)
from src.feature_store.catalog import (
    FeatureDefinition,
    FeatureCatalog,
)
from src.feature_store.offline import (
    FeatureValue,
    OfflineFeatureStore,
)
from src.feature_store.online import (
    CacheEntry,
    OnlineFeatureStore,
)
from src.feature_store.lineage import (
    LineageNode,
    LineageEdge,
    FeatureLineage,
)


# ── Config Tests ──────────────────────────────────────────────────────


class TestFeatureStoreConfig:
    def test_feature_type_enum(self):
        assert len(FeatureType) == 5
        assert FeatureType.NUMERIC.value == "numeric"
        assert FeatureType.CATEGORICAL.value == "categorical"
        assert FeatureType.BOOLEAN.value == "boolean"
        assert FeatureType.TIMESTAMP.value == "timestamp"
        assert FeatureType.EMBEDDING.value == "embedding"

    def test_feature_status_enum(self):
        assert len(FeatureStatus) == 4
        assert FeatureStatus.ACTIVE.value == "active"
        assert FeatureStatus.DEPRECATED.value == "deprecated"
        assert FeatureStatus.EXPERIMENTAL.value == "experimental"
        assert FeatureStatus.ARCHIVED.value == "archived"

    def test_entity_type_enum(self):
        assert len(EntityType) == 4
        assert EntityType.STOCK.value == "stock"
        assert EntityType.USER.value == "user"
        assert EntityType.PORTFOLIO.value == "portfolio"
        assert EntityType.ORDER.value == "order"

    def test_compute_mode_enum(self):
        assert len(ComputeMode) == 3
        assert ComputeMode.BATCH.value == "batch"
        assert ComputeMode.REALTIME.value == "realtime"
        assert ComputeMode.ON_DEMAND.value == "on_demand"

    def test_default_config(self):
        cfg = FeatureStoreConfig()
        assert cfg.cache_ttl_seconds == 300
        assert cfg.freshness_check_interval == 60
        assert cfg.max_feature_versions == 10
        assert cfg.offline_batch_size == 10000
        assert cfg.online_cache_max_entries == 100000
        assert cfg.lineage_max_depth == 20
        assert cfg.default_freshness_sla_minutes == 30
        assert cfg.enable_metrics is True
        assert cfg.enable_lineage_tracking is True

    def test_custom_config(self):
        cfg = FeatureStoreConfig(cache_ttl_seconds=600, enable_metrics=False)
        assert cfg.cache_ttl_seconds == 600
        assert cfg.enable_metrics is False

    def test_supported_types(self):
        cfg = FeatureStoreConfig()
        assert len(cfg.supported_entity_types) == 4
        assert len(cfg.supported_feature_types) == 5

    def test_enum_string_values(self):
        assert FeatureType.NUMERIC == "numeric"
        assert FeatureStatus.ACTIVE == "active"
        assert EntityType.STOCK == "stock"
        assert ComputeMode.BATCH == "batch"


# ── Dataclass Tests ───────────────────────────────────────────────────


class TestDataclasses:
    def test_feature_definition_defaults(self):
        fd = FeatureDefinition(name="test_feature")
        assert fd.feature_id  # Auto-generated
        assert len(fd.feature_id) == 16
        assert fd.name == "test_feature"
        assert fd.feature_type == FeatureType.NUMERIC
        assert fd.entity_type == EntityType.STOCK
        assert fd.version == 1
        assert fd.status == FeatureStatus.ACTIVE
        assert isinstance(fd.created_at, datetime)
        assert fd.created_at.tzinfo is not None

    def test_feature_definition_custom(self):
        fd = FeatureDefinition(
            feature_id="custom_id_12345",
            name="momentum_30d",
            description="30-day momentum factor",
            feature_type=FeatureType.NUMERIC,
            entity_type=EntityType.STOCK,
            owner="quant_team",
            freshness_sla_minutes=60,
            version=2,
            tags=["momentum", "factor"],
        )
        assert fd.feature_id == "custom_id_12345"
        assert fd.owner == "quant_team"
        assert "momentum" in fd.tags

    def test_feature_value_defaults(self):
        fv = FeatureValue(feature_id="f1", entity_id="AAPL", value=150.0)
        assert fv.value_id  # Auto-generated
        assert len(fv.value_id) == 16
        assert fv.feature_id == "f1"
        assert fv.value == 150.0
        assert fv.as_of_date.tzinfo is not None

    def test_cache_entry_defaults(self):
        ce = CacheEntry(feature_id="f1", entity_id="AAPL", value=150.0)
        assert ce.entry_id
        assert ce.ttl_seconds == 300
        assert ce.hits == 0
        assert not ce.is_expired

    def test_cache_entry_expired(self):
        ce = CacheEntry(
            feature_id="f1",
            entity_id="AAPL",
            value=150.0,
            cached_at=datetime.now(timezone.utc) - timedelta(seconds=600),
            ttl_seconds=300,
        )
        assert ce.is_expired

    def test_lineage_node_defaults(self):
        node = LineageNode(name="price_source")
        assert node.node_id
        assert len(node.node_id) == 16
        assert node.node_type == "feature"
        assert node.created_at.tzinfo is not None

    def test_lineage_edge_defaults(self):
        edge = LineageEdge(source_id="n1", target_id="n2")
        assert edge.edge_id
        assert edge.relationship == "derived_from"


# ── Feature Catalog Tests ─────────────────────────────────────────────


class TestFeatureCatalog:
    def setup_method(self):
        self.catalog = FeatureCatalog()
        self.feature1 = FeatureDefinition(
            name="momentum_30d",
            description="30-day price momentum",
            feature_type=FeatureType.NUMERIC,
            entity_type=EntityType.STOCK,
            owner="quant_team",
            tags=["momentum", "factor"],
        )
        self.feature2 = FeatureDefinition(
            name="sector_code",
            description="GICS sector classification",
            feature_type=FeatureType.CATEGORICAL,
            entity_type=EntityType.STOCK,
            owner="data_team",
            tags=["sector", "classification"],
        )
        self.feature3 = FeatureDefinition(
            name="is_sp500",
            description="Whether stock is in S&P 500",
            feature_type=FeatureType.BOOLEAN,
            entity_type=EntityType.STOCK,
            owner="data_team",
            tags=["index", "membership"],
        )

    def test_register_feature(self):
        result = self.catalog.register(self.feature1)
        assert result.name == "momentum_30d"
        assert result.feature_id == self.feature1.feature_id

    def test_get_feature(self):
        self.catalog.register(self.feature1)
        found = self.catalog.get(self.feature1.feature_id)
        assert found is not None
        assert found.name == "momentum_30d"

    def test_get_nonexistent_feature(self):
        assert self.catalog.get("nonexistent") is None

    def test_get_by_name(self):
        self.catalog.register(self.feature1)
        found = self.catalog.get_by_name("momentum_30d")
        assert found is not None
        assert found.feature_id == self.feature1.feature_id

    def test_get_by_name_not_found(self):
        assert self.catalog.get_by_name("nonexistent") is None

    def test_search_by_query(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        results = self.catalog.search(query="momentum")
        assert len(results) == 1
        assert results[0].name == "momentum_30d"

    def test_search_by_type(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        results = self.catalog.search(feature_type=FeatureType.CATEGORICAL)
        assert len(results) == 1
        assert results[0].name == "sector_code"

    def test_search_by_entity_type(self):
        self.catalog.register(self.feature1)
        user_feature = FeatureDefinition(
            name="user_pref",
            entity_type=EntityType.USER,
        )
        self.catalog.register(user_feature)
        results = self.catalog.search(entity_type=EntityType.USER)
        assert len(results) == 1

    def test_search_by_owner(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        results = self.catalog.search(owner="quant_team")
        assert len(results) == 1

    def test_search_by_tags(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        self.catalog.register(self.feature3)
        results = self.catalog.search(tags=["factor"])
        assert len(results) == 1

    def test_search_by_status(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        self.catalog.deprecate(self.feature2.feature_id)
        active = self.catalog.search(status=FeatureStatus.ACTIVE)
        assert len(active) == 1

    def test_search_all(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        results = self.catalog.search()
        assert len(results) == 2

    def test_deprecate_feature(self):
        self.catalog.register(self.feature1)
        result = self.catalog.deprecate(self.feature1.feature_id, reason="Replaced by v2")
        assert result is True
        feature = self.catalog.get(self.feature1.feature_id)
        assert feature.status == FeatureStatus.DEPRECATED
        assert feature.metadata["deprecation_reason"] == "Replaced by v2"

    def test_deprecate_nonexistent(self):
        assert self.catalog.deprecate("nonexistent") is False

    def test_archive_feature(self):
        self.catalog.register(self.feature1)
        result = self.catalog.archive(self.feature1.feature_id)
        assert result is True
        feature = self.catalog.get(self.feature1.feature_id)
        assert feature.status == FeatureStatus.ARCHIVED

    def test_archive_nonexistent(self):
        assert self.catalog.archive("nonexistent") is False

    def test_list_features(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        self.catalog.register(self.feature3)
        all_features = self.catalog.list_features()
        assert len(all_features) == 3

    def test_list_features_by_status(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        self.catalog.deprecate(self.feature2.feature_id)
        deprecated = self.catalog.list_features(status=FeatureStatus.DEPRECATED)
        assert len(deprecated) == 1

    def test_get_dependencies(self):
        self.catalog.register(self.feature1)
        dep_feature = FeatureDefinition(
            name="adjusted_momentum",
            dependencies=[self.feature1.feature_id],
        )
        self.catalog.register(dep_feature)
        deps = self.catalog.get_dependencies(dep_feature.feature_id)
        assert len(deps) == 1
        assert deps[0].name == "momentum_30d"

    def test_get_dependents(self):
        self.catalog.register(self.feature1)
        dep_feature = FeatureDefinition(
            name="adjusted_momentum",
            dependencies=[self.feature1.feature_id],
        )
        self.catalog.register(dep_feature)
        dependents = self.catalog.get_dependents(self.feature1.feature_id)
        assert len(dependents) == 1
        assert dependents[0].name == "adjusted_momentum"

    def test_get_statistics(self):
        self.catalog.register(self.feature1)
        self.catalog.register(self.feature2)
        self.catalog.register(self.feature3)
        stats = self.catalog.get_statistics()
        assert stats["total_features"] == 3
        assert stats["total_active"] == 3
        assert "by_status" in stats
        assert "by_type" in stats
        assert "by_owner" in stats

    def test_remove_feature(self):
        self.catalog.register(self.feature1)
        assert self.catalog.remove(self.feature1.feature_id) is True
        assert self.catalog.get(self.feature1.feature_id) is None

    def test_remove_nonexistent(self):
        assert self.catalog.remove("nonexistent") is False


# ── Offline Feature Store Tests ───────────────────────────────────────


class TestOfflineFeatureStore:
    def setup_method(self):
        self.store = OfflineFeatureStore()
        self.now = datetime.now(timezone.utc)

    def test_store_and_get_latest(self):
        fv = FeatureValue(
            feature_id="momentum_30d",
            entity_id="AAPL",
            value=0.15,
            as_of_date=self.now,
        )
        self.store.store(fv)
        result = self.store.get_latest("momentum_30d", "AAPL")
        assert result is not None
        assert result.value == 0.15

    def test_get_latest_returns_most_recent(self):
        for i in range(3):
            fv = FeatureValue(
                feature_id="f1",
                entity_id="AAPL",
                value=i * 10,
                as_of_date=self.now + timedelta(hours=i),
            )
            self.store.store(fv)
        result = self.store.get_latest("f1", "AAPL")
        assert result.value == 20

    def test_get_latest_not_found(self):
        assert self.store.get_latest("nonexistent", "AAPL") is None

    def test_store_batch(self):
        values = [
            FeatureValue(feature_id="f1", entity_id=f"E{i}", value=i)
            for i in range(5)
        ]
        count = self.store.store_batch(values)
        assert count == 5

    def test_point_in_time_retrieval(self):
        base = self.now - timedelta(days=5)
        for day in range(5):
            fv = FeatureValue(
                feature_id="f1",
                entity_id="AAPL",
                value=100 + day,
                as_of_date=base + timedelta(days=day),
            )
            self.store.store(fv)

        # Query at day 2.5 should return day 2 value
        pit = base + timedelta(days=2, hours=12)
        result = self.store.get_point_in_time("f1", "AAPL", pit)
        assert result is not None
        assert result.value == 102

    def test_point_in_time_before_any_data(self):
        fv = FeatureValue(
            feature_id="f1",
            entity_id="AAPL",
            value=100,
            as_of_date=self.now,
        )
        self.store.store(fv)
        early = self.now - timedelta(days=1)
        result = self.store.get_point_in_time("f1", "AAPL", early)
        assert result is None

    def test_get_history(self):
        for i in range(10):
            fv = FeatureValue(
                feature_id="f1",
                entity_id="AAPL",
                value=i,
                as_of_date=self.now + timedelta(hours=i),
            )
            self.store.store(fv)
        history = self.store.get_history("f1", "AAPL")
        assert len(history) == 10

    def test_get_history_with_date_range(self):
        base = self.now - timedelta(days=10)
        for i in range(10):
            fv = FeatureValue(
                feature_id="f1",
                entity_id="AAPL",
                value=i,
                as_of_date=base + timedelta(days=i),
            )
            self.store.store(fv)

        start = base + timedelta(days=3)
        end = base + timedelta(days=7)
        history = self.store.get_history("f1", "AAPL", start_date=start, end_date=end)
        assert len(history) == 5  # days 3,4,5,6,7

    def test_get_history_with_limit(self):
        for i in range(20):
            fv = FeatureValue(
                feature_id="f1",
                entity_id="AAPL",
                value=i,
                as_of_date=self.now + timedelta(hours=i),
            )
            self.store.store(fv)
        history = self.store.get_history("f1", "AAPL", limit=5)
        assert len(history) == 5

    def test_get_training_dataset(self):
        features = ["momentum", "volume", "volatility"]
        entities = ["AAPL", "MSFT", "GOOGL"]

        for fid in features:
            for eid in entities:
                fv = FeatureValue(
                    feature_id=fid,
                    entity_id=eid,
                    value=hash(f"{fid}_{eid}") % 100,
                    as_of_date=self.now,
                )
                self.store.store(fv)

        dataset = self.store.get_training_dataset(features, entities, self.now)
        assert len(dataset) == 3
        for row in dataset:
            assert "entity_id" in row
            for fid in features:
                assert fid in row
                assert row[fid] is not None

    def test_get_training_dataset_missing_features(self):
        fv = FeatureValue(
            feature_id="f1",
            entity_id="AAPL",
            value=100,
            as_of_date=self.now,
        )
        self.store.store(fv)
        dataset = self.store.get_training_dataset(["f1", "f2"], ["AAPL"])
        assert dataset[0]["f1"] == 100
        assert dataset[0]["f2"] is None

    def test_get_statistics(self):
        for i in range(5):
            fv = FeatureValue(
                feature_id=f"f{i % 2}",
                entity_id=f"E{i}",
                value=i,
                as_of_date=self.now,
            )
            self.store.store(fv)

        stats = self.store.get_statistics()
        assert stats["total_values"] == 5
        assert stats["unique_features"] == 2
        assert stats["unique_entities"] == 5

    def test_delete_feature(self):
        for eid in ["AAPL", "MSFT"]:
            fv = FeatureValue(feature_id="f1", entity_id=eid, value=100)
            self.store.store(fv)
        deleted = self.store.delete_feature("f1")
        assert deleted == 2
        assert self.store.get_latest("f1", "AAPL") is None

    def test_delete_entity(self):
        for fid in ["f1", "f2"]:
            fv = FeatureValue(feature_id=fid, entity_id="AAPL", value=100)
            self.store.store(fv)
        deleted = self.store.delete_entity("AAPL")
        assert deleted == 2

    def test_get_feature_entities(self):
        for eid in ["AAPL", "MSFT", "GOOGL"]:
            fv = FeatureValue(feature_id="f1", entity_id=eid, value=100)
            self.store.store(fv)
        entities = self.store.get_feature_entities("f1")
        assert set(entities) == {"AAPL", "MSFT", "GOOGL"}


# ── Online Feature Store Tests ────────────────────────────────────────


class TestOnlineFeatureStore:
    def setup_method(self):
        self.store = OnlineFeatureStore(default_ttl_seconds=300)

    def test_put_and_get(self):
        self.store.put("f1", "AAPL", 150.0)
        result = self.store.get("f1", "AAPL")
        assert result == 150.0

    def test_get_missing_returns_default(self):
        result = self.store.get("f1", "AAPL", default=-1)
        assert result == -1

    def test_get_missing_returns_none(self):
        result = self.store.get("f1", "AAPL")
        assert result is None

    def test_put_overwrites(self):
        self.store.put("f1", "AAPL", 100.0)
        self.store.put("f1", "AAPL", 200.0)
        assert self.store.get("f1", "AAPL") == 200.0

    def test_expired_entry_returns_default(self):
        self.store.put("f1", "AAPL", 100.0, ttl_seconds=0)
        # The entry is immediately expired (ttl=0)
        import time
        time.sleep(0.01)
        result = self.store.get("f1", "AAPL", default=-1)
        assert result == -1

    def test_put_batch(self):
        entries = [
            {"feature_id": "f1", "entity_id": "AAPL", "value": 150},
            {"feature_id": "f1", "entity_id": "MSFT", "value": 300},
            {"feature_id": "f2", "entity_id": "AAPL", "value": 0.5},
        ]
        count = self.store.put_batch(entries)
        assert count == 3
        assert self.store.get("f1", "AAPL") == 150
        assert self.store.get("f2", "AAPL") == 0.5

    def test_get_entry(self):
        self.store.put("f1", "AAPL", 150.0)
        entry = self.store.get_entry("f1", "AAPL")
        assert entry is not None
        assert entry.value == 150.0
        assert entry.feature_id == "f1"

    def test_get_entry_missing(self):
        assert self.store.get_entry("f1", "AAPL") is None

    def test_get_feature_vector(self):
        self.store.put("momentum", "AAPL", 0.15)
        self.store.put("volatility", "AAPL", 0.25)
        self.store.put("volume", "AAPL", 1000000)

        vector = self.store.get_feature_vector(
            ["momentum", "volatility", "volume", "missing"],
            "AAPL",
        )
        assert vector["momentum"] == 0.15
        assert vector["volatility"] == 0.25
        assert vector["volume"] == 1000000
        assert vector["missing"] is None

    def test_invalidate_single(self):
        self.store.put("f1", "AAPL", 100.0)
        count = self.store.invalidate("f1", "AAPL")
        assert count == 1
        assert self.store.get("f1", "AAPL") is None

    def test_invalidate_all_for_feature(self):
        self.store.put("f1", "AAPL", 100.0)
        self.store.put("f1", "MSFT", 200.0)
        self.store.put("f2", "AAPL", 300.0)
        count = self.store.invalidate("f1")
        assert count == 2
        assert self.store.get("f1", "AAPL") is None
        assert self.store.get("f2", "AAPL") == 300.0

    def test_invalidate_entity(self):
        self.store.put("f1", "AAPL", 100.0)
        self.store.put("f2", "AAPL", 200.0)
        self.store.put("f1", "MSFT", 300.0)
        count = self.store.invalidate_entity("AAPL")
        assert count == 2
        assert self.store.get("f1", "MSFT") == 300.0

    def test_invalidate_nonexistent(self):
        count = self.store.invalidate("f1", "AAPL")
        assert count == 0

    def test_cache_stats(self):
        self.store.put("f1", "AAPL", 100.0)
        self.store.put("f1", "MSFT", 200.0)
        self.store.get("f1", "AAPL")  # hit
        self.store.get("f1", "AAPL")  # hit
        self.store.get("f1", "MISSING")  # miss

        stats = self.store.get_cache_stats()
        assert stats["total_entries"] == 2
        assert stats["total_hits"] == 2
        assert stats["total_misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_cache_stats_empty(self):
        stats = self.store.get_cache_stats()
        assert stats["total_entries"] == 0
        assert stats["hit_rate"] == 0.0

    def test_is_fresh(self):
        self.store.put("f1", "AAPL", 100.0, ttl_seconds=600)
        assert self.store.is_fresh("f1", "AAPL") is True

    def test_is_fresh_with_max_age(self):
        self.store.put("f1", "AAPL", 100.0, ttl_seconds=600)
        assert self.store.is_fresh("f1", "AAPL", max_age_seconds=600) is True

    def test_is_fresh_missing(self):
        assert self.store.is_fresh("f1", "AAPL") is False

    def test_clear(self):
        self.store.put("f1", "AAPL", 100.0)
        self.store.put("f2", "MSFT", 200.0)
        count = self.store.clear()
        assert count == 2
        assert self.store.get("f1", "AAPL") is None

    def test_max_entries_eviction(self):
        small_store = OnlineFeatureStore(max_entries=5)
        for i in range(10):
            small_store.put("f1", f"E{i}", i)
        stats = small_store.get_cache_stats()
        assert stats["total_entries"] <= 5

    def test_hit_count_tracking(self):
        self.store.put("f1", "AAPL", 100.0)
        for _ in range(5):
            self.store.get("f1", "AAPL")
        entry = self.store.get_entry("f1", "AAPL")
        assert entry.hits == 5


# ── Feature Lineage Tests ─────────────────────────────────────────────


class TestFeatureLineage:
    def setup_method(self):
        self.lineage = FeatureLineage()
        self.source_node = LineageNode(
            node_id="src_prices",
            name="Price Data Source",
            node_type="source",
        )
        self.feature_node = LineageNode(
            node_id="feat_momentum",
            name="Momentum Feature",
            node_type="feature",
        )
        self.model_node = LineageNode(
            node_id="model_ranking",
            name="Ranking Model",
            node_type="model",
        )

    def test_add_node(self):
        result = self.lineage.add_node(self.source_node)
        assert result.name == "Price Data Source"

    def test_get_node(self):
        self.lineage.add_node(self.source_node)
        found = self.lineage.get_node("src_prices")
        assert found is not None
        assert found.name == "Price Data Source"

    def test_get_node_not_found(self):
        assert self.lineage.get_node("nonexistent") is None

    def test_add_edge(self):
        self.lineage.add_node(self.source_node)
        self.lineage.add_node(self.feature_node)
        edge = LineageEdge(
            source_id="src_prices",
            target_id="feat_momentum",
            relationship="derived_from",
        )
        result = self.lineage.add_edge(edge)
        assert result.source_id == "src_prices"

    def test_add_edge_missing_node(self):
        self.lineage.add_node(self.source_node)
        edge = LineageEdge(source_id="src_prices", target_id="nonexistent")
        with pytest.raises(ValueError):
            self.lineage.add_edge(edge)

    def test_get_upstream(self):
        self._build_chain()
        upstream = self.lineage.get_upstream("model_ranking")
        assert len(upstream) == 2
        upstream_ids = {n.node_id for n in upstream}
        assert "src_prices" in upstream_ids
        assert "feat_momentum" in upstream_ids

    def test_get_downstream(self):
        self._build_chain()
        downstream = self.lineage.get_downstream("src_prices")
        assert len(downstream) == 2
        downstream_ids = {n.node_id for n in downstream}
        assert "feat_momentum" in downstream_ids
        assert "model_ranking" in downstream_ids

    def test_get_upstream_empty(self):
        self.lineage.add_node(self.source_node)
        upstream = self.lineage.get_upstream("src_prices")
        assert len(upstream) == 0

    def test_get_downstream_empty(self):
        self.lineage.add_node(self.model_node)
        downstream = self.lineage.get_downstream("model_ranking")
        assert len(downstream) == 0

    def test_get_impact(self):
        self._build_chain()
        impact = self.lineage.get_impact("src_prices")
        assert impact["total_affected"] == 2
        assert impact["feature_count"] == 1
        assert impact["model_count"] == 1

    def test_get_impact_leaf_node(self):
        self._build_chain()
        impact = self.lineage.get_impact("model_ranking")
        assert impact["total_affected"] == 0

    def test_get_lineage_graph(self):
        self._build_chain()
        graph = self.lineage.get_lineage_graph()
        assert graph["node_count"] == 3
        assert graph["edge_count"] == 2
        assert len(graph["nodes"]) == 3
        assert len(graph["edges"]) == 2

    def test_get_roots(self):
        self._build_chain()
        roots = self.lineage.get_roots()
        assert len(roots) == 1
        assert roots[0].node_id == "src_prices"

    def test_get_leaves(self):
        self._build_chain()
        leaves = self.lineage.get_leaves()
        assert len(leaves) == 1
        assert leaves[0].node_id == "model_ranking"

    def test_get_edges_for_node(self):
        self._build_chain()
        edges = self.lineage.get_edges_for_node("feat_momentum")
        assert len(edges) == 2  # one incoming, one outgoing

    def test_remove_node(self):
        self._build_chain()
        result = self.lineage.remove_node("feat_momentum")
        assert result is True
        assert self.lineage.get_node("feat_momentum") is None
        # Edges should be cleaned up
        graph = self.lineage.get_lineage_graph()
        assert graph["edge_count"] == 0

    def test_remove_nonexistent_node(self):
        assert self.lineage.remove_node("nonexistent") is False

    def test_get_statistics(self):
        self._build_chain()
        stats = self.lineage.get_statistics()
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2
        assert stats["root_count"] == 1
        assert stats["leaf_count"] == 1
        assert stats["by_type"]["source"] == 1
        assert stats["by_type"]["feature"] == 1
        assert stats["by_type"]["model"] == 1

    def test_complex_dag(self):
        """Test a diamond-shaped DAG: S -> F1, S -> F2, F1 -> M, F2 -> M."""
        src = LineageNode(node_id="s1", name="Source", node_type="source")
        f1 = LineageNode(node_id="f1", name="Feature 1", node_type="feature")
        f2 = LineageNode(node_id="f2", name="Feature 2", node_type="feature")
        model = LineageNode(node_id="m1", name="Model", node_type="model")

        self.lineage.add_node(src)
        self.lineage.add_node(f1)
        self.lineage.add_node(f2)
        self.lineage.add_node(model)

        self.lineage.add_edge(LineageEdge(source_id="s1", target_id="f1"))
        self.lineage.add_edge(LineageEdge(source_id="s1", target_id="f2"))
        self.lineage.add_edge(LineageEdge(source_id="f1", target_id="m1"))
        self.lineage.add_edge(LineageEdge(source_id="f2", target_id="m1"))

        # Source impacts everything downstream
        impact = self.lineage.get_impact("s1")
        assert impact["total_affected"] == 3

        # Model has two upstream paths
        upstream = self.lineage.get_upstream("m1")
        upstream_ids = {n.node_id for n in upstream}
        assert upstream_ids == {"s1", "f1", "f2"}

    def test_max_depth_limit(self):
        """Build a long chain and test depth limiting."""
        prev_id = "n0"
        self.lineage.add_node(LineageNode(node_id="n0", name="Node 0", node_type="source"))
        for i in range(1, 10):
            nid = f"n{i}"
            self.lineage.add_node(LineageNode(node_id=nid, name=f"Node {i}", node_type="feature"))
            self.lineage.add_edge(LineageEdge(source_id=prev_id, target_id=nid))
            prev_id = nid

        downstream = self.lineage.get_downstream("n0", max_depth=3)
        assert len(downstream) == 3

    def _build_chain(self):
        """Helper: build source -> feature -> model chain."""
        self.lineage.add_node(self.source_node)
        self.lineage.add_node(self.feature_node)
        self.lineage.add_node(self.model_node)
        self.lineage.add_edge(
            LineageEdge(source_id="src_prices", target_id="feat_momentum")
        )
        self.lineage.add_edge(
            LineageEdge(source_id="feat_momentum", target_id="model_ranking")
        )


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_end_to_end_workflow(self):
        """Full workflow: register features, store values, serve online, track lineage."""
        # 1. Register features in catalog
        catalog = FeatureCatalog()
        momentum = FeatureDefinition(
            name="momentum_30d",
            feature_type=FeatureType.NUMERIC,
            entity_type=EntityType.STOCK,
            owner="quant_team",
        )
        volume = FeatureDefinition(
            name="avg_volume_10d",
            feature_type=FeatureType.NUMERIC,
            entity_type=EntityType.STOCK,
            owner="quant_team",
        )
        catalog.register(momentum)
        catalog.register(volume)
        assert catalog.get_statistics()["total_features"] == 2

        # 2. Store values in offline store
        offline = OfflineFeatureStore()
        now = datetime.now(timezone.utc)
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            offline.store(FeatureValue(
                feature_id=momentum.feature_id,
                entity_id=ticker,
                value=0.15,
                as_of_date=now,
            ))
            offline.store(FeatureValue(
                feature_id=volume.feature_id,
                entity_id=ticker,
                value=5000000,
                as_of_date=now,
            ))

        # 3. Build training dataset
        dataset = offline.get_training_dataset(
            [momentum.feature_id, volume.feature_id],
            ["AAPL", "MSFT", "GOOGL"],
            now,
        )
        assert len(dataset) == 3
        assert all(row[momentum.feature_id] == 0.15 for row in dataset)

        # 4. Push to online store for serving
        online = OnlineFeatureStore()
        for row in dataset:
            eid = row["entity_id"]
            for fid in [momentum.feature_id, volume.feature_id]:
                online.put(fid, eid, row[fid])

        # 5. Serve feature vector
        vector = online.get_feature_vector(
            [momentum.feature_id, volume.feature_id],
            "AAPL",
        )
        assert vector[momentum.feature_id] == 0.15
        assert vector[volume.feature_id] == 5000000

        # 6. Track lineage
        lineage = FeatureLineage()
        src = LineageNode(node_id="price_src", name="Price Data", node_type="source")
        feat = LineageNode(
            node_id=momentum.feature_id, name="momentum_30d", node_type="feature"
        )
        model = LineageNode(node_id="ranking_model", name="Stock Ranker", node_type="model")
        lineage.add_node(src)
        lineage.add_node(feat)
        lineage.add_node(model)
        lineage.add_edge(LineageEdge(source_id="price_src", target_id=momentum.feature_id))
        lineage.add_edge(LineageEdge(source_id=momentum.feature_id, target_id="ranking_model"))

        impact = lineage.get_impact("price_src")
        assert impact["model_count"] == 1

    def test_offline_to_online_sync(self):
        """Test syncing features from offline to online store."""
        offline = OfflineFeatureStore()
        online = OnlineFeatureStore()

        now = datetime.now(timezone.utc)
        entities = ["AAPL", "MSFT"]
        feature_id = "momentum_30d"

        # Store in offline
        for eid in entities:
            offline.store(FeatureValue(
                feature_id=feature_id, entity_id=eid, value=0.1, as_of_date=now
            ))

        # Sync to online
        for eid in entities:
            val = offline.get_latest(feature_id, eid)
            if val:
                online.put(feature_id, eid, val.value)

        # Verify online
        for eid in entities:
            assert online.get(feature_id, eid) == 0.1


# ── Module Import Test ────────────────────────────────────────────────


class TestModuleImports:
    def test_import_all(self):
        import src.feature_store as fs
        assert hasattr(fs, "FeatureType")
        assert hasattr(fs, "FeatureStatus")
        assert hasattr(fs, "EntityType")
        assert hasattr(fs, "ComputeMode")
        assert hasattr(fs, "FeatureStoreConfig")
        assert hasattr(fs, "FeatureDefinition")
        assert hasattr(fs, "FeatureCatalog")
        assert hasattr(fs, "FeatureValue")
        assert hasattr(fs, "OfflineFeatureStore")
        assert hasattr(fs, "CacheEntry")
        assert hasattr(fs, "OnlineFeatureStore")
        assert hasattr(fs, "LineageNode")
        assert hasattr(fs, "LineageEdge")
        assert hasattr(fs, "FeatureLineage")
