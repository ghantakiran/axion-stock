"""PRD-112: Data Pipeline Orchestration — Pipeline & Node Definition."""

import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .config import NodeStatus, PipelineStatus

logger = logging.getLogger(__name__)


@dataclass
class PipelineNode:
    """A single node (task) within a pipeline DAG."""

    node_id: str
    name: str
    func: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING


@dataclass
class PipelineRun:
    """A single execution run of a pipeline."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    status: PipelineStatus = PipelineStatus.PENDING
    nodes: Dict[str, PipelineNode] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class Pipeline:
    """A directed acyclic graph (DAG) of pipeline nodes."""

    def __init__(
        self,
        pipeline_id: str,
        name: str,
        description: str = "",
    ) -> None:
        self.pipeline_id = pipeline_id
        self.name = name
        self.description = description
        self.nodes: Dict[str, PipelineNode] = {}

    # ── Node management ──────────────────────────────────────────────

    def add_node(self, node: PipelineNode) -> None:
        """Add a node to the pipeline."""
        if node.node_id in self.nodes:
            raise ValueError(f"Node '{node.node_id}' already exists in pipeline")
        self.nodes[node.node_id] = node
        logger.debug("Added node '%s' to pipeline '%s'", node.node_id, self.pipeline_id)

    def remove_node(self, node_id: str) -> None:
        """Remove a node and clean up references from other nodes' dependencies."""
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found in pipeline")
        del self.nodes[node_id]
        # Remove from all dependency lists
        for node in self.nodes.values():
            if node_id in node.dependencies:
                node.dependencies.remove(node_id)
        logger.debug("Removed node '%s' from pipeline '%s'", node_id, self.pipeline_id)

    # ── Execution order (topological sort — Kahn's algorithm) ────────

    def get_execution_order(self) -> List[List[str]]:
        """Return nodes grouped by execution level (parallel batches).

        Uses Kahn's algorithm to produce a topological sort.  Each inner list
        contains nodes that can execute in parallel (no inter-dependencies).

        Returns:
            List of lists — each sub-list is a batch of node IDs.

        Raises:
            ValueError: If the graph contains a cycle.
        """
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.node_id] += 0  # dep contributes to *this* node
                # Actually: each dep edge means the *dependent* node has +1 in-degree
        # Recompute correctly
        in_degree = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in self.nodes:
                    in_degree[node.node_id] += 1

        queue: deque = deque()
        for nid, deg in in_degree.items():
            if deg == 0:
                queue.append(nid)

        levels: List[List[str]] = []
        processed = 0

        while queue:
            level: List[str] = list(queue)
            queue.clear()
            levels.append(level)
            processed += len(level)

            for nid in level:
                # Decrement in-degree for dependents
                for other in self.nodes.values():
                    if nid in other.dependencies:
                        in_degree[other.node_id] -= 1
                        if in_degree[other.node_id] == 0:
                            queue.append(other.node_id)

        if processed != len(self.nodes):
            raise ValueError("Pipeline contains a cycle — topological sort not possible")

        return levels

    # ── Validation ───────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """Validate the pipeline definition.

        Returns:
            List of error messages (empty if valid).
        """
        errors: List[str] = []

        # Check for missing dependencies
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    errors.append(
                        f"Node '{node.node_id}' depends on missing node '{dep}'"
                    )

        # Check for cycles
        try:
            self.get_execution_order()
        except ValueError:
            errors.append("Pipeline contains a cycle")

        return errors

    # ── Graph helpers ────────────────────────────────────────────────

    def get_node_dependents(self, node_id: str) -> List[str]:
        """Return all node IDs that directly depend on *node_id*."""
        dependents: List[str] = []
        for other in self.nodes.values():
            if node_id in other.dependencies:
                dependents.append(other.node_id)
        return dependents

    def create_run(self) -> PipelineRun:
        """Create a new PipelineRun with a deep-copy of current nodes."""
        import copy

        run_nodes: Dict[str, PipelineNode] = {}
        for nid, node in self.nodes.items():
            cloned = copy.deepcopy(node)
            cloned.status = NodeStatus.PENDING
            run_nodes[nid] = cloned

        return PipelineRun(
            pipeline_id=self.pipeline_id,
            nodes=run_nodes,
        )
