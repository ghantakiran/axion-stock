"""Navigation configuration for Axion platform.

Defines all page groupings, display names, and icons for st.navigation().
All 156 pages organized into 10 collapsible sections.
"""

import streamlit as st


def build_navigation_pages() -> dict[str, list]:
    """Build the navigation pages dictionary.

    Returns a dict mapping section names to lists of st.Page objects.
    Must be called within a Streamlit execution context.
    """
    return {
        # ── Home ─────────────────────────────────────────────
        "": [
            st.Page("pages/home.py", title="AI Chat", icon=":material/smart_toy:", default=True),
        ],

        # ── Market Analysis ──────────────────────────────────
        "Market Analysis": [
            st.Page("pages/screener.py", title="Stock Screener", icon=":material/filter_list:"),
            st.Page("pages/scanner.py", title="Market Scanner", icon=":material/radar:"),
            st.Page("pages/charting.py", title="Advanced Charting", icon=":material/candlestick_chart:"),
            st.Page("pages/breadth.py", title="Market Breadth", icon=":material/stacked_bar_chart:"),
            st.Page("pages/sectors.py", title="Sector Rotation", icon=":material/donut_large:"),
            st.Page("pages/correlation.py", title="Correlation Matrix", icon=":material/grid_on:"),
            st.Page("pages/volatility.py", title="Volatility Analysis", icon=":material/show_chart:"),
            st.Page("pages/regime.py", title="Regime Detection", icon=":material/timeline:"),
            st.Page("pages/regime_signals.py", title="Regime Signals", icon=":material/signal_cellular_alt:"),
            st.Page("pages/macro.py", title="Macro Indicators", icon=":material/public:"),
            st.Page("pages/economic.py", title="Economic Calendar", icon=":material/event:"),
            st.Page("pages/earnings.py", title="Earnings Calendar", icon=":material/date_range:"),
            st.Page("pages/dividends.py", title="Dividend Tracker", icon=":material/payments:"),
            st.Page("pages/events.py", title="Event Analytics", icon=":material/celebration:"),
            st.Page("pages/insider.py", title="Insider Trading", icon=":material/person_search:"),
            st.Page("pages/esg.py", title="ESG Scoring", icon=":material/eco:"),
        ],

        # ── Sentiment & Data ─────────────────────────────────
        "Sentiment & Data": [
            st.Page("pages/sentiment.py", title="Sentiment Analysis", icon=":material/sentiment_satisfied:"),
            st.Page("pages/news.py", title="News & Events", icon=":material/newspaper:"),
            st.Page("pages/altdata.py", title="Alternative Data", icon=":material/satellite_alt:"),
            st.Page("pages/social.py", title="Social Trading", icon=":material/groups:"),
            st.Page("pages/social_crawler.py", title="Social Crawler", icon=":material/bug_report:"),
            st.Page("pages/social_intelligence.py", title="Social Intelligence", icon=":material/psychology:"),
            st.Page("pages/social_backtester.py", title="Social Backtester", icon=":material/science:"),
            st.Page("pages/influencer_intel.py", title="Influencer Intel", icon=":material/trending_up:"),
            st.Page("pages/alert_network.py", title="Alert Network", icon=":material/campaign:"),
            st.Page("pages/crowding.py", title="Crowding Analysis", icon=":material/people:"),
            st.Page("pages/fundflow.py", title="Fund Flow", icon=":material/waterfall_chart:"),
            st.Page("pages/streaming.py", title="Real-time Streaming", icon=":material/stream:"),
            st.Page("pages/signal_streaming.py", title="Signal Streaming", icon=":material/sensors:"),
        ],

        # ── Trading & Execution ──────────────────────────────
        "Trading & Execution": [
            st.Page("pages/trading.py", title="Trading", icon=":material/trending_up:"),
            st.Page("pages/execution.py", title="Execution Analytics", icon=":material/speed:"),
            st.Page("pages/paper_trading.py", title="Paper Trading", icon=":material/edit_note:"),
            st.Page("pages/smart_router.py", title="Smart Router", icon=":material/route:"),
            st.Page("pages/brokers.py", title="Broker Integrations", icon=":material/handshake:"),
            st.Page("pages/orderflow.py", title="Order Flow", icon=":material/swap_vert:"),
            st.Page("pages/darkpool.py", title="Dark Pool Analytics", icon=":material/visibility_off:"),
            st.Page("pages/microstructure.py", title="Market Microstructure", icon=":material/grain:"),
            st.Page("pages/position_calculator.py", title="Position Calculator", icon=":material/calculate:"),
            st.Page("pages/bots.py", title="Trading Bots", icon=":material/precision_manufacturing:"),
            st.Page("pages/copilot.py", title="AI Trading Copilot", icon=":material/assistant:"),
            st.Page("pages/agents.py", title="Agent Hub", icon=":material/hub:"),
            st.Page("pages/ema_signals.py", title="EMA Signals", icon=":material/ssid_chart:"),
            st.Page("pages/trade_executor.py", title="Trade Executor", icon=":material/bolt:"),
            st.Page("pages/options_scalper.py", title="Options Scalper", icon=":material/flash_on:"),
            st.Page("pages/bot_control.py", title="Bot Control", icon=":material/smart_toy:"),
            st.Page("pages/tv_scanner.py", title="TradingView Scanner", icon=":material/travel_explore:"),
            st.Page("pages/alpaca_live.py", title="Alpaca Live", icon=":material/bolt:"),
            st.Page("pages/robinhood_broker.py", title="Robinhood", icon=":material/savings:"),
            st.Page("pages/coinbase_broker.py", title="Coinbase", icon=":material/currency_bitcoin:"),
            st.Page("pages/schwab_broker.py", title="Schwab", icon=":material/account_balance:"),
            st.Page("pages/multi_broker.py", title="Multi-Broker", icon=":material/hub:"),
            st.Page("pages/fidelity_broker.py", title="Fidelity", icon=":material/account_balance:"),
            st.Page("pages/ibkr_broker.py", title="IBKR", icon=":material/public:"),
            st.Page("pages/tastytrade_broker.py", title="tastytrade", icon=":material/candlestick_chart:"),
            st.Page("pages/webull_broker.py", title="Webull", icon=":material/trending_up:"),
            st.Page("pages/signal_fusion.py", title="Signal Fusion", icon=":material/merge:"),
            st.Page("pages/agent_consensus.py", title="Agent Consensus", icon=":material/how_to_vote:"),
            st.Page("pages/strategy_optimizer.py", title="Strategy Optimizer", icon=":material/tune:"),
            st.Page("pages/trade_pipeline.py", title="Trade Pipeline", icon=":material/conveyor_belt:"),
            st.Page("pages/risk_manager.py", title="Risk Manager", icon=":material/shield:"),
            st.Page("pages/trade_attribution.py", title="Trade Attribution", icon=":material/link:"),
            st.Page("pages/signal_persistence.py", title="Signal Audit Trail", icon=":material/history_edu:"),
            st.Page("pages/unified_risk.py", title="Unified Risk Center", icon=":material/verified_user:"),
            st.Page("pages/strategy_selector.py", title="Strategy Selector", icon=":material/swap_calls:"),
            st.Page("pages/signal_feedback.py", title="Signal Feedback", icon=":material/autorenew:"),
            st.Page("pages/integration_pipeline.py", title="Pipeline Monitor", icon=":material/device_hub:"),
            st.Page("pages/bot_pipeline.py", title="Bot Pipeline", icon=":material/security:"),
            st.Page("pages/bot_lifecycle.py", title="Bot Lifecycle", icon=":material/cycle:"),
            st.Page("pages/bot_api.py", title="Bot API", icon=":material/api:"),
            st.Page("pages/strategy_integration.py", title="Strategy Integration", icon=":material/merge_type:"),
            st.Page("pages/bot_alerting.py", title="Bot Alerting", icon=":material/notification_important:"),
            st.Page("pages/bot_analytics.py", title="Bot Analytics", icon=":material/insights:"),
            st.Page("pages/adaptive_feedback.py", title="Adaptive Feedback", icon=":material/autorenew:"),
            st.Page("pages/strategies.py", title="Strategies", icon=":material/category:"),
            st.Page("pages/pullback_strategy.py", title="Pullback Strategy", icon=":material/trending_down:"),
            st.Page("pages/trend_day_strategy.py", title="Trend Day Strategy", icon=":material/trending_up:"),
            st.Page("pages/session_scalp_strategy.py", title="Session Scalp", icon=":material/schedule:"),
            st.Page("pages/bot_dashboard.py", title="Bot Dashboard", icon=":material/dashboard_customize:"),
            st.Page("pages/qullamaggie_breakout.py", title="Qullamaggie Breakout", icon=":material/flag:"),
            st.Page("pages/qullamaggie_ep.py", title="Qullamaggie EP", icon=":material/bolt:"),
            st.Page("pages/qullamaggie_parabolic.py", title="Parabolic Short", icon=":material/trending_down:"),
            st.Page("pages/qullamaggie_scanner.py", title="Qullamaggie Scanner", icon=":material/search:"),
        ],

        # ── Portfolio & Risk ─────────────────────────────────
        "Portfolio & Risk": [
            st.Page("pages/optimizer.py", title="Portfolio Optimizer", icon=":material/tune:"),
            st.Page("pages/rebalancing.py", title="Rebalancing", icon=":material/balance:"),
            st.Page("pages/risk.py", title="Risk Management", icon=":material/shield:"),
            st.Page("pages/tailrisk.py", title="Tail Risk Hedging", icon=":material/warning:"),
            st.Page("pages/stress_testing.py", title="Stress Testing", icon=":material/science:"),
            st.Page("pages/liquidity.py", title="Liquidity Analysis", icon=":material/water_drop:"),
            st.Page("pages/liquidity_risk.py", title="Liquidity Risk", icon=":material/water:"),
            st.Page("pages/credit.py", title="Credit Risk", icon=":material/credit_score:"),
            st.Page("pages/scenarios.py", title="Scenarios", icon=":material/ssid_chart:"),
            st.Page("pages/attribution.py", title="Attribution", icon=":material/pie_chart:"),
            st.Page("pages/performance_report.py", title="Performance Report", icon=":material/assessment:"),
            st.Page("pages/factors.py", title="Factor Engine", icon=":material/functions:"),
            st.Page("pages/factor_builder.py", title="Factor Builder", icon=":material/build:"),
            st.Page("pages/pairs.py", title="Pairs Trading", icon=":material/compare_arrows:"),
            st.Page("pages/crossasset.py", title="Cross-Asset Signals", icon=":material/swap_horiz:"),
        ],

        # ── Options & Derivatives ────────────────────────────
        "Options & Derivatives": [
            st.Page("pages/options.py", title="Options Analytics", icon=":material/candlestick_chart:"),
            st.Page("pages/options_chain.py", title="Options Chain", icon=":material/table_chart:"),
            st.Page("pages/crypto_options.py", title="Crypto Options", icon=":material/currency_bitcoin:"),
            st.Page("pages/blockchain.py", title="Blockchain Settlement", icon=":material/link:"),
        ],

        # ── ML & AI ──────────────────────────────────────────
        "ML & AI": [
            st.Page("pages/ml_models.py", title="ML Models", icon=":material/model_training:"),
            st.Page("pages/model_providers.py", title="Model Providers", icon=":material/dns:"),
            st.Page("pages/model_registry.py", title="Model Registry", icon=":material/inventory:"),
            st.Page("pages/feature_store.py", title="Feature Store", icon=":material/dataset:"),
            st.Page("pages/anomaly_detection.py", title="Anomaly Detection", icon=":material/report:"),
            st.Page("pages/regime_adaptive.py", title="Regime Adaptive", icon=":material/tune:"),
            st.Page("pages/llm_sentiment.py", title="LLM Sentiment", icon=":material/psychology:"),
        ],

        # ── Enterprise & Compliance ──────────────────────────
        "Enterprise & Compliance": [
            st.Page("pages/enterprise.py", title="Enterprise", icon=":material/business:"),
            st.Page("pages/accounts.py", title="Accounts", icon=":material/account_balance:"),
            st.Page("pages/auth.py", title="Authentication", icon=":material/lock:"),
            st.Page("pages/workspaces.py", title="Workspaces", icon=":material/workspaces:"),
            st.Page("pages/compliance.py", title="Compliance", icon=":material/verified_user:"),
            st.Page("pages/compliance_engine.py", title="Compliance Engine", icon=":material/policy:"),
            st.Page("pages/billing.py", title="Billing & Metering", icon=":material/receipt_long:"),
            st.Page("pages/multi_tenancy.py", title="Multi-Tenancy", icon=":material/apartment:"),
            st.Page("pages/reconciliation.py", title="Reconciliation", icon=":material/fact_check:"),
            st.Page("pages/workflow.py", title="Workflow Engine", icon=":material/account_tree:"),
            st.Page("pages/audit.py", title="Audit Trail", icon=":material/history:"),
            st.Page("pages/multi_asset.py", title="Multi-Asset", icon=":material/category:"),
        ],

        # ── Research & Tools ─────────────────────────────────
        "Research & Tools": [
            st.Page("pages/research.py", title="AI Research", icon=":material/biotech:"),
            st.Page("pages/backtest.py", title="Backtesting", icon=":material/replay:"),
            st.Page("pages/backtesting.py", title="Backtesting Engine", icon=":material/fast_rewind:"),
            st.Page("pages/bot_backtesting.py", title="Bot Backtesting", icon=":material/science:"),
            st.Page("pages/enhanced_backtest.py", title="Enhanced Backtesting", icon=":material/query_stats:"),
            st.Page("pages/watchlist.py", title="Watchlist", icon=":material/bookmark:"),
            st.Page("pages/alerts.py", title="Alerts", icon=":material/notifications:"),
            st.Page("pages/notifications.py", title="Notification Settings", icon=":material/notification_add:"),
            st.Page("pages/trade_journal.py", title="Trade Journal", icon=":material/menu_book:"),
            st.Page("pages/journal.py", title="Journal Analytics", icon=":material/analytics:"),
            st.Page("pages/reports.py", title="Reports", icon=":material/summarize:"),
            st.Page("pages/tax.py", title="Tax Optimization", icon=":material/request_quote:"),
            st.Page("pages/marketplace.py", title="Strategy Marketplace", icon=":material/storefront:"),
        ],

        # ── Infrastructure & DevOps ──────────────────────────
        "Infrastructure & DevOps": [
            st.Page("pages/system_dashboard.py", title="System Dashboard", icon=":material/dashboard:"),
            st.Page("pages/api_dashboard.py", title="API Dashboard", icon=":material/api:"),
            st.Page("pages/api_errors.py", title="API Errors", icon=":material/error:"),
            st.Page("pages/api_gateway.py", title="API Gateway", icon=":material/cloud:"),
            st.Page("pages/pipeline.py", title="Data Pipeline", icon=":material/sync:"),
            st.Page("pages/config_service.py", title="Configuration", icon=":material/settings:"),
            st.Page("pages/secrets_vault.py", title="Secrets Vault", icon=":material/vpn_key:"),
            st.Page("pages/logging_config.py", title="Structured Logging", icon=":material/terminal:"),
            st.Page("pages/observability.py", title="Observability", icon=":material/monitoring:"),
            st.Page("pages/alerting.py", title="Alert System", icon=":material/crisis_alert:"),
            st.Page("pages/resilience.py", title="Resilience Patterns", icon=":material/security:"),
            st.Page("pages/lifecycle.py", title="Lifecycle Mgmt", icon=":material/autorenew:"),
            st.Page("pages/testing.py", title="Testing Framework", icon=":material/bug_report:"),
            st.Page("pages/migration_safety.py", title="Migration Safety", icon=":material/safety_check:"),
            st.Page("pages/deployment.py", title="Deployment", icon=":material/rocket_launch:"),
            st.Page("pages/backup.py", title="Backup & Recovery", icon=":material/backup:"),
            st.Page("pages/profiling.py", title="Perf Profiling", icon=":material/query_stats:"),
            st.Page("pages/archival.py", title="Data Archival", icon=":material/archive:"),
            st.Page("pages/ws_scaling.py", title="WebSocket Scaling", icon=":material/cable:"),
            st.Page("pages/event_bus.py", title="Event Bus", icon=":material/device_hub:"),
            st.Page("pages/data_contracts.py", title="Data Contracts", icon=":material/description:"),
            st.Page("pages/capacity.py", title="Capacity Planning", icon=":material/analytics:"),
        ],
    }
