"""WebSocket client for Binance USDT-M Futures using binance-sdk-derivatives-trading-usds-futures.

This module provides a synchronous wrapper around the new SDK's async WebSocket,
bridging async operations to the synchronous code pattern used by rezbot.
"""

import asyncio
import threading
import time
import logging
from typing import Dict, Any, Optional, Callable
from queue import Queue
from dataclasses import dataclass

from binance_common.configuration import ConfigurationWebSocketStreams
from binance_common.constants import (
    DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_PROD_URL,
    DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_TESTNET_URL,
)
from binance_sdk_derivatives_trading_usds_futures import DerivativesTradingUsdsFutures

logger = logging.getLogger(__name__)


@dataclass
class StreamConfig:
    """Configuration for a WebSocket stream."""
    symbol: str
    interval: str
    stream_name: str


class AsyncWebSocketBridge:
    """Bridge between async WebSocket and synchronous code.

    This class runs an asyncio event loop in a background thread and
    provides thread-safe methods for interacting with the async WebSocket.
    """

    def __init__(self, api_key: str, api_secret: str, stream_url: str):
        """Initialize the async WebSocket bridge.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            stream_url: WebSocket stream URL
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.stream_url = stream_url

        # Event loop and thread
        self._loop = None
        self._thread = None
        self._is_running = False
        self._lock = threading.RLock()

        # Binance SDK client and connection
        self._client = None
        self._connection = None

        # Stream management
        self._queues: Dict[str, Queue] = {}
        self._streams: Dict[str, Any] = {}
        self._is_stopping = False

        # Start event loop
        self._start_event_loop()

    def _start_event_loop(self) -> None:
        """Start asyncio event loop in background thread."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._is_running = True
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            time.sleep(0.001)

    def _run_coroutine(self, coro, timeout: float = 30.0):
        """Run a coroutine in the event loop from a synchronous thread.

        Args:
            coro: Coroutine to run
            timeout: Timeout in seconds

        Returns:
            Result of the coroutine

        Raises:
            TimeoutError: If coroutine doesn't complete within timeout
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def create_connection(self) -> None:
        """Create WebSocket connection."""
        async def _create():
            config = ConfigurationWebSocketStreams(
                stream_url=self.stream_url,
                # API key/secret not typically needed for public streams
                # but may be needed for user data streams
            )
            self._client = DerivativesTradingUsdsFutures(config_ws_streams=config)
            self._connection = await self._client.websocket_streams.create_connection()
            logger.info("WebSocket connection created")

        self._run_coroutine(_create())

    def subscribe_klines(self, symbol: str, interval: str, stream_name: str) -> None:
        """Subscribe to kline stream.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "1m", "5m", "1h")
            stream_name: Name for this stream
        """
        async def _subscribe():
            try:
                stream = await self._connection.kline_candlestick_streams(symbol=symbol, interval=interval)

                # Create thread-safe queue for this stream
                with self._lock:
                    self._queues[stream_name] = Queue()

                # Define message handler
                def on_message(data):
                    with self._lock:
                        if stream_name in self._queues and not self._is_stopping:
                            try:
                                converted = self._convert_kline_data(data)
                                self._queues[stream_name].put(converted)
                            except Exception as e:
                                logger.error(f"Error converting kline data: {e}")

                # Register message handler (error event is not supported by this SDK)
                stream.on("message", on_message)

                # Store stream reference
                with self._lock:
                    self._streams[stream_name] = stream

                logger.info(f"Subscribed to klines: {symbol} {interval} -> {stream_name}")

            except Exception as e:
                logger.error(f"Failed to subscribe to klines: {e}")
                raise

        self._run_coroutine(_subscribe())

    def _convert_kline_data(self, data) -> Dict[str, Any]:
        """Convert new SDK kline format to old format.

        The new SDK returns objects with attributes like k.o, k.h, k.l, k.c
        We need to convert to the format expected by rezbot.
        """
        try:
            # The new SDK structure has nested data
            # Try to access the kline data
            if hasattr(data, 'k'):
                k = data.k
                return {
                    "event_type": "kline",
                    "kline": {
                        "open_price": str(getattr(k, 'o', 0)),
                        "high_price": str(getattr(k, 'h', 0)),
                        "low_price": str(getattr(k, 'l', 0)),
                        "close_price": str(getattr(k, 'c', 0)),
                        "base_volume": str(getattr(k, 'v', 0)),
                        "trade_time": getattr(data, 'E', getattr(data, 't', 0)),
                        "is_closed": getattr(k, 'x', False),
                    }
                }
            else:
                # Fallback for different response format
                return {
                    "event_type": "kline",
                    "kline": {
                        "open_price": str(getattr(data, 'o', 0)),
                        "high_price": str(getattr(data, 'h', 0)),
                        "low_price": str(getattr(data, 'l', 0)),
                        "close_price": str(getattr(data, 'c', 0)),
                        "base_volume": str(getattr(data, 'v', 0)),
                        "trade_time": getattr(data, 'E', getattr(data, 't', 0)),
                        "is_closed": getattr(data, 'x', False),
                    }
                }
        except Exception as e:
            logger.error(f"Error converting kline data: {e}, data type: {type(data)}")
            # Return a minimal valid structure
            return {
                "event_type": "kline",
                "kline": {
                    "open_price": "0",
                    "high_price": "0",
                    "low_price": "0",
                    "close_price": "0",
                    "base_volume": "0",
                    "trade_time": 0,
                    "is_closed": False,
                }
            }

    def pop_stream_data(self, stream_name: str) -> Any:
        """Get next data from stream buffer (thread-safe, non-blocking).

        Args:
            stream_name: Name of the stream

        Returns:
            Data dict, or False if no data available
        """
        with self._lock:
            if stream_name in self._queues:
                try:
                    return self._queues[stream_name].get_nowait()
                except:
                    return False
        return False

    def stop_stream(self, stream_name: str) -> None:
        """Unsubscribe from a stream.

        Args:
            stream_name: Name of the stream to stop
        """
        async def _stop():
            with self._lock:
                if stream_name in self._streams:
                    try:
                        stream = self._streams[stream_name]
                        # Unsubscribe if the SDK supports it
                        if hasattr(stream, 'unsubscribe'):
                            await stream.unsubscribe()
                    except Exception as e:
                        logger.error(f"Error stopping stream {stream_name}: {e}")
                    finally:
                        del self._streams[stream_name]
                if stream_name in self._queues:
                    del self._queues[stream_name]

        self._run_coroutine(_stop())
        logger.debug(f"Stopped stream: {stream_name}")

    def stop_all(self) -> None:
        """Stop all streams and close connection."""
        self._is_stopping = True

        async def _close():
            # Close all streams
            with self._lock:
                for stream_name in list(self._streams.keys()):
                    try:
                        stream = self._streams[stream_name]
                        if hasattr(stream, 'unsubscribe'):
                            await stream.unsubscribe()
                    except Exception as e:
                        logger.error(f"Error closing stream {stream_name}: {e}")

                self._streams.clear()
                self._queues.clear()

            # Close connection
            if self._connection:
                try:
                    await self._connection.close_connection(close_session=True)
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

        try:
            self._run_coroutine(_close())
        except Exception as e:
            logger.error(f"Error in stop_all: {e}")

        # Stop event loop
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        self._is_running = False
        logger.info("WebSocket bridge stopped")

    @property
    def is_stopping(self) -> bool:
        """Check if the bridge is stopping."""
        return self._is_stopping

    @property
    def is_running(self) -> bool:
        """Check if the event loop is running."""
        return self._is_running


class BinanceWebSocketClient:
    """Synchronous wrapper for Binance WebSocket.

    This class provides a synchronous interface matching the old
    unicorn-binance-websocket-api pattern, using the async bridge internally.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """Initialize the WebSocket client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet instead of production
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # Select URL based on testnet flag
        stream_url = (
            DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_TESTNET_URL
            if testnet
            else DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_PROD_URL
        )

        # Create async bridge
        self._bridge = AsyncWebSocketBridge(api_key, api_secret, stream_url)
        self._bridge.create_connection()

        # Stream management
        self._stream_map: Dict[str, str] = {}
        self._next_stream_id = 0
        self._lock = threading.RLock()

        logger.info(f"Binance WebSocket client initialized (testnet={testnet})")

    def create_stream(
        self,
        channel: str,
        market: str,
        **kwargs
    ) -> Optional[str]:
        """Create a new WebSocket stream.

        Args:
            channel: Stream type (e.g., "kline")
            market: Trading symbol (e.g., "BTCUSDT")
            **kwargs: Additional parameters:
                - stream_buffer_name: Name for the stream buffer
                - interval: Timeframe for klines

        Returns:
            Stream ID for reference
        """
        with self._lock:
            stream_name = kwargs.get("stream_buffer_name", f"{channel}_{market}")

            if channel == "kline":
                interval = kwargs.get("interval", "1m")
                self._bridge.subscribe_klines(market, interval, stream_name)
            else:
                logger.warning(f"Unsupported channel: {channel}")
                return None

            # Create stream ID for backwards compatibility
            stream_id = str(self._next_stream_id)
            self._next_stream_id += 1
            self._stream_map[stream_id] = stream_name

            logger.debug(f"Created stream: {stream_name} (id: {stream_id})")
            return stream_id

    def pop_stream_data_from_stream_buffer(self, stream_name: str) -> Any:
        """Get next data from stream buffer (non-blocking).

        Args:
            stream_name: Name of the stream buffer

        Returns:
            Stream data dict, or False if no data available
        """
        return self._bridge.pop_stream_data(stream_name)

    def is_manager_stopping(self) -> bool:
        """Check if the manager is stopping.

        Returns:
            True if stopping, False otherwise
        """
        return self._bridge.is_stopping

    def stop_stream(self, stream_id: str) -> None:
        """Stop a specific stream.

        Args:
            stream_id: ID of the stream to stop
        """
        with self._lock:
            if stream_id in self._stream_map:
                stream_name = self._stream_map[stream_id]
                self._bridge.stop_stream(stream_name)
                del self._stream_map[stream_id]

    def stop_manager_with_all_streams(self) -> None:
        """Stop all streams and shut down the manager."""
        self._bridge.stop_all()
        logger.info("WebSocket manager stopped")


def create_websocket_client(api_key: str, api_secret: str, testnet: bool = False) -> BinanceWebSocketClient:
    """Create a Binance WebSocket client.

    Args:
        api_key: Binance API key
        api_secret: Binance API secret
        testnet: Use testnet instead of production

    Returns:
        BinanceWebSocketClient instance

    Example:
        ws_client = create_websocket_client(
            api_key="your_key",
            api_secret="your_secret"
        )
        stream_id = ws_client.create_stream(
            "kline",
            "BTCUSDT",
            interval="1m",
            stream_buffer_name="btc_kline_1m"
        )
    """
    return BinanceWebSocketClient(api_key, api_secret, testnet)
