"""Unit tests for IndicatorProcessor."""

import unittest
from unittest.mock import Mock, MagicMock
import pandas as pd
import numpy as np

from src.concurrency.multiprocessing import ProcessPoolManager
from src.trading import IndicatorProcessor


class TestIndicatorProcessor(unittest.TestCase):
    """Test cases for IndicatorProcessor."""

    def setUp(self):
        """Set up test fixtures."""
        self.pool = ProcessPoolManager(max_workers=2)
        self.pool.start()

        # Create sample close price data
        self.close_prices = pd.Series(
            np.linspace(50000, 50500, 100) +
            np.random.randn(100) * 50
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.pool.stop(wait=True)

    def test_submit_computation(self):
        """Test submitting indicator computation."""
        processor = IndicatorProcessor(
            process_pool=self.pool,
            w1=5,
            m1=1.2,
            macd_params={"fast": 12, "slow": 26, "signal": 9}
        )

        # Submit async computation
        processor.compute_indicators_async(self.close_prices)

        # Wait for result
        result = processor.get_indicators(timeout=5.0)

        self.assertIsNotNone(result)
        self.assertIn('close', result.columns)
        self.assertIn('histogram', result.columns)
        self.assertIn('close_ema', result.columns)

    def test_computation_not_ready(self):
        """Test getting indicators when not ready."""
        processor = IndicatorProcessor(
            process_pool=self.pool,
            w1=5,
            m1=1.2
        )

        # Submit computation
        processor.compute_indicators_async(self.close_prices)

        # Check immediately - should not be ready
        result = processor.get_indicators(timeout=0.01)
        self.assertIsNone(result)

    def test_sync_computation(self):
        """Test synchronous indicator computation."""
        processor = IndicatorProcessor(
            process_pool=self.pool,
            w1=5,
            m1=1.2
        )

        result = processor.compute_indicators_sync(self.close_prices)

        self.assertIsNotNone(result)
        self.assertIn('close', result.columns)

    def test_is_computing(self):
        """Test is_computing property."""
        import time
        processor = IndicatorProcessor(
            process_pool=self.pool,
            w1=5,
            m1=1.2
        )

        self.assertFalse(processor.is_computing)

        processor.compute_indicators_async(self.close_prices)
        # Small delay to ensure computation starts
        time.sleep(0.05)
        self.assertTrue(processor.is_computing)

        # Wait for completion
        processor.get_indicators(timeout=5.0)
        self.assertFalse(processor.is_computing)

    def test_cancel(self):
        """Test cancelling pending computation."""
        import time
        processor = IndicatorProcessor(
            process_pool=self.pool,
            w1=5,
            m1=1.2
        )

        processor.compute_indicators_async(self.close_prices)
        time.sleep(0.05)  # Ensure computation starts
        self.assertTrue(processor.is_computing)

        cancelled = processor.cancel()
        self.assertTrue(cancelled)
        self.assertFalse(processor.is_computing)

    def test_parameters(self):
        """Test parameter properties."""
        processor = IndicatorProcessor(
            process_pool=self.pool,
            w1=7,
            m1=1.5,
            macd_params={"fast": 5, "slow": 15, "signal": 8}
        )

        self.assertEqual(processor.w1, 7)
        self.assertEqual(processor.m1, 1.5)

        macd_params = processor.macd_params
        self.assertEqual(macd_params["fast"], 5)
        self.assertEqual(macd_params["slow"], 15)
        self.assertEqual(macd_params["signal"], 8)


if __name__ == '__main__':
    unittest.main()
