"""Data feed for paper trading and backtesting.

This module provides classes for fetching and managing market data
for paper trading and backtesting.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Iterator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DataGranularity(Enum):
    """Time granularity for data."""
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class DataFeed:
    """Base class for data feeds.

    Provides interface for streaming market data in a format
    compatible with the paper trading engine.
    """

    def __init__(self, symbol: str, timeframe: str):
        """Initialize the data feed.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "5m", "1h", "1d")
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self._data: Optional[pd.DataFrame] = None
        self._current_index = 0

    def load_data(self) -> pd.DataFrame:
        """Load market data.

        Returns:
            DataFrame with OHLCV data indexed by datetime
        """
        raise NotImplementedError

    def get_next_candle(self) -> Optional[pd.Series]:
        """Get the next candle in the data stream.

        Returns:
            Series with OHLCV data or None if at end
        """
        if self._data is None:
            self._data = self.load_data()
            self._current_index = 0

        if self._current_index >= len(self._data):
            return None

        candle = self._data.iloc[self._current_index]
        self._current_index += 1
        return candle

    def get_data_window(self, window_size: int) -> Optional[pd.DataFrame]:
        """Get a rolling window of historical data.

        Args:
            window_size: Number of candles to include

        Returns:
            DataFrame with historical data up to current point
        """
        if self._data is None or self._current_index < window_size:
            return None

        start_idx = max(0, self._current_index - window_size)
        return self._data.iloc[start_idx:self._current_index].copy()

    def reset(self) -> None:
        """Reset the data feed to the beginning."""
        self._current_index = 0

    @property
    def is_finished(self) -> bool:
        """Check if all data has been consumed."""
        if self._data is None:
            return False
        return self._current_index >= len(self._data)

    @property
    def current_time(self) -> Optional[datetime]:
        """Get the timestamp of the current candle."""
        if self._data is None or self._current_index == 0:
            return None
        return self._data.index[self._current_index - 1]


class HistoricalDataFeed(DataFeed):
    """Data feed that generates simulated historical data.

    This class generates realistic-looking market data using
    geometric Brownian motion or other models for testing purposes.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_price: float = 50000.0,
        volatility: float = 0.02,
        drift: float = 0.0,
        seed: Optional[int] = None
    ):
        """Initialize the historical data feed.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            start_date: Start date for data generation
            end_date: End date for data generation
            initial_price: Starting price for simulation
            volatility: Annualized volatility (default 2%)
            drift: Price drift/trend (default 0%)
            seed: Random seed for reproducibility
        """
        super().__init__(symbol, timeframe)
        self.start_date = start_date
        self.end_date = end_date
        self.initial_price = initial_price
        self.volatility = volatility
        self.drift = drift
        self.seed = seed

    def load_data(self) -> pd.DataFrame:
        """Generate simulated historical data using GBM.

        Returns:
            DataFrame with OHLCV data
        """
        if self.seed is not None:
            np.random.seed(self.seed)

        # Determine number of periods based on timeframe
        periods = self._calculate_periods()

        # Generate price path using geometric Brownian motion
        dt = 1 / (365 * 24 * 60)  # Assume minute granularity for dt
        if self.timeframe.endswith('min'):
            dt = int(self.timeframe[:-3]) / (365 * 24 * 60)
        elif self.timeframe.endswith('m'):
            dt = int(self.timeframe[:-1]) / (365 * 24 * 60)
        elif self.timeframe.endswith('h'):
            dt = int(self.timeframe[:-1]) / (365 * 24)
        elif self.timeframe.endswith('d'):
            dt = int(self.timeframe[:-1]) / 365

        # Generate random returns
        returns = np.random.normal(
            (self.drift - 0.5 * self.volatility ** 2) * dt,
            self.volatility * np.sqrt(dt),
            periods
        )

        # Calculate price path
        price_path = self.initial_price * np.exp(np.cumsum(returns))
        price_path = np.insert(price_path, 0, self.initial_price)

        # Generate timestamps
        timestamps = pd.date_range(
            start=self.start_date,
            periods=periods + 1,
            freq=self.timeframe
        )

        # Generate OHLCV from close prices
        data = self._generate_ohlcv(price_path)

        df = pd.DataFrame(data, index=timestamps)
        df.columns = ["open", "high", "low", "close", "volume"]

        logger.info(f"Generated {len(df)} candles of simulated data")
        return df

    def _calculate_periods(self) -> int:
        """Calculate number of periods between dates."""
        delta = self.end_date - self.start_date

        # Convert to minutes
        total_minutes = int(delta.total_seconds() / 60)

        # Parse timeframe to minutes
        if self.timeframe.endswith('min'):
            minutes_per_period = int(self.timeframe[:-3])
        elif self.timeframe.endswith('m'):
            minutes_per_period = int(self.timeframe[:-1])
        elif self.timeframe.endswith('h'):
            minutes_per_period = int(self.timeframe[:-1]) * 60
        elif self.timeframe.endswith('d'):
            minutes_per_period = int(self.timeframe[:-1]) * 60 * 24
        else:
            minutes_per_period = 1

        return max(1, total_minutes // minutes_per_period)

    def _generate_ohlcv(self, close_prices: np.ndarray) -> np.ndarray:
        """Generate OHLCV data from close prices.

        Args:
            close_prices: Array of close prices

        Returns:
            Array with shape (n, 5) containing open, high, low, close, volume
        """
        n = len(close_prices)
        ohlcv = np.zeros((n, 5))

        # Generate high/low with some volatility around close
        volatility_factor = self.volatility * 0.5
        for i in range(n):
            close = close_prices[i]
            open_price = close_prices[i - 1] if i > 0 else close

            # Generate high and low
            high_low_range = abs(close - open_price) * (1 + np.random.random() * 2)
            high = max(open_price, close) + high_low_range * volatility_factor * np.random.random()
            low = min(open_price, close) - high_low_range * volatility_factor * np.random.random()

            ohlcv[i, 0] = open_price  # open
            ohlcv[i, 1] = high  # high
            ohlcv[i, 2] = low  # low
            ohlcv[i, 3] = close  # close
            ohlcv[i, 4] = np.random.uniform(100, 10000)  # volume

        return ohlcv


class CSVDataFeed(DataFeed):
    """Data feed that reads from CSV files.

    Expects CSV format with columns: timestamp, open, high, low, close, volume
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        csv_path: str,
        timestamp_col: str = "timestamp",
        timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    ):
        """Initialize the CSV data feed.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            csv_path: Path to CSV file
            timestamp_col: Name of timestamp column
            timestamp_format: Format string for parsing timestamps
        """
        super().__init__(symbol, timeframe)
        self.csv_path = csv_path
        self.timestamp_col = timestamp_col
        self.timestamp_format = timestamp_format

    def load_data(self) -> pd.DataFrame:
        """Load data from CSV file.

        Returns:
            DataFrame with OHLCV data indexed by datetime
        """
        df = pd.read_csv(self.csv_path)

        # Parse timestamp
        df[self.timestamp_col] = pd.to_datetime(
            df[self.timestamp_col],
            format=self.timestamp_format
        )
        df.set_index(self.timestamp_col, inplace=True)

        # Ensure we have the required columns
        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Select only OHLCV columns
        df = df[required_cols]

        # Sort by index
        df.sort_index(inplace=True)

        logger.info(f"Loaded {len(df)} candles from {self.csv_path}")
        return df


class DataFrameDataFeed(DataFeed):
    """Data feed that wraps a pandas DataFrame.

    Useful for testing with pre-loaded data.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame
    ):
        """Initialize the DataFrame data feed.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            data: DataFrame with OHLCV data indexed by datetime
        """
        super().__init__(symbol, timeframe)
        self._preloaded_data = data.copy()

    def load_data(self) -> pd.DataFrame:
        """Return the preloaded data.

        Returns:
            DataFrame with OHLCV data
        """
        # Ensure required columns exist
        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in self._preloaded_data.columns:
                raise ValueError(f"Missing required column: {col}")

        return self._preloaded_data[required_cols]


class LiveSimulatedFeed(DataFeed):
    """Data feed that simulates live market data.

    This feed generates new candles in real-time, useful for
    testing paper trading in a live-like environment.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        initial_price: float = 50000.0,
        volatility: float = 0.02,
        drift: float = 0.0
    ):
        """Initialize the live simulated feed.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            initial_price: Starting price
            volatility: Price volatility
            drift: Price drift/trend
        """
        super().__init__(symbol, timeframe)
        self.initial_price = initial_price
        self.volatility = volatility
        self.drift = drift
        self._current_price = initial_price
        self._last_update: Optional[datetime] = None

    def load_data(self) -> pd.DataFrame:
        """Initialize empty data frame that will be filled as candles arrive."""
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    def get_next_candle(self) -> Optional[pd.Series]:
        """Generate a new simulated candle.

        Returns:
            Series with OHLCV data
        """
        now = datetime.now()

        # Calculate time delta
        if self._last_update is not None:
            delta = (now - self._last_update).total_seconds()
            period_seconds = self._parse_timeframe()

            if delta < period_seconds:
                # Not enough time has passed
                return None

        # Generate new candle
        open_price = self._current_price

        # Generate price movement
        dt = self._parse_timeframe() / (365 * 24 * 3600)
        change = np.random.normal(
            (self.drift - 0.5 * self.volatility ** 2) * dt,
            self.volatility * np.sqrt(dt)
        )
        close_price = open_price * (1 + change)

        # Generate high/low
        high_low_range = abs(close_price - open_price) * (1 + np.random.random() * 2)
        high = max(open_price, close_price) * (1 + np.random.random() * 0.001)
        low = min(open_price, close_price) * (1 - np.random.random() * 0.001)

        # Generate volume
        volume = np.random.uniform(100, 10000)

        # Create candle
        candle = pd.Series({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_price,
            "volume": volume
        }, name=now)

        self._current_price = close_price
        self._last_update = now

        # Append to data
        if self._data is None:
            self._data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        self._data.loc[now] = candle
        self._current_index = len(self._data)

        return candle

    def _parse_timeframe(self) -> int:
        """Parse timeframe string to seconds.

        Returns:
            Timeframe in seconds
        """
        if self.timeframe.endswith('min'):
            return int(self.timeframe[:-3]) * 60
        elif self.timeframe.endswith('m'):
            return int(self.timeframe[:-1]) * 60
        elif self.timeframe.endswith('h'):
            return int(self.timeframe[:-1]) * 3600
        elif self.timeframe.endswith('d'):
            return int(self.timeframe[:-1]) * 86400
        else:
            return 60
