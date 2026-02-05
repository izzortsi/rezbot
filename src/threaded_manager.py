"""ThreadedManager - Central coordinator for trading operations.

This module provides the main manager class that coordinates multiple
trading threads and process pools for CPU-bound operations.
"""

from contextlib import contextmanager
from typing import Dict, Optional, List, Any
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import logging
import os
import sys

# Import from existing modules
from src import *
from src.config import ApiConfig
from src.concurrency.multiprocessing import ProcessPoolManager
from src.threaded_atrader import ThreadedATrader
from src.tradingview_handlers import ThreadedTAHandler

# Optional imports for plotting
try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

logger = logging.getLogger(__name__)


class ThreadedManager:
    """Central coordinator for trading operations.

    This class manages:
    - Multiple trader threads (I/O-bound operations)
    - Process pool for CPU-bound operations (indicators, ML)
    - Thread-safe collections for traders and handlers
    - Graceful shutdown coordination

    Example:
        config = ApiConfig.from_env()
        manager = ThreadedManager(api_config=config, tf="30m", rate=1)
        manager.start_process_pool()

        trader = manager.start_trader(strategy, "BTCUSDT", leverage=5)

        # Later...
        manager.stop(timeout=30)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_config: Optional[ApiConfig] = None,
        rate: int = 1,
        tf: str = "5m"
    ):
        """Initialize the ThreadedManager.

        Args:
            api_key: Binance API key (deprecated, use api_config instead)
            api_secret: Binance API secret (deprecated, use api_config instead)
            api_config: ApiConfig object with credentials (recommended)
            rate: Update rate for debugging purposes
            tf: Default timeframe for trading
        """
        # Handle both old and new API configuration methods
        if api_config is not None:
            self._api_config = api_config
        elif api_key is not None and api_secret is not None:
            # Backwards compatibility with old API
            self._api_config = ApiConfig(api_key=api_key, api_secret=api_secret)
            logger.warning(
                "Direct api_key/api_secret parameters are deprecated. "
                "Use ApiConfig instead."
            )
        else:
            # Try to load from environment
            self._api_config = ApiConfig.from_env()

        # Initialize Binance clients
        self.client = Client(
            api_key=self._api_config.api_key,
            api_secret=self._api_config.api_secret,
            exchange=self._api_config.exchange
        )
        self.bwsm = BinanceWebSocketApiManager(
            output_default="UnicornFy",
            exchange=self._api_config.exchange
        )

        # Configuration
        self.rate = rate
        self.tf = tf
        self.is_monitoring = False

        # Thread-safe collections with locks
        self._traders_lock = threading.RLock()
        self._ta_handlers_lock = threading.RLock()
        self._traders: Dict[str, ThreadedATrader] = {}
        self._ta_handlers: Dict[str, ThreadedTAHandler] = {}

        # Thread pool for managing trader threads
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        self._threads: List[threading.Thread] = []

        # Process pool for CPU-bound operations
        self._process_pool = ProcessPoolManager(max_workers=None)

        # Shutdown coordination
        self._shutdown_event = threading.Event()
        self._is_shutting_down = False

        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None

    # ============================================================
    # Process Pool Management
    # ============================================================

    @property
    def process_pool(self) -> ProcessPoolManager:
        """Get the process pool for CPU-bound operations."""
        return self._process_pool

    def start_process_pool(self) -> None:
        """Start the process pool for CPU-bound tasks.

        This must be called before traders can use indicator computation
        via the process pool.
        """
        if not self._process_pool.is_running:
            self._process_pool.start()
            logger.info("Process pool started")

    # ============================================================
    # Thread-Safe Trader Management
    # ============================================================

    @contextmanager
    def _traders_context(self):
        """Thread-safe context for traders dictionary access.

        Example:
            with self._traders_context() as traders:
                for name, trader in traders.items():
                    # Safe access to traders
        """
        with self._traders_lock:
            yield self._traders

    @contextmanager
    def _ta_handlers_context(self):
        """Thread-safe context for TA handlers access.

        Example:
            with self._ta_handlers_context() as handlers:
                for name, handler in handlers.items():
                    # Safe access to handlers
        """
        with self._ta_handlers_lock:
            yield self._ta_handlers

    def start_trader(
        self,
        strategy,
        symbol: str,
        leverage: int = 1,
        is_real: bool = False,
        qty: float = 0.002,
        w1: int = 5,
        m1: float = 1.2
    ) -> Optional[ThreadedATrader]:
        """Start a new trader with thread-safe registration.

        Args:
            strategy: Strategy instance to use
            symbol: Trading symbol (e.g., "BTCUSDT")
            leverage: Trading leverage
            is_real: Whether to use real trading (vs test mode)
            qty: Base quantity
            w1: EMA window for indicators
            m1: Standard deviation multiplier for Bollinger Bands

        Returns:
            The created ThreadedATrader instance, or None if already exists
        """
        trader_name = name_trader(strategy, symbol)

        with self._traders_context() as traders:
            if trader_name in traders:
                print(f"Redundant trader. No new thread was created.")
                print("Try changing some of the strategy's parameters.")
                return None

            # Create TA handler for this trader
            handler = ThreadedTAHandler(symbol, [self.tf], self.rate)

            with self._ta_handlers_context() as ta_handlers:
                ta_handlers[trader_name] = handler

            # Create and start the trader
            trader = ThreadedATrader(
                self, trader_name, strategy, symbol, leverage, is_real, qty, w1=w1, m1=m1
            )
            traders[trader.name] = trader
            trader.ta_handler = handler

            # Track thread for shutdown
            self._threads.append(trader)
            self._threads.append(handler)

            logger.info(f"Started trader: {trader_name}")
            return trader

    def get_traders(self) -> List[tuple[str, ThreadedATrader]]:
        """Get list of all traders (thread-safe).

        Returns:
            List of (name, trader) tuples
        """
        with self._traders_context() as traders:
            return list(traders.items())

    def get_ta_handlers(self) -> List[tuple[str, ThreadedTAHandler]]:
        """Get list of all TA handlers (thread-safe).

        Returns:
            List of (name, handler) tuples
        """
        with self._ta_handlers_context() as handlers:
            return list(handlers.items())

    def close_traders(self, traders: Optional[List[Any]] = None) -> None:
        """Close traders and positions.

        Args:
            traders: List of specific traders to close, or None for all
        """
        if traders is None:
            # Close all traders
            with self._traders_context() as traders_dict:
                for name, trader in list(traders_dict.items()):
                    trader.stop()

            with self._ta_handlers_context() as handlers:
                for name, handler in list(handlers.items()):
                    handler.stop()
                    del handlers[name]

            # Clear threads list
            self._threads.clear()
        else:
            # Close specific traders
            for trader in traders:
                trader.stop()

    # ============================================================
    # Shutdown
    # ============================================================

    def stop(self, timeout: float = 30.0, kill: bool = False) -> None:
        """Graceful shutdown with timeout.

        Args:
            timeout: Maximum time to wait for threads to stop (seconds)
            kill: If True, call os.sys.exit(0) after shutdown (legacy behavior)
        """
        if self._is_shutting_down:
            logger.warning("Shutdown already in progress")
            return

        self._is_shutting_down = True
        self._shutdown_event.set()

        logger.info("Starting graceful shutdown...")

        # Stop monitoring
        self.stop_monitoring()

        # Stop all traders and wait for completion
        with self._traders_context() as traders:
            for name, trader in list(traders.items()):
                trader.stop()

        # Wait for threads to complete
        for thread in self._threads:
            if hasattr(thread, 'wait_stopped'):
                thread.wait_stopped(timeout=timeout)
            elif thread.is_alive():
                thread.join(timeout=timeout)

        # Stop all TA handlers
        with self._ta_handlers_context() as handlers:
            for name, handler in list(handlers.items()):
                handler.stop()

        # Shutdown process pool first (CPU workers)
        self._process_pool.stop(wait=True)

        # Shutdown thread pool if it exists
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None

        # Stop WebSocket manager
        self.bwsm.stop_manager_with_all_streams()

        logger.info("Shutdown complete")

        # Legacy behavior: exit the process
        if kill:
            sys.exit(0)

    # ============================================================
    # Monitoring
    # ============================================================

    def traders_status(self) -> List[Any]:
        """Get status of all traders.

        Returns:
            List of trader status objects
        """
        return [trader.status() for _, trader in self.get_traders()]

    def pcheck(self) -> None:
        """Print status of all traders."""
        for name, trader in self.get_traders():
            print(f"""
            trader: {trader.name}
            avg volatility: {(trader.data_window.close_std/trader.data_window.close_ema).mean()*100}%
            number of trades: {trader.num_trades}
            is positioned? {trader.is_positioned}
            position type: {trader.position_type}
            entry price: {trader.entry_price}
            last price: {trader.last_price}
            TV signals: {[s["RECOMMENDATION"] for s in self.ta_handlers[name].summary]}, {self.ta_handlers[name].signal}
            current percentual profit (unleveraged): {trader.current_percentual_profit}
            cummulative leveraged profit: {trader.cum_profit}

            {trader.data_window.tail(3)}
                    """)

    def market_overview(self) -> None:
        """Display market overview (placeholder for future implementation)."""
        pass

    def _monitoring(self, sleep: float) -> None:
        """Internal monitoring loop."""
        while self.is_monitoring and not self._shutdown_event.is_set():
            self.pcheck()
            time.sleep(sleep)

    def start_monitoring(self, sleep: float = 5) -> None:
        """Start monitoring thread.

        Args:
            sleep: Sleep interval between status checks
        """
        if self.is_monitoring:
            logger.warning("Monitoring already started")
            return

        self.is_monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring,
            args=(sleep,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Monitoring started with {sleep}s interval")

    def sm(self, sleep: float = 5) -> None:
        """Toggle monitoring on/off.

        Args:
            sleep: Sleep interval between status checks
        """
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring(sleep)

    def stop_monitoring(self) -> None:
        """Stop monitoring thread."""
        self.is_monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        logger.info("Monitoring stopped")

    # ============================================================
    # Plotting
    # ============================================================

    def plot_dw(self, trader: ThreadedATrader) -> None:
        """Plot data window for a trader.

        Args:
            trader: The trader to plot data for
        """
        if not HAS_MATPLOTLIB:
            logger.error("matplotlib not available for plotting")
            return

        data = trader.data_window
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        close_line, = ax.plot(data.close)
        close_ema_line, = ax.plot(data.close_ema)
        cs_line, = ax.plot(data.cs, "g--")
        ci_line, = ax.plot(data.ci, "r--")

        def animate(i, trader):
            data = trader.data_window
            close_line.set_ydata(data.close)
            close_ema_line.set_ydata(data.close_ema)
            cs_line.set_ydata(data.cs)
            ci_line.set_ydata(data.ci)
            return close_line, close_ema_line, cs_line, ci_line

        ani = animation.FuncAnimation(
            fig, animate, fargs=(trader,), interval=100, blit=True
        )
        plt.show()
