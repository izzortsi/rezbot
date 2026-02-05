"""Indicator computation using process pool.

This module provides the IndicatorProcessor class which manages
asynchronous indicator computation via the process pool.
"""

import threading
from typing import Optional, Dict, Callable
import pandas as pd
from concurrent.futures import Future
import logging

from ..compute.indicators import compute_all_indicators
from ..concurrency.multiprocessing import ProcessPoolManager

logger = logging.getLogger(__name__)


class IndicatorProcessor:
    """Manages indicator computation using process pool.

    This class handles asynchronous submission of indicator computation
    tasks to the process pool and retrieval of results when ready.

    The async pattern allows the main thread to continue processing
    WebSocket data while CPU-intensive indicator calculations run
    in separate processes.

    Example:
        processor = IndicatorProcessor(
            process_pool=manager.process_pool,
            w1=5,
            m1=1.2,
            macd_params={"fast": 12, "slow": 26, "signal": 9}
        )

        # Submit computation (non-blocking)
        processor.compute_indicators_async(close_prices)

        # Later, check if ready
        indicators = processor.get_indicators(timeout=0.1)
        if indicators is not None:
            # Use computed indicators
            data_window.update(indicators)
    """

    def __init__(
        self,
        process_pool: ProcessPoolManager,
        w1: int = 5,
        m1: float = 1.2,
        macd_params: Optional[Dict[str, int]] = None
    ):
        """Initialize the indicator processor.

        Args:
            process_pool: ProcessPoolManager for CPU-bound computation
            w1: EMA window for Bollinger Bands
            m1: Standard deviation multiplier for Bollinger Bands
            macd_params: Dictionary with MACD parameters (fast, slow, signal)
        """
        self._process_pool = process_pool
        self._w1 = w1
        self._m1 = m1
        self._macd_params = macd_params or {"fast": 12, "slow": 26, "signal": 9}

        self._lock = threading.RLock()
        self._pending_result: Optional[Future] = None
        self._last_result: Optional[pd.DataFrame] = None

    def compute_indicators_async(self, close: pd.Series) -> None:
        """Submit indicator computation to process pool (non-blocking).

        This method submits the computation task and returns immediately.
        The result will be available later via get_indicators().

        Args:
            close: Close price series

        Example:
            processor.compute_indicators_async(data_window.close)
            # Computation runs in background
            # Continue with other work...
        """
        with self._lock:
            # Cancel pending computation if exists
            if self._pending_result is not None and not self._pending_result.done():
                self._pending_result.cancel()
                logger.debug("Cancelled pending indicator computation")

            # Submit new computation
            try:
                self._pending_result = self._process_pool.submit(
                    compute_all_indicators,
                    close=close,
                    w1=self._w1,
                    m1=self._m1,
                    macd_params=self._macd_params
                )
                logger.debug("Submitted indicator computation to process pool")
            except Exception as e:
                logger.error(f"Failed to submit indicator computation: {e}")
                self._pending_result = None

    def get_indicators(self, timeout: float = 0.1) -> Optional[pd.DataFrame]:
        """Get computed indicators if ready.

        This method checks if the computation is complete and returns
        the result if available. If the computation is still running,
        returns None.

        Args:
            timeout: Maximum time to wait for result (seconds)

        Returns:
            DataFrame with computed indicators, or None if not ready

        Example:
            indicators = processor.get_indicators(timeout=0.01)
            if indicators is not None:
                # Update data window
                data_window.update(indicators)
            else:
                # Computation still in progress, check again later
                pass
        """
        with self._lock:
            if self._pending_result is None:
                return None

            try:
                if self._pending_result.done():
                    result = self._pending_result.result(timeout=0)
                    self._pending_result = None
                    self._last_result = result
                    logger.debug("Retrieved computed indicators from process pool")
                    return result
            except Exception as e:
                logger.error(f"Failed to get indicator result: {e}")
                self._pending_result = None
                return None

        return None

    def compute_indicators_sync(self, close: pd.Series) -> pd.DataFrame:
        """Synchronous indicator computation (blocking).

        This method computes indicators directly in the current thread/process.
        Use this when you need immediate results and can afford to block.

        Args:
            close: Close price series

        Returns:
            DataFrame with computed indicators

        Example:
            indicators = processor.compute_indicators_sync(close_prices)
        """
        return compute_all_indicators(
            close=close,
            w1=self._w1,
            m1=self._m1,
            macd_params=self._macd_params
        )

    @property
    def is_computing(self) -> bool:
        """Check if computation is currently in progress.

        Returns:
            True if computation is running, False otherwise
        """
        with self._lock:
            return (
                self._pending_result is not None and
                not self._pending_result.done()
            )

    @property
    def last_result(self) -> Optional[pd.DataFrame]:
        """Get the last computed result without checking for new computation.

        Returns:
            Last computed DataFrame, or None if no computation has completed
        """
        with self._lock:
            return self._last_result

    def cancel(self) -> bool:
        """Cancel pending computation if any.

        Returns:
            True if computation was cancelled, False if none was pending
        """
        with self._lock:
            if self._pending_result is not None and not self._pending_result.done():
                cancelled = self._pending_result.cancel()
                if cancelled:
                    self._pending_result = None
                    logger.info("Cancelled pending indicator computation")
                return cancelled
            return False

    @property
    def w1(self) -> int:
        """Get EMA window parameter."""
        return self._w1

    @property
    def m1(self) -> float:
        """Get standard deviation multiplier."""
        return self._m1

    @property
    def macd_params(self) -> Dict[str, int]:
        """Get MACD parameters."""
        return self._macd_params.copy()
