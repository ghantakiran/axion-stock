# PRD-15: Performance Attribution System

## Overview

Comprehensive performance attribution and reporting system that decomposes portfolio returns into explainable components using Brinson-Fachler and factor-based models, with benchmark comparison and professional tear sheet generation.

---

## Components

### 1. Brinson-Fachler Attribution
- Allocation effect: Over/underweight in outperforming sectors
- Selection effect: Stock picking within sectors
- Interaction effect: Combined allocation + selection
- Multi-period linking (Carino method)
- Sector-level and security-level decomposition

### 2. Factor Attribution
- Decompose returns by factor exposures (value, momentum, quality, etc.)
- Factor return contribution = factor exposure × factor return
- Specific/residual return (alpha)
- Factor timing analysis

### 3. Benchmark Comparison
- Tracking error (annualized)
- Information ratio
- Active share
- Up/down capture ratios
- Relative returns by period

### 4. Performance Metrics
- Return: total, annualized, CAGR
- Risk: volatility, Sortino, Calmar, max drawdown
- Risk-adjusted: Sharpe, Treynor, Jensen's alpha
- Drawdown analysis: depth, duration, recovery

### 5. Tear Sheet Generation
- Summary statistics
- Return distribution (histogram, QQ plot data)
- Rolling metrics (Sharpe, beta, volatility)
- Drawdown timeline
- Monthly/yearly return heatmap data
- Sector/factor contribution breakdown

### 6. Database Tables
- `attribution_reports`: Stored attribution analysis results
- `benchmark_definitions`: Benchmark configurations
- `performance_snapshots`: Periodic performance captures
- `tear_sheets`: Generated tear sheet data

### 7. Success Metrics
- Attribution computation: <5s for 1-year history
- Report accuracy: allocation + selection + interaction = total active return

---

*Priority: P1 | Phase: 7*
