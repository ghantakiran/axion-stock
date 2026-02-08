"""PRD-103: Observability & Metrics Export — Prometheus Exporter."""

import logging
import time
from typing import Optional

from .config import MetricType, MetricsConfig
from .registry import Counter, Gauge, Histogram, MetricsRegistry

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """Exports metrics in Prometheus text exposition format."""

    def __init__(self, config: Optional[MetricsConfig] = None):
        self.config = config or MetricsConfig()
        self.registry = MetricsRegistry()

    def expose_metrics(self) -> str:
        """Generate Prometheus text format output for all registered metrics."""
        lines = []
        all_metrics = self.registry.get_all_metrics()
        all_meta = self.registry.get_all_meta()
        timestamp_ms = int(time.time() * 1000) if self.config.include_timestamp else None

        for name in sorted(all_metrics.keys()):
            metric = all_metrics[name]
            meta = all_meta.get(name)
            if meta is None:
                continue

            # HELP line
            lines.append(f"# HELP {name} {meta.description}")
            # TYPE line
            lines.append(f"# TYPE {name} {meta.metric_type.value}")

            if isinstance(metric, Counter):
                self._render_counter(lines, name, metric, meta, timestamp_ms)
            elif isinstance(metric, Gauge):
                self._render_gauge(lines, name, metric, meta, timestamp_ms)
            elif isinstance(metric, Histogram):
                self._render_histogram(lines, name, metric, meta, timestamp_ms)

            lines.append("")  # blank line between metric families

        return "\n".join(lines)

    def _render_counter(
        self, lines: list, name: str, metric: Counter, meta, timestamp_ms: Optional[int]
    ) -> None:
        all_values = metric.get_all()
        if not all_values:
            line = f"{name} 0"
            if timestamp_ms:
                line += f" {timestamp_ms}"
            lines.append(line)
            return

        for label_key, value in sorted(all_values.items()):
            label_str = self._format_labels(meta.label_names, label_key)
            line = f"{name}{label_str} {self._format_value(value)}"
            if timestamp_ms:
                line += f" {timestamp_ms}"
            lines.append(line)

    def _render_gauge(
        self, lines: list, name: str, metric: Gauge, meta, timestamp_ms: Optional[int]
    ) -> None:
        all_values = metric.get_all()
        if not all_values:
            line = f"{name} 0"
            if timestamp_ms:
                line += f" {timestamp_ms}"
            lines.append(line)
            return

        for label_key, value in sorted(all_values.items()):
            label_str = self._format_labels(meta.label_names, label_key)
            line = f"{name}{label_str} {self._format_value(value)}"
            if timestamp_ms:
                line += f" {timestamp_ms}"
            lines.append(line)

    def _render_histogram(
        self, lines: list, name: str, metric: Histogram, meta, timestamp_ms: Optional[int]
    ) -> None:
        all_data = metric.get_all()
        if not all_data:
            # Empty histogram: output zero-valued _count and _sum
            ts_suffix = f" {timestamp_ms}" if timestamp_ms else ""
            lines.append(f"{name}_count 0{ts_suffix}")
            lines.append(f"{name}_sum 0{ts_suffix}")
            return

        for label_key, data in sorted(all_data.items()):
            base_label_str = self._format_labels(meta.label_names, label_key)
            bucket_counts = data.get("buckets", [])
            ts_suffix = f" {timestamp_ms}" if timestamp_ms else ""

            # Cumulative bucket lines
            cumulative = 0
            for i, bound in enumerate(metric.bucket_bounds):
                cumulative += bucket_counts[i] if i < len(bucket_counts) else 0
                le_label = f'le="{self._format_value(bound)}"'
                if base_label_str:
                    # Insert le label inside existing braces
                    combined = base_label_str[1:-1] + f",{le_label}"
                    lines.append(f"{name}_bucket{{{combined}}} {cumulative}{ts_suffix}")
                else:
                    lines.append(f"{name}_bucket{{{le_label}}} {cumulative}{ts_suffix}")

            # +Inf bucket
            total_count = data.get("count", 0)
            le_inf = 'le="+Inf"'
            if base_label_str:
                combined = base_label_str[1:-1] + f",{le_inf}"
                lines.append(f"{name}_bucket{{{combined}}} {total_count}{ts_suffix}")
            else:
                lines.append(f"{name}_bucket{{{le_inf}}} {total_count}{ts_suffix}")

            # _count and _sum
            lines.append(
                f"{name}_count{base_label_str} {data.get('count', 0)}{ts_suffix}"
            )
            lines.append(
                f"{name}_sum{base_label_str} {self._format_value(data.get('sum', 0.0))}{ts_suffix}"
            )

    @staticmethod
    def _format_labels(label_names: tuple, label_key: tuple) -> str:
        """Format label names and values into Prometheus label string."""
        if not label_names or not label_key:
            return ""
        pairs = []
        for k, v in zip(label_names, label_key):
            # Escape special characters in label values
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            pairs.append(f'{k}="{escaped}"')
        return "{" + ",".join(pairs) + "}"

    @staticmethod
    def _format_value(value) -> str:
        """Format a numeric value for Prometheus output."""
        if isinstance(value, float):
            if value == float("inf"):
                return "+Inf"
            if value == float("-inf"):
                return "-Inf"
            # Use integer format when possible for cleanliness
            if value == int(value) and abs(value) < 1e15:
                return str(int(value))
            return f"{value:g}"
        return str(value)


def create_metrics_router():
    """Create a FastAPI router with a /metrics endpoint.

    Returns a FastAPI APIRouter. Import FastAPI only when called
    to avoid hard dependency.
    """
    from fastapi import APIRouter
    from fastapi.responses import PlainTextResponse

    router = APIRouter(tags=["observability"])
    exporter = PrometheusExporter()

    @router.get("/metrics", response_class=PlainTextResponse)
    async def metrics_endpoint():
        """Expose Prometheus metrics."""
        content = exporter.expose_metrics()
        return PlainTextResponse(
            content=content,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return router
