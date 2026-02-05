"""Unit tests for paper trading module."""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.strategies import MacdStrategy, StrategyParams
from paper.data_feed import (
    HistoricalDataFeed,
    CSVDataFeed,
    DataFrameDataFeed,
    LiveSimulatedFeed
)
from paper.backtester import Backtester, BacktestConfig, run_strategy_backtest
from paper.trading_engine import PaperTrader, PaperConfig
from paper.reporting import Statistics, TradeReport


class TestDataFeed(unittest.TestCase):
    """Test cases for data feed classes."""

    def test_historical_data_feed_generation(self):
        """Test generating historical data."""
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()

        feed = HistoricalDataFeed(
            symbol="BTCUSDT",
            timeframe="5min",
            start_date=start,
            end_date=end,
            initial_price=50000.0,
            seed=42
        )

        data = feed.load_data()

        self.assertIsNotNone(data)
        self.assertGreater(len(data), 0)
        self.assertIn("close", data.columns)
        self.assertIn("open", data.columns)
        self.assertIn("high", data.columns)
        self.assertIn("low", data.columns)
        self.assertIn("volume", data.columns)

    def test_data_frame_feed(self):
        """Test DataFrame data feed."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="5min")
        data = pd.DataFrame({
            "open": np.linspace(50000, 51000, 100),
            "high": np.linspace(50100, 51100, 100),
            "low": np.linspace(49900, 50900, 100),
            "close": np.linspace(50000, 51000, 100),
            "volume": np.random.uniform(100, 10000, 100)
        }, index=dates)

        feed = DataFrameDataFeed("BTCUSDT", "5m", data)
        loaded = feed.load_data()

        self.assertEqual(len(loaded), 100)
        self.assertIn("close", loaded.columns)

    def test_get_next_candle(self):
        """Test getting candles sequentially."""
        dates = pd.date_range(start="2024-01-01", periods=10, freq="5min")
        data = pd.DataFrame({
            "open": range(10),
            "high": range(10),
            "low": range(10),
            "close": range(10),
            "volume": range(10)
        }, index=dates)

        feed = DataFrameDataFeed("TEST", "5m", data)

        for i in range(10):
            candle = feed.get_next_candle()
            self.assertIsNotNone(candle)
            self.assertEqual(candle["close"], i)

        # Should return None after exhausting data
        candle = feed.get_next_candle()
        self.assertIsNone(candle)

    def test_reset(self):
        """Test resetting data feed."""
        dates = pd.date_range(start="2024-01-01", periods=5, freq="5min")
        data = pd.DataFrame({
            "open": range(5),
            "high": range(5),
            "low": range(5),
            "close": range(5),
            "volume": range(5)
        }, index=dates)

        feed = DataFrameDataFeed("TEST", "5m", data)

        # Consume all data
        for _ in range(5):
            feed.get_next_candle()

        self.assertTrue(feed.is_finished)

        # Reset
        feed.reset()
        self.assertFalse(feed.is_finished)

        # Should be able to get candles again
        candle = feed.get_next_candle()
        self.assertIsNotNone(candle)


class TestBacktester(unittest.TestCase):
    """Test cases for backtester."""

    def setUp(self):
        """Set up test fixtures."""
        self.params = StrategyParams(
            name="macd",
            timeframe="5min",
            take_profit=6.0,
            stoploss=-0.2,
            entry_window=1,
            exit_window=0
        )
        self.strategy = MacdStrategy(self.params)

        # Create sample data
        dates = pd.date_range(start="2024-01-01", periods=200, freq="5min")
        np.random.seed(42)

        # Generate price series with some trend
        close = 50000 + np.cumsum(np.random.randn(200) * 50)

        self.data = pd.DataFrame({
            "open": close,
            "high": close + 20,
            "low": close - 20,
            "close": close,
            "volume": np.random.uniform(100, 10000, 200)
        }, index=dates)

    def test_backtester_initialization(self):
        """Test backtester initialization."""
        config = BacktestConfig(
            symbol="BTCUSDT",
            leverage=10
        )

        data_feed = DataFrameDataFeed("BTCUSDT", "5m", self.data)
        backtester = Backtester(config, self.strategy, data_feed)

        self.assertEqual(backtester._config.symbol, "BTCUSDT")
        self.assertEqual(backtester._config.leverage, 10)

    def test_run_backtest(self):
        """Test running a full backtest."""
        config = BacktestConfig(
            symbol="BTCUSDT",
            leverage=10,
            w1=5,
            m1=1.2
        )

        data_feed = DataFrameDataFeed("BTCUSDT", "5m", self.data)
        backtester = Backtester(config, self.strategy, data_feed)

        result = backtester.run()

        self.assertIsNotNone(result)
        self.assertGreater(result.total_candles, 0)
        self.assertIsNotNone(result.report)

    def test_backtest_result_contains_trades(self):
        """Test that backtest results contain trade information."""
        config = BacktestConfig(symbol="BTCUSDT", leverage=10)
        data_feed = DataFrameDataFeed("BTCUSDT", "5m", self.data)
        backtester = Backtester(config, self.strategy, data_feed)

        result = backtester.run()

        # Should have some trades or at least no errors
        self.assertIsInstance(result.report.trade_records, list)

    def test_equity_curve_generated(self):
        """Test that equity curve is generated."""
        config = BacktestConfig(symbol="BTCUSDT", leverage=10)
        data_feed = DataFrameDataFeed("BTCUSDT", "5m", self.data)
        backtester = Backtester(config, self.strategy, data_feed)

        result = backtester.run()

        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(len(result.equity_curve), result.total_candles)


class TestPaperTrader(unittest.TestCase):
    """Test cases for paper trader."""

    def setUp(self):
        """Set up test fixtures."""
        self.params = StrategyParams(
            name="macd",
            timeframe="5min",
            take_profit=6.0,
            stoploss=-0.2,
            entry_window=1,
            exit_window=0
        )
        self.strategy = MacdStrategy(self.params)

        self.config = PaperConfig(
            symbol="BTCUSDT",
            timeframe="5min",
            leverage=10,
            initial_balance=1000.0
        )

    def test_paper_trader_initialization(self):
        """Test paper trader initialization."""
        trader = PaperTrader(
            config=self.config,
            strategy=self.strategy
        )

        self.assertEqual(trader._config.symbol, "BTCUSDT")
        self.assertEqual(trader._config.leverage, 10)
        self.assertFalse(trader.is_running)
        self.assertFalse(trader.is_positioned)

    def test_paper_trader_run_short_duration(self):
        """Test running paper trader for short duration."""
        trader = PaperTrader(
            config=self.config,
            strategy=self.strategy
        )

        # Run for 5 seconds
        trader.run(duration_seconds=5)

        self.assertFalse(trader.is_running)

        report = trader.get_report()
        self.assertIsNotNone(report)

    def test_paper_trader_balance_tracking(self):
        """Test that balance is tracked correctly."""
        config = PaperConfig(
            symbol="BTCUSDT",
            timeframe="5min",
            leverage=10,
            initial_balance=5000.0
        )
        trader = PaperTrader(
            config=config,
            strategy=self.strategy
        )

        self.assertEqual(trader._initial_balance, 5000.0)
        self.assertEqual(trader.balance, 5000.0)

    def test_paper_trader_stop(self):
        """Test stopping paper trader."""
        trader = PaperTrader(
            config=self.config,
            strategy=self.strategy
        )

        # Start and immediately stop
        trader.start()
        self.assertTrue(trader.is_running)

        trader.stop(timeout=5)
        self.assertFalse(trader.is_running)


class TestReporting(unittest.TestCase):
    """Test cases for reporting module."""

    def test_statistics_from_empty_records(self):
        """Test statistics calculation with no records."""
        stats = Statistics.calculate_from_records([])

        self.assertEqual(stats.total_trades, 0)
        self.assertEqual(stats.winning_trades, 0)
        self.assertEqual(stats.losing_trades, 0)

    def test_trade_report_creation(self):
        """Test creating a trade report."""
        from src.trading.position_manager import Position, TradeRecord
        from src.strategies.base import PositionType

        position = Position(
            symbol="BTCUSDT",
            position_type=PositionType.LONG,
            entry_price=50000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=10
        )

        record = TradeRecord(
            position=position,
            exit_price=51000.0,
            exit_time=datetime.now(),
            exit_reason="TP",
            profit=100.0,
            percentual_profit=2.0,
            leveraged_profit=20.0
        )

        stats = Statistics.calculate_from_records([record], leverage=10)

        report = TradeReport(
            symbol="BTCUSDT",
            timeframe="5min",
            start_time=datetime.now(),
            end_time=datetime.now(),
            statistics=stats,
            trade_records=[record]
        )

        self.assertEqual(report.symbol, "BTCUSDT")
        self.assertEqual(len(report.trade_records), 1)


if __name__ == '__main__':
    unittest.main()
