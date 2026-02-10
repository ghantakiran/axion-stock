"""Blockchain Settlement Dashboard.

4 tabs: Settlement Status, Transaction Monitor, Chain Activity, Configuration.
Tracks on-chain settlements, transactions, atomic swaps, and network health.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Blockchain Settlement", page_icon="", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("Blockchain Settlement")
st.caption("On-chain settlement tracking, transaction monitoring, and network configuration")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ---- Try importing real module ----
_module_available = False
try:
    from src.blockchain import (
        BlockchainNetwork,
        SettlementStatus,
        TokenStandard,
        BlockchainConfig,
        DEFAULT_BLOCKCHAIN_CONFIG,
        BlockchainTransaction,
        SettlementRecord,
        SmartContractInfo,
        TokenTransfer,
        AtomicSwap,
        SettlementSummary,
        SettlementEngine,
        TransactionMonitor,
    )
    _module_available = True
except ImportError:
    st.warning("Blockchain module (src.blockchain) is not available. Showing demo data.")

# =====================================================================
# Demo Data
# =====================================================================

np.random.seed(99)

NETWORKS = ["ethereum", "polygon", "arbitrum", "solana", "optimism", "base", "avalanche"]
STATUSES = ["initiated", "pending", "confirming", "settled", "failed", "reverted"]
SETTLEMENT_TYPES = ["instant", "deferred", "atomic_swap", "dvp", "batch"]
ASSETS = ["USDC", "USDT", "ETH", "MATIC", "SOL", "WBTC", "DAI"]

base_time = datetime(2025, 4, 10, 9, 0)

# Settlement records
n_settlements = 40
demo_settlements = pd.DataFrame({
    "settlement_id": [f"STL-{2000 + i}" for i in range(n_settlements)],
    "trade_id": [f"TRD-{5000 + i}" for i in range(n_settlements)],
    "type": np.random.choice(SETTLEMENT_TYPES, n_settlements, p=[0.40, 0.20, 0.15, 0.15, 0.10]),
    "network": np.random.choice(NETWORKS[:4], n_settlements, p=[0.40, 0.25, 0.20, 0.15]),
    "status": np.random.choice(STATUSES, n_settlements, p=[0.05, 0.10, 0.10, 0.55, 0.12, 0.08]),
    "amount": np.round(np.random.uniform(100, 50000, n_settlements), 2),
    "asset": np.random.choice(ASSETS, n_settlements),
    "gas_cost_eth": np.round(np.random.uniform(0.001, 0.05, n_settlements), 6),
    "settlement_time_s": np.random.choice(
        [None] + list(np.round(np.random.uniform(2, 600, 30), 1)),
        n_settlements,
    ),
    "retries": np.random.choice([0, 0, 0, 1, 2], n_settlements),
    "timestamp": [(base_time + timedelta(minutes=i * 15)).strftime("%Y-%m-%d %H:%M") for i in range(n_settlements)],
})

# Transaction records
n_txs = 50
tx_hashes = [f"0x{np.random.bytes(32).hex()[:64]}" for _ in range(n_txs)]
demo_transactions = pd.DataFrame({
    "tx_id": [f"TX-{3000 + i}" for i in range(n_txs)],
    "tx_hash": tx_hashes,
    "network": np.random.choice(NETWORKS[:4], n_txs),
    "from_address": [f"0x{np.random.bytes(20).hex()[:40]}" for _ in range(n_txs)],
    "to_address": [f"0x{np.random.bytes(20).hex()[:40]}" for _ in range(n_txs)],
    "value": np.round(np.random.uniform(0.1, 10000, n_txs), 4),
    "gas_used": np.random.randint(21000, 250000, n_txs),
    "gas_price_gwei": np.round(np.random.uniform(5, 80, n_txs), 1),
    "confirmations": np.random.randint(0, 100, n_txs),
    "status": np.random.choice(["settled", "pending", "confirming", "reverted"], n_txs, p=[0.60, 0.15, 0.15, 0.10]),
    "block_number": np.random.randint(18000000, 19500000, n_txs),
    "timestamp": [(base_time + timedelta(minutes=i * 8)).strftime("%Y-%m-%d %H:%M") for i in range(n_txs)],
})

# Summary stats
settled_count = len(demo_settlements[demo_settlements["status"] == "settled"])
pending_count = len(demo_settlements[demo_settlements["status"].isin(["initiated", "pending", "confirming"])])
failed_count = len(demo_settlements[demo_settlements["status"].isin(["failed", "reverted"])])
total_volume = demo_settlements["amount"].sum()
total_gas = demo_settlements["gas_cost_eth"].sum()
success_rate = settled_count / n_settlements * 100 if n_settlements > 0 else 0

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "Settlement Status",
    "Transaction Monitor",
    "Chain Activity",
    "Configuration",
])

# -- Tab 1: Settlement Status ----------------------------------------------

with tab1:
    st.subheader("Settlement Status Overview")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Settlements", n_settlements)
    m2.metric("Settled", settled_count, f"{success_rate:.0f}%")
    m3.metric("Pending", pending_count)
    m4.metric("Failed/Reverted", failed_count)

    st.divider()

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Total Volume", f"${total_volume:,.2f}")
    m6.metric("Total Gas Cost", f"{total_gas:.4f} ETH")
    settled_times = demo_settlements[demo_settlements["settlement_time_s"].notna()]["settlement_time_s"].astype(float)
    avg_time = settled_times.mean() if len(settled_times) > 0 else 0
    m7.metric("Avg Settlement Time", f"{avg_time:.1f}s")
    m8.metric("Success Rate", f"{success_rate:.1f}%")

    st.divider()

    # Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_network = st.selectbox("Filter Network", ["All"] + sorted(set(NETWORKS[:4])), key="stl_net")
    with col_f2:
        filter_status = st.selectbox("Filter Status", ["All"] + sorted(STATUSES), key="stl_status")
    with col_f3:
        filter_type = st.selectbox("Filter Type", ["All"] + sorted(SETTLEMENT_TYPES), key="stl_type")

    filtered = demo_settlements.copy()
    if filter_network != "All":
        filtered = filtered[filtered["network"] == filter_network]
    if filter_status != "All":
        filtered = filtered[filtered["status"] == filter_status]
    if filter_type != "All":
        filtered = filtered[filtered["type"] == filter_type]

    st.dataframe(filtered, use_container_width=True)

    st.divider()

    st.subheader("Settlement Status Distribution")
    status_counts = demo_settlements["status"].value_counts()
    st.bar_chart(status_counts)

    st.divider()

    st.subheader("Failed Settlements")
    failed_df = demo_settlements[demo_settlements["status"].isin(["failed", "reverted"])]
    if len(failed_df) > 0:
        st.dataframe(failed_df, use_container_width=True)
        retry_eligible = failed_df[failed_df["retries"] < 3]
        if len(retry_eligible) > 0:
            st.info(f"{len(retry_eligible)} settlement(s) eligible for retry (retries < 3).")
    else:
        st.success("No failed settlements.")


# -- Tab 2: Transaction Monitor --------------------------------------------

with tab2:
    st.subheader("Transaction Monitor")

    pending_txs = demo_transactions[demo_transactions["status"].isin(["pending", "confirming"])]
    confirmed_txs = demo_transactions[demo_transactions["status"] == "settled"]
    reverted_txs = demo_transactions[demo_transactions["status"] == "reverted"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Transactions", n_txs)
    m2.metric("Confirmed", len(confirmed_txs))
    m3.metric("Pending/Confirming", len(pending_txs))
    m4.metric("Reverted", len(reverted_txs))

    st.divider()

    # Pending transactions (priority view)
    st.subheader("Pending Transactions")
    if len(pending_txs) > 0:
        st.dataframe(
            pending_txs[["tx_id", "tx_hash", "network", "value", "confirmations", "status", "timestamp"]],
            use_container_width=True,
        )
    else:
        st.success("No pending transactions.")

    st.divider()

    # All transactions
    st.subheader("All Transactions")
    tx_filter_net = st.selectbox("Network", ["All"] + sorted(set(NETWORKS[:4])), key="tx_net")
    tx_display = demo_transactions.copy()
    if tx_filter_net != "All":
        tx_display = tx_display[tx_display["network"] == tx_filter_net]

    st.dataframe(
        tx_display[["tx_id", "tx_hash", "network", "value", "gas_used", "gas_price_gwei", "confirmations", "status", "block_number", "timestamp"]],
        use_container_width=True,
    )

    st.divider()

    # Reverted transactions
    st.subheader("Reverted Transactions")
    if len(reverted_txs) > 0:
        st.dataframe(reverted_txs, use_container_width=True)
        st.error(f"{len(reverted_txs)} transaction(s) reverted -- review for potential issues.")
    else:
        st.success("No reverted transactions.")


# -- Tab 3: Chain Activity -------------------------------------------------

with tab3:
    st.subheader("Chain Activity Overview")

    # Network breakdown
    st.subheader("Activity by Network")
    network_stats = []
    for net in sorted(set(NETWORKS[:4])):
        net_settlements = demo_settlements[demo_settlements["network"] == net]
        net_txs = demo_transactions[demo_transactions["network"] == net]
        settled_net = net_settlements[net_settlements["status"] == "settled"]
        network_stats.append({
            "Network": net.title(),
            "Settlements": len(net_settlements),
            "Transactions": len(net_txs),
            "Volume ($)": f"${net_settlements['amount'].sum():,.2f}",
            "Success Rate": f"{len(settled_net) / len(net_settlements) * 100:.0f}%" if len(net_settlements) > 0 else "N/A",
            "Avg Gas (gwei)": f"{net_txs['gas_price_gwei'].mean():.1f}" if len(net_txs) > 0 else "N/A",
        })
    st.dataframe(pd.DataFrame(network_stats), use_container_width=True)

    st.divider()

    # Volume by network
    st.subheader("Settlement Volume by Network")
    vol_by_net = demo_settlements.groupby("network")["amount"].sum().sort_values(ascending=True)
    st.bar_chart(vol_by_net)

    st.divider()

    # Settlement type breakdown
    st.subheader("Settlement Type Distribution")
    type_counts = demo_settlements["type"].value_counts()
    st.bar_chart(type_counts)

    st.divider()

    # Atomic swap tracking
    st.subheader("Atomic Swaps")
    n_swaps = 8
    demo_swaps = pd.DataFrame({
        "swap_id": [f"SWP-{100 + i}" for i in range(n_swaps)],
        "initiator": [f"0x{np.random.bytes(20).hex()[:12]}..." for _ in range(n_swaps)],
        "participant": [f"0x{np.random.bytes(20).hex()[:12]}..." for _ in range(n_swaps)],
        "send": [f"{np.random.uniform(0.5, 10):.2f} ETH" for _ in range(n_swaps)],
        "receive": [f"{np.random.uniform(500, 20000):.2f} USDC" for _ in range(n_swaps)],
        "exchange_rate": np.round(np.random.uniform(1800, 3200, n_swaps), 2),
        "status": np.random.choice(["settled", "initiated", "pending"], n_swaps, p=[0.6, 0.2, 0.2]),
        "timelock_s": np.random.choice([1800, 3600, 7200], n_swaps),
    })
    st.dataframe(demo_swaps, use_container_width=True)

    st.divider()

    # Gas cost analysis
    st.subheader("Gas Cost Trend")
    gas_trend = pd.DataFrame({
        "Avg Gas Price (gwei)": np.round(np.random.uniform(10, 60, 20), 1),
    }, index=range(20))
    st.line_chart(gas_trend)


# -- Tab 4: Configuration --------------------------------------------------

with tab4:
    st.subheader("Blockchain Configuration")

    if _module_available:
        try:
            config = DEFAULT_BLOCKCHAIN_CONFIG
            st.success("Blockchain configuration loaded from module.")
            config_enabled = config.enabled
            config_network = config.default_network.value
            config_max_gas = config.max_gas_price_gwei
            config_timeout = config.settlement_timeout_seconds
            config_retry = config.auto_retry_failed
            config_max_retries = config.max_retries
            config_batch = config.batch_settlement_threshold
        except Exception:
            config_enabled = True
            config_network = "ethereum"
            config_max_gas = 100.0
            config_timeout = 3600
            config_retry = True
            config_max_retries = 3
            config_batch = 10
    else:
        config_enabled = True
        config_network = "ethereum"
        config_max_gas = 100.0
        config_timeout = 3600
        config_retry = True
        config_max_retries = 3
        config_batch = 10

    st.subheader("Current Settings")
    settings_data = pd.DataFrame({
        "Setting": [
            "Enabled", "Default Network", "Max Gas Price (gwei)",
            "Settlement Timeout (s)", "Auto Retry Failed",
            "Max Retries", "Batch Threshold",
        ],
        "Value": [
            str(config_enabled), config_network.title(), str(config_max_gas),
            str(config_timeout), str(config_retry),
            str(config_max_retries), str(config_batch),
        ],
    })
    st.dataframe(settings_data, use_container_width=True)

    st.divider()

    # Network configurations
    st.subheader("Supported Network Configurations")
    net_configs = pd.DataFrame({
        "Network": ["Ethereum", "Polygon", "Arbitrum", "Solana", "Optimism", "Base", "Avalanche"],
        "Chain ID": [1, 137, 42161, 0, 10, 8453, 43114],
        "Block Time (s)": [12, 2, 0.3, 0.4, 2, 2, 2],
        "Confirmations": [12, 64, 1, 32, 10, 10, 12],
        "Native Token": ["ETH", "MATIC", "ETH", "SOL", "ETH", "ETH", "AVAX"],
        "Status": ["Active", "Active", "Active", "Active", "Active", "Active", "Active"],
    })
    st.dataframe(net_configs, use_container_width=True)

    st.divider()

    # Gas estimation
    st.subheader("Gas Estimation Tool")
    est_network = st.selectbox(
        "Select Network for Estimate",
        ["Ethereum", "Polygon", "Arbitrum", "Solana"],
        key="gas_est_net",
    )

    gas_estimates = {
        "Ethereum": {"gas": 65000, "price": 30.0, "confirms": 12, "time": 144},
        "Polygon": {"gas": 65000, "price": 50.0, "confirms": 64, "time": 128},
        "Arbitrum": {"gas": 65000, "price": 0.1, "confirms": 1, "time": 0.3},
        "Solana": {"gas": 5000, "price": 0.0, "confirms": 32, "time": 12.8},
    }

    est = gas_estimates[est_network]
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Estimated Gas", f"{est['gas']:,}")
    e2.metric("Gas Price", f"{est['price']} gwei")
    cost_eth = (est["gas"] * est["price"]) / 1e9
    e3.metric("Estimated Cost", f"{cost_eth:.8f} ETH")
    e4.metric("Est. Time", f"{est['time']:.1f}s ({est['confirms']} confirms)")

    st.divider()

    # Smart contracts
    st.subheader("Deployed Smart Contracts")
    contracts = pd.DataFrame({
        "Name": ["SettlementV1", "AtomicSwapHTLC", "TokenVault", "BatchProcessor"],
        "Network": ["Ethereum", "Ethereum", "Polygon", "Arbitrum"],
        "Address": [
            "0x1a2b3c...4d5e6f",
            "0x7g8h9i...0j1k2l",
            "0x3m4n5o...6p7q8r",
            "0x9s0t1u...2v3w4x",
        ],
        "Version": ["1.0", "1.2", "1.0", "1.1"],
        "Verified": [True, True, True, False],
        "Active": [True, True, True, True],
    })
    st.dataframe(contracts, use_container_width=True)
