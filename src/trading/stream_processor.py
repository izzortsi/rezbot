"""Stream data processing and management.

This module provides the StreamProcessor class which handles
WebSocket stream data, updates the data window, and manages
indicator computation via the process pool.
"""

import threading
import time
import pandas as pd
from typing import Optional, Callable, Any
from dataclasses import dataclass
import logging

# Try to import from unicorn_binance_rest_api, use fallback for testing
try:
    from unicorn_binance_rest_api.unicorn_binance_rest_api_helpers import interval_to_milliseconds
except ImportError:
    # Fallback function for testing/paper trading
    def interval_to_milliseconds(interval: str) -> int:
        """Convert interval string to milliseconds (fallback)."""
        units = {"m": 60000, "h": 3600000, "d": 86400000, "w": 604800000}
        if interval.endswith("min"):
            unit = "m"
            num = int(interval[:-3])
        else:
            unit = interval[-1]
            num = int(interval[:-1])
        return num * units[unit]

from .indicator_processor import IndicatorProcessor

logger = logging.getLogger(__name__)


@dataclass
class StreamConfig:
    """Stream processor configuration.

    Attributes:
        symbol: Trading symbol
        timeframe: Trading timeframe (e.g., "30m", "1h")
        w1: EMA window for indicators
        m1: Standard deviation multiplier
        macd_params: MACD parameters
    """
    symbol: str
    timeframe: str
    w1: int = 5
    m1: float = 1.2
    macd_params: dict = None

    def __post_init__(self):
        if self.macd_params is None:
            self.macd_params = {"fast": 12, "slow": 26, "signal": 9}


class StreamProcessor:
    """Processes WebSocket streams and manages indicator computation.

    This class handles the main data processing loop:
    1. Receives WebSocket data
    2. Updates the data window with new prices
    3. Submits indicator computation to process pool (async)
    4. Updates data window when indicators are ready

    Example:
        config = StreamConfig(symbol="BTCUSDT", timeframe="30m", w1=5, m1=1.2)
        processor = StreamProcessor(
            config=config,
            bwsm=binance_ws_manager,
            data_window=initial_data,
            indicator_processor=indicator_processor
        )
        processor.start_stream()

        # Main loop
        while running:
            processor.process_next()
            processor.update_indicators_if_ready()
            # Check trading signals...
    """

    def __init__(
        self,
        config: StreamConfig,
        bwsm: Any,
        data_window: pd.DataFrame,
        indicator_processor: IndicatorProcessor,
        on_new_candle: Optional[Callable] = None
    ):
        """Initialize the stream processor.

        Args:
            config: Stream configuration
            bwsm: Binance WebSocket manager
            data_window: Initial data window with historical data
            indicator_processor: IndicatorProcessor for async computation
            on_new_candle: Optional callback when new candle is added
        """
        self.config = config
        self.bwsm = bwsm
        self.data_window = data_window
        self.indicator_processor = indicator_processor
        self.on_new_candle = on_new_candle

        self._lock = threading.RLock()
        self._last_price = None
        self._last_update_time = None
        self._init_time = time.time()

        # Stream setup
        self.stream_name = f"kline_{config.timeframe}@{config.symbol}"
        self.stream_id = None

    def start_stream(self) -> None:
        """Initialize WebSocket stream.

        Creates the WebSocket stream for receiving kline data.
        """
        channel = "kline"
        market = self.config.symbol

        self.stream_id = self.bwsm.create_stream(
            channel, market,
            stream_buffer_name=self.stream_name
        )

        logger.info(f"Started stream: {self.stream_name}")

    def process_next(self) -> bool:
        """Process next available stream data.

        This method:
        1. Pops data from the WebSocket buffer
        2. Updates close price in data window
        3. Submits indicator computation to process pool

        Returns:
            True if new candle was added, False otherwise

        Example:
            if processor.process_next():
                # New candle added, indicators computing in background
        """
        with self._lock:
            if self.bwsm.is_manager_stopping():
                return False

            data = self.bwsm.pop_stream_data_from_stream_buffer(self.stream_name)

            if data is False:
                time.sleep(0.01)
                return False

            if data.get("event_type") != "kline":
                return False

            return self._process_kline(data["kline"])

    def update_indicators_if_ready(self) -> bool:
        """Update data_window with computed indicators if ready.

        This method checks if the async indicator computation has completed
        and updates the data window with the results.

        Returns:
            True if indicators were updated, False if not ready yet

        Example:
            if processor.update_indicators_if_ready():
                # Indicators updated, can now check trading signals
        """
        indicators = self.indicator_processor.get_indicators(timeout=0.01)
        if indicators is not None:
            with self._lock:
                # Update data window with new indicators (pandas 3.0+ compatible)
                update_dict = {col: indicators[col] for col in indicators.columns}
                self.data_window.update(update_dict)
                logger.debug("Updated data window with computed indicators")
                return True
        return False

    def _process_kline(self, kline: dict) -> bool:
        """Process individual kline data.

        Args:
            kline: Kline data from WebSocket

        Returns:
            True if new candle was added, False otherwise
        """
        try:
            # Extract kline data
            o = float(kline["open_price"])
            h = float(kline["high_price"])
            l = float(kline["low_price"])
            c = float(kline["close_price"])
            v = float(kline["base_volume"])

            self._last_price = c
            self._last_update_time = time.time()

            # Create new row - use naive timestamp to match historical data
            now_time = pd.Timestamp.now().tz_localize(None)  # naive timestamp
            last_index = self.data_window.index[-1]

            # Update close price in data window (pandas 3.0+ compatible)
            self.data_window.loc[last_index, "close"] = c

            # Submit indicator computation to process pool (non-blocking)
            with self._lock:
                self.indicator_processor.compute_indicators_async(self.data_window.close)

            # Check if we should add new candle
            tf_seconds = interval_to_milliseconds(self.config.timeframe) * 0.001

            # Handle timezone-aware comparison - convert to naive timestamps
            last_date = pd.Timestamp(self.data_window.date.values[-1]).tz_localize(None)
            prev_date = pd.Timestamp(self.data_window.date.values[-2]).tz_localize(None)
            time_diff = (last_date - prev_date).total_seconds()

            if time_diff >= tf_seconds:
                # Add new candle
                self.data_window.drop(index=0, axis=0, inplace=True)
                new_row_full = self._create_full_row(now_time, o, h, l, c, v)
                self.data_window = pd.concat([
                    self.data_window,
                    new_row_full
                ], ignore_index=True)

                self._init_time = time.time()

                if self.on_new_candle:
                    self.on_new_candle(new_row_full)

                logger.debug(f"New candle added for {self.config.symbol}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error processing kline: {e}")
            return False

    def _create_full_row(
        self,
        date,
        o: float,
        h: float,
        l: float,
        c: float,
        v: float
    ) -> pd.DataFrame:
        """Create full row with all indicators for new candle.

        Args:
            date: Candle timestamp
            o, h, l, c, v: OHLCV values

        Returns:
            DataFrame with all columns
        """
        # This is a simplified version - in production, indicators would be
        # computed separately via the process pool
        return pd.DataFrame({
            "date": [date],
            "open": [o],
            "high": [h],
            "low": [l],
            "close": [c],
            "volume": [v],
            # Indicators will be populated by async computation
            "cs": [0],
            "close_ema": [c],
            "ci": [0],
            "close_std": [0],
            "histogram": [0],
            "hist_ema": [0]
        })

    def stop(self) -> None:
        """Stop stream processing.

        Stops the WebSocket stream and cancels any pending computations.
        """
        if self.stream_id is not None:
            self.bwsm.stop_stream(self.stream_id)
            logger.info(f"Stopped stream: {self.stream_name}")

        self.indicator_processor.cancel()

    @property
    def last_price(self) -> Optional[float]:
        """Get last processed price.

        Returns:
            Last close price or None if no data processed yet
        """
        with self._lock:
            return self._last_price

    @property
    def last_update_time(self) -> Optional[float]:
        """Get last update timestamp.

        Returns:
            Unix timestamp of last update or None
        """
        with self._lock:
            return self._last_update_time

    @property
    def uptime(self) -> float:
        """Get processor uptime in seconds.

        Returns:
            Uptime since initialization
        """
        return time.time() - self._init_time
