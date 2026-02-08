"""Contract registry for discovery, lifecycle management, and dependency mapping."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .config import CompatibilityMode, ContractConfig, ContractStatus
from .schema import DataContract, SchemaBuilder, SchemaVersion


class ContractRegistry:
    """Central registry for data contracts.

    Supports contract lifecycle (register, update, deprecate, retire),
    querying by producer/consumer, and dependency graph construction.
    """

    def __init__(self, config: Optional[ContractConfig] = None):
        self._config = config or ContractConfig()
        self._contracts: Dict[str, DataContract] = {}

    @property
    def config(self) -> ContractConfig:
        return self._config

    def register(self, contract: DataContract) -> str:
        """Register a new contract and return its ID.

        Raises ValueError if a contract with the same ID already exists.
        """
        if contract.contract_id in self._contracts:
            raise ValueError(
                f"Contract '{contract.contract_id}' already registered"
            )

        contract.status = ContractStatus.ACTIVE
        contract.created_at = datetime.now(timezone.utc)
        contract.updated_at = datetime.now(timezone.utc)

        # Store initial schema in version history
        if contract.schema_version and contract.schema_version not in contract.version_history:
            contract.version_history.append(contract.schema_version)

        self._contracts[contract.contract_id] = contract
        return contract.contract_id

    def update_schema(
        self,
        contract_id: str,
        new_version: SchemaVersion,
        changelog: str = "",
    ) -> DataContract:
        """Update a contract's schema to a new version.

        Performs compatibility checking based on the registry's config.
        Raises ValueError if the contract is not found or compatibility fails.
        """
        contract = self._get_contract_or_raise(contract_id)

        # Check compatibility if we have an existing schema
        if contract.schema_version:
            compatible, issues = SchemaBuilder.check_compatibility(
                contract.schema_version,
                new_version,
                self._config.compatibility_mode,
            )
            if not compatible:
                raise ValueError(
                    f"Schema update failed compatibility check: {'; '.join(issues)}"
                )

        # Archive current version
        if contract.schema_version:
            contract.version_history.append(contract.schema_version)

        if changelog:
            new_version.changelog = changelog

        contract.schema_version = new_version
        contract.updated_at = datetime.now(timezone.utc)

        return contract

    def deprecate(self, contract_id: str, reason: str = "") -> DataContract:
        """Mark a contract as deprecated.

        Raises ValueError if the contract is not found.
        """
        contract = self._get_contract_or_raise(contract_id)
        contract.status = ContractStatus.DEPRECATED
        contract.updated_at = datetime.now(timezone.utc)
        if reason:
            contract.description = f"[DEPRECATED] {reason}"
        return contract

    def retire(self, contract_id: str) -> DataContract:
        """Mark a contract as retired.

        Raises ValueError if the contract is not found.
        """
        contract = self._get_contract_or_raise(contract_id)
        contract.status = ContractStatus.RETIRED
        contract.updated_at = datetime.now(timezone.utc)
        return contract

    def get_contract(self, contract_id: str) -> Optional[DataContract]:
        """Retrieve a contract by ID, or None if not found."""
        return self._contracts.get(contract_id)

    def find_by_producer(self, producer: str) -> List[DataContract]:
        """Find all contracts for a given producer."""
        return [
            c for c in self._contracts.values()
            if c.producer == producer
        ]

    def find_by_consumer(self, consumer: str) -> List[DataContract]:
        """Find all contracts for a given consumer."""
        return [
            c for c in self._contracts.values()
            if c.consumer == consumer
        ]

    def find_by_tag(self, tag: str) -> List[DataContract]:
        """Find all contracts with a given tag."""
        return [
            c for c in self._contracts.values()
            if tag in c.tags
        ]

    def dependency_graph(self) -> Dict[str, List[str]]:
        """Build a dependency graph showing producer -> consumer relationships.

        Returns a dict where keys are producers and values are lists of consumers.
        """
        graph: Dict[str, List[str]] = {}
        for contract in self._contracts.values():
            if contract.status in (ContractStatus.ACTIVE, ContractStatus.DEPRECATED):
                if contract.producer not in graph:
                    graph[contract.producer] = []
                if contract.consumer not in graph[contract.producer]:
                    graph[contract.producer].append(contract.consumer)
        return graph

    def list_contracts(
        self,
        status_filter: Optional[ContractStatus] = None,
    ) -> List[DataContract]:
        """List all contracts, optionally filtered by status."""
        if status_filter is None:
            return list(self._contracts.values())
        return [
            c for c in self._contracts.values()
            if c.status == status_filter
        ]

    def contract_count(self) -> int:
        """Return total number of registered contracts."""
        return len(self._contracts)

    def remove(self, contract_id: str) -> bool:
        """Remove a contract from the registry. Returns True if removed."""
        if contract_id in self._contracts:
            del self._contracts[contract_id]
            return True
        return False

    def _get_contract_or_raise(self, contract_id: str) -> DataContract:
        """Get a contract by ID or raise ValueError."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            raise ValueError(f"Contract '{contract_id}' not found")
        return contract
