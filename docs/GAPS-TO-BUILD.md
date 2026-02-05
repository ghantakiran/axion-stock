# Gaps to Build — Workspace Analysis

*Generated from PRDs, app pages, src modules, API routes, migrations, and tests.*

---

## 1. Missing App Pages (PRD specifies dashboard but no page)

| PRD | Feature | Gap |
|-----|---------|-----|
| **PRD-34** | Trade Journal | No `app/pages/trade_journal.py`. PRD requires trade entry (setup, emotions, lessons), analytics dashboard (equity curve, win rate by setup, emotion vs P&L), and review system. Backend exists: `src/execution/journal.py` (TradeJournal). |
| **PRD-54** | Liquidity Risk Management | No `app/pages/liquidity_risk.py`. PRD extends liquidity with redemption risk modeler and LaVaR; `src/liquidity/redemption.py` and `lavar.py` exist. Dashboard for redemption scenarios, LaVaR, and liquidation schedule is missing. |

---

## 2. API Route Gaps (no REST exposure)

The API (`src/api/app.py`) currently mounts: `market_data`, `factors`, `portfolio`, `trading`, `ai`, `options`, `backtesting`. Missing route modules or endpoints for:

| Area | Gap |
|------|-----|
| **Order Flow** | No `/orderflow` or `/flow` routes (imbalance, blocks, pressure, smart money). |
| **Alerts** | No `/alerts` routes (create/update/delete alerts, alert history, notification preferences). |
| **Scanner** | No `/scanner` routes (run scan, presets, unusual activity). |
| **Screener** | Factors has `/screen/results`; no dedicated screener CRUD or saved screens. |
| **Rebalancing** | Portfolio has `POST /rebalance`; no rebalancing-specific routes (plans, drift, schedule). |
| **Trade Journal** | No `/journal` routes (trades, analytics, reviews). |
| **Sentiment** | AI has `GET /sentiment/{symbol}`; no bulk sentiment or sentiment history. |
| **Liquidity Risk** | No `/liquidity/risk` or LaVaR/redemption endpoints. |

---

## 3. Dashboard Data Gaps (demo/sample vs live/DB)

Many app pages rely on **demo/sample/mock data** instead of live market data or DB-backed history. Gaps:

- **Live or DB-backed data integration** for:
  - `orderflow.py` — sample data + optional DB; real-time order book/tick feed not wired.
  - `sectors.py` — `generate_sample_rankings` / `generate_sample_cycle`.
  - `insider.py` — `generate_sample_transactions` / `generate_sample_institutional`.
  - `economic.py` — `generate_sample_calendar` / `generate_sample_history` / `generate_sample_fed_data`.
  - `scanner.py` — `get_sample_market_data()`.
  - `watchlist.py` — `create_demo_watchlist`.
  - `dividends.py` — `get_demo_holdings`, `generate_sample_calendar`.
  - `earnings.py` — `generate_sample_calendar` / `generate_sample_estimates` / sample quality.
  - `scenarios.py` — `get_demo_portfolio()`.
  - `screener.py` — `get_demo_stock_data()`.
  - `research.py` — `get_demo_data(symbol)`.
  - `bots.py` — demo DCA/rebalance bots, `demo_market_data`.
  - `news.py` — demo articles, demo filings, demo alerts.
  - `tax.py` — demo lots, demo prices.
  - `backtest.py` / `backtesting.py` — demo/synthetic data, demo results.
  - `optimizer.py` — synthetic data, demo X-ray, demo harvest candidates.
  - `sentiment.py` — `get_demo_composite`, news, social, insider.
  - `ml_models.py` — `get_demo_predictions`, regime, feature importance, IC history.
  - `risk.py` — `demo_mode`, `get_demo_data()`.
  - `options.py` — demo IV surface, demo activity.
  - `multi_asset.py` — demo position summary.
  - `api_dashboard.py` — demo keys, webhooks, usage.

**Recommended direction:** Prefer loading from DB when available (e.g. orderflow repository pattern), then fall back to sample data; add optional “live data” path via data service where applicable.

---

## 4. Database / Persistence Gaps

| PRD / Area | Specified Tables / Persistence | Status |
|------------|--------------------------------|--------|
| **PRD-34 Trade Journal** | Trade entries, setup, emotions, screenshots, analytics | `trade_orders` / `trade_executions` exist in db; no dedicated journal tables (e.g. `trade_journal_entries`, `trade_setups`, `emotion_logs`) or ORM for PRD-34 model. |
| **PRD-54 Liquidity Risk** | RedemptionScenario, LiquidityBuffer, LiquidationSchedule, LaVaR | No migration or ORM for redemption/LaVaR tables. |
| **PRD-50 Alternative Data** | `satellite_signals`, `web_traffic_snapshots`, `social_mentions`, `alt_data_composites` | Migration 036 (alternative_data) exists; verify ORM models in `src/db/models.py` and repo usage in `app/pages/altdata.py`. |
| **PRD-42 Order Flow** | `orderbook_snapshots`, `block_trades`, `flow_pressure`, `smart_money_signals` | Migration 028 + ORM + `src/orderflow/repository.py` implemented. |
| **PRD-13 Alerts** | `alerts`, `alert_history`, `notifications`, `notification_preferences` | Migration 014 exists; verify ORM and alert service persistence. |

---

## 5. Master Roadmap Index Gap

**PRD-00-MASTER-ROADMAP.md** index table lists only **PRD-01 through PRD-12**. PRD-13 through PRD-54 are not in the roadmap index. **Gap:** Update the PRD index table to include all PRDs (13–54) with title, priority, and phase for traceability.

---

## 6. Test Gaps

| Area | Gap |
|------|-----|
| **Trade Journal** | No `tests/test_trade_journal.py` (or test module for PRD-34 dashboard + extended journal model). |
| **Liquidity Risk** | `tests/test_liquidity_risk.py` exists; ensure it covers PRD-54 (redemption, LaVaR). |
| **Order Flow** | `tests/test_orderflow.py` exists; add tests for `src/orderflow/repository.py` (save/load with DB) if not covered. |
| **API** | Add API tests for any new routes (orderflow, alerts, scanner, journal, etc.) when built. |

---

## 7. Feature Completeness (PRD vs implementation)

| PRD | Summary gap |
|-----|-------------|
| **PRD-34 Trade Journal** | Full trade model (setup, strategy, emotions, lessons_learned, screenshots), tagging, analytics dashboard, and review system not implemented in UI or dedicated persistence. |
| **PRD-54 Liquidity Risk** | Backend (redemption, lavar) present; dashboard and DB persistence for scenarios/buffers/LaVaR missing. |
| **PRD-50 Alternative Data** | Satellite, webtraffic, social, scoring in `src/altdata`; confirm altdata dashboard and DB persistence use them. |
| **PRD-37 Correlation Matrix** | `src/correlation` exists; confirm dashboard supports rolling correlations, pair discovery, regimes, diversification scoring per PRD. |
| **PRD-51 Portfolio Attribution** | `src/attribution` has Brinson, risk, factor, performance; confirm dashboard exposes all and supports multi-period linking. |

---

## 8. Prioritized Gap List (suggested build order)

1. **Trade Journal Dashboard** — `app/pages/trade_journal.py` + optional journal-specific tables/ORM (PRD-34).
2. **Liquidity Risk Dashboard** — `app/pages/liquidity_risk.py` + persistence for redemption/LaVaR if required (PRD-54).
3. **API: Order Flow** — `src/api/routes/orderflow.py` (or extend existing router) for imbalance/blocks/pressure/smart money.
4. **API: Alerts** — `src/api/routes/alerts.py` for alert CRUD, history, preferences (PRD-13).
5. **API: Scanner** — `src/api/routes/scanner.py` for run scan, presets (PRD-30).
6. **Live/DB-backed data** — Replace or complement demo data on high-traffic pages (screener, scanner, risk, sentiment, orderflow) with DB + data service.
7. **Master roadmap** — Update PRD-00 index with PRD-13 through PRD-54.
8. **Tests** — `test_trade_journal.py`; repository tests for orderflow; API tests for new routes.

---

*Last updated: February 2026*
