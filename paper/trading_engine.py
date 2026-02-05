"""Paper trading engine for simulated live trading.

This module provides the PaperTrader class that simulates live trading
without using real money or making actual API calls.
"""

import threading
import time
import pandas as pd
from typing import Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field
import logging

from src.strategies.base import Strategy, PositionType
from src.trading.position_manager import Position, PositionManager, TradeRecord
from src.trading.risk_manager import RiskManager, RiskParameters, ProfitMetrics
from src.trading.indicator_processor import IndicatorProcessor
from src.compute.indicators import compute_all_indicators
from paper.data_feed import DataFeed, LiveSimulatedFeed

logger = logging.getLogger(__name__)


@dataclass
class PaperConfig:
    """Configuration for paper trading.

    Attributes:
        symbol: Trading symbol
        timeframe: Timeframe for trading
        leverage: Trading leverage
        initial_balance: Starting virtual balance
        position_size_pct: Position size as percentage of balance
        w1: Bollinger band window parameter
        m1: Bollinger band multiplier parameter
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period
    """
    symbol: str = "BTCUSDT"
    timeframe: str = "5m"
    leverage: int = 10
    initial_balance: float = 1000.0
    position_size_pct: float = 0.95
    w1: int = 5
    m1: float = 1.2
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


class PaperTrader:
    """Simulated live trading without real money.

    This class implements a complete paper trading system that:
    - Uses the same Strategy ABC as live trading
    - Simulates order execution with realistic fills
    - Tracks virtual positions and P&L
    - Generates trade history and statistics

    Example:
        config = PaperConfig(symbol="BTCUSDT", timeframe="5m", leverage=10)
        strategy = PullbackStrategy(params)

        trader = PaperTrader(
            config=config,
            strategy=strategy,
            data_feed=data_feed
        )

        # Run for 1 hour
        trader.run(duration_seconds=3600)

        # Get results
        report = trader.get_report()
    """

    def __init__(
        self,
        config: PaperConfig,
        strategy: Strategy,
        data_feed: Optional[DataFeed] = None,
        on_trade: Optional[Callable[[TradeRecord], None]] = None
    ):
        """Initialize the paper trader.

        Args:
            config: Paper trading configuration
            strategy: Trading strategy to use
            data_feed: Data feed for market data (creates LiveSimulatedFeed if None)
            on_trade: Callback function when a trade completes
        """
        self._config = config
        self._strategy = strategy

        # Create data feed if not provided
        if data_feed is None:
            data_feed = LiveSimulatedFeed(
                symbol=config.symbol,
                timeframe=config.timeframe,
                initial_price=50000.0,
                volatility=0.02
            )
        self._data_feed = data_feed

        self._on_trade = on_trade

        # Trading components
        self._position_manager = PositionManager()

        risk_params = RiskParameters(
            stoploss_pct=strategy.stoploss,
            take_profit_pct=strategy.take_profit,
            leverage=config.leverage
        )
        self._risk_manager = RiskManager(risk_params)

        # State
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Data
        self._data_window: Optional[pd.DataFrame] = None
        self._current_price: Optional[float] = None
        self._current_metrics: Optional[ProfitMetrics] = None

        # Statistics
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._balance = config.initial_balance
        self._initial_balance = config.initial_balance

    def start(self) -> None:
        """Start paper trading in a separate thread."""
        if self._running:
            logger.warning("Paper trader already running")
            return

        self._running = True
        self._stop_event.clear()
        self._start_time = datetime.now()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        logger.info(f"Paper trading started for {self._config.symbol}")

    def stop(self, timeout: float = 30.0) -> None:
        """Stop paper trading.

        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Paper trader thread did not stop within timeout")

        self._end_time = datetime.now()
        logger.info(f"Paper trading stopped for {self._config.symbol}")

    def run(self, duration_seconds: Optional[float] = None) -> None:
        """Run paper trading in the current thread.

        Args:
            duration_seconds: Duration to run (None for infinite)
        """
        self._running = True
        self._stop_event.clear()
        self._start_time = datetime.now()

        if duration_seconds:
            # Set a timer to stop
            def timer_stop():
                time.sleep(duration_seconds)
                self._stop_event.set()

            timer_thread = threading.Thread(target=timer_stop, daemon=True)
            timer_thread.start()

        self._run_loop()

        self._end_time = datetime.now()
        self._running = False

    def _run_loop(self) -> None:
        """Main trading loop."""
        while not self._stop_event.is_set():
            try:
                # Get next candle
                candle = self._data_feed.get_next_candle()

                if candle is None:
                    # No new data yet
                    time.sleep(0.1)
                    continue

                # Update current price
                self._current_price = float(candle["close"])

                # Update data window
                self._update_data_window(candle)

                # Process trading logic
                self._process_trading_logic()

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(1)

        # Close any open position at end
        if self._position_manager.is_positioned:
            self._close_position("END_OF_SESSION")

    def _update_data_window(self, candle: pd.Series) -> None:
        """Update the data window with new candle data.

        Args:
            candle: New candle data
        """
        # Initialize data window if needed
        if self._data_window is None:
            # Create initial window with NaN
            index = pd.date_range(
                end=candle.name,
                periods=100,
                freq=self._config.timeframe
            )
            self._data_window = pd.DataFrame(index=index)
            self._data_window["close"] = float(candle["close"])

        # Add new candle
        self._data_window.loc[candle.name] = {
            "close": float(candle["close"]),
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "volume": float(candle["volume"]),
        }

        # Compute indicators
        try:
            indicators = compute_all_indicators(
                close=self._data_window["close"],
                w1=self._config.w1,
                m1=self._config.m1,
                macd_params={
                    "fast": self._config.macd_fast,
                    "slow": self._config.macd_slow,
                    "signal": self._config.macd_signal
                }
            )

            # Merge indicators
            for col in indicators.columns:
                if col not in self._data_window.columns:
                    self._data_window[col] = indicators[col]
                else:
                    self._data_window.loc[:, col] = indicators[col]

        except Exception as e:
            logger.error(f"Error computing indicators: {e}")

    def _process_trading_logic(self) -> None:
        """Process entry and exit signals."""
        if self._position_manager.is_positioned:
            self._check_exit_conditions()
        else:
            self._check_entry_condition()

    def _check_entry_condition(self) -> None:
        """Check for entry signal and open position if valid."""
        if self._data_window is None or len(self._data_window) < 30:
            return

        # Create mock trader context
        context = self._create_trader_context()

        # Check strategy entry signal
        should_enter, position_type = self._strategy.entry_signal(context)

        if should_enter and position_type is not None:
            self._open_position(position_type)

    def _check_exit_conditions(self) -> None:
        """Check for exit signals (TP, SL, strategy exit)."""
        if not self._position_manager.is_positioned:
            return

        position = self._position_manager.position

        # Calculate current profit
        metrics = self._risk_manager.calculate_current_profit(
            position, self._current_price
        )
        self._current_metrics = metrics

        # Check stop loss
        if self._risk_manager.check_stop_loss(metrics):
            self._close_position("SL")
            return

        # Check take profit
        if self._risk_manager.check_take_profit(metrics):
            self._close_position("TP")
            return

        # Check strategy exit signal
        context = self._create_trader_context()
        if self._strategy.exit_signal(context):
            self._close_position("STRATEGY")

    def _open_position(self, position_type: PositionType) -> None:
        """Open a new position.

        Args:
            position_type: LONG or SHORT
        """
        # Calculate position size
        entry_price = self._current_price
        qty = self._calculate_position_size(entry_price)

        # Create position
        position = Position(
            symbol=self._config.symbol,
            position_type=position_type,
            entry_price=entry_price,
            entry_time=datetime.now(),
            qty=qty,
            leverage=self._config.leverage
        )

        try:
            self._position_manager.enter_position(position)
            logger.info(f"Opened {position.side} position at {entry_price:.2f}")

        except ValueError as e:
            logger.error(f"Failed to open position: {e}")

    def _close_position(self, reason: str) -> None:
        """Close current position.

        Args:
            reason: Exit reason ("TP", "SL", "STRATEGY", "END_OF_SESSION")
        """
        position = self._position_manager.position
        if position is None:
            return

        exit_price = self._current_price
        exit_time = datetime.now()

        record = self._position_manager.exit_position(
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=reason
        )

        if record:
            # Update balance
            self._balance += record.profit * record.position.qty

            logger.info(
                f"Closed {record.side} position: "
                f"entry={record.position.entry_price:.2f}, "
                f"exit={exit_price:.2f}, "
                f"PnL={record.leveraged_profit:.2f}% "
                f"({reason})"
            )

            # Call callback
            if self._on_trade:
                self._on_trade(record)

    def _calculate_position_size(self, entry_price: float) -> float:
        """Calculate position size based on balance and risk.

        Args:
            entry_price: Current entry price

        Returns:
            Position quantity
        """
        # Simple position sizing: use percentage of balance
        # This is a simplified calculation
        balance_for_trade = self._balance * self._config.position_size_pct
        notional_value = balance_for_trade * self._config.leverage

        qty = notional_value / entry_price

        # Round to reasonable precision
        qty = round(qty, 6)

        # Ensure minimum position size
        if qty < 0.001:
            qty = 0.001

        return qty

    def _create_trader_context(self):
        """Create a mock trader context for strategy evaluation."""
        class MockTraderContext:
            def __init__(self, data_window, position_manager, risk_manager, current_price):
                self._data_window = data_window
                self._position_manager = position_manager
                self._risk_manager = risk_manager
                self._current_price = current_price

            @property
            def data_window(self):
                return self._data_window

            @property
            def current_percentual_profit(self):
                if self._position_manager.is_positioned:
                    metrics = self._risk_manager.calculate_current_profit(
                        self._position_manager.position,
                        self._current_price
                    )
                    return metrics.percentual_profit
                return 0.0

            @property
            def is_positioned(self):
                return self._position_manager.is_positioned

            @property
            def position_type(self):
                return self._position_manager.position_type

        return MockTraderContext(
            self._data_window,
            self._position_manager,
            self._risk_manager,
            self._current_price
        )

    @property
    def is_running(self) -> bool:
        """Check if paper trader is running."""
        return self._running

    @property
    def is_positioned(self) -> bool:
        """Check if currently in a position."""
        return self._position_manager.is_positioned

    @property
    def current_price(self) -> Optional[float]:
        """Get current market price."""
        return self._current_price

    @property
    def current_profit(self) -> Optional[ProfitMetrics]:
        """Get current profit metrics if positioned."""
        if self._position_manager.is_positioned:
            return self._current_metrics
        return None

    @property
    def balance(self) -> float:
        """Get current virtual balance."""
        if self._position_manager.is_positioned and self._current_metrics:
            return self._balance + self._current_metrics.unrealized_pnl
        return self._balance

    @property
    def total_return_pct(self) -> float:
        """Get total return percentage."""
        return ((self.balance - self._initial_balance) / self._initial_balance) * 100

    def get_trade_records(self) -> List[TradeRecord]:
        """Get list of completed trades.

        Returns:
            List of TradeRecord objects
        """
        return self._position_manager.get_trade_history()

    def get_report(self):
        """Generate a trade report.

        Returns:
            TradeReport object with statistics
        """
        from .reporting import TradeReport, Statistics

        records = self.get_trade_records()
        stats = Statistics.calculate_from_records(records, self._config.leverage)

        return TradeReport(
            symbol=self._config.symbol,
            timeframe=self._config.timeframe,
            start_time=self._start_time or datetime.now(),
            end_time=self._end_time or datetime.now(),
            statistics=stats,
            trade_records=records
        )
