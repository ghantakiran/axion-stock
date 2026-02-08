# PRD-108: Integration & Load Testing Framework

## Overview
Build a comprehensive testing framework with integration test base classes, mock service infrastructure, load testing scenarios, and performance benchmarks. The current test suite has 4,010 unit tests but lacks integration testing patterns, shared fixtures, and load testing capabilities.

## Goals
1. **Integration Test Base** — Base classes for tests that need database, Redis, or API client
2. **Mock Services** — Configurable mock servers for brokers, market data providers, and external APIs
3. **Load Testing** — Scenario-based load test framework for API endpoints and data pipelines
4. **Test Fixtures** — Shared pytest fixtures for common test data (portfolios, orders, market data)
5. **Performance Benchmarks** — Automated benchmark suite with regression detection

## Technical Design

### Components
- `src/testing/__init__.py` — Public API exports
- `src/testing/config.py` — Test configuration dataclass
- `src/testing/base.py` — IntegrationTestBase, APITestBase, DatabaseTestBase classes
- `src/testing/mocks.py` — MockBroker, MockMarketData, MockRedis service implementations
- `src/testing/fixtures.py` — Factory functions for test data (orders, portfolios, signals)
- `src/testing/load.py` — LoadTestRunner, LoadScenario, load test result collection
- `src/testing/benchmarks.py` — BenchmarkSuite, BenchmarkResult, regression detection

### Database
- `test_runs` table for storing test/benchmark results over time

### Dashboard
- Test coverage trends, benchmark results, load test visualization, mock service status

## Success Criteria
- Integration test base classes reduce boilerplate by 50%+
- Load testing can simulate 100+ concurrent users
- Benchmark results are tracked over time for regression detection
- 40+ tests for the testing framework itself
