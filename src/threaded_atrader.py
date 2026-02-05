"""ThreadedATrader - Lightweight trader coordinator.

This module provides the refactored ThreadedATrader class that uses
the new trading components and StoppableThread base class.
"""

import threading
import time
import os
import pandas as pd
from datetime import datetime
from typing import Optional
import logging

from src import *
from src.concurrency.threading import StoppableThread
from src.strategies.base import Strategy, PositionType
from src.trading import (
    Position,
    PositionManager,
    StreamConfig,
    StreamProcessor,
    IndicatorProcessor,
    TradeExecutor,
    OrderSide,
    RiskManager,
    RiskParameters,
)
from src.grabber import DataGrabber
from src.symbols_formats import FORMATS

logger = logging.getLogger(__name__)


class ThreadedATrader(StoppableThread):
    """Lightweight trader coordinator with hybrid concurrency.

    This class coordinates trading operations by delegating to
    specialized components:
    - PositionManager: Thread-safe position state
    - StreamProcessor: WebSocket data processing
    - IndicatorProcessor: Async indicator computation via process pool
    - TradeExecutor: API calls and order management
    - RiskManager: Profit/loss calculations

    The main loop handles:
    1. Processing WebSocket data (I/O-bound, in thread)
    2. Checking if indicators are ready (CPU-bound from process pool)
    3. Evaluating trading signals
    4. Executing trades if signals trigger

    Example:
        trader = ThreadedATrader(
            manager=manager,
            name="pullback_30m_btcusdt",
            strategy=strategy,
            symbol="BTCUSDT",
            leverage=5,
            is_real=False,
            qty=0.002,
            w1=5,
            m1=1.2
        )
        # Thread auto-starts, no need to call start()
    """

    def __init__(
        self,
        manager,
        name: str,
        strategy: Strategy,
        symbol: str,
        leverage: int,
        is_real: bool = False,
        qty: float = 0.002,
        w1: int = 5,
        m1: float = 1.2
    ):
        """Initialize the threaded trader.

        Args:
            manager: ThreadedManager instance
            name: Unique trader name
            strategy: Strategy instance
            symbol: Trading symbol
            leverage: Trading leverage
            is_real: Whether to use real trading
            qty: Base quantity
            w1: EMA window for indicators
            m1: Standard deviation multiplier for Bollinger Bands
        """
        # Initialize base thread class
        super().__init__(name=name, daemon=True)

        # Basic properties
        self.manager = manager
        self.name = name
        self.strategy = strategy
        self.symbol = symbol
        self.leverage = leverage
        self.is_real = is_real
        self.w1 = w1
        self.m1 = m1

        # Initialize trading components
        self.position_manager = PositionManager()

        self.indicator_processor = IndicatorProcessor(
            process_pool=manager.process_pool,
            w1=w1,
            m1=m1,
            macd_params=strategy.macd_params
        )

        self.trade_executor = TradeExecutor(
            client=manager.client,
            symbol=symbol,
            leverage=leverage,
            is_real=is_real
        )

        risk_params = RiskParameters(
            stoploss_pct=strategy.stoploss,
            take_profit_pct=strategy.take_profit,
            leverage=leverage
        )
        self.risk_manager = RiskManager(risk_params)

        # Legacy data grabber for initial data window
        self.grabber = DataGrabber(manager.client)
        self.data_window = self._get_initial_data_window()
        self.running_candles = []

        # Tracking properties (for backwards compatibility)
        # Note: cum_profit is now a property that delegates to position_manager
        self.num_trades = 0
        self.start_time = time.time()
        self.init_time = time.time()
        self.now = time.time()
        self.confirmatory_data = []

        # Setup logging
        strf_init_time = strf_epoch(self.init_time, fmt="%H-%M-%S")
        self.name_for_logs = f"{self.name}-{strf_init_time}"
        self.logger = setup_logger(
            f"{self.name}-logger",
            os.path.join(logs_for_this_run, f"{self.name_for_logs}.log"),
        )
        self.csv_log_path = os.path.join(
            logs_for_this_run, f"{self.name_for_logs}.csv"
        )

        # Setup stream processor
        stream_config = StreamConfig(
            symbol=symbol,
            timeframe=strategy.timeframe,
            w1=w1,
            m1=m1,
            macd_params=strategy.macd_params
        )
        self.stream_processor = StreamProcessor(
            config=stream_config,
            bwsm=manager.bwsm,
            data_window=self.data_window,
            indicator_processor=self.indicator_processor
        )

        # Start the stream
        self._start_stream()

        # Auto-start thread
        self.start()

    def _run_impl(self) -> None:
        """Main trader loop.

        This is the main loop that:
        1. Processes WebSocket data from the stream
        2. Updates indicators when computation completes
        3. Checks trading signals
        4. Executes trades if signals trigger
        """
        while not self.should_stop():
            try:
                # Process WebSocket data (I/O-bound)
                if self.stream_processor.process_next():
                    # New candle added
                    pass

                # Update indicators if computation complete (CPU-bound)
                if self.stream_processor.update_indicators_if_ready():
                    # Indicators ready, check signals
                    self._check_trading_signals()

                # Health check
                try:
                    self.manager.client.ping()
                except Exception as e:
                    self.logger.error(f"Connection error: {e}")

                # Log trades to CSV
                self._drop_trades_to_csv()

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")

    def _check_trading_signals(self) -> None:
        """Check and act on trading signals.

        This method evaluates entry/exit signals and executes trades.
        """
        if self.position_manager.is_positioned:
            self._check_exit_conditions()
        else:
            self._check_entry_condition()

    def _check_entry_condition(self) -> None:
        """Check entry signal and enter position if triggered."""
        should_enter, pos_type = self.strategy.entry_signal(self)

        if should_enter and pos_type is not None:
            entry_price = self.data_window.close.values[-1]
            entry_time = pd.Timestamp.now(tz="UTC")

            position = Position(
                symbol=self.symbol,
                position_type=pos_type,
                entry_price=entry_price,
                entry_time=entry_time,
                qty=self._get_qty(),
                leverage=self.leverage
            )

            if self.is_real:
                # Execute real orders
                self._execute_entry_order(pos_type)
            else:
                # Test mode - just track position
                self.position_manager.enter_position(position)
                self.logger.info(
                    f"TEST ENTRY: {entry_price} at {entry_time}; "
                    f"type: {pos_type.name}"
                )

    def _check_exit_conditions(self) -> None:
        """Check exit conditions and exit if triggered."""
        position = self.position_manager.position
        if position is None:
            return

        # Get current profit metrics
        current_price = self.stream_processor.last_price
        if current_price is None:
            return

        metrics = self.risk_manager.calculate_current_profit(
            position, current_price
        )

        exit_reason = None
        exit_price = current_price
        exit_time = pd.Timestamp.now(tz="UTC")

        if self.risk_manager.check_stop_loss(metrics):
            exit_reason = "SL"
        elif self.strategy.exit_signal(self):
            exit_reason = "TP"

        if exit_reason:
            if self.is_real:
                # Close position in real trading
                self._execute_exit_order(position.position_type)
            else:
                # Test mode - just close tracking
                self.position_manager.exit_position(
                    exit_price=exit_price,
                    exit_time=exit_time,
                    exit_reason=exit_reason
                )
                self.logger.info(
                    f"TEST {exit_reason}: {exit_price} at {exit_time}; "
                    f"pnl: {metrics.leveraged_profit:.2f}%"
                )

    def _execute_entry_order(self, pos_type: PositionType) -> None:
        """Execute entry order in real trading.

        Args:
            pos_type: LONG or SHORT position type
        """
        side = OrderSide.BUY if pos_type.long_side else OrderSide.SELL
        qty = self._get_qty()

        result = self.trade_executor.enter_position(side, qty)

        if result.success:
            # Get actual entry price from API
            entry_price = result.price
            entry_time = pd.Timestamp.now(tz="UTC")

            position = Position(
                symbol=self.symbol,
                position_type=pos_type,
                entry_price=entry_price,
                entry_time=entry_time,
                qty=qty,
                leverage=self.leverage
            )

            self.position_manager.enter_position(position)
            self.logger.info(
                f"ENTRY: {entry_price} at {entry_time}; type: {pos_type.name}"
            )

            # Place take profit order
            counterside = side.opposite
            tp_price = self.risk_manager.compute_take_profit_price(
                entry_price, pos_type
            )
            self.trade_executor.place_take_profit(counterside, tp_price, qty)
        else:
            self.logger.error(f"Entry order failed: {result.error}")

    def _execute_exit_order(self, pos_type: PositionType) -> None:
        """Execute exit order in real trading.

        Args:
            pos_type: LONG or SHORT position type
        """
        side = OrderSide.SELL if pos_type.long_side else OrderSide.BUY
        qty = self._get_qty()

        result = self.trade_executor.close_position(side, qty)

        if result.success:
            exit_price = result.price
            exit_time = pd.Timestamp.now(tz="UTC")

            # Record the trade
            self.position_manager.exit_position(
                exit_price=exit_price,
                exit_time=exit_time,
                exit_reason="MANUAL"
            )
            self.logger.info(f"EXIT: {exit_price} at {exit_time}")
        else:
            self.logger.error(f"Exit order failed: {result.error}")

    def _get_qty(self) -> str:
        """Get formatted quantity for trading.

        Returns:
            Formatted quantity string
        """
        if self.is_real and hasattr(self, 'qty'):
            return self.qty
        return str(self.trade_executor._format_qty(0.001))

    def _get_initial_data_window(self) -> pd.DataFrame:
        """Get initial data window with historical data.

        Returns:
            DataFrame with OHLCV and indicators
        """
        klines = self.grabber.get_data(
            symbol=self.symbol,
            tframe=self.strategy.timeframe,
            limit=2 * self.strategy.macd_params["slow"] + 1,
        )

        df = self.grabber.compute_indicators(
            klines.close,
            w1=self.w1,
            m1=self.m1,
            **self.strategy.macd_params
        )

        date = klines.date
        ohlv = klines[["open", "high", "low", "volume"]]
        return pd.concat([date, ohlv, df], axis=1)

    def _start_stream(self) -> None:
        """Start the WebSocket stream."""
        self.stream_processor.start_stream()

    def _drop_trades_to_csv(self) -> None:
        """Write completed trades to CSV file."""
        trades = self.position_manager.get_trade_history()
        updated_num = len(trades)

        if updated_num > 0:
            if updated_num == 1 and self.num_trades == 0:
                # First trade - write with header
                row = pd.DataFrame([{
                    "type": t.position.side,
                    "entry_time": t.position.entry_time,
                    "entry_price": t.position.entry_price,
                    "exit_time": t.exit_time,
                    "exit_price": t.exit_price,
                    "percentual_difference": t.percentual_profit,
                    "leveraged_percentual_difference": t.leveraged_profit,
                    "cumulative_profit": self.position_manager.get_cumulative_profit(),
                    "exit_reason": t.exit_reason,
                } for t in trades])
                row.to_csv(self.csv_log_path, header=True, mode="w", index=False)
                self.num_trades += 1
            elif updated_num > self.num_trades:
                # Subsequent trades - append without header
                trade = trades[-1]
                row = pd.DataFrame([{
                    "type": trade.position.side,
                    "entry_time": trade.position.entry_time,
                    "entry_price": trade.position.entry_price,
                    "exit_time": trade.exit_time,
                    "exit_price": trade.exit_price,
                    "percentual_difference": trade.percentual_profit,
                    "leveraged_percentual_difference": trade.leveraged_profit,
                    "cumulative_profit": self.position_manager.get_cumulative_profit(),
                    "exit_reason": trade.exit_reason,
                }])
                row.to_csv(self.csv_log_path, header=False, mode="a", index=False)
                self.num_trades += 1

    def stop(self) -> None:
        """Stop the trader gracefully.

        This method:
        1. Requests thread stop
        2. Stops the WebSocket stream
        3. Removes from manager's trader list
        """
        super().stop()
        self.stream_processor.stop()

        # Remove from manager
        with self.manager._traders_context() as traders:
            if self.name in traders:
                del traders[self.name]

        self.logger.info(f"Trader {self.name} stopped")

    # ============================================================
    # Backwards Compatibility Properties
    # ============================================================

    @property
    def is_positioned(self) -> bool:
        """Check if currently in a position (backwards compatibility)."""
        return self.position_manager.is_positioned

    @property
    def position_type(self) -> Optional[PositionType]:
        """Get current position type (backwards compatibility)."""
        return self.position_manager.position_type

    @property
    def entry_price(self) -> Optional[float]:
        """Get entry price (backwards compatibility)."""
        return self.position_manager.entry_price

    @property
    def last_price(self) -> Optional[float]:
        """Get last price (backwards compatibility)."""
        return self.stream_processor.last_price

    @property
    def current_percentual_profit(self) -> float:
        """Get current profit percentage (backwards compatibility)."""
        position = self.position_manager.position
        current_price = self.last_price
        if position and current_price:
            metrics = self.risk_manager.calculate_current_profit(
                position, current_price
            )
            return metrics.percentual_profit
        return 0.0

    @property
    def cum_profit(self) -> float:
        """Get cumulative profit (backwards compatibility)."""
        return self.position_manager.get_cumulative_profit()
