# PRD-104: Production Docker & Environment Configuration

## Overview
Upgrade Docker Compose to production-ready with all platform services, monitoring stack, health checks, and a documented .env.example for developer onboarding.

## Components

### 1. Enhanced Docker Compose (`docker-compose.yml`)
- **postgres**: TimescaleDB with init scripts, persistent volume, health check
- **redis**: Redis 7 with config file, persistent volume, health check
- **app**: Axion Streamlit dashboard, depends on postgres + redis
- **api**: FastAPI server with uvicorn, auto-reload in dev
- **worker**: Background job processor (bot scheduler, data pipeline)
- **prometheus**: Metrics collection, scrape app + api + node_exporter
- **grafana**: Dashboard visualization, pre-configured datasources

### 2. Multi-stage Dockerfile (`Dockerfile`)
- Build stage: install dependencies, compile requirements
- Runtime stage: slim image, non-root user, security hardened
- Proper signal handling for graceful shutdown

### 3. Environment Template (`.env.example`)
- All AXION_ prefixed settings with descriptions
- Grouped by: Database, Redis, API Keys, Feature Flags, Logging, Security
- Sensible development defaults, clear markers for required production values

### 4. Prometheus Configuration (`infrastructure/prometheus/prometheus.yml`)
- Scrape config for API and app metrics endpoints
- Alert rules for key SLOs

### 5. Grafana Provisioning (`infrastructure/grafana/`)
- Datasource auto-provisioning for Prometheus
- Pre-built dashboard JSON for system overview

## Security
- No secrets in docker-compose, all via .env
- Non-root container users
- Read-only filesystem where possible
