"""PRD-112: Data Pipeline Orchestration — Data Lineage Tracking."""

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class LineageNode:
    """A node in the data lineage graph."""

    node_id: str
    node_type: str  # "source", "transform", "sink"
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageEdge:
    """A directed edge in the data lineage graph."""

    source_id: str
    target_id: str
    relationship: str = "feeds_into"
    metadata: Dict[str, Any] = field(default_factory=dict)


class LineageGraph:
    """Tracks data lineage as a directed graph."""

    def __init__(self) -> None:
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: List[LineageEdge] = []

    # ── Node / Edge management ───────────────────────────────────────

    def add_node(self, node: LineageNode) -> None:
        """Add a lineage node."""
        self._nodes[node.node_id] = node
        logger.debug("Lineage: added node '%s'", node.node_id)

    def add_edge(self, edge: LineageEdge) -> None:
        """Add a directed edge between two lineage nodes."""
        if edge.source_id not in self._nodes:
            raise KeyError(f"Source node '{edge.source_id}' not found")
        if edge.target_id not in self._nodes:
            raise KeyError(f"Target node '{edge.target_id}' not found")
        self._edges.append(edge)
        logger.debug(
            "Lineage: added edge '%s' -> '%s'", edge.source_id, edge.target_id
        )

    # ── Traversal ────────────────────────────────────────────────────

    def get_upstream(self, node_id: str) -> List[str]:
        """Return direct upstream (parent) node IDs."""
        return [e.source_id for e in self._edges if e.target_id == node_id]

    def get_downstream(self, node_id: str) -> List[str]:
        """Return direct downstream (child) node IDs."""
        return [e.target_id for e in self._edges if e.source_id == node_id]

    def get_impact(self, node_id: str) -> List[str]:
        """Return all transitively downstream nodes (BFS) — impact analysis."""
        visited: set = set()
        queue: deque = deque()
        queue.append(node_id)

        while queue:
            current = queue.popleft()
            for child in self.get_downstream(current):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)

        return sorted(visited)

    def get_lineage(self, node_id: str) -> List[str]:
        """Return all transitively upstream nodes (BFS) — full lineage."""
        visited: set = set()
        queue: deque = deque()
        queue.append(node_id)

        while queue:
            current = queue.popleft()
            for parent in self.get_upstream(current):
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)

        return sorted(visited)

    # ── Utilities ────────────────────────────────────────────────────

    def get_roots(self) -> List[str]:
        """Return node IDs with no upstream edges (data sources)."""
        targets = {e.target_id for e in self._edges}
        return sorted(nid for nid in self._nodes if nid not in targets)

    def get_leaves(self) -> List[str]:
        """Return node IDs with no downstream edges (data sinks)."""
        sources = {e.source_id for e in self._edges}
        return sorted(nid for nid in self._nodes if nid not in sources)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation of the lineage graph."""
        return {
            "nodes": [
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "name": n.name,
                    "metadata": n.metadata,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "relationship": e.relationship,
                    "metadata": e.metadata,
                }
                for e in self._edges
            ],
        }
