"""Tests for Custom Factor Builder."""

import pytest
import pandas as pd
import numpy as np

from src.factors.builder import (
    TransformType,
    AggregationMethod,
    FactorComponent,
    CustomFactor,
    FactorResult,
    CustomFactorBuilder,
)


# ── Enum Tests ──


class TestEnums:
    def test_transform_types(self):
        assert TransformType.PERCENTILE_RANK.value == "percentile_rank"
        assert len(TransformType) == 6

    def test_aggregation_methods(self):
        assert AggregationMethod.WEIGHTED_AVERAGE.value == "weighted_average"
        assert len(AggregationMethod) == 5


# ── Model Tests ──


class TestFactorComponent:
    def test_defaults(self):
        c = FactorComponent(metric_name="pe_ratio")
        assert c.weight == 1.0
        assert c.transform == TransformType.PERCENTILE_RANK
        assert c.direction == "positive"

    def test_to_dict(self):
        c = FactorComponent(metric_name="roe", weight=2.0, direction="negative")
        d = c.to_dict()
        assert d["metric_name"] == "roe"
        assert d["weight"] == 2.0


class TestCustomFactor:
    def test_n_components(self):
        f = CustomFactor(
            name="Test",
            components=[
                FactorComponent(metric_name="pe"),
                FactorComponent(metric_name="roe"),
            ],
        )
        assert f.n_components == 2

    def test_total_weight(self):
        f = CustomFactor(
            components=[
                FactorComponent(metric_name="a", weight=2.0),
                FactorComponent(metric_name="b", weight=3.0),
            ],
        )
        assert f.total_weight == 5.0

    def test_component_names(self):
        f = CustomFactor(
            components=[
                FactorComponent(metric_name="pe"),
                FactorComponent(metric_name="roe"),
            ],
        )
        assert f.component_names == ["pe", "roe"]

    def test_to_dict(self):
        f = CustomFactor(name="Value Plus", description="Custom value factor")
        d = f.to_dict()
        assert d["name"] == "Value Plus"
        assert d["n_components"] == 0


class TestFactorResult:
    def test_n_scored(self):
        r = FactorResult(factor_id="1", factor_name="Test", scores={"AAPL": 80, "MSFT": 90})
        assert r.n_scored == 2

    def test_top_n(self):
        r = FactorResult(
            factor_id="1", factor_name="Test",
            scores={"AAPL": 80, "MSFT": 90, "GOOG": 70},
        )
        top = r.top_n(2)
        assert top[0][0] == "MSFT"
        assert top[1][0] == "AAPL"

    def test_bottom_n(self):
        r = FactorResult(
            factor_id="1", factor_name="Test",
            scores={"AAPL": 80, "MSFT": 90, "GOOG": 70},
        )
        bottom = r.bottom_n(1)
        assert bottom[0][0] == "GOOG"

    def test_to_dict(self):
        r = FactorResult(factor_id="1", factor_name="Test", scores={"AAPL": 80})
        d = r.to_dict()
        assert d["n_scored"] == 1


# ── Builder Tests ──


def make_sample_data() -> pd.DataFrame:
    """Create sample data for testing."""
    return pd.DataFrame({
        "pe_ratio": [15, 20, 25, 10, 30],
        "roe": [0.15, 0.20, 0.10, 0.25, 0.05],
        "momentum": [0.10, 0.05, -0.02, 0.15, -0.05],
        "volatility": [0.20, 0.30, 0.15, 0.25, 0.40],
    }, index=["AAPL", "MSFT", "GOOG", "AMZN", "META"])


class TestCustomFactorBuilder:
    def setup_method(self):
        self.builder = CustomFactorBuilder()

    def test_create_factor(self):
        components = [FactorComponent(metric_name="pe_ratio")]
        factor = self.builder.create_factor("Value", components, created_by="user1")
        assert factor.name == "Value"
        assert factor.n_components == 1
        assert factor.created_by == "user1"

    def test_create_factor_no_name_raises(self):
        with pytest.raises(ValueError, match="name is required"):
            self.builder.create_factor("", [FactorComponent(metric_name="pe")])

    def test_create_factor_no_components_raises(self):
        with pytest.raises(ValueError, match="one component"):
            self.builder.create_factor("Test", [])

    def test_get_factor(self):
        components = [FactorComponent(metric_name="pe_ratio")]
        factor = self.builder.create_factor("Value", components)
        retrieved = self.builder.get_factor(factor.id)
        assert retrieved is not None
        assert retrieved.name == "Value"

    def test_get_factor_not_found(self):
        assert self.builder.get_factor("nonexistent") is None

    def test_list_factors(self):
        self.builder.create_factor("A", [FactorComponent(metric_name="pe")])
        self.builder.create_factor("B", [FactorComponent(metric_name="roe")])
        assert len(self.builder.list_factors()) == 2

    def test_list_factors_by_creator(self):
        self.builder.create_factor("A", [FactorComponent(metric_name="pe")], created_by="user1")
        self.builder.create_factor("B", [FactorComponent(metric_name="roe")], created_by="user2")
        assert len(self.builder.list_factors(created_by="user1")) == 1

    def test_update_factor(self):
        factor = self.builder.create_factor("Old", [FactorComponent(metric_name="pe")])
        updated = self.builder.update_factor(factor.id, name="New")
        assert updated.name == "New"
        assert updated.updated_at is not None

    def test_update_factor_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            self.builder.update_factor("nonexistent", name="New")

    def test_delete_factor(self):
        factor = self.builder.create_factor("Test", [FactorComponent(metric_name="pe")])
        assert self.builder.delete_factor(factor.id) is True
        assert self.builder.get_factor(factor.id) is None

    def test_delete_factor_not_found(self):
        assert self.builder.delete_factor("nonexistent") is False


class TestFactorComputation:
    def setup_method(self):
        self.builder = CustomFactorBuilder()
        self.data = make_sample_data()

    def test_compute_single_component(self):
        components = [FactorComponent(metric_name="pe_ratio")]
        factor = self.builder.create_factor("PE Factor", components)
        result = self.builder.compute(factor.id, self.data)
        assert result.n_scored == 5
        assert all(isinstance(v, float) for v in result.scores.values())

    def test_compute_weighted_average(self):
        components = [
            FactorComponent(metric_name="pe_ratio", weight=2.0),
            FactorComponent(metric_name="roe", weight=1.0),
        ]
        factor = self.builder.create_factor("Combined", components)
        result = self.builder.compute(factor.id, self.data)
        assert result.n_scored == 5

    def test_compute_equal_weight(self):
        components = [
            FactorComponent(metric_name="pe_ratio"),
            FactorComponent(metric_name="roe"),
        ]
        factor = self.builder.create_factor(
            "EW", components, aggregation=AggregationMethod.EQUAL_WEIGHT,
        )
        result = self.builder.compute(factor.id, self.data)
        assert result.n_scored == 5

    def test_compute_max_aggregation(self):
        components = [
            FactorComponent(metric_name="pe_ratio"),
            FactorComponent(metric_name="roe"),
        ]
        factor = self.builder.create_factor(
            "Max", components, aggregation=AggregationMethod.MAX,
        )
        result = self.builder.compute(factor.id, self.data)
        assert result.n_scored == 5

    def test_compute_min_aggregation(self):
        components = [
            FactorComponent(metric_name="pe_ratio"),
            FactorComponent(metric_name="roe"),
        ]
        factor = self.builder.create_factor(
            "Min", components, aggregation=AggregationMethod.MIN,
        )
        result = self.builder.compute(factor.id, self.data)
        assert result.n_scored == 5

    def test_compute_geometric_mean(self):
        components = [
            FactorComponent(metric_name="pe_ratio"),
            FactorComponent(metric_name="roe"),
        ]
        factor = self.builder.create_factor(
            "Geo", components, aggregation=AggregationMethod.GEOMETRIC_MEAN,
        )
        result = self.builder.compute(factor.id, self.data)
        assert result.n_scored == 5

    def test_negative_direction(self):
        components = [FactorComponent(metric_name="pe_ratio", direction="negative")]
        factor = self.builder.create_factor("Low PE", components)
        result = self.builder.compute(factor.id, self.data)
        # Lower PE should score higher with negative direction
        assert result.scores["AMZN"] > result.scores["META"]  # AMZN PE=10, META PE=30

    def test_raw_transform(self):
        components = [FactorComponent(metric_name="pe_ratio", transform=TransformType.RAW)]
        factor = self.builder.create_factor("Raw PE", components)
        result = self.builder.compute(factor.id, self.data)
        assert result.scores["AAPL"] == 15.0

    def test_zscore_transform(self):
        components = [FactorComponent(metric_name="roe", transform=TransformType.ZSCORE)]
        factor = self.builder.create_factor("Z-ROE", components)
        result = self.builder.compute(factor.id, self.data)
        scores = list(result.scores.values())
        assert abs(np.mean(scores)) < 0.01  # Mean near 0

    def test_log_transform(self):
        components = [FactorComponent(metric_name="pe_ratio", transform=TransformType.LOG)]
        factor = self.builder.create_factor("Log PE", components)
        result = self.builder.compute(factor.id, self.data)
        assert all(v >= 0 for v in result.scores.values())

    def test_missing_column_raises(self):
        components = [FactorComponent(metric_name="nonexistent")]
        factor = self.builder.create_factor("Bad", components)
        with pytest.raises(ValueError, match="Missing columns"):
            self.builder.compute(factor.id, self.data)

    def test_factor_not_found_raises(self):
        with pytest.raises(ValueError, match="not found"):
            self.builder.compute("nonexistent", self.data)

    def test_top_bottom_ranking(self):
        components = [FactorComponent(metric_name="roe")]
        factor = self.builder.create_factor("ROE", components)
        result = self.builder.compute(factor.id, self.data)
        top = result.top_n(1)
        assert top[0][0] == "AMZN"  # Highest ROE = 0.25


# ── Module Import Test ──


class TestModuleImports:
    def test_builder_imports(self):
        from src.factors.builder import CustomFactorBuilder, CustomFactor, FactorComponent
        assert CustomFactorBuilder is not None
        assert CustomFactor is not None
        assert FactorComponent is not None
