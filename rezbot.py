#!/usr/bin/env python3
"""Rezbot - Cryptocurrency Trading Bot

Entry point for the trading bot. Uses the refactored architecture
with thread-safe collections and process pools for CPU-bound operations.
"""

import argparse
import signal
import sys
import logging

# Legacy imports for backwards compatibility
from src import *
from src.threaded_manager import ThreadedManager
from src.threaded_atrader import ThreadedATrader
from src.config import ConfigManager
from src.strategies import (
    PullbackStrategy,
    PullbackReversalStrategy,
    VolatilityStrategy,
    StrategyParams,
    Strategy,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Rezbot - Cryptocurrency Trading Bot"
    )
    parser.add_argument("-r", "--rate", default=1, type=int,
                        help="Update rate (debugging)")
    parser.add_argument("-sl", "--stoploss", default=-0.2, type=float,
                        help="Stop loss percentage (negative)")
    parser.add_argument("-tp", "--takeprofit", default=6, type=float,
                        help="Take profit percentage (positive)")
    parser.add_argument("-ew", "--entry_window", default=1, type=int,
                        help="Entry confirmation window")
    parser.add_argument("-xw", "--exit_window", default=0, type=int,
                        help="Exit confirmation window")
    parser.add_argument("-L", "--leverage", default=5, type=int,
                        help="Trading leverage")
    parser.add_argument("-R", "--is_real", action="store_true",
                        help="Use real trading (not test mode)")
    parser.add_argument("-Q", "--qty", default=1, type=float,
                        help="Base quantity")
    parser.add_argument("-S", "--symbol", default="sandusdt", type=str,
                        help="Trading symbol")
    parser.add_argument("-tf", "--timeframe", default="30m", type=str,
                        help="Trading timeframe")
    parser.add_argument("-s", "--strategy", default=1, type=int,
                        choices=[1, 2, 3],
                        help="Strategy: 1=Pullback, 2=PullbackReversal, 3=Volatility")
    parser.add_argument("-w1", "--window_1", default=5, type=int,
                        help="EMA window for indicators")
    parser.add_argument("-m1", "--multiplier_1", default=1.2, type=float,
                        help="Standard deviation multiplier")
    parser.add_argument("-p", "--plot", action="store_true",
                        help="Enable live Plotly dashboard")
    parser.add_argument("--plot-port", default=8050, type=int,
                        help="Port for live plot dashboard (default: 8050)")
    parser.add_argument("--plot-interval", default=1000, type=int,
                        help="Plot update interval in ms (default: 1000)")
    return parser.parse_args()


def create_strategy(args) -> Strategy:
    """Create strategy instance from arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        Strategy instance
    """
    params = StrategyParams(
        name=_get_strategy_name(args.strategy),
        timeframe=args.timeframe,
        take_profit=args.takeprofit,
        stoploss=args.stoploss,
        entry_window=args.entry_window,
        exit_window=args.exit_window
    )

    strategy_map = {
        1: PullbackStrategy,
        2: PullbackReversalStrategy,
        3: VolatilityStrategy,
    }

    strategy_class = strategy_map[args.strategy]
    return strategy_class(params)


def _get_strategy_name(strategy_id: int) -> str:
    """Get strategy name from ID.

    Args:
        strategy_id: Strategy selection from command line

    Returns:
        Strategy name string
    """
    names = {
        1: "pullback",
        2: "pullback_reversal",
        3: "volatility",
    }
    return names.get(strategy_id, "pullback")


def signal_handler(sig, frame, manager: ThreadedManager):
    """Handle shutdown signals gracefully.

    Args:
        sig: Signal number
        frame: Current stack frame
        manager: ThreadedManager instance to shutdown
    """
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    manager.stop(timeout=30)
    sys.exit(0)


def main():
    """Main entry point."""
    args = parse_arguments()

    # Log configuration
    logger.info(f"Starting Rezbot with strategy {_get_strategy_name(args.strategy)}")
    logger.info(f"Symbol: {args.symbol}, Timeframe: {args.timeframe}")
    logger.info(f"Leverage: {args.leverage}x, Real Trading: {args.is_real}")

    try:
        # Initialize configuration (loads from environment variables)
        config = ConfigManager().get_api_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set API_KEY and API_SECRET environment variables")
        sys.exit(1)

    # Initialize manager
    manager = ThreadedManager(
        api_config=config,
        tf=args.timeframe,
        rate=args.rate
    )

    # Start process pool for CPU-bound operations
    manager.start_process_pool()

    # Create strategy
    strategy = create_strategy(args)

    # Setup signal handlers for graceful shutdown
    def handler(sig, frame):
        signal_handler(sig, frame, manager)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    # Available symbols
    symbols = ["ethusdt", "bnbusdt", "btcusdt", "adausdt", "axsusdt", "dotusdt"]

    # Start trader
    symbol = args.symbol if args.symbol else symbols[0]

    try:
        trader = manager.start_trader(
            strategy=strategy,
            symbol=symbol,
            leverage=args.leverage,
            is_real=args.is_real,
            qty=args.qty,
            w1=args.window_1,
            m1=args.multiplier_1
        )

        if trader is None:
            logger.error("Failed to start trader")
            sys.exit(1)

        logger.info(f"Trader started: {trader.name}")

        # Start live plotter if requested
        if args.plot:
            plotter = manager.start_live_plotter(
                trader,
                update_interval_ms=args.plot_interval,
                port=args.plot_port
            )
            if plotter:
                logger.info(f"Live plotter started at http://127.0.0.1:{args.plot_port}")
            else:
                logger.warning("Could not start live plotter (plotly/dash not installed)")

        logger.info("Press Ctrl+C to stop...")

        # Keep main thread alive
        while trader.is_alive():
            trader.join(timeout=1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        manager.stop(timeout=30)
        sys.exit(1)


if __name__ == "__main__":
    main()
