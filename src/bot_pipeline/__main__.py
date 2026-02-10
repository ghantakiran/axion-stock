"""Standalone CLI entry point for the Axion trading bot.

Usage:
    python -m src.bot_pipeline --paper
    python -m src.bot_pipeline --config bot_config.json
    python -m src.bot_pipeline --state-dir /data/state --log-level DEBUG
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path

from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig
from src.bot_pipeline.state_manager import PersistentStateManager
from src.trade_executor.executor import AccountState, ExecutorConfig
from src.trade_executor.router import OrderRouter

logger = logging.getLogger("axion.bot")

# Graceful shutdown flag
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — initiating graceful shutdown", sig_name)
    _shutdown = True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.bot_pipeline",
        description="Axion Trading Bot — standalone runner",
    )
    parser.add_argument(
        "--paper", action="store_true", default=True,
        help="Run in paper trading mode (default: True)",
    )
    parser.add_argument(
        "--live", action="store_true", default=False,
        help="Run in live trading mode (disables paper mode)",
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to JSON config file",
    )
    parser.add_argument(
        "--state-dir", type=str, default=".bot_state",
        help="Directory for persistent state files (default: .bot_state)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=30.0,
        help="Signal poll interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--symbols", type=str, nargs="+", default=None,
        help="Symbols to scan (default: use scanner universe)",
    )
    return parser.parse_args(argv)


def load_config(args: argparse.Namespace) -> PipelineConfig:
    """Build PipelineConfig from CLI args and optional JSON config file."""
    config = PipelineConfig()

    # Load JSON config if provided
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
            # Map JSON keys to PipelineConfig / ExecutorConfig fields
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                elif hasattr(config.executor_config, key):
                    setattr(config.executor_config, key, value)
            logger.info("Loaded config from %s", config_path)
        else:
            logger.warning("Config file %s not found — using defaults", config_path)

    # Override from CLI args
    config.state_dir = args.state_dir

    if args.live:
        config.executor_config.primary_broker = "alpaca"
    else:
        config.executor_config.primary_broker = "paper"

    return config


def create_orchestrator(config: PipelineConfig, paper_mode: bool) -> BotOrchestrator:
    """Create a fully-wired BotOrchestrator."""
    state_manager = PersistentStateManager(config.state_dir)
    order_router = OrderRouter(
        primary_broker=config.executor_config.primary_broker,
        paper_mode=paper_mode,
    )
    return BotOrchestrator(
        config=config,
        state_manager=state_manager,
        order_router=order_router,
    )


def scan_signals(symbols: list[str] | None) -> list:
    """Scan for trade signals using available detectors.

    Tries EMA detector first, then TV scanner as fallback.
    Returns a list of TradeSignal objects.
    """
    signals = []

    # Try EMA cloud detector
    try:
        from src.ema_signals.detector import EMASignalDetector
        import yfinance as yf

        detector = EMASignalDetector()
        scan_symbols = symbols or ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]

        for sym in scan_symbols:
            try:
                df = yf.download(sym, period="5d", interval="5m", progress=False)
                if df.empty:
                    continue
                detected = detector.detect(df, ticker=sym)
                signals.extend(detected)
            except Exception as e:
                logger.debug("EMA scan failed for %s: %s", sym, e)
    except ImportError:
        logger.debug("EMA detector not available")

    # Try TV scanner as supplementary source
    try:
        from src.tv_scanner.scanner import TVScanner
        scanner = TVScanner()
        tv_results = scanner.scan_momentum()
        logger.debug("TV scanner returned %d results", len(tv_results))
    except (ImportError, Exception) as e:
        logger.debug("TV scanner not available: %s", e)

    return signals


def run_signal_loop(
    orchestrator: BotOrchestrator,
    poll_interval: float,
    symbols: list[str] | None,
) -> None:
    """Main signal loop: poll → detect → process → sleep."""
    account = AccountState(
        equity=100_000.0,
        cash=50_000.0,
        buying_power=50_000.0,
        starting_equity=100_000.0,
    )

    # Lazy-load lifecycle manager for position monitoring
    lifecycle = None
    try:
        from src.bot_pipeline.lifecycle_manager import LifecycleManager
        lifecycle = LifecycleManager(orchestrator)
    except ImportError:
        logger.info("LifecycleManager not available")

    logger.info(
        "Signal loop started — polling every %.0fs for %s",
        poll_interval,
        symbols or "default universe",
    )

    while not _shutdown:
        try:
            # Scan for signals
            signals = scan_signals(symbols)
            if signals:
                logger.info("Detected %d signal(s)", len(signals))

            for sig in signals:
                if _shutdown:
                    break
                result = orchestrator.process_signal(sig, account)
                if result.success:
                    logger.info(
                        "Executed: %s %s @ $%.2f (%d shares)",
                        result.signal.direction,
                        result.signal.ticker,
                        result.position.entry_price,
                        result.position.shares,
                    )
                else:
                    logger.debug(
                        "Rejected %s %s at %s: %s",
                        sig.direction, sig.ticker,
                        result.pipeline_stage, result.rejection_reason,
                    )

            # Check exits on open positions
            if lifecycle and orchestrator.positions:
                try:
                    exits = lifecycle.check_exits({})
                    for exit_sig in exits:
                        orchestrator.close_position(
                            exit_sig.ticker, exit_sig.reason, exit_sig.exit_price,
                        )
                except Exception as e:
                    logger.warning("Exit check failed: %s", e)

        except Exception as e:
            logger.error("Signal loop error: %s", e, exc_info=True)

        # Sleep with early-exit check
        for _ in range(int(poll_interval)):
            if _shutdown:
                break
            time.sleep(1)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    paper_mode = not args.live

    # Banner
    logger.info("=" * 60)
    logger.info("  Axion Trading Bot")
    logger.info("  Mode: %s", "PAPER" if paper_mode else "LIVE")
    logger.info("  State dir: %s", args.state_dir)
    logger.info("  Poll interval: %.0fs", args.poll_interval)
    if args.symbols:
        logger.info("  Symbols: %s", ", ".join(args.symbols))
    if args.config:
        logger.info("  Config: %s", args.config)
    logger.info("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Build config and orchestrator
    config = load_config(args)
    orchestrator = create_orchestrator(config, paper_mode)

    if orchestrator._state.kill_switch_active:
        logger.warning(
            "Kill switch is ACTIVE: %s — deactivate before running",
            orchestrator._state.kill_switch_reason,
        )
        return 1

    # Run the signal loop
    try:
        run_signal_loop(orchestrator, args.poll_interval, args.symbols)
    finally:
        # Graceful shutdown: close all positions
        logger.info("Shutting down — closing %d open position(s)", len(orchestrator.positions))
        for pos in list(orchestrator.positions):
            orchestrator.close_position(pos.ticker, "graceful_shutdown", pos.current_price)
        logger.info("Bot shutdown complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
