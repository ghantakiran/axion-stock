---
name: data-quality-pipelines
description: >
  Build and orchestrate data quality pipelines for the Axion trading platform.
  Covers OHLCV and fundamental data validation (src/quality/), schema contracts
  with compatibility checking and SLA monitoring (src/data_contracts/), DAG-based
  pipeline orchestration with topological execution and lineage tracking
  (src/pipeline/), and data archival with tiered storage, retention policies,
  and GDPR compliance (src/archival/). Use this skill when validating market
  data, defining producer-consumer contracts, building data pipelines, managing
  data lifecycle, or handling GDPR requests.
metadata:
  author: Axion Platform Team
  version: 1.0.0
---

# Data Quality Pipelines

## When to use this skill

- Validating OHLCV price data or fundamental data for quality issues
- Defining and enforcing data contracts between upstream producers and downstream consumers
- Building DAG-based data pipelines with dependency ordering, parallel execution, and retries
- Tracking data lineage across pipeline nodes (source, transform, sink)
- Monitoring pipeline health, SLA compliance, and data freshness
- Archiving historical data to Parquet with tiered storage (hot/warm/cold/archive)
- Managing retention policies with legal hold support
- Handling GDPR data subject requests (access, export, deletion, rectification)
- Computing storage cost optimization recommendations

## Step-by-step instructions

### 1. Validate price and fundamental data

Use `PriceValidator` to check OHLCV data for zero/negative prices, OHLC consistency,
extreme moves, volume anomalies, and stale data. Use `FundamentalValidator` for
market cap, PE ratio, and data completeness checks.

```python
from src.quality.validators import PriceValidator, FundamentalValidator, ValidationResult
from src.quality.gap_detector import GapDetector, Gap

# Validate OHLCV price data
validator = PriceValidator()
results: list[ValidationResult] = validator.validate_ohlcv(ohlcv_df, ticker="AAPL")

for r in results:
    if not r.passed:
        print(f"[{r.severity}] {r.check_name}: {r.message}")

# Validate fundamental data
fund_validator = FundamentalValidator()
fund_results = fund_validator.validate(fundamentals_df)

# Detect missing trading days
detector = GapDetector()
gaps: list[Gap] = detector.detect_gaps(ohlcv_df, ticker="AAPL", max_gap_days=5)

# Summarize gaps across the universe
all_gaps = {"AAPL": gaps, "MSFT": detector.detect_gaps(msft_df, "MSFT")}
summary_df = detector.summarize_gaps(all_gaps)
```

### 2. Define and register data contracts

Use `SchemaBuilder` to construct versioned schemas, `DataContract` to formalize
producer-consumer agreements, and `ContractRegistry` for lifecycle management.

```python
from src.data_contracts import (
    SchemaBuilder, FieldType, FieldDefinition, SchemaVersion,
    DataContract, ContractRegistry, ContractConfig,
    CompatibilityMode, ContractStatus,
)

# Build a schema with the fluent API
schema = (
    SchemaBuilder()
    .set_version("1.0.0")
    .set_changelog("Initial OHLCV contract")
    .add_field("symbol", FieldType.STRING, required=True, constraints={"min_length": 1})
    .add_field("close", FieldType.FLOAT, required=True, constraints={"min_value": 0.0})
    .add_field("volume", FieldType.INTEGER, required=True, constraints={"min_value": 0})
    .add_field("is_adjusted", FieldType.BOOLEAN, required=False)
    .build()
)

# Or infer schema from a sample record
sample = {"symbol": "AAPL", "close": 185.50, "volume": 55000000}
inferred_schema = SchemaBuilder.from_sample(sample, version="1.0.0")

# Create a contract
contract = DataContract(
    name="ohlcv_daily",
    producer="polygon_ingest",
    consumer="factor_engine",
    schema_version=schema,
    description="Daily OHLCV bars from Polygon",
    tags=["market_data", "daily"],
)

# Register in the registry with compatibility checking
config = ContractConfig(compatibility_mode=CompatibilityMode.BACKWARD)
registry = ContractRegistry(config=config)
contract_id = registry.register(contract)

# Update schema (new optional fields are backward-compatible)
v2 = SchemaBuilder().set_version("2.0.0").add_field("symbol", FieldType.STRING).add_field(
    "close", FieldType.FLOAT).add_field("vwap", FieldType.FLOAT, required=False).build()
registry.update_schema(contract_id, v2, changelog="Added optional vwap field")

# Query contracts
producer_contracts = registry.find_by_producer("polygon_ingest")
consumer_contracts = registry.find_by_consumer("factor_engine")
tagged = registry.find_by_tag("market_data")
dep_graph = registry.dependency_graph()  # producer -> [consumers]

# Lifecycle transitions
registry.deprecate(contract_id, reason="Migrating to v3 schema")
registry.retire(contract_id)
```

### 3. Validate data against contracts

Use `ContractValidator` for field-level type checking, constraint enforcement,
freshness monitoring, and completeness scoring.

```python
from src.data_contracts import (
    ContractValidator, ValidationLevel, ValidationResult,
    ContractViolation, ViolationType,
)

validator = ContractValidator(validation_level=ValidationLevel.STRICT)

# Validate a single record
record = {"symbol": "AAPL", "open": 182.0, "high": 186.5,
          "low": 181.2, "close": 185.5, "volume": 55000000}
result: ValidationResult = validator.validate(record, contract)

print(f"Valid: {result.valid}")
print(f"Completeness: {result.completeness:.2%}")
print(f"Violations: {result.violation_count}")
for v in result.violations:
    print(f"  [{v.violation_type.value}] {v.field_name}: {v.message}")

# Validate a batch of records
batch_result = validator.validate_batch(records_list, contract)

# Check data freshness against SLA
from datetime import datetime, timezone
is_fresh = validator.validate_freshness(
    timestamp=datetime.now(timezone.utc),
    sla_seconds=300.0,  # 5-minute SLA
)

# Get violation statistics
stats = validator.violation_statistics(contract_id=contract_id, period_hours=24)
# Returns: {"total": N, "by_type": {...}, "by_field": {...}}
```

### 4. Monitor contract SLAs

Use `SLAMonitor` to track delivery freshness, completeness, and violation limits.

```python
from src.data_contracts import SLAMonitor, SLADefinition, SLAReport, DeliveryRecord

monitor = SLAMonitor()

# Set SLA thresholds
sla = SLADefinition(
    freshness_seconds=300.0,        # Data must arrive within 5 minutes
    completeness_threshold=0.95,    # 95% field completeness required
    max_violations_per_day=10,      # Max 10 violations per 24h
    uptime_target=0.999,            # 99.9% uptime target
)
monitor.set_sla(contract_id, sla)

# Record data deliveries
delivery: DeliveryRecord = monitor.record_delivery(
    contract_id=contract_id,
    record_count=5000,
    completeness=0.98,
)

# Check SLA compliance
report: SLAReport = monitor.check_sla(contract_id, period_hours=24)
print(f"Compliant: {report.is_compliant}")
print(f"Freshness met: {report.freshness_met}")
print(f"Completeness met: {report.completeness_met}")
print(f"Violations within limit: {report.violations_within_limit}")

# Get overall compliance across all contracts
overall = monitor.overall_compliance()
# Returns: {"total_contracts": N, "compliant": N, "compliance_rate": 95.0, ...}

# Historical compliance
history = monitor.get_compliance_history(contract_id, days=7)
```

### 5. Build and execute data pipelines

Use `Pipeline` to define DAG-based workflows, `PipelineEngine` to execute them
with parallel batching, retries, and timeouts.

```python
from src.pipeline import (
    Pipeline, PipelineNode, PipelineRun, PipelineEngine,
    PipelineConfig, PipelineStatus, NodeStatus, ExecutionResult,
)

# Define a pipeline
pipeline = Pipeline(
    pipeline_id="daily_factors",
    name="Daily Factor Pipeline",
    description="Ingest data, compute factors, store results",
)

# Add nodes with dependencies
pipeline.add_node(PipelineNode(
    node_id="ingest",
    name="Data Ingestion",
    func=ingest_ohlcv,
    timeout_seconds=120,
    retries=3,
))
pipeline.add_node(PipelineNode(
    node_id="validate",
    name="Quality Validation",
    func=run_validation,
    dependencies=["ingest"],
    timeout_seconds=60,
))
pipeline.add_node(PipelineNode(
    node_id="factors",
    name="Factor Computation",
    func=compute_factors,
    dependencies=["validate"],
    timeout_seconds=300,
))
pipeline.add_node(PipelineNode(
    node_id="store",
    name="Store Results",
    func=store_to_db,
    dependencies=["factors"],
))

# Validate the pipeline DAG (checks for missing deps and cycles)
errors = pipeline.validate()

# Get execution order (topological sort with parallel batches)
levels = pipeline.get_execution_order()
# levels = [["ingest"], ["validate"], ["factors"], ["store"]]

# Execute with engine
config = PipelineConfig(max_parallel_nodes=4, default_retries=3)
engine = PipelineEngine(config=config)
run: PipelineRun = engine.execute(pipeline)

print(f"Status: {run.status.value}")  # success, failed, cancelled
for node_id, node in run.nodes.items():
    print(f"  {node_id}: {node.status.value}")

# Cancel a running pipeline
engine.cancel_run(run.run_id)
```

### 6. Track data lineage

Use `LineageGraph` to model data flow, trace upstream origins, and analyze
downstream impact of changes.

```python
from src.pipeline import LineageGraph, LineageNode, LineageEdge

graph = LineageGraph()

# Define lineage nodes
graph.add_node(LineageNode(node_id="polygon", node_type="source", name="Polygon API"))
graph.add_node(LineageNode(node_id="clean", node_type="transform", name="Data Cleaner"))
graph.add_node(LineageNode(node_id="factors", node_type="transform", name="Factor Engine"))
graph.add_node(LineageNode(node_id="db", node_type="sink", name="PostgreSQL"))

# Define edges
graph.add_edge(LineageEdge(source_id="polygon", target_id="clean"))
graph.add_edge(LineageEdge(source_id="clean", target_id="factors"))
graph.add_edge(LineageEdge(source_id="factors", target_id="db"))

# Trace lineage
upstream = graph.get_upstream("factors")       # ["clean"]
full_lineage = graph.get_lineage("db")         # ["clean", "factors", "polygon"]
downstream = graph.get_downstream("polygon")    # ["clean"]
impact = graph.get_impact("polygon")            # ["clean", "db", "factors"]

# Find roots (sources) and leaves (sinks)
roots = graph.get_roots()   # ["polygon"]
leaves = graph.get_leaves() # ["db"]

# Export for visualization
lineage_dict = graph.to_dict()
```

### 7. Monitor pipeline health and SLAs

Use `PipelineMonitor` for metrics tracking, SLA checks, and freshness monitoring.

```python
from src.pipeline import PipelineMonitor, PipelineMetrics, SLAConfig, SLAResult

monitor = PipelineMonitor()

# Record completed runs
monitor.record_run("daily_factors", run)

# Get pipeline metrics
metrics: PipelineMetrics = monitor.get_metrics("daily_factors")
print(f"Success rate: {metrics.success_rate:.1%}")
print(f"Avg duration: {metrics.avg_duration_ms:.0f}ms")

# Set and check SLAs
monitor.set_sla("daily_factors", SLAConfig(
    max_duration_seconds=600.0,
    max_failure_rate=0.1,
))
sla_result: SLAResult = monitor.check_sla("daily_factors")

# Track data freshness
monitor.add_freshness_check("polygon_prices", max_staleness_seconds=3600)
monitor.update_freshness("polygon_prices")
stale = monitor.get_stale_sources()  # list of stale source names

# Health score (0.0-1.0): 70% success rate + 30% SLA compliance
health = monitor.get_health_score("daily_factors")
```

### 8. Archive data and manage retention

Use `ArchivalEngine` for archival jobs, `RetentionManager` for tiered storage
policies, and `DataLifecycleManager` for cost tracking and optimization.

```python
from datetime import datetime
from src.archival import (
    ArchivalEngine, ArchivalJob, ArchivalConfig, ArchivalFormat,
    RetentionManager, RetentionPolicy, StorageTier,
    DataLifecycleManager, TierStats,
)

# Create and execute archival jobs
engine = ArchivalEngine(ArchivalConfig(default_format=ArchivalFormat.PARQUET))
job = engine.create_job(
    table_name="trade_executions",
    start=datetime(2024, 1, 1),
    end=datetime(2024, 6, 30),
)
completed_job: ArchivalJob = engine.execute_job(job.job_id)
print(f"Archived {completed_job.records_archived} records to {completed_job.storage_path}")

# Restore from archive
restore_info = engine.restore_from_archive(job.job_id)

# Define retention policies
retention = RetentionManager()
retention.add_policy(
    table_name="trade_executions",
    hot_days=90,
    warm_days=365,
    cold_days=2555,
    delete_after=3650,  # 10 years
    description="Trade execution retention",
)

# Evaluate data tier
result = retention.evaluate_table("trade_executions", data_age_days=180)
# {"current_tier": "warm", "action_needed": "none", "next_transition": {...}}

# Legal holds
retention.set_legal_hold("trade_executions", reason="SEC investigation")
retention.release_legal_hold("trade_executions")

# Lifecycle cost management
lifecycle = DataLifecycleManager()
lifecycle.record_tier_stats(StorageTier.HOT, records=1_000_000, bytes_used=5_000_000_000, tables=10)
lifecycle.record_tier_stats(StorageTier.WARM, records=5_000_000, bytes_used=20_000_000_000, tables=8)

total_cost = lifecycle.get_total_cost()
cost_breakdown = lifecycle.get_cost_by_tier()
recommendations = lifecycle.get_optimization_recommendations()
summary = lifecycle.get_storage_summary()
```

### 9. Handle GDPR requests

Use `GDPRManager` for data subject access, export, deletion, and rectification
requests with full audit trail.

```python
from src.archival import GDPRManager, GDPRRequest, GDPRRequestType, GDPRRequestStatus

gdpr = GDPRManager()

# Submit a deletion request
request: GDPRRequest = gdpr.submit_request(
    user_id="user_12345",
    request_type=GDPRRequestType.DELETION,
    notes="User requested full data deletion",
)

# Process the request
completed: GDPRRequest = gdpr.process_request(request.request_id)
print(f"Status: {completed.status.value}")
print(f"Records affected: {completed.records_affected}")
print(f"Audit proof: {completed.audit_proof}")

# Generate a data export for a user
export = gdpr.generate_export(user_id="user_12345")

# Get compliance report
compliance = gdpr.generate_compliance_report()

# Audit trail
deletion_log = gdpr.get_deletion_log(user_id="user_12345")
```

## Key classes and methods

| Module | Class | Key Methods | Description |
|--------|-------|-------------|-------------|
| `src.quality.validators` | `PriceValidator` | `validate_ohlcv(df, ticker)` | OHLCV quality checks: zero prices, OHLC consistency, extreme moves, volume anomalies, stale data |
| `src.quality.validators` | `FundamentalValidator` | `validate(df)` | Fundamental data checks: market cap, PE sanity, completeness, coverage |
| `src.quality.validators` | `ValidationResult` | `.passed`, `.severity`, `.message` | Result of a single validation check |
| `src.quality.gap_detector` | `GapDetector` | `detect_gaps(df, ticker)`, `summarize_gaps(all_gaps)` | Missing trading day detection with holiday awareness |
| `src.data_contracts.schema` | `SchemaBuilder` | `add_field()`, `build()`, `from_sample()`, `diff()`, `check_compatibility()` | Fluent schema construction, inference, diffing, and compatibility |
| `src.data_contracts.schema` | `DataContract` | `.contract_id`, `.schema_version`, `.version_history` | Producer-consumer agreement with versioned schema |
| `src.data_contracts.registry` | `ContractRegistry` | `register()`, `update_schema()`, `deprecate()`, `retire()`, `find_by_producer()`, `dependency_graph()` | Contract lifecycle and discovery |
| `src.data_contracts.validator` | `ContractValidator` | `validate()`, `validate_batch()`, `validate_freshness()`, `validate_completeness()`, `violation_statistics()` | Field-level type/constraint checking with violation tracking |
| `src.data_contracts.sla_monitor` | `SLAMonitor` | `set_sla()`, `record_delivery()`, `check_sla()`, `overall_compliance()` | SLA compliance monitoring for freshness, completeness, violations |
| `src.pipeline.definition` | `Pipeline` | `add_node()`, `validate()`, `get_execution_order()`, `create_run()` | DAG pipeline with topological sort (Kahn's algorithm) |
| `src.pipeline.definition` | `PipelineNode` | `.node_id`, `.func`, `.dependencies`, `.retries` | Single task in the pipeline DAG |
| `src.pipeline.engine` | `PipelineEngine` | `execute(pipeline)`, `cancel_run()`, `get_run()` | Parallel execution with retry, timeout, and failure propagation |
| `src.pipeline.lineage` | `LineageGraph` | `add_node()`, `add_edge()`, `get_lineage()`, `get_impact()`, `get_roots()` | Data lineage tracking with BFS traversal |
| `src.pipeline.monitoring` | `PipelineMonitor` | `record_run()`, `check_sla()`, `get_stale_sources()`, `get_health_score()` | Pipeline metrics, SLA monitoring, and freshness checks |
| `src.archival.engine` | `ArchivalEngine` | `create_job()`, `execute_job()`, `restore_from_archive()`, `get_storage_stats()` | Archival job creation and execution (Parquet/CSV/JSON) |
| `src.archival.retention` | `RetentionManager` | `add_policy()`, `evaluate_table()`, `set_legal_hold()`, `get_expiring_data()` | Tiered retention policies with legal hold support |
| `src.archival.gdpr` | `GDPRManager` | `submit_request()`, `process_request()`, `generate_export()`, `generate_compliance_report()` | GDPR request handling with audit proof |
| `src.archival.lifecycle` | `DataLifecycleManager` | `record_tier_stats()`, `transition_data()`, `get_total_cost()`, `get_optimization_recommendations()` | Storage tier cost management and optimization |

## Common patterns

### Schema evolution with backward compatibility

Use `CompatibilityMode.BACKWARD` when evolving contracts. New optional fields are safe; new required fields or type changes are rejected.

```python
compatible, issues = SchemaBuilder.check_compatibility(
    old=v1_schema, new=v2_schema, mode=CompatibilityMode.BACKWARD,
)
```

### Pipeline with parallel fan-out

Nodes at the same DAG level execute in parallel. Use `max_parallel_nodes` in `PipelineConfig` to limit concurrency.

```python
pipeline.add_node(PipelineNode(node_id="A", name="A", func=fn_a))
pipeline.add_node(PipelineNode(node_id="B", name="B", func=fn_b))
pipeline.add_node(PipelineNode(node_id="C", name="C", func=fn_c, dependencies=["A", "B"]))
# Execution order: [["A", "B"], ["C"]]
```

### Connecting quality validation to contracts

Combine `PriceValidator` with `ContractValidator` for a unified quality gate.

```python
def quality_gate():
    pv = PriceValidator()
    critical = [r for r in pv.validate_ohlcv(df, "AAPL") if not r.passed and r.severity == "critical"]
    if critical:
        raise ValueError(f"Critical quality failures: {critical}")
    cv = ContractValidator(validation_level=ValidationLevel.STRICT)
    for record in records:
        result = cv.validate(record, contract)
        if not result.valid:
            monitor.record_violation(contract.contract_id)
```

### Tiered storage cost tracking

Record tier transitions and use automated recommendations to optimize costs.

```python
lifecycle = DataLifecycleManager()
lifecycle.transition_data("trade_executions", StorageTier.HOT, StorageTier.WARM, 500_000, 2_500_000_000)
print(f"Monthly cost: ${lifecycle.get_total_cost():.2f}")
for rec in lifecycle.get_optimization_recommendations():
    print(f"[{rec['priority']}] {rec['recommendation']} (saves ${rec['savings']:.2f}/mo)")
```
