"""Unit tests for TradeExecutor."""

import unittest
from unittest.mock import Mock, MagicMock

from src.trading import OrderSide, OrderResult, TradeExecutor

# Mock BinanceAPIException for testing
class BinanceAPIException(Exception):
    pass


class TestOrderSide(unittest.TestCase):
    """Test cases for OrderSide enum."""

    def test_values(self):
        """Test OrderSide enum values."""
        self.assertEqual(OrderSide.BUY.value, "BUY")
        self.assertEqual(OrderSide.SELL.value, "SELL")

    def test_opposite(self):
        """Test opposite method."""
        self.assertEqual(OrderSide.BUY.opposite, OrderSide.SELL)
        self.assertEqual(OrderSide.SELL.opposite, OrderSide.BUY)


class TestOrderResult(unittest.TestCase):
    """Test cases for OrderResult."""

    def test_success_result(self):
        """Test creating success result."""
        result = OrderResult.success_result(
            order_id="12345",
            price=50000.0,
            executed_qty="0.001"
        )

        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.assertEqual(result.price, 50000.0)
        self.assertEqual(result.executed_qty, "0.001")

    def test_failure_result(self):
        """Test creating failure result."""
        result = OrderResult.failure_result("Insufficient balance")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Insufficient balance")


class TestTradeExecutor(unittest.TestCase):
    """Test cases for TradeExecutor."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()

    def test_initialization(self):
        """Test TradeExecutor initialization."""
        executor = TradeExecutor(
            client=self.mock_client,
            symbol="BTCUSDT",
            leverage=10,
            is_real=False
        )

        self.assertEqual(executor.symbol, "BTCUSDT")
        self.assertEqual(executor.leverage, 10)
        self.assertFalse(executor.is_real)

    def test_enter_position_mock(self):
        """Test entering position with mocked client."""
        # Mock the API call
        self.mock_client.futures_create_order = MagicMock(
            return_value={
                "orderId": "12345",
                "executedQty": "0.001",
                "status": "FILLED"
            }
        )
        # Mock position info call
        self.mock_client.futures_position_information = MagicMock(
            return_value=[{
                "entryPrice": "50000.0",
                "positionAmt": "0.001"
            }]
        )

        executor = TradeExecutor(
            client=self.mock_client,
            symbol="BTCUSDT",
            leverage=10,
            is_real=False
        )

        result = executor.enter_position(OrderSide.BUY, "0.001")

        # Check the API was called correctly
        self.mock_client.futures_create_order.assert_called_once()

    def test_close_position_mock(self):
        """Test closing position with mocked client."""
        self.mock_client.futures_create_order = MagicMock(
            return_value={
                "orderId": "67890",
                "avgPrice": "51000.0",
                "executedQty": "0.001",
                "status": "FILLED"
            }
        )

        executor = TradeExecutor(
            client=self.mock_client,
            symbol="BTCUSDT",
            leverage=10,
            is_real=False
        )

        result = executor.close_position(OrderSide.SELL, "0.001")

        self.mock_client.futures_create_order.assert_called_once()


if __name__ == '__main__':
    unittest.main()
