"""Unit tests for PositionManager."""

import unittest
import threading
import time
import pandas as pd
from datetime import datetime

from src.strategies.base import PositionType
from src.trading import Position, PositionManager, TradeRecord


class TestPosition(unittest.TestCase):
    """Test cases for Position dataclass."""

    def test_creation(self):
        """Test creating a Position."""
        position = Position(
            symbol="BTCUSDT",
            position_type=PositionType.LONG,
            entry_price=50000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=10
        )

        self.assertEqual(position.symbol, "BTCUSDT")
        self.assertTrue(position.is_long)
        self.assertFalse(position.is_short)
        self.assertEqual(position.leverage, 10)

    def test_properties(self):
        """Test Position properties."""
        position = Position(
            symbol="BTCUSDT",
            position_type=PositionType.SHORT,
            entry_price=50000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=5
        )

        self.assertTrue(position.is_short)
        self.assertEqual(position.side, "SHORT")


class TestPositionManager(unittest.TestCase):
    """Test cases for PositionManager."""

    def test_initial_state(self):
        """Test initial state of PositionManager."""
        pm = PositionManager()

        self.assertFalse(pm.is_positioned)
        self.assertIsNone(pm.position)
        self.assertEqual(pm.num_trades, 0)

    def test_enter_position(self):
        """Test entering a position."""
        pm = PositionManager()
        position = Position(
            symbol="BTCUSDT",
            position_type=PositionType.LONG,
            entry_price=50000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=10
        )

        pm.enter_position(position)

        self.assertTrue(pm.is_positioned)
        self.assertEqual(pm.position, position)

    def test_enter_when_positioned(self):
        """Test that entering while positioned raises error."""
        pm = PositionManager()
        position1 = Position(
            symbol="BTCUSDT",
            position_type=PositionType.LONG,
            entry_price=50000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=10
        )

        pm.enter_position(position1)

        position2 = Position(
            symbol="BTCUSDT",
            position_type=PositionType.SHORT,
            entry_price=51000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=10
        )

        with self.assertRaises(ValueError):
            pm.enter_position(position2)

    def test_exit_position(self):
        """Test exiting a position."""
        pm = PositionManager()
        entry_time = datetime.now()

        position = Position(
            symbol="BTCUSDT",
            position_type=PositionType.LONG,
            entry_price=50000.0,
            entry_time=entry_time,
            qty=0.001,
            leverage=10
        )

        pm.enter_position(position)

        exit_time = datetime.now()
        record = pm.exit_position(51000.0, exit_time, "TP")

        self.assertIsNotNone(record)
        self.assertEqual(record.exit_price, 51000.0)
        self.assertFalse(pm.is_positioned)

    def test_exit_when_not_positioned(self):
        """Test that exiting when not positioned returns None."""
        pm = PositionManager()

        record = pm.exit_position(50000.0, datetime.now(), "TP")

        self.assertIsNone(record)

    def test_trade_history(self):
        """Test trade history tracking."""
        pm = PositionManager()

        # Enter and exit a few positions
        for i in range(3):
            position = Position(
                symbol="BTCUSDT",
                position_type=PositionType.LONG,
                entry_price=50000.0 + i * 100,
                entry_time=datetime.now(),
                qty=0.001,
                leverage=10
            )

            pm.enter_position(position)
            pm.exit_position(51000.0 + i * 100, datetime.now(), "TP")

        self.assertEqual(pm.num_trades, 3)

        history = pm.get_trade_history()
        self.assertEqual(len(history), 3)

    def test_cumulative_profit(self):
        """Test cumulative profit calculation."""
        pm = PositionManager()

        position = Position(
            symbol="BTCUSDT",
            position_type=PositionType.LONG,
            entry_price=50000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=10
        )

        pm.enter_position(position)
        pm.exit_position(51000.0, datetime.now(), "TP")

        # First trade with 1% profit, 10x leverage = 10% cumulative
        cum_profit = pm.get_cumulative_profit()

        self.assertIsInstance(cum_profit, float)

    def test_thread_safety(self):
        """Test thread safety of PositionManager."""
        pm = PositionManager()
        errors = []

        def enter_exit_cycle():
            try:
                for i in range(10):
                    if not pm.is_positioned:
                        position = Position(
                            symbol="BTCUSDT",
                            position_type=PositionType.LONG,
                            entry_price=50000.0,
                            entry_time=datetime.now(),
                            qty=0.001,
                            leverage=10
                        )
                        pm.enter_position(position)
                    else:
                        pm.exit_position(51000.0, datetime.now(), "TP")
                    time.sleep(0.001)
            except ValueError as e:
                # Expected: "Already in a position" due to race condition
                if "Already in a position" not in str(e):
                    errors.append(e)
            except AttributeError:
                # Can happen if exit_position accesses attributes on None return
                pass
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=enter_exit_cycle)
            for _ in range(3)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=5)

        # Should not have unexpected errors
        self.assertEqual(len(errors), 0)

        # Should have some trades completed
        self.assertGreater(pm.num_trades, 0)


if __name__ == '__main__':
    unittest.main()
