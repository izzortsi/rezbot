"""Unit tests for trading strategies."""

import unittest
import pandas as pd
import numpy as np

from src.strategies.base import Strategy, StrategyParams, PositionType
from src.strategies import (
    PullbackStrategy,
    MacdStrategy,
    TrendReversalStrategy,
)


class MockTraderContext:
    """Mock trader context for testing strategies."""

    def __init__(self):
        # Create sample data window
        dates = pd.date_range('2024-01-01', periods=50, freq='1h')
        close = np.linspace(50000, 51000, 50)
        histogram = np.sin(np.linspace(0, 4*np.pi, 50)) * 100

        # Add Bollinger Bands
        close_ema = pd.Series(close).ewm(span=5).mean()
        close_std = pd.Series(close).ewm(span=5).std()

        self.data_window = pd.DataFrame({
            'date': dates,
            'close': close,
            'histogram': histogram,
            'close_ema': close_ema,
            'close_std': close_std,
            'cs': close_ema + 1.2 * close_std,
            'ci': close_ema - 1.2 * close_std,
            'hist_ema': pd.Series(histogram).ewm(span=5).mean(),
        })

        self.is_positioned = False
        self.current_percentual_profit = 0.0


class TestStrategyParams(unittest.TestCase):
    """Test cases for StrategyParams."""

    def test_creation(self):
        """Test creating StrategyParams."""
        params = StrategyParams(
            name="test",
            timeframe="30m",
            take_profit=6.0,
            stoploss=-0.2,
            entry_window=1,
            exit_window=0
        )

        self.assertEqual(params.name, "test")
        self.assertEqual(params.take_profit, 6.0)
        self.assertEqual(params.stoploss, -0.2)

    def test_validation_positive_stoploss(self):
        """Test that positive stoploss raises error."""
        with self.assertRaises(ValueError):
            StrategyParams(
                name="test",
                timeframe="30m",
                take_profit=6.0,
                stoploss=0.2,  # Invalid: positive
                entry_window=1,
                exit_window=0
            )

    def test_validation_negative_take_profit(self):
        """Test that negative take_profit raises error."""
        with self.assertRaises(ValueError):
            StrategyParams(
                name="test",
                timeframe="30m",
                take_profit=-6.0,  # Invalid: negative
                stoploss=-0.2,
                entry_window=1,
                exit_window=0
            )


class TestMacdStrategy(unittest.TestCase):
    """Test cases for MacdStrategy."""

    def setUp(self):
        """Set up test fixtures."""
        params = StrategyParams(
            name="macd",
            timeframe="30m",
            take_profit=6.0,
            stoploss=-0.2,
            entry_window=5,  # Use larger window for trend detection
            exit_window=0
        )
        self.strategy = MacdStrategy(params)
        self.trader = MockTraderContext()

    def test_entry_long_signal(self):
        """Test long entry signal detection."""
        # Set up histogram pattern for long entry (last 5 values negative and strictly increasing)
        # pandas_ta.increasing returns 1 for each element greater than previous, 0 otherwise
        # So we need: -10 < -8 < -5 < -3 < -1 (strictly increasing, all negative)
        histogram = np.concatenate([np.zeros(45), [-10, -8, -5, -3, -1]])
        hist_ema = np.concatenate([np.zeros(45), [-9, -7, -4, -2, -1]])
        self.trader.data_window['histogram'] = histogram
        self.trader.data_window['hist_ema'] = hist_ema

        should_enter, pos_type = self.strategy.entry_signal(self.trader)

        self.assertTrue(should_enter)
        self.assertEqual(pos_type, PositionType.LONG)

    def test_entry_short_signal(self):
        """Test short entry signal detection."""
        # Set up histogram pattern for short entry (last 5 values positive and strictly decreasing)
        histogram = np.concatenate([np.zeros(45), [10, 8, 5, 3, 1]])
        hist_ema = np.concatenate([np.zeros(45), [9, 7, 4, 2, 1]])
        self.trader.data_window['histogram'] = histogram
        self.trader.data_window['hist_ema'] = hist_ema

        should_enter, pos_type = self.strategy.entry_signal(self.trader)

        self.assertTrue(should_enter)
        self.assertEqual(pos_type, PositionType.SHORT)

    def test_no_entry_signal(self):
        """Test no entry signal when conditions not met."""
        # Mixed histogram (last 5 values)
        histogram = np.concatenate([np.zeros(45), [10, -5, 5, -10, 10]])
        hist_ema = np.concatenate([np.zeros(45), [8, -4, 2, -8, 8]])
        self.trader.data_window['histogram'] = histogram
        self.trader.data_window['hist_ema'] = hist_ema

        should_enter, pos_type = self.strategy.entry_signal(self.trader)

        self.assertFalse(should_enter)
        self.assertIsNone(pos_type)

    def test_stoploss_check(self):
        """Test stop loss check."""
        self.trader.current_percentual_profit = -0.25  # Below -0.2% threshold

        self.assertTrue(self.strategy.stoploss_check(self.trader))

    def test_stoploss_not_triggered(self):
        """Test stop loss not triggered when above threshold."""
        self.trader.current_percentual_profit = -0.15  # Above -0.2% threshold

        self.assertFalse(self.strategy.stoploss_check(self.trader))


class TestPullbackStrategy(unittest.TestCase):
    """Test cases for PullbackStrategy."""

    def setUp(self):
        """Set up test fixtures."""
        params = StrategyParams(
            name="pullback",
            timeframe="30m",
            take_profit=6.0,
            stoploss=-0.2,
            entry_window=1,
            exit_window=0
        )
        self.strategy = PullbackStrategy(params)
        self.trader = MockTraderContext()

    def test_entry_pullback_lower_band(self):
        """Test entry signal on pullback to lower band."""
        # Price at lower band, histogram positive
        last_close = self.trader.data_window['close'].iloc[-1]
        last_ci = self.trader.data_window['ci'].iloc[-1]

        self.trader.data_window.at[len(self.trader.data_window) - 1, 'close'] = last_ci - 1
        self.trader.data_window.at[len(self.trader.data_window) - 1, 'histogram'] = 5

        should_enter, pos_type = self.strategy.entry_signal(self.trader)

        self.assertTrue(should_enter)
        self.assertEqual(pos_type, PositionType.LONG)


class TestTrendReversalStrategy(unittest.TestCase):
    """Test cases for TrendReversalStrategy."""

    def setUp(self):
        """Set up test fixtures."""
        params = StrategyParams(
            name="trend_reversal",
            timeframe="30m",
            take_profit=6.0,
            stoploss=-0.2,
            entry_window=3,
            exit_window=0
        )
        self.strategy = TrendReversalStrategy(params)
        self.trader = MockTraderContext()

    def test_entry_reversal_long(self):
        """Test long reversal entry signal."""
        # Histogram: negative, with reversal pattern
        # Need: all tail(entry_window=3) <= 0, and decreasing then increasing
        # Pattern: ... positive, positive, [-15, -10, -5]
        # ta.decreasing([-15, -10]) -> values=[0, 1] -> values[-2]=0, values[-1]=1
        # ta.increasing([-10, -5]) -> values=[0, 1] -> values[-2]=0, values[-1]=1
        # So we need: values[-2]==1 from decreasing, values[-1]==1 from increasing
        # This means we need: [decreasing, increasing] = [-20, -10, -5]
        # ta.decreasing([-20, -10]) -> values=[0, 1] -> values[-1]=1
        # ta.increasing([-10, -5]) -> values=[0, 1] -> values[-1]=1
        histogram = np.concatenate([[10] * 47, [-20, -10, -5]])
        hist_ema = np.concatenate([[10] * 47, [-18, -9, -4]])
        self.trader.data_window['histogram'] = histogram
        self.trader.data_window['hist_ema'] = hist_ema

        should_enter, pos_type = self.strategy.entry_signal(self.trader)

        self.assertTrue(should_enter)
        self.assertEqual(pos_type, PositionType.LONG)


if __name__ == '__main__':
    unittest.main()
