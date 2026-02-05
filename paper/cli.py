#!/usr/bin/env python3
"""CLI for paper trading and backtesting.

This script provides a command-line interface for running paper trading
sessions and backtests with strategies.
"""

import argparse
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies import (
    PullbackStrategy,
    MacdStrategy,
    TrendReversalStrategy,
    StrategyParams
)
from src.concurrency.multiprocessing import ProcessPoolManager
from paper import (
    PaperTrader,
    PaperConfig,
    Backtester,
    BacktestConfig,
    HistoricalDataFeed,
    CSVDataFeed,
)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_strategy(args) -> tuple:
    """Create strategy instance from CLI args.

    Returns:
        Tuple of (strategy, strategy_params)
    """
    params = StrategyParams(
        name=args.strategy,
        timeframe=args.timeframe,
        take_profit=args.take_profit,
        stoploss=args.stoploss,
        entry_window=args.entry_window,
        exit_window=args.exit_window,
        macd_fast=args.macd_fast,
        macd_slow=args.macd_slow,
        macd_signal=args.macd_signal
    )

    strategy_map = {
        "pullback": PullbackStrategy,
        "macd": MacdStrategy,
        "trend_reversal": TrendReversalStrategy,
    }

    if args.strategy not in strategy_map:
        raise ValueError(f"Unknown strategy: {args.strategy}. "
                        f"Available: {list(strategy_map.keys())}")

    strategy = strategy_map[args.strategy](params)
    return strategy, params


def run_paper_trading(args):
    """Run paper trading session."""
    logger.info("Starting paper trading session...")

    # Create strategy
    strategy, params = create_strategy(args)

    # Create process pool for indicator computation
    process_pool = ProcessPoolManager(max_workers=2)
    process_pool.start()

    # Create config
    config = PaperConfig(
        symbol=args.symbol.upper(),
        timeframe=args.timeframe,
        leverage=args.leverage,
        initial_balance=args.balance,
        position_size_pct=args.position_size,
        w1=args.w1,
        m1=args.m1,
        macd_fast=params.macd_fast,
        macd_slow=params.macd_slow,
        macd_signal=params.macd_signal
    )

    # Create data feed
    if args.csv:
        data_feed = CSVDataFeed(
            symbol=args.symbol.upper(),
            timeframe=args.timeframe,
            csv_path=args.csv
        )
        # Use in simulation mode
        from paper.data_feed import DataFrameDataFeed
        data = data_feed.load_data()
        data_feed = DataFrameDataFeed(args.symbol.upper(), args.timeframe, data)
    else:
        data_feed = None  # Will use LiveSimulatedFeed

    # Create paper trader
    trader = PaperTrader(
        config=config,
        strategy=strategy,
        data_feed=data_feed
    )

    def on_trade(record):
        """Callback when trade completes."""
        logger.info(
            f"Trade closed: {record.side} | "
            f"PnL: {record.leveraged_profit:.2f}% | "
            f"Reason: {record.exit_reason}"
        )

    trader._on_trade = on_trade

    # Run for specified duration
    logger.info(f"Running paper trading for {args.duration} seconds...")
    trader.run(duration_seconds=args.duration)

    # Get and print report
    report = trader.get_report()
    report.print_summary()

    # Save results
    if args.output:
        report.save_to_csv(f"{args.output}_trades.csv")
        report.save_summary_to_txt(f"{args.output}_summary.txt")
        logger.info(f"Results saved to {args.output}_*.csv/txt")

    # Cleanup
    process_pool.stop(wait=True)

    return report


def run_backtest(args):
    """Run backtest with historical data."""
    logger.info("Starting backtest...")

    # Create strategy
    strategy, params = create_strategy(args)

    # Create config
    config = BacktestConfig(
        symbol=args.symbol.upper(),
        timeframe=args.timeframe,
        leverage=args.leverage,
        initial_balance=args.balance,
        position_size_pct=args.position_size,
        w1=args.w1,
        m1=args.m1,
        macd_fast=params.macd_fast,
        macd_slow=params.macd_slow,
        macd_signal=params.macd_signal
    )

    # Create data feed
    if args.csv:
        data_feed = CSVDataFeed(
            symbol=args.symbol.upper(),
            timeframe=args.timeframe,
            csv_path=args.csv
        )
    else:
        # Generate historical data
        start_date = datetime.now() - timedelta(days=args.days)
        end_date = datetime.now()

        data_feed = HistoricalDataFeed(
            symbol=args.symbol.upper(),
            timeframe=args.timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_price=args.initial_price,
            volatility=args.volatility,
            seed=42
        )

    # Run backtest
    backtester = Backtester(config, strategy, data_feed)
    result = backtester.run(max_candles=args.max_candles)

    # Print report
    result.report.print_summary()

    # Save results
    if args.output:
        result.report.save_to_csv(f"{args.output}_trades.csv")
        result.report.save_summary_to_txt(f"{args.output}_summary.txt")

        # Save equity curve
        import pandas as pd
        equity_df = pd.DataFrame({
            "equity": result.equity_curve,
            "drawdown": result.drawdown_curve
        })
        equity_df.to_csv(f"{args.output}_equity.csv", index=False)
        logger.info(f"Results saved to {args.output}_*.csv")

    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Paper trading and backtesting for rezbot strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run paper trading with simulated data for 1 hour
  python paper/cli.py paper --symbol BTCUSDT --strategy pullback --duration 3600

  # Run backtest with historical data from CSV
  python paper/cli.py backtest --symbol BTCUSDT --strategy macd --csv data.csv

  # Run backtest with generated historical data (30 days)
  python paper/cli.py backtest --symbol BTCUSDT --strategy pullback --days 30
        """
    )

    subparsers = parser.add_subparsers(dest="mode", help="Trading mode")

    # Common arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "-s", "--symbol",
        type=str,
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)"
    )
    common_parser.add_argument(
        "--strategy",
        type=str,
        choices=["pullback", "macd", "trend_reversal"],
        default="pullback",
        help="Strategy to use (default: pullback)"
    )
    common_parser.add_argument(
        "--timeframe",
        type=str,
        default="5m",
        help="Timeframe (default: 5m)"
    )
    common_parser.add_argument(
        "--leverage",
        type=int,
        default=10,
        help="Trading leverage (default: 10)"
    )
    common_parser.add_argument(
        "--balance",
        type=float,
        default=1000.0,
        help="Initial balance (default: 1000.0)"
    )
    common_parser.add_argument(
        "--take-profit",
        type=float,
        default=6.0,
        help="Take profit percentage (default: 6.0)"
    )
    common_parser.add_argument(
        "--stoploss",
        type=float,
        default=-0.2,
        help="Stop loss percentage (default: -0.2)"
    )
    common_parser.add_argument(
        "--entry-window",
        type=int,
        default=1,
        help="Entry window (default: 1)"
    )
    common_parser.add_argument(
        "--exit-window",
        type=int,
        default=0,
        help="Exit window (default: 0)"
    )
    common_parser.add_argument(
        "--position-size",
        type=float,
        default=0.95,
        help="Position size as %% of balance (default: 0.95)"
    )
    common_parser.add_argument(
        "--w1",
        type=int,
        default=5,
        help="Bollinger band window (default: 5)"
    )
    common_parser.add_argument(
        "--m1",
        type=float,
        default=1.2,
        help="Bollinger band multiplier (default: 1.2)"
    )
    common_parser.add_argument(
        "--macd-fast",
        type=int,
        default=12,
        help="MACD fast period (default: 12)"
    )
    common_parser.add_argument(
        "--macd-slow",
        type=int,
        default=26,
        help="MACD slow period (default: 26)"
    )
    common_parser.add_argument(
        "--macd-signal",
        type=int,
        default=9,
        help="MACD signal period (default: 9)"
    )
    common_parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file prefix for results"
    )

    # Paper trading subcommand
    paper_parser = subparsers.add_parser(
        "paper",
        help="Run paper trading session",
        parents=[common_parser]
    )
    paper_parser.add_argument(
        "--duration",
        type=int,
        default=3600,
        help="Duration in seconds (default: 3600)"
    )
    paper_parser.add_argument(
        "--csv",
        type=str,
        help="Use historical data from CSV file instead of live simulation"
    )

    # Backtest subcommand
    backtest_parser = subparsers.add_parser(
        "backtest",
        help="Run backtest with historical data",
        parents=[common_parser]
    )
    backtest_parser.add_argument(
        "--csv",
        type=str,
        help="CSV file with historical OHLCV data"
    )
    backtest_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to generate (if not using CSV, default: 7)"
    )
    backtest_parser.add_argument(
        "--max-candles",
        type=int,
        help="Maximum number of candles to process"
    )
    backtest_parser.add_argument(
        "--initial-price",
        type=float,
        default=50000.0,
        help="Initial price for simulated data (default: 50000.0)"
    )
    backtest_parser.add_argument(
        "--volatility",
        type=float,
        default=0.02,
        help="Volatility for simulated data (default: 0.02)"
    )

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        return 1

    try:
        if args.mode == "paper":
            run_paper_trading(args)
        elif args.mode == "backtest":
            run_backtest(args)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
