# PRD-129: Data Contracts & Schema Governance

## Overview
Data contract framework for defining, validating, and enforcing schema agreements between data producers and consumers. Ensures data quality at service boundaries with versioned contracts, compatibility checks, and violation tracking.

## Goals
1. Define typed data contracts between producers and consumers
2. Schema evolution with backward/forward compatibility checks
3. Contract validation at runtime with violation tracking
4. Contract registry for discovery and dependency mapping
5. SLA monitoring for data freshness and quality

## Components

### 1. Contract Config (`config.py`)
- ContractStatus enum: DRAFT, ACTIVE, DEPRECATED, RETIRED
- CompatibilityMode enum: BACKWARD, FORWARD, FULL, NONE
- FieldType enum: STRING, INTEGER, FLOAT, BOOLEAN, DATETIME, LIST, MAP, ENUM
- ViolationType enum: MISSING_FIELD, TYPE_MISMATCH, CONSTRAINT_VIOLATION, SCHEMA_DRIFT, FRESHNESS, COMPLETENESS
- ValidationLevel enum: STRICT, WARN, PERMISSIVE
- ContractConfig dataclass (compatibility_mode, validation_level, max_violations_per_hour, alert_on_violation)

### 2. Schema Definition (`schema.py`)
- FieldDefinition dataclass (name, field_type, required, constraints, description, default)
- SchemaVersion dataclass (version, fields, created_at, changelog)
- DataContract dataclass (contract_id, name, producer, consumer, schema_version, status, sla)
- SchemaBuilder class:
  - add_field(name, field_type, required, constraints) -> SchemaBuilder
  - build() -> SchemaVersion
  - from_sample(data) -> SchemaVersion (infer schema from data)
  - diff(v1, v2) -> list of changes
  - check_compatibility(old, new, mode) -> (bool, list of issues)

### 3. Contract Registry (`registry.py`)
- ContractRegistry class:
  - register(contract) -> contract_id
  - update_schema(contract_id, new_version) -> DataContract
  - deprecate(contract_id, reason) -> DataContract
  - get_contract(contract_id) -> DataContract
  - find_by_producer(producer) -> list
  - find_by_consumer(consumer) -> list
  - dependency_graph() -> dict of dependencies
  - list_contracts(status_filter) -> list

### 4. Validator (`validator.py`)
- ValidationResult dataclass (valid, violations, warnings, checked_at)
- ContractViolation dataclass (violation_id, contract_id, violation_type, field, expected, actual, severity)
- ContractValidator class:
  - validate(data, contract) -> ValidationResult
  - validate_field(value, field_def) -> list of violations
  - validate_constraints(value, constraints) -> list of violations
  - validate_freshness(timestamp, sla) -> bool
  - validate_completeness(data, schema) -> float
  - violation_statistics(contract_id, period) -> dict

### 5. SLA Monitor (`sla_monitor.py`)
- SLADefinition dataclass (freshness_seconds, completeness_threshold, max_violations_per_day, uptime_target)
- SLAReport dataclass (contract_id, period, freshness_met, completeness_met, violations_count, compliance_pct)
- SLAMonitor class:
  - set_sla(contract_id, sla) -> None
  - check_sla(contract_id) -> SLAReport
  - record_delivery(contract_id, timestamp, record_count) -> None
  - get_compliance_history(contract_id, days) -> list of SLAReport
  - overall_compliance() -> dict

## Database Tables
- `data_contracts`: Contract definitions with schema
- `contract_violations`: Recorded violations

## Dashboard (4 tabs)
1. Contract Overview — active contracts, compliance rates, dependency graph
2. Schema Browser — contract schemas, field definitions, version history
3. Violations — recent violations, severity breakdown, trends
4. SLA Compliance — freshness metrics, completeness tracking, uptime

## Test Coverage
- Schema builder and compatibility tests
- Contract registry lifecycle tests
- Validator tests (all field types and constraints)
- SLA monitoring tests
- ~80+ tests
