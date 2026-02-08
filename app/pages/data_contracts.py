"""PRD-129: Data Contracts & Schema Governance Dashboard."""

import streamlit as st
from datetime import datetime, timedelta, timezone

from src.data_contracts import (
    ContractStatus,
    CompatibilityMode,
    FieldType,
    ValidationLevel,
    ViolationType,
    ContractConfig,
    FieldDefinition,
    SchemaVersion,
    DataContract,
    SchemaBuilder,
    ContractRegistry,
    ValidationResult,
    ContractViolation,
    ContractValidator,
    SLADefinition,
    SLAReport,
    SLAMonitor,
)


def _build_demo_registry():
    """Build a demo registry with sample contracts."""
    registry = ContractRegistry()

    # Price feed contract
    price_schema = (
        SchemaBuilder()
        .set_version("2.1.0")
        .add_field("symbol", FieldType.STRING, constraints={"min_length": 1, "max_length": 10})
        .add_field("price", FieldType.FLOAT, constraints={"min_value": 0})
        .add_field("volume", FieldType.INTEGER, constraints={"min_value": 0})
        .add_field("timestamp", FieldType.DATETIME)
        .add_field("source", FieldType.STRING, required=False)
        .build()
    )
    price_contract = DataContract(
        name="Real-Time Price Feed",
        producer="market-data-service",
        consumer="trading-engine",
        schema_version=price_schema,
        description="Real-time equity price feed",
        tags=["realtime", "market-data", "pricing"],
    )
    registry.register(price_contract)

    # Order events contract
    order_schema = (
        SchemaBuilder()
        .set_version("1.3.0")
        .add_field("order_id", FieldType.STRING)
        .add_field("symbol", FieldType.STRING)
        .add_field("side", FieldType.STRING, constraints={"allowed_values": ["buy", "sell"]})
        .add_field("quantity", FieldType.INTEGER, constraints={"min_value": 1})
        .add_field("price", FieldType.FLOAT, constraints={"min_value": 0})
        .add_field("status", FieldType.STRING)
        .build()
    )
    order_contract = DataContract(
        name="Order Events",
        producer="trading-engine",
        consumer="risk-service",
        schema_version=order_schema,
        description="Order lifecycle events",
        tags=["orders", "trading"],
    )
    registry.register(order_contract)

    # Risk metrics contract
    risk_schema = (
        SchemaBuilder()
        .set_version("1.0.0")
        .add_field("portfolio_id", FieldType.STRING)
        .add_field("var_95", FieldType.FLOAT)
        .add_field("sharpe_ratio", FieldType.FLOAT)
        .add_field("max_drawdown", FieldType.FLOAT)
        .add_field("positions", FieldType.LIST)
        .build()
    )
    risk_contract = DataContract(
        name="Risk Metrics",
        producer="risk-service",
        consumer="reporting-service",
        schema_version=risk_schema,
        description="Portfolio risk metrics",
        tags=["risk", "analytics"],
    )
    registry.register(risk_contract)

    # Deprecated contract
    old_contract = DataContract(
        name="Legacy Price Feed (v1)",
        producer="market-data-service",
        consumer="old-dashboard",
        schema_version=SchemaBuilder().add_field("price", FieldType.FLOAT).build(),
        tags=["legacy"],
    )
    registry.register(old_contract)
    registry.deprecate(old_contract.contract_id, "Replaced by v2 price feed")

    return registry, [price_contract, order_contract, risk_contract, old_contract]


def render():
    st.title("Data Contracts & Schema Governance")

    tabs = st.tabs(["Contract Overview", "Schema Browser", "Violations", "SLA Compliance"])

    registry, contracts = _build_demo_registry()
    price_contract, order_contract, risk_contract, old_contract = contracts

    # ── Tab 1: Contract Overview ─────────────────────────────────────
    with tabs[0]:
        st.subheader("Contract Overview")

        all_contracts = registry.list_contracts()
        active = registry.list_contracts(status_filter=ContractStatus.ACTIVE)
        deprecated = registry.list_contracts(status_filter=ContractStatus.DEPRECATED)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Contracts", len(all_contracts))
        col2.metric("Active", len(active))
        col3.metric("Deprecated", len(deprecated))
        col4.metric("Compliance", "98.5%")

        st.markdown("---")
        st.subheader("Active Contracts")
        for c in active:
            with st.expander(f"{c.name} ({c.schema_version.version if c.schema_version else 'N/A'})"):
                st.markdown(f"**Producer:** {c.producer}")
                st.markdown(f"**Consumer:** {c.consumer}")
                st.markdown(f"**Status:** {c.status.value}")
                st.markdown(f"**Description:** {c.description}")
                if c.tags:
                    st.markdown(f"**Tags:** {', '.join(c.tags)}")

        st.markdown("---")
        st.subheader("Dependency Graph")
        graph = registry.dependency_graph()
        for producer, consumers in graph.items():
            for consumer in consumers:
                st.markdown(f"  {producer} --> {consumer}")

    # ── Tab 2: Schema Browser ────────────────────────────────────────
    with tabs[1]:
        st.subheader("Schema Browser")

        contract_names = {c.name: c for c in all_contracts}
        selected_name = st.selectbox("Select Contract", list(contract_names.keys()))

        if selected_name:
            selected = contract_names[selected_name]
            schema = selected.schema_version
            if schema:
                st.markdown(f"**Version:** {schema.version}")
                st.markdown(f"**Fields:** {len(schema.fields)}")

                st.markdown("#### Field Definitions")
                field_data = []
                for f in schema.fields:
                    field_data.append({
                        "Name": f.name,
                        "Type": f.field_type.value,
                        "Required": f.required,
                        "Constraints": str(f.constraints) if f.constraints else "-",
                        "Description": f.description or "-",
                    })
                st.table(field_data)

                # Version history
                if selected.version_history:
                    st.markdown("#### Version History")
                    for v in selected.version_history:
                        st.markdown(f"- **v{v.version}** ({v.created_at.strftime('%Y-%m-%d %H:%M')})")
                        if v.changelog:
                            st.markdown(f"  {v.changelog}")

                # Schema diff demo
                st.markdown("#### Schema Diff Tool")
                if len(selected.version_history) >= 2:
                    v1 = selected.version_history[-2]
                    v2 = selected.version_history[-1]
                    changes = SchemaBuilder.diff(v1, v2)
                    if changes:
                        for ch in changes:
                            st.markdown(f"  - **{ch['change'].upper()}**: {ch['field']} - {ch['details']}")
                    else:
                        st.info("No changes between versions.")
                else:
                    st.info("Need at least 2 versions for diff comparison.")

    # ── Tab 3: Violations ────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Contract Violations")

        # Generate demo violations
        validator = ContractValidator()
        demo_violations_data = [
            {"symbol": 12345, "price": 175.0, "volume": 1000,
             "timestamp": datetime.now(timezone.utc)},
            {"symbol": "AAPL", "price": -5.0, "volume": 1000,
             "timestamp": datetime.now(timezone.utc)},
            {"price": 175.0, "volume": 1000,
             "timestamp": datetime.now(timezone.utc)},
            {"symbol": "VERYLONGSYMBOLNAME", "price": 175.0, "volume": 1000,
             "timestamp": datetime.now(timezone.utc)},
        ]

        all_violations = []
        all_warnings = []
        for data in demo_violations_data:
            result = validator.validate(data, price_contract)
            all_violations.extend(result.violations)
            all_warnings.extend(result.warnings)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Violations", len(all_violations))
        col2.metric("Warnings", len(all_warnings))
        col3.metric("Error Rate", f"{len(all_violations) / len(demo_violations_data) * 100:.0f}%")

        st.markdown("---")
        st.subheader("Recent Violations")
        for v in all_violations[:10]:
            severity_icon = {"error": "red", "warning": "orange"}.get(v.severity, "gray")
            st.markdown(
                f":{severity_icon}[{v.severity.upper()}] | "
                f"**{v.violation_type.value}** | "
                f"Field: `{v.field_name}` | "
                f"{v.message}"
            )

        # Violation statistics
        st.markdown("---")
        st.subheader("Violation Breakdown")
        stats = validator.violation_statistics(price_contract.contract_id)
        if stats["by_type"]:
            for vtype, count in stats["by_type"].items():
                st.markdown(f"  - **{vtype}**: {count}")

    # ── Tab 4: SLA Compliance ────────────────────────────────────────
    with tabs[3]:
        st.subheader("SLA Compliance")

        monitor = SLAMonitor()

        # Set up SLAs
        monitor.set_sla(
            price_contract.contract_id,
            SLADefinition(freshness_seconds=60.0, completeness_threshold=0.95),
        )
        monitor.set_sla(
            order_contract.contract_id,
            SLADefinition(freshness_seconds=120.0, completeness_threshold=0.99),
        )
        monitor.set_sla(
            risk_contract.contract_id,
            SLADefinition(freshness_seconds=300.0, completeness_threshold=0.90),
        )

        # Record deliveries
        now = datetime.now(timezone.utc)
        monitor.record_delivery(
            price_contract.contract_id, timestamp=now, record_count=50000, completeness=0.98,
        )
        monitor.record_delivery(
            order_contract.contract_id, timestamp=now, record_count=1200, completeness=0.995,
        )
        monitor.record_delivery(
            risk_contract.contract_id,
            timestamp=now - timedelta(minutes=10),
            record_count=50,
            completeness=0.92,
        )

        overall = monitor.overall_compliance()

        col1, col2, col3 = st.columns(3)
        col1.metric("Monitored Contracts", overall["total_contracts"])
        col2.metric("Compliant", overall["compliant"])
        col3.metric("Compliance Rate", f"{overall['compliance_rate']:.1f}%")

        st.markdown("---")
        st.subheader("Contract SLA Status")

        for cid, status in overall.get("contracts", {}).items():
            # Find contract name
            contract = registry.get_contract(cid)
            name = contract.name if contract else cid
            compliant_str = "Compliant" if status["compliant"] else "Non-Compliant"
            color = "green" if status["compliant"] else "red"
            st.markdown(
                f":{color}[{compliant_str}] **{name}** | "
                f"Freshness: {'OK' if status['freshness_met'] else 'FAIL'} | "
                f"Completeness: {'OK' if status['completeness_met'] else 'FAIL'} | "
                f"Violations: {status['violations_count']}"
            )

        # Freshness metrics
        st.markdown("---")
        st.subheader("Freshness Metrics")
        for contract in [price_contract, order_contract, risk_contract]:
            deliveries = monitor.get_delivery_history(contract.contract_id, hours=1)
            if deliveries:
                latest = max(deliveries, key=lambda d: d.timestamp)
                age = (now - latest.timestamp).total_seconds()
                st.markdown(f"**{contract.name}**: Last delivery {age:.0f}s ago ({latest.record_count} records)")



render()
