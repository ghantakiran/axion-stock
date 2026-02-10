---
name: data-platform-mlops
description: >
  Axion data governance, MLOps, and platform services. 12 modules: feature store (catalog,
  offline/online stores, lineage), model registry (versioning, A/B tests, serving), pipeline
  orchestration (DAG engine, scheduling, SLA), event bus (pub/sub, event store, schema registry),
  data contracts (schema builder, compatibility, SLA monitor), audit trail (SHA-256 hash chain),
  config service (feature flags, secrets, env resolver), secrets vault (encryption, rotation,
  access control), billing (metering, invoices, cost analytics), multi-tenancy (RLS, RBAC,
  isolation middleware), workflow engine (state machine, approvals), trade reconciliation
  (exact/fuzzy matching, T+2 settlement). Use when building data pipelines, ML model lifecycle,
  event-driven architectures, schema governance, audit compliance, tenant isolation, approval
  workflows, billing, or trade settlement.
metadata:
  author: axion-platform
  version: "1.0"
---

# Data Platform & MLOps

## When to Use This Skill

- Registering, discovering, or serving ML features (offline batch or online cache)
- Managing ML model versions, stage promotions, A/B tests, or experiment tracking
- Building or debugging DAG-based data pipelines with scheduling and SLA enforcement
- Publishing or consuming events via the platform event bus
- Defining, versioning, or validating data contracts between producers and consumers
- Recording or querying immutable audit events with hash-chain integrity
- Managing configuration, feature flags, or environment-specific settings
- Storing, rotating, or retrieving encrypted secrets and API credentials
- Implementing usage metering, billing, invoicing, or cost forecasting
- Enforcing multi-tenant data isolation, RLS, or RBAC policies
- Creating approval workflows or multi-step state machine pipelines
- Reconciling internal trades against broker confirmations

## Feature Store

**Module**: `src/feature_store/` (PRD-123)

Core classes from `src.feature_store`:

| Class | Source file | Purpose |
|---|---|---|
| `FeatureDefinition` | `catalog.py` | Metadata dataclass: name, type, entity, SLA, tags, dependencies |
| `FeatureCatalog` | `catalog.py` | Central registry: `register()`, `get()`, `get_by_name()`, `search()` |
| `FeatureValue` | `offline.py` | Single value record with `feature_id`, `entity_id`, `as_of_date` |
| `OfflineFeatureStore` | `offline.py` | Batch store: `store()`, `store_batch()`, `get_latest()`, point-in-time joins |
| `CacheEntry` | `online.py` | TTL-aware cache entry for real-time serving |
| `OnlineFeatureStore` | `online.py` | Low-latency cache: `get()`, `put()`, `get_many()` |
| `LineageNode` / `LineageEdge` | `lineage.py` | DAG nodes and edges for feature dependency tracking |
| `FeatureLineage` | `lineage.py` | Lineage graph: `add_node()`, `add_edge()`, `get_upstream()`, `get_downstream()` |

Config enums: `FeatureType`, `FeatureStatus`, `EntityType`, `ComputeMode`, `FeatureStoreConfig`.

```python
from src.feature_store import FeatureCatalog, FeatureDefinition, FeatureType, EntityType

catalog = FeatureCatalog()
feat = FeatureDefinition(
    name="rsi_14d",
    feature_type=FeatureType.NUMERIC,
    entity_type=EntityType.STOCK,
    owner="quant-team",
    freshness_sla_minutes=15,
)
catalog.register(feat)
```

## Model Registry & Serving

**Module**: `src/model_registry/` (PRD-113)

Core classes from `src.model_registry`:

| Class | Source file | Purpose |
|---|---|---|
| `ModelVersion` | `registry.py` | Dataclass: `model_name`, `version`, `stage`, `framework`, `metrics`, `hyperparameters` |
| `ModelRegistry` | `registry.py` | Thread-safe registry: `register()`, `get_version()`, `list_versions()`, `delete()` |
| `StageTransition` | `versioning.py` | Records stage changes with timestamp and reason |
| `ModelVersionManager` | `versioning.py` | Stage workflow: draft -> staging -> production -> archived |
| `ABExperiment` | `ab_testing.py` | A/B test definition with control/treatment split |
| `ABTestManager` | `ab_testing.py` | Manages A/B experiments: `create()`, `record_result()`, `get_winner()` |
| `ExperimentRun` | `experiments.py` | Single experiment run with metrics and params |
| `ExperimentTracker` | `experiments.py` | Track experiments: `start_run()`, `log_metric()`, `end_run()` |
| `ModelServer` | `serving.py` | Model serving: `load_model()`, `predict()`, `health_check()` |

Config enums: `ModelStage`, `ModelFramework`, `ExperimentStatus`, `ModelRegistryConfig`.

```python
from src.model_registry import ModelRegistry, ModelFramework

registry = ModelRegistry()
version = registry.register(
    model_name="ema_signal_classifier",
    version="1.2.0",
    framework=ModelFramework.CUSTOM,
    metrics={"accuracy": 0.87, "sharpe": 1.42},
)
```

## Data Pipeline Orchestration

**Module**: `src/pipeline/` (PRD-112)

Core classes from `src.pipeline`:

| Class | Source file | Purpose |
|---|---|---|
| `PipelineNode` | `definition.py` | DAG node with `node_id`, `function`, `dependencies`, `timeout_seconds` |
| `Pipeline` | `definition.py` | DAG container: `add_node()`, `validate()`, `get_execution_order()` (topological sort) |
| `PipelineRun` | `definition.py` | Execution record with status and timing |
| `ExecutionResult` | `engine.py` | Per-node result: `status`, `duration_ms`, `error`, `retries_used` |
| `PipelineEngine` | `engine.py` | Executes pipelines respecting DAG order with thread pool parallelism |
| `LineageNode` / `LineageEdge` | `lineage.py` | Data lineage tracking nodes and edges |
| `LineageGraph` | `lineage.py` | Full lineage DAG: `add_node()`, `add_edge()`, `get_upstream()` |
| `Schedule` | `scheduler.py` | Cron or interval schedule definition |
| `PipelineScheduler` | `scheduler.py` | Schedule management: `add_schedule()`, `get_due_pipelines()` |
| `PipelineMetrics` / `FreshnessCheck` | `monitoring.py` | Pipeline health metrics and data freshness checks |
| `SLAResult` | `monitoring.py` | SLA compliance result |
| `PipelineMonitor` | `monitoring.py` | Monitors pipelines: freshness, SLA breaches, alerting |

Config enums: `PipelineStatus`, `NodeStatus`, `ScheduleType`, `PipelineConfig`, `SLAConfig`.

```python
from src.pipeline import Pipeline, PipelineNode, PipelineEngine

pipeline = Pipeline(pipeline_id="daily_features", name="Daily Feature Pipeline")
pipeline.add_node(PipelineNode(node_id="fetch", function=fetch_data))
pipeline.add_node(PipelineNode(node_id="compute", function=compute_features, dependencies=["fetch"]))

engine = PipelineEngine()
run = engine.execute(pipeline)
```

## Event Bus & Messaging

**Module**: `src/event_bus/` (PRD-121)

Core classes from `src.event_bus`:

| Class | Source file | Purpose |
|---|---|---|
| `EventEnvelope` | `schema.py` | Immutable event wrapper: `event_id`, `topic`, `payload`, `timestamp` |
| `SchemaDefinition` | `schema.py` | Event schema with required/optional fields |
| `SchemaRegistry` | `schema.py` | Schema versioning: `register()`, `validate()`, `get_schema()` |
| `Subscriber` | `bus.py` | Subscriber: `topic_pattern` (glob), `handler`, `filter_fn` |
| `DeliveryRecord` | `bus.py` | Delivery attempt record with status and retry count |
| `EventBus` | `bus.py` | Central pub/sub: `subscribe()`, `publish()`, `unsubscribe()` |
| `EventRecord` / `Snapshot` | `store.py` | Immutable event storage with snapshots |
| `EventStore` | `store.py` | Append-only store: `append()`, `get_events()`, `create_snapshot()` |
| `ConsumerCheckpoint` | `consumer.py` | Consumer offset tracking |
| `ConsumerGroup` | `consumer.py` | Grouped consumption with checkpointing |
| `AsyncConsumer` | `consumer.py` | Async event consumer |

Pre-built schemas: `order_executed_event`, `alert_triggered_event`, `model_updated_event`, `compliance_violation_event`.

Config enums: `EventPriority`, `DeliveryStatus`, `SubscriberState`, `EventCategory`, `EventBusConfig`.

```python
from src.event_bus import EventBus, EventEnvelope

bus = EventBus()
bus.subscribe(name="risk_monitor", topic_pattern="trades.*", handler=on_trade)
records = bus.publish("trades.executed", EventEnvelope(
    topic="trades.executed",
    payload={"symbol": "AAPL", "qty": 100},
))
```

## Data Contracts & SLA

**Module**: `src/data_contracts/` (PRD-129)

Core classes from `src.data_contracts`:

| Class | Source file | Purpose |
|---|---|---|
| `FieldDefinition` | `schema.py` | Field spec: `name`, `field_type`, `required`, `constraints` |
| `SchemaVersion` | `schema.py` | Versioned schema: `get_field()`, `field_names()`, `required_fields()` |
| `DataContract` | `schema.py` | Contract between producer and consumer with SLA and version history |
| `SchemaBuilder` | `schema.py` | Fluent builder: `set_version()`, `add_field()`, `set_changelog()`, `build()` |
| `ContractRegistry` | `registry.py` | Registry: `register()`, `get()`, `search()`, `list_contracts()` |
| `ContractValidator` | `validator.py` | Validates data against contracts: `validate()` |
| `ContractViolation` / `ValidationResult` | `validator.py` | Validation outcome dataclasses |
| `SLADefinition` / `SLAReport` | `sla_monitor.py` | SLA spec and compliance report |
| `SLAMonitor` | `sla_monitor.py` | Monitors SLA compliance: freshness, completeness, latency |

Config enums: `ContractStatus`, `CompatibilityMode`, `FieldType`, `ViolationType`, `ValidationLevel`, `ContractConfig`.

```python
from src.data_contracts import SchemaBuilder, FieldType, ContractRegistry, DataContract

schema = (
    SchemaBuilder()
    .set_version("2.0.0")
    .add_field("symbol", FieldType.STRING, required=True)
    .add_field("price", FieldType.FLOAT, required=True)
    .set_changelog("Added price field")
    .build()
)
registry = ContractRegistry()
contract = DataContract(name="market_data_feed", producer="data_team", consumer="quant_engine", schema_version=schema)
registry.register(contract)
```

## Audit Trail

**Module**: `src/audit/` (PRD-109)

Core classes from `src.audit`:

| Class | Source file | Purpose |
|---|---|---|
| `Actor` | `events.py` | Who performed the action: `user_id`, `service`, `ip_address` |
| `Resource` | `events.py` | What was acted upon: `resource_type`, `resource_id` |
| `AuditEvent` | `events.py` | Immutable event with SHA-256 `hash` and `previous_hash` chain link |
| `AuditRecorder` | `recorder.py` | Singleton, thread-safe recorder: `record()`, `flush()`, `verify_chain()` |
| `AuditQuery` | `query.py` | Query builder: `by_actor()`, `by_action()`, `by_category()`, `between()`, `execute()` |
| `AuditExporter` | `export.py` | Export to JSON/CSV: `export_json()`, `export_csv()` |

Config: `AuditConfig`, `EventCategory`, `EventOutcome`, `RetentionPolicy`.

```python
from src.audit import AuditRecorder, Actor, Resource, EventCategory

recorder = AuditRecorder()
event = recorder.record(
    action="order.create",
    actor=Actor(user_id="trader-1", service="bot_pipeline"),
    resource=Resource(resource_type="order", resource_id="ORD-12345"),
    category=EventCategory.TRADING,
    details={"symbol": "TSLA", "qty": 50},
)
```

## Configuration & Feature Flags

**Module**: `src/config_service/` (PRD-111)

Core classes from `src.config_service`:

| Class | Source file | Purpose |
|---|---|---|
| `ConfigEntry` | `config_store.py` | Key-value config entry with namespace, type, and metadata |
| `ConfigStore` | `config_store.py` | Central store: `set()`, `get()`, `list_namespace()`, `delete()` |
| `FeatureFlag` | `feature_flags.py` | Flag definition: `boolean`, `percentage`, or `user_list` type |
| `FeatureFlagService` | `feature_flags.py` | Flag evaluation: `create_flag()`, `is_enabled()`, `evaluate()` |
| `FlagContext` | `feature_flags.py` | Evaluation context: `user_id`, `workspace_id`, attributes |
| `Secret` | `secrets.py` | Encrypted secret entry |
| `SecretsManager` | `secrets.py` | Secret lifecycle: `store()`, `retrieve()`, `rotate()` |
| `EnvironmentConfig` | `environments.py` | Per-environment configuration |
| `EnvironmentResolver` | `environments.py` | Resolves config values per environment (dev/staging/prod) |
| `ConfigValidator` | `validators.py` | Validates config entries against `ValidationRule` definitions |

Config enums: `ConfigNamespace`, `ConfigValueType`, `Environment`, `FeatureFlagType`, `ServiceConfig`.

```python
from src.config_service import FeatureFlagService, FeatureFlag, FlagContext, FeatureFlagType

flags = FeatureFlagService()
flags.create_flag(FeatureFlag(
    name="enable_options_scalping",
    flag_type=FeatureFlagType.PERCENTAGE,
    percentage=25,  # 25% rollout
))
ctx = FlagContext(user_id="user-42", workspace_id="ws-1")
if flags.is_enabled("enable_options_scalping", ctx):
    run_scalping_strategy()
```

## Secrets Vault

**Module**: `src/secrets_vault/` (PRD-124)

Core classes from `src.secrets_vault`:

| Class | Source file | Purpose |
|---|---|---|
| `SecretEntry` | `vault.py` | Versioned secret: `key_path`, `encrypted_value`, `secret_type`, `expires_at` |
| `SecretsVault` | `vault.py` | Encrypted store: `store_secret()`, `get_secret()`, `delete_secret()`, `list_secrets()` |
| `RotationPolicy` / `RotationResult` | `rotation.py` | Rotation schedule and outcome |
| `CredentialRotation` | `rotation.py` | Auto-rotation: `register_policy()`, `check_rotations()`, `rotate()` |
| `AccessPolicy` / `AccessAuditEntry` | `access.py` | Glob-pattern access rules and audit log |
| `AccessControl` | `access.py` | Enforces access: `add_policy()`, `check_access()`, `get_audit_log()` |
| `CacheEntry` | `client.py` | TTL-aware cached secret |
| `SecretsClient` | `client.py` | SDK client with caching: `get()`, `set()`, `invalidate_cache()` |

Config enums: `SecretType`, `RotationStrategy`, `AccessAction`, `VaultConfig`.

```python
from src.secrets_vault import SecretsVault, SecretType

vault = SecretsVault(encryption_key="my-prod-key")
vault.store_secret(key_path="brokers/alpaca/api_key", value="AKXYZ...", secret_type=SecretType.API_KEY)
secret = vault.get_secret("brokers/alpaca/api_key")
```

## Billing & Usage Metering

**Module**: `src/billing/` (PRD-125)

Core classes from `src.billing`:

| Class | Source file | Purpose |
|---|---|---|
| `MeterDefinition` | `meter.py` | Meter spec: `meter_id`, `meter_type`, unit, pricing |
| `UsageRecord` | `meter.py` | Single usage event: workspace, meter, quantity, cost |
| `UsageMeter` | `meter.py` | Track usage: `record_usage()`, `get_workspace_usage()`, `get_meter()` |
| `BillLineItem` / `Bill` | `engine.py` | Itemized bill with line items |
| `BillingEngine` | `engine.py` | Generates bills: tiers, discounts, credits |
| `Invoice` | `invoices.py` | Invoice with status lifecycle |
| `InvoiceManager` | `invoices.py` | Invoice CRUD: `create_invoice()`, `send()`, `mark_paid()` |
| `CostBreakdown` | `analytics.py` | Per-workspace cost breakdown by meter type |
| `CostAnalytics` | `analytics.py` | Analysis: `get_workspace_costs()`, trend detection, optimization recs |

Config enums: `MeterType`, `InvoiceStatus`, `BillingPeriod`, `PricingTier`, `BillingConfig`.

```python
from src.billing import UsageMeter, MeterDefinition, MeterType

meter = UsageMeter()
meter.register_meter(MeterDefinition(meter_id="api_calls", meter_type=MeterType.COUNTER))
meter.record_usage(workspace_id="ws-1", meter_id="api_calls", quantity=1)
```

## Multi-Tenancy & Isolation

**Module**: `src/multi_tenancy/` (PRD-122)

Core classes from `src.multi_tenancy`:

| Class | Source file | Purpose |
|---|---|---|
| `TenantContext` | `context.py` | Request context: `workspace_id`, `user_id`, `roles`, `permissions` |
| `TenantContextManager` | `context.py` | Thread-local context: `set_context()`, `get_context()`, `clear()` |
| `QueryFilter` | `filters.py` | Injects `workspace_id` WHERE clause into queries |
| `QueryAuditEntry` | `filters.py` | Logs filtered query audit entries |
| `DataIsolationMiddleware` | `middleware.py` | FastAPI middleware: extracts tenant from headers, sets context |
| `RateLimitState` / `MiddlewareAuditEntry` | `middleware.py` | Per-tenant rate limiting and audit |
| `Policy` / `PolicyEvaluation` | `policies.py` | RBAC policy definition and evaluation result |
| `PolicyEngine` | `policies.py` | Evaluates policies: `add_policy()`, `evaluate()`, `check_access()` |

Config: `AccessLevel`, `ResourceType`, `PolicyAction`, `TenancyConfig`, `ROLE_HIERARCHY`.

Helper: `get_global_context_manager()` returns the singleton `TenantContextManager`.

```python
from src.multi_tenancy import TenantContext, get_global_context_manager

ctx_mgr = get_global_context_manager()
ctx = TenantContext(workspace_id="ws-acme", user_id="trader-1", roles=["admin"])
ctx_mgr.set_context(ctx)
# All subsequent queries automatically filtered by workspace_id
```

## Workflow Engine

**Module**: `src/workflow/` (PRD-127)

Core classes from `src.workflow`:

| Class | Source file | Purpose |
|---|---|---|
| `State` / `Transition` | `state_machine.py` | State and transition definitions |
| `TransitionRecord` | `state_machine.py` | Audit log of state transitions |
| `StateMachine` | `state_machine.py` | FSM: `add_state()`, `add_transition()`, `trigger()`, `current_state` |
| `ApprovalRequest` / `ApprovalDecision` | `approvals.py` | Approval request and decision records |
| `ApprovalManager` | `approvals.py` | Multi-level approvals: single, dual, committee |
| `PipelineStep` / `PipelineResult` | `pipeline.py` | Step definition and execution result |
| `PipelineRunner` | `pipeline.py` | Executes sequential workflow steps |
| `WorkflowTemplate` | `templates.py` | Pre-built workflow template definition |
| `TemplateRegistry` | `templates.py` | Stores and retrieves templates |

Config enums: `WorkflowStatus`, `TaskStatus`, `ApprovalLevel`, `TriggerType`, `WorkflowConfig`.

Four built-in templates available via `TemplateRegistry`.

```python
from src.workflow import StateMachine, State, Transition

sm = StateMachine(machine_id="trade_approval")
sm.add_state(State(name="pending", is_initial=True))
sm.add_state(State(name="approved"))
sm.add_state(State(name="rejected", is_terminal=True))
sm.add_transition(Transition(from_state="pending", to_state="approved", trigger="approve"))
sm.add_transition(Transition(from_state="pending", to_state="rejected", trigger="reject"))
sm.trigger("approve")
```

## Trade Reconciliation

**Module**: `src/reconciliation/` (PRD-126)

Core classes from `src.reconciliation`:

| Class | Source file | Purpose |
|---|---|---|
| `TradeRecord` | `matcher.py` | Trade record: `symbol`, `side`, `quantity`, `price`, `source` |
| `MatchResult` | `matcher.py` | Match outcome: `internal_trade`, `broker_trade`, `status`, `confidence` |
| `MatchingEngine` | `matcher.py` | Two-phase matching (exact then fuzzy): `match_trades()`, `exact_match()`, `fuzzy_match()` |
| `SettlementEvent` | `settlement.py` | Settlement lifecycle event |
| `SettlementTracker` | `settlement.py` | T+2 settlement tracking: `track()`, `get_pending()`, `settle()` |
| `ReconciliationBreak` / `BreakResolution` | `breaks.py` | Break records and resolution actions |
| `BreakManager` | `breaks.py` | Break management: `create_break()`, `resolve()`, `get_open_breaks()` |
| `DailyReconciliation` / `ReconciliationReport` | `reporter.py` | Daily recon summary and full report |
| `ReconciliationReporter` | `reporter.py` | Generates reports: `generate_daily()`, `generate_report()` |

Config enums: `BreakSeverity`, `BreakType`, `MatchStrategy`, `ReconciliationStatus`, `SettlementStatus`, `ToleranceConfig`, `ReconciliationConfig`.

```python
from src.reconciliation import MatchingEngine, TradeRecord
from datetime import datetime, timezone

engine = MatchingEngine()
results = engine.match_trades(
    internal_trades=[TradeRecord(trade_id="T1", symbol="AAPL", side="buy", quantity=100, price=150.0, timestamp=datetime.now(timezone.utc), source="internal")],
    broker_trades=[TradeRecord(trade_id="T1", symbol="AAPL", side="buy", quantity=100, price=150.0, timestamp=datetime.now(timezone.utc), source="alpaca")],
)
```

## Key Classes Reference

| Module | Primary Classes | Import Path |
|---|---|---|
| feature_store | `FeatureCatalog`, `OfflineFeatureStore`, `OnlineFeatureStore`, `FeatureLineage` | `src.feature_store` |
| model_registry | `ModelRegistry`, `ModelVersionManager`, `ABTestManager`, `ExperimentTracker`, `ModelServer` | `src.model_registry` |
| pipeline | `Pipeline`, `PipelineEngine`, `PipelineScheduler`, `PipelineMonitor`, `LineageGraph` | `src.pipeline` |
| event_bus | `EventBus`, `EventStore`, `SchemaRegistry`, `ConsumerGroup`, `AsyncConsumer` | `src.event_bus` |
| data_contracts | `SchemaBuilder`, `ContractRegistry`, `ContractValidator`, `SLAMonitor` | `src.data_contracts` |
| audit | `AuditRecorder`, `AuditQuery`, `AuditExporter` | `src.audit` |
| config_service | `ConfigStore`, `FeatureFlagService`, `SecretsManager`, `EnvironmentResolver`, `ConfigValidator` | `src.config_service` |
| secrets_vault | `SecretsVault`, `CredentialRotation`, `AccessControl`, `SecretsClient` | `src.secrets_vault` |
| billing | `UsageMeter`, `BillingEngine`, `InvoiceManager`, `CostAnalytics` | `src.billing` |
| multi_tenancy | `TenantContext`, `TenantContextManager`, `QueryFilter`, `DataIsolationMiddleware`, `PolicyEngine` | `src.multi_tenancy` |
| workflow | `StateMachine`, `ApprovalManager`, `PipelineRunner`, `TemplateRegistry` | `src.workflow` |
| reconciliation | `MatchingEngine`, `SettlementTracker`, `BreakManager`, `ReconciliationReporter` | `src.reconciliation` |

## Common Patterns

**Thread safety**: `ModelRegistry`, `PipelineEngine`, and `AuditRecorder` use `threading.Lock` internally. `AuditRecorder` provides a singleton via `AuditRecorder.get_instance()`. `TenantContextManager` uses thread-local storage for per-request tenant isolation.

**Configuration convention**: Every module accepts an optional config dataclass, defaulting to sensible values:

```python
engine = PipelineEngine()                                       # default config
engine = PipelineEngine(config=PipelineConfig(max_parallel=8))  # custom config
```

**Event-driven integration**: Modules integrate via the event bus -- publish domain events from any module, consume in others:

```python
from src.event_bus import EventBus, EventEnvelope
from src.audit import AuditRecorder, Actor

bus = EventBus()
recorder = AuditRecorder()

def on_model_promoted(event: EventEnvelope):
    recorder.record(
        action="model.promoted",
        actor=Actor(user_id="ml_pipeline", service="model_registry"),
        details=event.payload,
    )

bus.subscribe(name="audit_logger", topic_pattern="models.*", handler=on_model_promoted)
```
