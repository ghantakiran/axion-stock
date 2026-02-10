"""Tests for PRD-129: Data Contracts & Schema Governance."""

from datetime import datetime, timedelta, timezone

import pytest

from src.data_contracts.config import (
    ContractStatus,
    CompatibilityMode,
    FieldType,
    ViolationType,
    ValidationLevel,
    ContractConfig,
)
from src.data_contracts.schema import (
    FieldDefinition,
    SchemaVersion,
    DataContract,
    SchemaBuilder,
)
from src.data_contracts.registry import ContractRegistry
from src.data_contracts.validator import (
    ValidationResult,
    ContractViolation,
    ContractValidator,
)
from src.data_contracts.sla_monitor import (
    SLADefinition,
    SLAReport,
    SLAMonitor,
    DeliveryRecord,
)


# ── Config Tests ─────────────────────────────────────────────────────


class TestDataContractsEnums:
    """Test all configuration enums."""

    def test_contract_status_values(self):
        assert len(ContractStatus) == 4
        assert ContractStatus.DRAFT.value == "draft"
        assert ContractStatus.ACTIVE.value == "active"
        assert ContractStatus.DEPRECATED.value == "deprecated"
        assert ContractStatus.RETIRED.value == "retired"

    def test_compatibility_mode_values(self):
        assert len(CompatibilityMode) == 4
        assert CompatibilityMode.BACKWARD.value == "backward"
        assert CompatibilityMode.FORWARD.value == "forward"
        assert CompatibilityMode.FULL.value == "full"
        assert CompatibilityMode.NONE.value == "none"

    def test_field_type_values(self):
        assert len(FieldType) == 8
        assert FieldType.STRING.value == "string"
        assert FieldType.INTEGER.value == "integer"
        assert FieldType.FLOAT.value == "float"
        assert FieldType.BOOLEAN.value == "boolean"
        assert FieldType.DATETIME.value == "datetime"
        assert FieldType.LIST.value == "list"
        assert FieldType.MAP.value == "map"
        assert FieldType.ENUM.value == "enum"

    def test_violation_type_values(self):
        assert len(ViolationType) == 6
        assert ViolationType.MISSING_FIELD.value == "missing_field"
        assert ViolationType.TYPE_MISMATCH.value == "type_mismatch"
        assert ViolationType.CONSTRAINT_VIOLATION.value == "constraint_violation"
        assert ViolationType.SCHEMA_DRIFT.value == "schema_drift"
        assert ViolationType.FRESHNESS.value == "freshness"
        assert ViolationType.COMPLETENESS.value == "completeness"

    def test_validation_level_values(self):
        assert len(ValidationLevel) == 3
        assert ValidationLevel.STRICT.value == "strict"
        assert ValidationLevel.WARN.value == "warn"
        assert ValidationLevel.PERMISSIVE.value == "permissive"


class TestContractConfig:
    """Test ContractConfig dataclass."""

    def test_default_config(self):
        cfg = ContractConfig()
        assert cfg.compatibility_mode == CompatibilityMode.BACKWARD
        assert cfg.validation_level == ValidationLevel.STRICT
        assert cfg.max_violations_per_hour == 100
        assert cfg.alert_on_violation is True

    def test_custom_config(self):
        cfg = ContractConfig(
            compatibility_mode=CompatibilityMode.FULL,
            validation_level=ValidationLevel.WARN,
            max_violations_per_hour=50,
            alert_on_violation=False,
        )
        assert cfg.compatibility_mode == CompatibilityMode.FULL
        assert cfg.validation_level == ValidationLevel.WARN
        assert cfg.max_violations_per_hour == 50
        assert cfg.alert_on_violation is False

    def test_config_track_schema_drift(self):
        cfg = ContractConfig()
        assert cfg.track_schema_drift is True

    def test_config_retention_days(self):
        cfg = ContractConfig(retention_days=180)
        assert cfg.retention_days == 180


# ── Schema Tests ─────────────────────────────────────────────────────


class TestFieldDefinition:
    """Test FieldDefinition dataclass."""

    def test_basic_field(self):
        f = FieldDefinition(name="price", field_type=FieldType.FLOAT)
        assert f.name == "price"
        assert f.field_type == FieldType.FLOAT
        assert f.required is True
        assert f.constraints == {}
        assert f.description == ""
        assert f.default is None

    def test_optional_field(self):
        f = FieldDefinition(
            name="notes", field_type=FieldType.STRING, required=False, default="N/A"
        )
        assert f.required is False
        assert f.default == "N/A"

    def test_field_with_constraints(self):
        f = FieldDefinition(
            name="quantity",
            field_type=FieldType.INTEGER,
            constraints={"min_value": 1, "max_value": 10000},
        )
        assert f.constraints["min_value"] == 1
        assert f.constraints["max_value"] == 10000

    def test_to_dict(self):
        f = FieldDefinition(name="symbol", field_type=FieldType.STRING, description="Ticker")
        d = f.to_dict()
        assert d["name"] == "symbol"
        assert d["field_type"] == "string"
        assert d["description"] == "Ticker"

    def test_from_dict(self):
        data = {
            "name": "price",
            "field_type": "float",
            "required": True,
            "constraints": {"min_value": 0},
        }
        f = FieldDefinition.from_dict(data)
        assert f.name == "price"
        assert f.field_type == FieldType.FLOAT
        assert f.constraints["min_value"] == 0

    def test_roundtrip_serialization(self):
        original = FieldDefinition(
            name="volume",
            field_type=FieldType.INTEGER,
            required=True,
            constraints={"min_value": 0},
            description="Trading volume",
        )
        restored = FieldDefinition.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.field_type == original.field_type
        assert restored.required == original.required
        assert restored.constraints == original.constraints


class TestSchemaVersion:
    """Test SchemaVersion dataclass."""

    def setup_method(self):
        self.fields = [
            FieldDefinition(name="symbol", field_type=FieldType.STRING),
            FieldDefinition(name="price", field_type=FieldType.FLOAT),
            FieldDefinition(name="volume", field_type=FieldType.INTEGER),
        ]
        self.schema = SchemaVersion(version="1.0.0", fields=self.fields)

    def test_basic_schema(self):
        assert self.schema.version == "1.0.0"
        assert len(self.schema.fields) == 3

    def test_get_field(self):
        f = self.schema.get_field("price")
        assert f is not None
        assert f.field_type == FieldType.FLOAT

    def test_get_field_missing(self):
        assert self.schema.get_field("nonexistent") is None

    def test_field_names(self):
        names = self.schema.field_names()
        assert names == ["symbol", "price", "volume"]

    def test_required_fields(self):
        fields = [
            FieldDefinition(name="a", field_type=FieldType.STRING, required=True),
            FieldDefinition(name="b", field_type=FieldType.STRING, required=False),
            FieldDefinition(name="c", field_type=FieldType.STRING, required=True),
        ]
        schema = SchemaVersion(version="1.0.0", fields=fields)
        required = schema.required_fields()
        assert len(required) == 2
        assert required[0].name == "a"
        assert required[1].name == "c"

    def test_to_dict(self):
        d = self.schema.to_dict()
        assert d["version"] == "1.0.0"
        assert len(d["fields"]) == 3
        assert "created_at" in d

    def test_created_at_is_set(self):
        assert self.schema.created_at is not None
        assert isinstance(self.schema.created_at, datetime)


class TestDataContract:
    """Test DataContract dataclass."""

    def test_default_contract(self):
        c = DataContract()
        assert len(c.contract_id) == 16
        assert c.status == ContractStatus.DRAFT
        assert c.name == ""
        assert c.producer == ""
        assert c.consumer == ""

    def test_contract_with_details(self):
        c = DataContract(
            name="price-feed",
            producer="market-data-service",
            consumer="trading-engine",
            description="Real-time price feed",
            tags=["realtime", "market-data"],
        )
        assert c.name == "price-feed"
        assert c.producer == "market-data-service"
        assert c.consumer == "trading-engine"
        assert "realtime" in c.tags

    def test_contract_id_uniqueness(self):
        c1 = DataContract()
        c2 = DataContract()
        assert c1.contract_id != c2.contract_id

    def test_to_dict(self):
        c = DataContract(name="test", producer="p", consumer="c")
        d = c.to_dict()
        assert d["name"] == "test"
        assert d["producer"] == "p"
        assert d["consumer"] == "c"
        assert d["status"] == "draft"


class TestSchemaBuilder:
    """Test SchemaBuilder fluent API."""

    def test_basic_build(self):
        schema = (
            SchemaBuilder()
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .build()
        )
        assert schema.version == "1.0.0"
        assert len(schema.fields) == 2

    def test_set_version(self):
        schema = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("x", FieldType.INTEGER)
            .build()
        )
        assert schema.version == "2.0.0"

    def test_set_changelog(self):
        schema = (
            SchemaBuilder()
            .set_changelog("Added price field")
            .add_field("price", FieldType.FLOAT)
            .build()
        )
        assert schema.changelog == "Added price field"

    def test_field_with_constraints(self):
        schema = (
            SchemaBuilder()
            .add_field("age", FieldType.INTEGER, constraints={"min_value": 0, "max_value": 150})
            .build()
        )
        f = schema.get_field("age")
        assert f.constraints["min_value"] == 0

    def test_optional_field(self):
        schema = (
            SchemaBuilder()
            .add_field("notes", FieldType.STRING, required=False, default="")
            .build()
        )
        f = schema.get_field("notes")
        assert f.required is False
        assert f.default == ""

    def test_from_sample_basic_types(self):
        sample = {
            "symbol": "AAPL",
            "price": 175.50,
            "volume": 1000000,
            "active": True,
        }
        schema = SchemaBuilder.from_sample(sample)
        assert schema.get_field("symbol").field_type == FieldType.STRING
        assert schema.get_field("price").field_type == FieldType.FLOAT
        assert schema.get_field("volume").field_type == FieldType.INTEGER
        assert schema.get_field("active").field_type == FieldType.BOOLEAN

    def test_from_sample_complex_types(self):
        sample = {
            "tags": ["a", "b"],
            "metadata": {"key": "val"},
            "timestamp": datetime.now(timezone.utc),
        }
        schema = SchemaBuilder.from_sample(sample)
        assert schema.get_field("tags").field_type == FieldType.LIST
        assert schema.get_field("metadata").field_type == FieldType.MAP
        assert schema.get_field("timestamp").field_type == FieldType.DATETIME

    def test_from_sample_version(self):
        schema = SchemaBuilder.from_sample({"x": 1}, version="3.0.0")
        assert schema.version == "3.0.0"

    def test_diff_no_changes(self):
        v1 = SchemaBuilder().add_field("a", FieldType.STRING).build()
        v2 = SchemaBuilder().add_field("a", FieldType.STRING).build()
        changes = SchemaBuilder.diff(v1, v2)
        assert len(changes) == 0

    def test_diff_field_added(self):
        v1 = SchemaBuilder().add_field("a", FieldType.STRING).build()
        v2 = (
            SchemaBuilder()
            .add_field("a", FieldType.STRING)
            .add_field("b", FieldType.INTEGER)
            .build()
        )
        changes = SchemaBuilder.diff(v1, v2)
        assert len(changes) == 1
        assert changes[0]["change"] == "added"
        assert changes[0]["field"] == "b"

    def test_diff_field_removed(self):
        v1 = (
            SchemaBuilder()
            .add_field("a", FieldType.STRING)
            .add_field("b", FieldType.INTEGER)
            .build()
        )
        v2 = SchemaBuilder().add_field("a", FieldType.STRING).build()
        changes = SchemaBuilder.diff(v1, v2)
        assert len(changes) == 1
        assert changes[0]["change"] == "removed"
        assert changes[0]["field"] == "b"

    def test_diff_field_modified_type(self):
        v1 = SchemaBuilder().add_field("a", FieldType.STRING).build()
        v2 = SchemaBuilder().add_field("a", FieldType.INTEGER).build()
        changes = SchemaBuilder.diff(v1, v2)
        assert len(changes) == 1
        assert changes[0]["change"] == "modified"
        assert "type changed" in changes[0]["details"]

    def test_diff_field_modified_required(self):
        v1 = SchemaBuilder().add_field("a", FieldType.STRING, required=True).build()
        v2 = SchemaBuilder().add_field("a", FieldType.STRING, required=False).build()
        changes = SchemaBuilder.diff(v1, v2)
        assert len(changes) == 1
        assert "required changed" in changes[0]["details"]


class TestCompatibilityChecks:
    """Test schema compatibility checking."""

    def setup_method(self):
        self.v1 = (
            SchemaBuilder()
            .set_version("1.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .build()
        )

    def test_backward_compatible_optional_field_added(self):
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .add_field("notes", FieldType.STRING, required=False)
            .build()
        )
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.BACKWARD)
        assert ok is True
        assert len(issues) == 0

    def test_backward_incompatible_required_field_added(self):
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .add_field("volume", FieldType.INTEGER, required=True)
            .build()
        )
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.BACKWARD)
        assert ok is False
        assert any("required" in i.lower() for i in issues)

    def test_backward_incompatible_type_change(self):
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.INTEGER)
            .add_field("price", FieldType.FLOAT)
            .build()
        )
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.BACKWARD)
        assert ok is False
        assert any("type changed" in i.lower() for i in issues)

    def test_forward_incompatible_field_removed(self):
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .build()
        )
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.FORWARD)
        assert ok is False
        assert any("removed" in i.lower() for i in issues)

    def test_forward_compatible_field_added(self):
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .add_field("extra", FieldType.STRING, required=False)
            .build()
        )
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.FORWARD)
        assert ok is True

    def test_full_compatibility(self):
        # Same schema is fully compatible
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .build()
        )
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.FULL)
        assert ok is True

    def test_full_incompatible_removed_and_added(self):
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("volume", FieldType.INTEGER, required=True)
            .build()
        )
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.FULL)
        assert ok is False
        # Both backward (new required) and forward (removed field) issues
        assert len(issues) >= 2

    def test_none_compatibility_always_passes(self):
        v2 = SchemaBuilder().add_field("completely_different", FieldType.BOOLEAN).build()
        ok, issues = SchemaBuilder.check_compatibility(self.v1, v2, CompatibilityMode.NONE)
        assert ok is True
        assert len(issues) == 0


# ── Registry Tests ───────────────────────────────────────────────────


class TestContractRegistry:
    """Test ContractRegistry lifecycle and querying."""

    def setup_method(self):
        self.registry = ContractRegistry()
        self.schema = (
            SchemaBuilder()
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .build()
        )

    def _make_contract(self, name="test-contract", producer="svc-a", consumer="svc-b"):
        return DataContract(
            name=name,
            producer=producer,
            consumer=consumer,
            schema_version=self.schema,
        )

    def test_register_contract(self):
        c = self._make_contract()
        cid = self.registry.register(c)
        assert cid == c.contract_id
        assert self.registry.contract_count() == 1

    def test_register_sets_active_status(self):
        c = self._make_contract()
        self.registry.register(c)
        retrieved = self.registry.get_contract(c.contract_id)
        assert retrieved.status == ContractStatus.ACTIVE

    def test_register_duplicate_raises(self):
        c = self._make_contract()
        self.registry.register(c)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(c)

    def test_get_contract(self):
        c = self._make_contract()
        self.registry.register(c)
        retrieved = self.registry.get_contract(c.contract_id)
        assert retrieved.name == "test-contract"

    def test_get_contract_not_found(self):
        assert self.registry.get_contract("nonexistent") is None

    def test_deprecate_contract(self):
        c = self._make_contract()
        self.registry.register(c)
        result = self.registry.deprecate(c.contract_id, "No longer needed")
        assert result.status == ContractStatus.DEPRECATED
        assert "DEPRECATED" in result.description

    def test_deprecate_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            self.registry.deprecate("no-such-contract")

    def test_retire_contract(self):
        c = self._make_contract()
        self.registry.register(c)
        result = self.registry.retire(c.contract_id)
        assert result.status == ContractStatus.RETIRED

    def test_update_schema_compatible(self):
        c = self._make_contract()
        self.registry.register(c)
        new_schema = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .add_field("notes", FieldType.STRING, required=False)
            .build()
        )
        updated = self.registry.update_schema(c.contract_id, new_schema)
        assert updated.schema_version.version == "2.0.0"
        assert len(updated.version_history) == 2  # original + archived

    def test_update_schema_incompatible_raises(self):
        c = self._make_contract()
        self.registry.register(c)
        bad_schema = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT)
            .add_field("required_new", FieldType.INTEGER, required=True)
            .build()
        )
        with pytest.raises(ValueError, match="compatibility"):
            self.registry.update_schema(c.contract_id, bad_schema)

    def test_find_by_producer(self):
        c1 = self._make_contract(name="c1", producer="svc-a")
        c2 = self._make_contract(name="c2", producer="svc-a")
        c3 = self._make_contract(name="c3", producer="svc-b")
        self.registry.register(c1)
        self.registry.register(c2)
        self.registry.register(c3)
        results = self.registry.find_by_producer("svc-a")
        assert len(results) == 2

    def test_find_by_consumer(self):
        c1 = self._make_contract(name="c1", consumer="svc-x")
        c2 = self._make_contract(name="c2", consumer="svc-y")
        self.registry.register(c1)
        self.registry.register(c2)
        results = self.registry.find_by_consumer("svc-x")
        assert len(results) == 1

    def test_find_by_tag(self):
        c = self._make_contract()
        c.tags = ["realtime", "pricing"]
        self.registry.register(c)
        results = self.registry.find_by_tag("realtime")
        assert len(results) == 1
        assert results[0].contract_id == c.contract_id

    def test_dependency_graph(self):
        c1 = self._make_contract(name="c1", producer="data-svc", consumer="trading")
        c2 = self._make_contract(name="c2", producer="data-svc", consumer="risk")
        c3 = self._make_contract(name="c3", producer="trading", consumer="reporting")
        self.registry.register(c1)
        self.registry.register(c2)
        self.registry.register(c3)
        graph = self.registry.dependency_graph()
        assert "data-svc" in graph
        assert "trading" in graph["data-svc"]
        assert "risk" in graph["data-svc"]
        assert "reporting" in graph["trading"]

    def test_list_contracts_all(self):
        c1 = self._make_contract(name="c1")
        c2 = self._make_contract(name="c2")
        self.registry.register(c1)
        self.registry.register(c2)
        all_contracts = self.registry.list_contracts()
        assert len(all_contracts) == 2

    def test_list_contracts_filtered(self):
        c1 = self._make_contract(name="c1")
        c2 = self._make_contract(name="c2")
        self.registry.register(c1)
        self.registry.register(c2)
        self.registry.deprecate(c1.contract_id, "old")
        deprecated = self.registry.list_contracts(status_filter=ContractStatus.DEPRECATED)
        assert len(deprecated) == 1
        active = self.registry.list_contracts(status_filter=ContractStatus.ACTIVE)
        assert len(active) == 1

    def test_remove_contract(self):
        c = self._make_contract()
        self.registry.register(c)
        assert self.registry.remove(c.contract_id) is True
        assert self.registry.get_contract(c.contract_id) is None
        assert self.registry.contract_count() == 0

    def test_remove_nonexistent(self):
        assert self.registry.remove("no-such") is False


# ── Validator Tests ──────────────────────────────────────────────────


class TestContractValidator:
    """Test ContractValidator with all field types and constraints."""

    def setup_method(self):
        self.validator = ContractValidator()
        self.schema = (
            SchemaBuilder()
            .add_field("symbol", FieldType.STRING, constraints={"min_length": 1, "max_length": 10})
            .add_field("price", FieldType.FLOAT, constraints={"min_value": 0})
            .add_field("volume", FieldType.INTEGER, constraints={"min_value": 0})
            .add_field("active", FieldType.BOOLEAN)
            .add_field("notes", FieldType.STRING, required=False)
            .build()
        )
        self.contract = DataContract(
            name="test-contract",
            producer="svc-a",
            consumer="svc-b",
            schema_version=self.schema,
        )

    def test_valid_data(self):
        data = {"symbol": "AAPL", "price": 175.0, "volume": 1000, "active": True}
        result = self.validator.validate(data, self.contract)
        assert result.valid is True
        assert result.violation_count == 0

    def test_missing_required_field(self):
        data = {"symbol": "AAPL", "price": 175.0, "active": True}
        # volume is missing
        result = self.validator.validate(data, self.contract)
        assert result.valid is False
        assert result.violation_count >= 1
        assert any(v.violation_type == ViolationType.MISSING_FIELD for v in result.violations)

    def test_type_mismatch_string(self):
        data = {"symbol": 123, "price": 175.0, "volume": 1000, "active": True}
        result = self.validator.validate(data, self.contract)
        assert result.valid is False
        assert any(v.violation_type == ViolationType.TYPE_MISMATCH for v in result.violations)

    def test_type_mismatch_float(self):
        data = {"symbol": "AAPL", "price": "not_a_number", "volume": 1000, "active": True}
        result = self.validator.validate(data, self.contract)
        assert result.valid is False

    def test_type_mismatch_bool_vs_int(self):
        data = {"symbol": "AAPL", "price": 175.0, "volume": 1000, "active": 1}
        result = self.validator.validate(data, self.contract)
        assert result.valid is False

    def test_int_accepts_int_not_bool(self):
        data = {"symbol": "AAPL", "price": 175.0, "volume": True, "active": True}
        result = self.validator.validate(data, self.contract)
        # bool should not pass as integer
        assert result.valid is False

    def test_float_accepts_int(self):
        data = {"symbol": "AAPL", "price": 175, "volume": 1000, "active": True}
        result = self.validator.validate(data, self.contract)
        # int is valid for float type
        assert result.valid is True

    def test_constraint_min_value(self):
        data = {"symbol": "AAPL", "price": -5.0, "volume": 1000, "active": True}
        result = self.validator.validate(data, self.contract)
        assert result.valid is False
        assert any(v.violation_type == ViolationType.CONSTRAINT_VIOLATION for v in result.violations)

    def test_constraint_max_length(self):
        data = {"symbol": "VERYLONGSYMBOLNAME", "price": 175.0, "volume": 1000, "active": True}
        result = self.validator.validate(data, self.contract)
        assert result.valid is False

    def test_constraint_min_length(self):
        data = {"symbol": "", "price": 175.0, "volume": 1000, "active": True}
        result = self.validator.validate(data, self.contract)
        assert result.valid is False

    def test_constraint_pattern(self):
        schema = (
            SchemaBuilder()
            .add_field("email", FieldType.STRING, constraints={"pattern": r"^[^@]+@[^@]+\.[^@]+$"})
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate({"email": "invalid"}, contract)
        assert result.valid is False

    def test_constraint_pattern_valid(self):
        schema = (
            SchemaBuilder()
            .add_field("email", FieldType.STRING, constraints={"pattern": r"^[^@]+@[^@]+\.[^@]+$"})
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate({"email": "user@example.com"}, contract)
        assert result.valid is True

    def test_constraint_allowed_values(self):
        schema = (
            SchemaBuilder()
            .add_field("status", FieldType.STRING, constraints={"allowed_values": ["active", "inactive"]})
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate({"status": "pending"}, contract)
        assert result.valid is False

    def test_constraint_allowed_values_valid(self):
        schema = (
            SchemaBuilder()
            .add_field("status", FieldType.STRING, constraints={"allowed_values": ["active", "inactive"]})
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate({"status": "active"}, contract)
        assert result.valid is True

    def test_optional_field_missing_ok(self):
        data = {"symbol": "AAPL", "price": 175.0, "volume": 1000, "active": True}
        # 'notes' is optional and missing - should be fine
        result = self.validator.validate(data, self.contract)
        assert result.valid is True

    def test_schema_drift_detection_strict(self):
        data = {"symbol": "AAPL", "price": 175.0, "volume": 1000, "active": True, "extra_field": "surprise"}
        result = self.validator.validate(data, self.contract)
        assert result.warning_count >= 1
        assert any(w.violation_type == ViolationType.SCHEMA_DRIFT for w in result.warnings)

    def test_warn_mode_converts_to_warnings(self):
        validator = ContractValidator(validation_level=ValidationLevel.WARN)
        data = {"symbol": 123, "price": 175.0, "volume": 1000, "active": True}
        result = validator.validate(data, self.contract)
        assert result.valid is True  # Warnings don't fail
        assert result.warning_count >= 1

    def test_permissive_mode_drops_violations(self):
        validator = ContractValidator(validation_level=ValidationLevel.PERMISSIVE)
        data = {"symbol": 123, "price": 175.0, "volume": 1000, "active": True}
        result = validator.validate(data, self.contract)
        assert result.valid is True
        assert result.violation_count == 0
        assert result.warning_count == 0

    def test_validate_batch(self):
        records = [
            {"symbol": "AAPL", "price": 175.0, "volume": 1000, "active": True},
            {"symbol": "MSFT", "price": 350.0, "volume": 2000, "active": False},
            {"symbol": 123, "price": 175.0, "volume": 1000, "active": True},
        ]
        result = self.validator.validate_batch(records, self.contract)
        assert result.valid is False
        assert result.records_checked == 3
        assert result.violation_count >= 1

    def test_validate_freshness_fresh(self):
        ts = datetime.now(timezone.utc) - timedelta(seconds=10)
        assert self.validator.validate_freshness(ts, 60.0) is True

    def test_validate_freshness_stale(self):
        ts = datetime.now(timezone.utc) - timedelta(hours=2)
        assert self.validator.validate_freshness(ts, 60.0) is False

    def test_validate_freshness_naive_timestamp(self):
        ts = datetime.now() - timedelta(seconds=10)
        assert self.validator.validate_freshness(ts, 60.0) is True

    def test_validate_completeness_full(self):
        data = {"symbol": "AAPL", "price": 175.0, "volume": 1000, "active": True}
        completeness = self.validator.validate_completeness(data, self.schema)
        assert completeness == 1.0

    def test_validate_completeness_partial(self):
        data = {"symbol": "AAPL"}
        completeness = self.validator.validate_completeness(data, self.schema)
        assert 0.0 < completeness < 1.0

    def test_validate_completeness_empty(self):
        completeness = self.validator.validate_completeness({}, self.schema)
        assert completeness == 0.0

    def test_violation_statistics(self):
        # Generate some violations
        data_bad = {"symbol": 123, "price": 175.0, "volume": 1000, "active": True}
        self.validator.validate(data_bad, self.contract)
        stats = self.validator.violation_statistics(self.contract.contract_id)
        assert stats["total"] >= 1
        assert "by_type" in stats
        assert "by_field" in stats

    def test_violation_statistics_empty(self):
        stats = self.validator.violation_statistics("nonexistent")
        assert stats["total"] == 0

    def test_clear_log(self):
        data_bad = {"symbol": 123, "price": 175.0, "volume": 1000, "active": True}
        self.validator.validate(data_bad, self.contract)
        assert len(self.validator.violation_log) > 0
        self.validator.clear_log()
        assert len(self.validator.violation_log) == 0

    def test_validate_no_schema(self):
        contract = DataContract(name="no-schema")
        result = self.validator.validate({"x": 1}, contract)
        assert result.valid is True

    def test_validate_list_field(self):
        schema = (
            SchemaBuilder()
            .add_field("tags", FieldType.LIST)
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate({"tags": ["a", "b"]}, contract)
        assert result.valid is True

    def test_validate_map_field(self):
        schema = (
            SchemaBuilder()
            .add_field("metadata", FieldType.MAP)
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate({"metadata": {"key": "val"}}, contract)
        assert result.valid is True

    def test_validate_datetime_field(self):
        schema = (
            SchemaBuilder()
            .add_field("timestamp", FieldType.DATETIME)
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate(
            {"timestamp": datetime.now(timezone.utc)}, contract
        )
        assert result.valid is True

    def test_constraint_not_null(self):
        schema = (
            SchemaBuilder()
            .add_field("value", FieldType.STRING, constraints={"not_null": True})
            .build()
        )
        contract = DataContract(schema_version=schema)
        result = self.validator.validate({"value": None}, contract)
        assert result.valid is False


# ── SLA Monitor Tests ────────────────────────────────────────────────


class TestSLADefinition:
    """Test SLADefinition dataclass."""

    def test_default_sla(self):
        sla = SLADefinition()
        assert sla.freshness_seconds == 300.0
        assert sla.completeness_threshold == 0.95
        assert sla.max_violations_per_day == 10
        assert sla.uptime_target == 0.999

    def test_custom_sla(self):
        sla = SLADefinition(
            freshness_seconds=60.0,
            completeness_threshold=0.99,
            max_violations_per_day=5,
            uptime_target=0.9999,
        )
        assert sla.freshness_seconds == 60.0
        assert sla.completeness_threshold == 0.99

    def test_to_dict(self):
        sla = SLADefinition()
        d = sla.to_dict()
        assert d["freshness_seconds"] == 300.0
        assert d["completeness_threshold"] == 0.95


class TestSLAMonitor:
    """Test SLAMonitor functionality."""

    def setup_method(self):
        self.monitor = SLAMonitor()
        self.sla = SLADefinition(
            freshness_seconds=300.0,
            completeness_threshold=0.90,
            max_violations_per_day=5,
        )
        self.contract_id = "test-contract-001"
        self.monitor.set_sla(self.contract_id, self.sla)

    def test_set_sla(self):
        retrieved = self.monitor.get_sla(self.contract_id)
        assert retrieved is not None
        assert retrieved.freshness_seconds == 300.0

    def test_get_sla_not_found(self):
        assert self.monitor.get_sla("nonexistent") is None

    def test_record_delivery(self):
        delivery = self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
        )
        assert delivery.contract_id == self.contract_id
        assert delivery.record_count == 100
        assert delivery.is_fresh is True

    def test_record_delivery_stale(self):
        old_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        delivery = self.monitor.record_delivery(
            self.contract_id,
            timestamp=old_ts,
            record_count=50,
        )
        assert delivery.is_fresh is False

    def test_check_sla_compliant(self):
        # Recent delivery with good completeness
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
            completeness=0.95,
        )
        report = self.monitor.check_sla(self.contract_id)
        assert report.freshness_met is True
        assert report.completeness_met is True
        assert report.violations_within_limit is True
        assert report.is_compliant is True

    def test_check_sla_freshness_failed(self):
        # Only stale delivery
        old_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=old_ts,
            record_count=100,
            completeness=0.95,
        )
        report = self.monitor.check_sla(self.contract_id)
        assert report.freshness_met is False

    def test_check_sla_completeness_failed(self):
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
            completeness=0.50,
        )
        report = self.monitor.check_sla(self.contract_id)
        assert report.completeness_met is False

    def test_check_sla_violations_exceeded(self):
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
            completeness=0.95,
        )
        for _ in range(10):
            self.monitor.record_violation(self.contract_id)
        report = self.monitor.check_sla(self.contract_id)
        assert report.violations_within_limit is False

    def test_check_sla_no_deliveries(self):
        report = self.monitor.check_sla(self.contract_id)
        assert report.freshness_met is False
        assert report.completeness_met is False

    def test_check_sla_no_sla_defined(self):
        report = self.monitor.check_sla("undefined-contract")
        assert report.freshness_met is True  # default when no SLA set

    def test_compliance_history(self):
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
            completeness=0.95,
        )
        self.monitor.check_sla(self.contract_id)
        self.monitor.check_sla(self.contract_id)
        history = self.monitor.get_compliance_history(self.contract_id, days=1)
        assert len(history) >= 2

    def test_overall_compliance(self):
        cid2 = "test-contract-002"
        self.monitor.set_sla(cid2, SLADefinition())
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
            completeness=0.95,
        )
        self.monitor.record_delivery(
            cid2,
            timestamp=datetime.now(timezone.utc),
            record_count=50,
            completeness=0.99,
        )
        overall = self.monitor.overall_compliance()
        assert overall["total_contracts"] == 2
        assert "compliance_rate" in overall
        assert "contracts" in overall

    def test_overall_compliance_empty(self):
        monitor = SLAMonitor()
        result = monitor.overall_compliance()
        assert result["total_contracts"] == 0
        assert result["compliance_rate"] == 100.0

    def test_delivery_history(self):
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
        )
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=200,
        )
        history = self.monitor.get_delivery_history(self.contract_id, hours=1)
        assert len(history) == 2

    def test_sla_report_to_dict(self):
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
            completeness=0.95,
        )
        report = self.monitor.check_sla(self.contract_id)
        d = report.to_dict()
        assert "contract_id" in d
        assert "compliance_pct" in d
        assert "is_compliant" in d

    def test_compliance_pct_calculation(self):
        # All 3 checks pass -> 100%
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=datetime.now(timezone.utc),
            record_count=100,
            completeness=0.95,
        )
        report = self.monitor.check_sla(self.contract_id)
        assert report.compliance_pct == 100.0

    def test_compliance_pct_partial(self):
        # Freshness fails (stale), completeness ok, violations ok
        old_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        self.monitor.record_delivery(
            self.contract_id,
            timestamp=old_ts,
            record_count=100,
            completeness=0.95,
        )
        report = self.monitor.check_sla(self.contract_id)
        # 2 of 3 checks pass
        assert abs(report.compliance_pct - 66.66666666666667) < 0.01


# ── Integration Tests ────────────────────────────────────────────────


class TestDataContractsIntegration:
    """End-to-end integration tests."""

    def test_full_lifecycle(self):
        """Test complete contract lifecycle: create, validate, update, deprecate."""
        # 1. Create registry and register contract
        registry = ContractRegistry()
        schema = (
            SchemaBuilder()
            .set_version("1.0.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT, constraints={"min_value": 0})
            .build()
        )
        contract = DataContract(
            name="price-feed",
            producer="market-data",
            consumer="trading-engine",
            schema_version=schema,
        )
        registry.register(contract)

        # 2. Validate data
        validator = ContractValidator()
        good_data = {"symbol": "AAPL", "price": 175.0}
        result = validator.validate(good_data, contract)
        assert result.valid is True

        bad_data = {"symbol": "AAPL", "price": -5.0}
        result = validator.validate(bad_data, contract)
        assert result.valid is False

        # 3. Update schema (backward compatible)
        new_schema = (
            SchemaBuilder()
            .set_version("1.1.0")
            .add_field("symbol", FieldType.STRING)
            .add_field("price", FieldType.FLOAT, constraints={"min_value": 0})
            .add_field("source", FieldType.STRING, required=False)
            .build()
        )
        registry.update_schema(contract.contract_id, new_schema)

        # 4. Deprecate
        registry.deprecate(contract.contract_id, "Replaced by v2 API")
        assert contract.status == ContractStatus.DEPRECATED

    def test_sla_monitoring_flow(self):
        """Test SLA monitoring with deliveries and compliance checks."""
        monitor = SLAMonitor()
        sla = SLADefinition(
            freshness_seconds=120.0,
            completeness_threshold=0.90,
            max_violations_per_day=3,
        )
        cid = "price-feed-001"
        monitor.set_sla(cid, sla)

        # Deliver fresh data
        monitor.record_delivery(
            cid,
            timestamp=datetime.now(timezone.utc),
            record_count=500,
            completeness=0.98,
        )

        report = monitor.check_sla(cid)
        assert report.is_compliant is True
        assert report.compliance_pct == 100.0

    def test_schema_evolution_with_validation(self):
        """Test schema evolves and old/new data validates correctly."""
        v1 = (
            SchemaBuilder()
            .set_version("1.0.0")
            .add_field("id", FieldType.INTEGER)
            .add_field("name", FieldType.STRING)
            .build()
        )
        v2 = (
            SchemaBuilder()
            .set_version("2.0.0")
            .add_field("id", FieldType.INTEGER)
            .add_field("name", FieldType.STRING)
            .add_field("email", FieldType.STRING, required=False)
            .build()
        )

        # Check backward compat
        ok, issues = SchemaBuilder.check_compatibility(v1, v2, CompatibilityMode.BACKWARD)
        assert ok is True

        # Old data validates against new schema
        validator = ContractValidator()
        contract = DataContract(schema_version=v2)
        result = validator.validate({"id": 1, "name": "Alice"}, contract)
        assert result.valid is True

        # New data also validates
        result = validator.validate(
            {"id": 2, "name": "Bob", "email": "bob@example.com"}, contract
        )
        assert result.valid is True
