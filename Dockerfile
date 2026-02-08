# =============================================================================
# Axion Trading Platform — Multi-stage Production Dockerfile
# =============================================================================
# Stage 1: Build dependencies and wheel cache
# Stage 2: Lightweight runtime with non-root user
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — Builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Build wheels into /build/wheels
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir=/build/wheels -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 — Runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL maintainer="Axion Platform <ops@axion.dev>"
LABEL description="Axion algorithmic trading platform"

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels from builder and install
COPY --from=builder /build/wheels /tmp/wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r requirements.txt \
    && rm -rf /tmp/wheels

# Copy application code
COPY . .

# Create cache directory
RUN mkdir -p cache

# Create non-root user for security
RUN groupadd --gid 1000 axion \
    && useradd --uid 1000 --gid axion --shell /bin/bash --create-home axion \
    && chown -R axion:axion /app

USER axion

# Expose default ports (Streamlit 8501, FastAPI 8000)
EXPOSE 8501 8000

# Health check — defaults to Streamlit; override per service in docker-compose
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Default command: Streamlit dashboard
# Override in docker-compose for api/worker services
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
