"""Feature Lineage tracking for dependency and impact analysis."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


@dataclass
class LineageNode:
    """A node in the feature lineage graph."""

    node_id: str = ""
    name: str = ""
    node_type: str = "feature"  # source, feature, model
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.node_id:
            self.node_id = uuid.uuid4().hex[:16]


@dataclass
class LineageEdge:
    """A directed edge in the lineage graph."""

    source_id: str = ""
    target_id: str = ""
    relationship: str = "derived_from"  # derived_from, feeds_into, consumes
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    edge_id: str = ""

    def __post_init__(self):
        if not self.edge_id:
            self.edge_id = uuid.uuid4().hex[:16]


class FeatureLineage:
    """DAG-based lineage tracker for feature dependencies and impact analysis."""

    def __init__(self) -> None:
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: List[LineageEdge] = []
        # Adjacency lists for fast traversal
        self._forward: Dict[str, List[str]] = defaultdict(list)  # node -> downstream
        self._backward: Dict[str, List[str]] = defaultdict(list)  # node -> upstream

    def add_node(self, node: LineageNode) -> LineageNode:
        """Add a node to the lineage graph."""
        self._nodes[node.node_id] = node
        return node

    def get_node(self, node_id: str) -> Optional[LineageNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def add_edge(self, edge: LineageEdge) -> LineageEdge:
        """Add a directed edge (source -> target) to the lineage graph."""
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise ValueError(
                f"Both source ({edge.source_id}) and target ({edge.target_id}) "
                f"must exist as nodes before adding an edge."
            )
        self._edges.append(edge)
        self._forward[edge.source_id].append(edge.target_id)
        self._backward[edge.target_id].append(edge.source_id)
        return edge

    def get_upstream(self, node_id: str, max_depth: int = 20) -> List[LineageNode]:
        """Get all upstream (ancestor) nodes for a given node.

        Traverses backward through the DAG up to max_depth levels.
        """
        visited: Set[str] = set()
        result: List[LineageNode] = []
        self._traverse_backward(node_id, visited, result, 0, max_depth)
        return result

    def get_downstream(self, node_id: str, max_depth: int = 20) -> List[LineageNode]:
        """Get all downstream (descendant) nodes for a given node.

        Traverses forward through the DAG up to max_depth levels.
        """
        visited: Set[str] = set()
        result: List[LineageNode] = []
        self._traverse_forward(node_id, visited, result, 0, max_depth)
        return result

    def get_impact(self, node_id: str) -> Dict[str, Any]:
        """Analyze the impact of a change to a node.

        Returns which features and models would be affected downstream.
        """
        downstream = self.get_downstream(node_id)

        affected_features = [n for n in downstream if n.node_type == "feature"]
        affected_models = [n for n in downstream if n.node_type == "model"]
        affected_sources = [n for n in downstream if n.node_type == "source"]

        return {
            "node_id": node_id,
            "total_affected": len(downstream),
            "affected_features": affected_features,
            "affected_models": affected_models,
            "affected_sources": affected_sources,
            "feature_count": len(affected_features),
            "model_count": len(affected_models),
        }

    def get_lineage_graph(self) -> Dict[str, Any]:
        """Get the full lineage graph as a serializable dict."""
        nodes = []
        for node in self._nodes.values():
            nodes.append({
                "node_id": node.node_id,
                "name": node.name,
                "node_type": node.node_type,
                "metadata": node.metadata,
            })

        edges = []
        for edge in self._edges:
            edges.append({
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relationship": edge.relationship,
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def get_roots(self) -> List[LineageNode]:
        """Get all root nodes (nodes with no upstream dependencies)."""
        root_ids = set(self._nodes.keys()) - set(self._backward.keys())
        return [self._nodes[nid] for nid in root_ids if nid in self._nodes]

    def get_leaves(self) -> List[LineageNode]:
        """Get all leaf nodes (nodes with no downstream dependents)."""
        leaf_ids = set(self._nodes.keys()) - set(self._forward.keys())
        return [self._nodes[nid] for nid in leaf_ids if nid in self._nodes]

    def get_edges_for_node(self, node_id: str) -> List[LineageEdge]:
        """Get all edges connected to a node (both incoming and outgoing)."""
        return [
            e for e in self._edges
            if e.source_id == node_id or e.target_id == node_id
        ]

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges from the graph."""
        if node_id not in self._nodes:
            return False

        # Remove edges
        self._edges = [
            e for e in self._edges
            if e.source_id != node_id and e.target_id != node_id
        ]

        # Update adjacency lists
        if node_id in self._forward:
            for target_id in self._forward[node_id]:
                if node_id in self._backward.get(target_id, []):
                    self._backward[target_id].remove(node_id)
            del self._forward[node_id]

        if node_id in self._backward:
            for source_id in self._backward[node_id]:
                if node_id in self._forward.get(source_id, []):
                    self._forward[source_id].remove(node_id)
            del self._backward[node_id]

        del self._nodes[node_id]
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        type_counts: Dict[str, int] = {}
        for node in self._nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "by_type": type_counts,
            "root_count": len(self.get_roots()),
            "leaf_count": len(self.get_leaves()),
        }

    def _traverse_backward(
        self,
        node_id: str,
        visited: Set[str],
        result: List[LineageNode],
        depth: int,
        max_depth: int,
    ) -> None:
        """Recursively traverse upstream nodes."""
        if depth >= max_depth:
            return
        for upstream_id in self._backward.get(node_id, []):
            if upstream_id not in visited:
                visited.add(upstream_id)
                node = self._nodes.get(upstream_id)
                if node:
                    result.append(node)
                self._traverse_backward(upstream_id, visited, result, depth + 1, max_depth)

    def _traverse_forward(
        self,
        node_id: str,
        visited: Set[str],
        result: List[LineageNode],
        depth: int,
        max_depth: int,
    ) -> None:
        """Recursively traverse downstream nodes."""
        if depth >= max_depth:
            return
        for downstream_id in self._forward.get(node_id, []):
            if downstream_id not in visited:
                visited.add(downstream_id)
                node = self._nodes.get(downstream_id)
                if node:
                    result.append(node)
                self._traverse_forward(downstream_id, visited, result, depth + 1, max_depth)
