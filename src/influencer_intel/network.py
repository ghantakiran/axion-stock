"""Influencer Network Analysis.

Analyzes co-mention patterns to discover influencer clusters,
detect coordinated activity, and measure influence propagation.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Configuration for network analysis."""

    min_co_mentions: int = 3  # Minimum shared ticker mentions for edge
    min_cluster_size: int = 2
    max_clusters: int = 20
    coordination_time_window_hours: float = 4.0  # Same ticker within N hours


@dataclass
class InfluencerNode:
    """A node in the influencer network graph."""

    author_id: str = ""
    platform: str = ""
    degree: int = 0  # Number of connections
    tickers: list[str] = field(default_factory=list)
    cluster_id: int = -1
    centrality: float = 0.0  # 0-1

    def to_dict(self) -> dict:
        return {
            "author_id": self.author_id,
            "platform": self.platform,
            "degree": self.degree,
            "tickers": self.tickers[:5],
            "cluster_id": self.cluster_id,
            "centrality": round(self.centrality, 3),
        }


@dataclass
class CommunityCluster:
    """A detected community of related influencers."""

    cluster_id: int = 0
    members: list[str] = field(default_factory=list)  # author keys
    shared_tickers: list[str] = field(default_factory=list)
    avg_sentiment: float = 0.0
    coordination_score: float = 0.0  # 0-1, higher = more synchronized
    size: int = 0

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "members": self.members,
            "shared_tickers": self.shared_tickers[:5],
            "avg_sentiment": round(self.avg_sentiment, 3),
            "coordination_score": round(self.coordination_score, 3),
            "size": self.size,
        }


@dataclass
class NetworkReport:
    """Full network analysis report."""

    nodes: list[InfluencerNode] = field(default_factory=list)
    clusters: list[CommunityCluster] = field(default_factory=list)
    total_edges: int = 0
    density: float = 0.0  # Graph density (0-1)
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "clusters": [c.to_dict() for c in self.clusters],
            "total_edges": self.total_edges,
            "density": round(self.density, 4),
            "generated_at": self.generated_at,
        }

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def cluster_count(self) -> int:
        return len(self.clusters)

    def get_most_connected(self, n: int = 5) -> list[InfluencerNode]:
        """Top N most connected influencers."""
        return sorted(self.nodes, key=lambda x: x.degree, reverse=True)[:n]

    def get_most_coordinated_cluster(self) -> Optional[CommunityCluster]:
        """Cluster with highest coordination score."""
        if not self.clusters:
            return None
        return max(self.clusters, key=lambda c: c.coordination_score)


@dataclass
class _PostRecord:
    """Internal: a post record for co-mention analysis."""

    author_key: str
    ticker: str
    sentiment: float
    timestamp: datetime


class NetworkAnalyzer:
    """Analyze influencer co-mention networks.

    Builds a graph where influencers are nodes and edges represent
    shared ticker coverage. Detects clusters of influencers who
    discuss the same tickers with similar timing.

    Example::

        analyzer = NetworkAnalyzer()
        analyzer.ingest_posts(posts)
        report = analyzer.analyze()
        for cluster in report.clusters:
            print(f"Cluster {cluster.cluster_id}: {cluster.members}")
    """

    def __init__(self, config: Optional[NetworkConfig] = None):
        self.config = config or NetworkConfig()
        self._posts: list[_PostRecord] = []
        self._author_tickers: dict[str, set[str]] = defaultdict(set)
        self._author_sentiments: dict[str, list[float]] = defaultdict(list)

    def ingest_posts(self, posts: list) -> int:
        """Ingest posts for network analysis.

        Args:
            posts: SocialPost-like objects.

        Returns:
            Number of posts ingested.
        """
        ingested = 0

        for post in posts:
            author = getattr(post, "author", "") or ""
            source = getattr(post, "source", "") or ""
            if not author:
                continue

            key = f"{source}:{author}"
            sentiment = getattr(post, "sentiment", 0.0)
            tickers = getattr(post, "tickers", []) or []

            ts_str = getattr(post, "timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                ts = datetime.now(timezone.utc)

            for ticker in tickers:
                self._posts.append(_PostRecord(
                    author_key=key, ticker=ticker,
                    sentiment=sentiment, timestamp=ts,
                ))
                self._author_tickers[key].add(ticker)

            self._author_sentiments[key].append(sentiment)
            ingested += 1

        return ingested

    def analyze(self) -> NetworkReport:
        """Run network analysis on ingested posts.

        Returns:
            NetworkReport with nodes, clusters, and density metrics.
        """
        # Build adjacency: edge between authors who share >= N tickers
        authors = list(self._author_tickers.keys())
        edges: dict[tuple[str, str], int] = {}

        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                shared = self._author_tickers[authors[i]] & self._author_tickers[authors[j]]
                if len(shared) >= self.config.min_co_mentions:
                    edges[(authors[i], authors[j])] = len(shared)

        # Build adjacency list
        adj: dict[str, set[str]] = defaultdict(set)
        for (a, b) in edges:
            adj[a].add(b)
            adj[b].add(a)

        # Build nodes
        nodes = []
        max_degree = max((len(adj[a]) for a in authors), default=1)
        for author in authors:
            parts = author.split(":", 1)
            platform = parts[0] if len(parts) > 1 else ""
            author_id = parts[1] if len(parts) > 1 else parts[0]
            degree = len(adj[author])
            centrality = degree / max_degree if max_degree > 0 else 0.0

            nodes.append(InfluencerNode(
                author_id=author_id,
                platform=platform,
                degree=degree,
                tickers=sorted(self._author_tickers[author])[:10],
                centrality=centrality,
            ))

        # Simple community detection: connected components via BFS
        visited: set[str] = set()
        clusters: list[CommunityCluster] = []
        cluster_id = 0

        for author in authors:
            if author in visited or author not in adj:
                continue

            # BFS
            component: list[str] = []
            queue = [author]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.append(node)
                for neighbor in adj[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(component) < self.config.min_cluster_size:
                continue

            # Shared tickers across all members
            shared = set.intersection(*(self._author_tickers[a] for a in component))

            # Average sentiment
            all_sents = []
            for a in component:
                all_sents.extend(self._author_sentiments.get(a, []))
            avg_sent = sum(all_sents) / len(all_sents) if all_sents else 0.0

            # Coordination score: how synchronized are their postings?
            coord = self._compute_coordination(component)

            cluster = CommunityCluster(
                cluster_id=cluster_id,
                members=component,
                shared_tickers=sorted(shared),
                avg_sentiment=avg_sent,
                coordination_score=coord,
                size=len(component),
            )
            clusters.append(cluster)

            # Assign cluster_id to nodes
            for node in nodes:
                full_key = f"{node.platform}:{node.author_id}"
                if full_key in component:
                    node.cluster_id = cluster_id

            cluster_id += 1

        clusters = clusters[:self.config.max_clusters]

        # Graph density
        n = len(authors)
        max_edges = n * (n - 1) / 2 if n > 1 else 1
        density = len(edges) / max_edges if max_edges > 0 else 0.0

        return NetworkReport(
            nodes=nodes,
            clusters=clusters,
            total_edges=len(edges),
            density=density,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _compute_coordination(self, members: list[str]) -> float:
        """Compute how coordinated a group's posting is (0-1)."""
        # For each shared ticker, check if members post within the time window
        shared = set.intersection(*(self._author_tickers[a] for a in members))
        if not shared:
            return 0.0

        window_seconds = self.config.coordination_time_window_hours * 3600
        coordinated_tickers = 0

        for ticker in shared:
            # Get all posts for this ticker by group members
            ticker_posts = [
                p for p in self._posts
                if p.ticker == ticker and p.author_key in members
            ]
            if len(ticker_posts) < 2:
                continue

            ticker_posts.sort(key=lambda p: p.timestamp)

            # Check if any pair is within the window
            for i in range(len(ticker_posts) - 1):
                if ticker_posts[i].author_key != ticker_posts[i + 1].author_key:
                    gap = abs((ticker_posts[i + 1].timestamp - ticker_posts[i].timestamp).total_seconds())
                    if gap <= window_seconds:
                        coordinated_tickers += 1
                        break

        return coordinated_tickers / len(shared) if shared else 0.0

    def clear(self):
        """Reset all network state."""
        self._posts.clear()
        self._author_tickers.clear()
        self._author_sentiments.clear()
