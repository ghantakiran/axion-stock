---
name: infrastructure-operations
description: >
  Axion platform infrastructure and operations modules covering deployment orchestration
  (rolling/blue-green/canary), application lifecycle with K8s health probes, Prometheus
  observability, performance profiling with query analysis, WebSocket scaling with pub/sub
  and backpressure, backup and disaster recovery, data archival with GDPR compliance,
  resilience patterns (circuit breaker/retry/rate limiter/bulkhead), structured JSON
  logging with request tracing, integration and load testing framework, migration safety
  with AST-based validation, API error handling and sanitization, API gateway with
  sliding-window rate limiting and versioning, and capacity planning with demand forecasting.
  Use when building, configuring, debugging, or extending any infrastructure, operations,
  or platform reliability feature in the Axion trading platform.
metadata:
  author: axion-platform
  version: "1.0"
---

# Infrastructure & Operations

## When to Use This Skill

- Setting up or modifying deployment pipelines (rolling, blue-green, canary)
- Configuring application lifecycle, health probes, or graceful shutdown
- Adding Prometheus metrics, custom counters, or latency tracking
- Profiling slow queries, detecting N+1 patterns, or tuning connection pools
- Scaling WebSocket connections with pub/sub routing and backpressure
- Configuring backup schedules, disaster recovery, or replication monitoring
- Implementing data archival policies or GDPR deletion/export/anonymization
- Adding circuit breakers, retry policies, rate limiters, or bulkhead isolation
- Setting up structured logging, request tracing, or performance timing
- Writing integration tests, load tests, or benchmarks
- Validating Alembic migrations for safety and reversibility
- Handling API errors, input validation, or request sanitization
- Configuring API gateway rate limits, user quotas, or API versioning
- Planning capacity, forecasting demand, or managing auto-scaling rules

## Deployment & Release Management

Source: `src/deployment/` (PRD-120)

```python
from src.deployment import (
    DeploymentOrchestrator, DeploymentConfig, DeploymentStrategy,
    TrafficManager, TrafficSplit, RollbackEngine, RollbackAction,
    DeploymentValidator, ValidationCheck, Deployment,
    DeploymentStatus, ValidationStatus,
)

config = DeploymentConfig(strategy=DeploymentStrategy.CANARY)
orchestrator = DeploymentOrchestrator(config)
deployment = orchestrator.create_deployment(version="v2.1.0", config=config)

traffic_mgr = TrafficManager()
traffic_mgr.set_split(TrafficSplit(canary_percent=10))

validator = DeploymentValidator()
result = validator.run_checks(deployment)
if result.status == ValidationStatus.PASSED:
    orchestrator.promote(deployment)

rollback = RollbackEngine()
rollback.execute(RollbackAction(deployment_id=deployment.id))
```

Strategies: `ROLLING`, `BLUE_GREEN`, `CANARY`. Status tracking via `DeploymentStatus`.

## Application Lifecycle & Health

Source: `src/lifecycle/` (PRD-107)

```python
from src.lifecycle import (
    LifecycleManager, LifecycleEvent, HealthCheckRegistry,
    HealthCheckResult, ProbeResponse, DependencyCheck, ProbeType,
    HookRegistry, Hook, HookResult, SignalHandler,
    AppState, HealthStatus, LifecycleConfig, ShutdownPhase,
)

manager = LifecycleManager(LifecycleConfig())
health = HealthCheckRegistry()
health.register(DependencyCheck(name="postgres", probe_type=ProbeType.READINESS))
response: ProbeResponse = health.check(ProbeType.LIVENESS)

hooks = HookRegistry()
hooks.register(Hook(name="cache_warmup", phase=ShutdownPhase.PRE_SHUTDOWN))

handler = SignalHandler(manager)
handler.install()  # Captures SIGTERM, SIGINT
```

App states: STARTING, RUNNING, STOPPING, STOPPED. Probes: LIVENESS, READINESS, STARTUP.

## Observability & Metrics

Source: `src/observability/` (PRD-103)

```python
from src.observability import (
    MetricsRegistry, Counter, Gauge, Histogram, MetricMeta,
    MetricType, MetricsConfig, ExportFormat, HistogramBuckets,
    TradingMetrics, SystemMetrics,
    PrometheusExporter, create_metrics_router,
    track_latency, count_calls, track_errors,
)

registry = MetricsRegistry()
order_count = registry.counter("orders_total", "Total orders placed")
order_count.increment(labels={"side": "buy"})
trading = TradingMetrics(registry)
system = SystemMetrics(registry)
router = create_metrics_router(registry)  # Mount in FastAPI for /metrics

@track_latency(registry, "order_latency_seconds")
@count_calls(registry, "order_calls_total")
@track_errors(registry, "order_errors_total")
async def place_order(symbol: str, qty: int): ...
```

## Performance Profiling

Source: `src/profiling/` (PRD-117)

```python
from src.profiling import (
    QueryProfiler, QueryFingerprint, PerformanceAnalyzer,
    PerformanceSnapshot, IndexAdvisor, IndexRecommendation,
    ConnectionMonitor, ConnectionStats, LongRunningQuery,
    ProfilingConfig, QuerySeverity, IndexStatus,
)

profiler = QueryProfiler(ProfilingConfig())
profiler.record("SELECT * FROM orders WHERE symbol = ?", duration_ms=12.5)
fingerprint: QueryFingerprint = profiler.get_fingerprint(query_hash)

analyzer = PerformanceAnalyzer(profiler)
snapshot: PerformanceSnapshot = analyzer.analyze()  # Detects N+1 patterns

advisor = IndexAdvisor()
recs: list[IndexRecommendation] = advisor.recommend(profiler)

monitor = ConnectionMonitor()
stats: ConnectionStats = monitor.get_stats()
long: list[LongRunningQuery] = monitor.find_long_running()
```

## WebSocket Scaling

Source: `src/ws_scaling/` (PRD-119)

```python
from src.ws_scaling import (
    ConnectionRegistry, ConnectionInfo, MessageRouter, Message,
    BackpressureHandler, QueueStats, ReconnectionManager,
    ReconnectionSession, MessagePriority, ConnectionState,
    DropStrategy, WSScalingConfig,
)

config = WSScalingConfig()
registry = ConnectionRegistry(config)
registry.register(ConnectionInfo(conn_id="ws-001", user_id="u-42"))

router = MessageRouter(registry)
msg = Message(topic="signals", payload={"symbol": "AAPL"}, priority=MessagePriority.HIGH)
await router.publish(msg)
await router.subscribe(conn_id="ws-001", topic="signals")

bp = BackpressureHandler(config)
stats: QueueStats = bp.get_stats(conn_id="ws-001")
# DropStrategy: DROP_OLDEST, DROP_NEWEST, BLOCK
```

## Backup & Disaster Recovery

Source: `src/backup/` (PRD-116)

```python
from src.backup import (
    BackupEngine, BackupJob, BackupArtifact,
    RecoveryManager, RecoveryPlan, RecoveryResult, RecoveryStep,
    ReplicationMonitor, Replica, ReplicationEvent,
    BackupMonitor, RecoveryDrill, SLAReport,
    BackupType, BackupStatus, BackupConfig,
    StorageBackend, StorageTier, RecoveryStatus, ReplicaStatus,
    DataSource, RetentionPolicy,
)

config = BackupConfig(backup_type=BackupType.INCREMENTAL)
engine = BackupEngine(config)
job: BackupJob = engine.create_backup(source=DataSource.DATABASE)

recovery = RecoveryManager()
plan = recovery.create_plan(target_time="2025-01-15T10:00:00Z")
result: RecoveryResult = recovery.execute(plan)

monitor = BackupMonitor()
report: SLAReport = monitor.generate_sla_report()
drill: RecoveryDrill = monitor.run_drill()
```

Backup types: `FULL`, `INCREMENTAL`, `SNAPSHOT`. Storage backends with tiered retention.

## Data Archival & GDPR

Source: `src/archival/` (PRD-118)

```python
from src.archival import (
    ArchivalEngine, ArchivalJob, RetentionManager, RetentionPolicy,
    GDPRManager, GDPRRequest, DataLifecycleManager, TierStats,
    StorageTier, ArchivalFormat, ArchivalConfig,
    GDPRRequestType, GDPRRequestStatus,
)

engine = ArchivalEngine(ArchivalConfig(format=ArchivalFormat.PARQUET))
job: ArchivalJob = engine.archive(table="orders", older_than_days=90)

retention = RetentionManager()
retention.add_policy(RetentionPolicy(table="orders", retain_days=365))

gdpr = GDPRManager()
request = gdpr.create_request(user_id="u-42", request_type=GDPRRequestType.DELETION)
gdpr.process(request)  # Also supports EXPORT, ANONYMIZATION

lifecycle = DataLifecycleManager(ArchivalConfig())
stats: TierStats = lifecycle.get_tier_stats(StorageTier.COLD)
```

## Resilience Patterns

Source: `src/resilience/` (PRD-102)

```python
from src.resilience import (
    CircuitBreaker, CircuitBreakerRegistry, CircuitBreakerOpen,
    CircuitBreakerConfig, CircuitState, circuit_breaker, get_registry,
    retry, RetryConfig, RetryStrategy, MaxRetriesExceeded,
    RateLimiter, RateLimiterRegistry, RateLimitExceeded,
    RateLimiterConfig, RateLimitAlgorithm, create_rate_limit_middleware,
    Bulkhead, BulkheadRegistry, BulkheadFull,
    BulkheadConfig, BulkheadType, bulkhead, get_bulkhead_registry,
    ResilienceConfig, ResilienceMetrics,
)

@circuit_breaker(failure_threshold=5, recovery_timeout=30)
async def call_external_api(): ...
# States: CircuitState.CLOSED -> OPEN -> HALF_OPEN

@retry(RetryConfig(max_retries=3, strategy=RetryStrategy.EXPONENTIAL))
async def flaky_operation(): ...

limiter = RateLimiter(RateLimiterConfig(
    requests_per_second=100, algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
))
middleware = create_rate_limit_middleware(limiter)

@bulkhead(max_concurrent=10, type=BulkheadType.THREAD_POOL)
async def isolated_operation(): ...
```

## Structured Logging

Source: `src/logging_config/` (PRD-101)

```python
from src.logging_config import (
    configure_logging, get_logger, LoggingConfig, LogFormat, LogLevel,
    RequestContext, generate_request_id, log_performance,
)

configure_logging(LoggingConfig(format=LogFormat.JSON, level=LogLevel.INFO))
logger = get_logger("my_module")

request_id = generate_request_id()
with RequestContext(request_id=request_id):
    logger.info("Processing order", extra={"symbol": "AAPL"})

with log_performance(logger, "order_placement"):
    place_order()  # Logs elapsed time on exit
```

## Testing Framework

Source: `src/testing/` (PRD-108)

```python
from src.testing import (
    APITestBase, DatabaseTestBase, IntegrationTestBase, TestResult,
    MockBroker, MockMarketData, MockRedis, MockOrder, OHLCVBar,
    create_test_market_data, create_test_order, create_test_signal,
    create_test_orders_batch, create_test_portfolio,
    create_test_portfolio_with_positions,
    LoadTestRunner, LoadScenario, LoadTestResult, LoadProfile,
    BenchmarkSuite, BenchmarkResult,
    TestConfig, TestType, TestStatus,
)

class TestOrderFlow(IntegrationTestBase):
    def setup_method(self):
        self.broker = MockBroker()
        self.market = MockMarketData()
        self.redis = MockRedis()

signal = create_test_signal(symbol="AAPL", direction="buy")
order = create_test_order(symbol="AAPL", quantity=100)

runner = LoadTestRunner()
scenario = LoadScenario(name="throughput", profile=LoadProfile.RAMP_UP, target_rps=500)
result: LoadTestResult = runner.run(scenario)
```

## Migration Safety

Source: `src/migration_safety/` (PRD-110)

```python
from src.migration_safety import (
    MigrationValidator, ValidationResult,
    MigrationLinter, LintReport, LintIssue,
    PreMigrationCheck, PostMigrationCheck, MigrationCheckReport, CheckResult,
    ValidationReporter, MigrationSafetyConfig, Severity,
    RuleCategory, MigrationDirection, MigrationStatus, RuleConfig, DEFAULT_RULES,
)

config = MigrationSafetyConfig()
validator = MigrationValidator(config)
result: ValidationResult = validator.validate("alembic/versions/178_rename.py")

linter = MigrationLinter(config)
report: LintReport = linter.lint("alembic/versions/178_rename.py")

pre_report = PreMigrationCheck().run()
post_report = PostMigrationCheck().run()

ValidationReporter().render(result)
```

## API Error Handling

Source: `src/api_errors/` (PRD-106)

```python
from src.api_errors import (
    AxionAPIError, ValidationError, NotFoundError,
    AuthenticationError, AuthorizationError,
    RateLimitError, ConflictError, ServiceUnavailableError,
    ErrorResponse, ErrorDetail, ErrorCode, ErrorSeverity, ErrorConfig,
    create_error_response, register_exception_handlers,
    ErrorHandlingMiddleware, RequestSanitizer, sanitize_string,
    validate_symbol, validate_quantity, validate_pagination,
    validate_date_range, validate_symbols_list,
)

raise NotFoundError(detail="Order not found", resource_id="ord-123")
raise ValidationError(detail="Invalid quantity", field="quantity")

register_exception_handlers(app)
app.add_middleware(ErrorHandlingMiddleware)
clean = sanitize_string(user_input)
validate_symbol("AAPL")
validate_quantity(100, min_val=1)
```

## API Gateway

Source: `src/api_gateway/` (PRD-115)

```python
from src.api_gateway import (
    APIGateway, RequestContext, GatewayResponse, GatewayConfig,
    GatewayRateLimiter, RateLimitResult, EndpointRateLimit,
    SlidingWindowEntry, RateLimitTier, TierConfig, DEFAULT_TIERS,
    APIAnalytics, EndpointStats,
    VersionManager, APIVersion, VersionStatus,
    RequestValidator, ValidationResult,
)

gateway = APIGateway(GatewayConfig())
limiter = GatewayRateLimiter(GatewayConfig())
result: RateLimitResult = limiter.check(
    EndpointRateLimit(endpoint="/api/orders", tier=RateLimitTier.PREMIUM)
)

analytics = APIAnalytics()
stats: EndpointStats = analytics.get_stats("/api/orders")

versions = VersionManager()
versions.register(APIVersion(version="v2", status=VersionStatus.ACTIVE))
```

## Capacity Planning

Source: `src/capacity/` (PRD-130)

```python
from src.capacity import (
    ResourceMonitor, ResourceMetric, ResourceSnapshot,
    DemandForecaster, DemandForecast, ForecastPoint,
    ScalingManager, ScalingRule, ScalingAction,
    CostAnalyzer, CostReport, ResourceCost, SavingsOpportunity,
    ResourceType, ScalingDirection, ScalingPolicy,
    CapacityStatus, ResourceThreshold, CapacityConfig,
)

monitor = ResourceMonitor(CapacityConfig())
snapshot: ResourceSnapshot = monitor.snapshot()

forecast: DemandForecast = DemandForecaster().predict(
    resource_type=ResourceType.CPU, horizon_hours=24
)

scaling = ScalingManager(CapacityConfig())
scaling.add_rule(ScalingRule(
    resource=ResourceType.MEMORY, threshold=ResourceThreshold(upper=85.0),
    direction=ScalingDirection.UP, policy=ScalingPolicy.STEP,
))
action: ScalingAction = scaling.evaluate()

report: CostReport = CostAnalyzer().generate_report()
savings: list[SavingsOpportunity] = CostAnalyzer().find_savings()
```

## Key Classes Reference

| Module | Primary Classes | Import |
|--------|----------------|--------|
| deployment | `DeploymentOrchestrator`, `TrafficManager`, `RollbackEngine`, `DeploymentValidator` | `src.deployment` |
| lifecycle | `LifecycleManager`, `HealthCheckRegistry`, `HookRegistry`, `SignalHandler` | `src.lifecycle` |
| observability | `MetricsRegistry`, `TradingMetrics`, `SystemMetrics`, `PrometheusExporter` | `src.observability` |
| profiling | `QueryProfiler`, `PerformanceAnalyzer`, `IndexAdvisor`, `ConnectionMonitor` | `src.profiling` |
| ws_scaling | `ConnectionRegistry`, `MessageRouter`, `BackpressureHandler`, `ReconnectionManager` | `src.ws_scaling` |
| backup | `BackupEngine`, `RecoveryManager`, `ReplicationMonitor`, `BackupMonitor` | `src.backup` |
| archival | `ArchivalEngine`, `RetentionManager`, `GDPRManager`, `DataLifecycleManager` | `src.archival` |
| resilience | `CircuitBreaker`, `RateLimiter`, `Bulkhead`, `CircuitBreakerRegistry` | `src.resilience` |
| logging_config | `configure_logging`, `get_logger`, `RequestContext`, `log_performance` | `src.logging_config` |
| testing | `IntegrationTestBase`, `MockBroker`, `MockMarketData`, `LoadTestRunner` | `src.testing` |
| migration_safety | `MigrationValidator`, `MigrationLinter`, `PreMigrationCheck`, `PostMigrationCheck` | `src.migration_safety` |
| api_errors | `AxionAPIError`, `ErrorHandlingMiddleware`, `RequestSanitizer` | `src.api_errors` |
| api_gateway | `APIGateway`, `GatewayRateLimiter`, `APIAnalytics`, `VersionManager` | `src.api_gateway` |
| capacity | `ResourceMonitor`, `DemandForecaster`, `ScalingManager`, `CostAnalyzer` | `src.capacity` |

## Common Patterns

**Resilience + observability stack:**
```python
from src.resilience import circuit_breaker, retry, RetryConfig, RetryStrategy
from src.observability import MetricsRegistry, track_latency, track_errors

registry = MetricsRegistry()

@track_latency(registry, "broker_call_seconds")
@track_errors(registry, "broker_errors_total")
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
@retry(RetryConfig(max_retries=3, strategy=RetryStrategy.EXPONENTIAL))
async def call_broker(order): ...
```

**Pre-deployment validation pipeline:**
```python
from src.migration_safety import MigrationValidator, PreMigrationCheck, MigrationSafetyConfig
from src.deployment import DeploymentOrchestrator, DeploymentValidator, DeploymentConfig

result = MigrationValidator(MigrationSafetyConfig()).validate("alembic/versions/latest.py")
check_report = PreMigrationCheck().run()
if result.passed and check_report.passed:
    orchestrator = DeploymentOrchestrator(DeploymentConfig())
    deployment = orchestrator.create_deployment(version="v2.1.0")
    DeploymentValidator().run_checks(deployment)
```
