"""Backtesting engine for strategy testing with historical data.

This module provides the Backtester class for testing trading strategies
against historical market data.
"""

import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
import logging

from src.strategies.base import Strategy, StrategyParams, PositionType
from src.trading.position_manager import Position, PositionManager, TradeRecord
from src.trading.risk_manager import RiskManager, RiskParameters
from src.compute.indicators import compute_all_indicators
from paper.data_feed import DataFeed, DataFrameDataFeed, CSVDataFeed, HistoricalDataFeed
from paper.reporting import TradeReport, Statistics

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting.

    Attributes:
        symbol: Trading symbol
        timeframe: Timeframe for backtesting
        leverage: Trading leverage
        initial_balance: Starting virtual balance
        position_size_pct: Position size as percentage of balance
        w1: Bollinger band window parameter
        m1: Bollinger band multiplier parameter
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period
        commission_rate: Trading commission rate (default 0.04%)
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
    commission_rate: float = 0.04


@dataclass
class BacktestResult:
    """Result of a backtest run.

    Attributes:
        config: Backtest configuration used
        start_time: Backtest start time
        end_time: Backtest end time
        total_candles: Number of candles processed
        report: Trade report with statistics
        equity_curve: List of equity values over time
        drawdown_curve: List of drawdown values over time
    """
    config: BacktestConfig
    start_time: datetime
    end_time: datetime
    total_candles: int
    report: TradeReport
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "config": self.config.__dict__,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_candles": self.total_candles,
            "statistics": self.report.statistics.to_dict(),
            "total_trades": len(self.report.trade_records),
        }


class Backtester:
    """Backtesting engine for strategy evaluation.

    This class runs strategies against historical data to evaluate
    performance without using real money.

    Example:
        config = BacktestConfig(symbol="BTCUSDT", leverage=10)

        strategy = PullbackStrategy(params)
        data_feed = CSVDataFeed("BTCUSDT", "5m", "data.csv")

        backtester = Backtester(config, strategy, data_feed)
        result = backtester.run()

        result.report.print_summary()
    """

    def __init__(
        self,
        config: BacktestConfig,
        strategy: Strategy,
        data_feed: DataFeed
    ):
        """Initialize the backtester.

        Args:
            config: Backtest configuration
            strategy: Trading strategy to test
            data_feed: Data feed with historical data
        """
        self._config = config
        self._strategy = strategy
        self._data_feed = data_feed

        # Trading components
        self._position_manager = PositionManager()

        risk_params = RiskParameters(
            stoploss_pct=strategy.stoploss,
            take_profit_pct=strategy.take_profit,
            leverage=config.leverage,
            entry_fee=config.commission_rate,
            exit_fee=config.commission_rate
        )
        self._risk_manager = RiskManager(risk_params)

        # State
        self._balance = config.initial_balance
        self._initial_balance = config.initial_balance
        self._equity_curve: List[float] = []
        self._peak_equity = config.initial_balance

    def run(self, max_candles: Optional[int] = None) -> BacktestResult:
        """Run the backtest.

        Args:
            max_candles: Maximum number of candles to process (None for all)

        Returns:
            BacktestResult with complete results
        """
        start_time = datetime.now()

        logger.info(f"Starting backtest for {self._config.symbol} {self._config.timeframe}")

        # Load historical data
        data = self._data_feed.load_data()

        if data is None or len(data) == 0:
            raise ValueError("No data available for backtesting")

        # Compute indicators for entire dataset
        logger.info("Computing indicators...")
        data = self._compute_indicators_full(data)

        # Reset data feed for iteration
        self._data_feed.reset()
        self._data_feed._data = data
        self._data_feed._current_index = 0

        # Process candles
        candle_count = 0
        while not self._data_feed.is_finished:
            if max_candles and candle_count >= max_candles:
                break

            candle = self._data_feed.get_next_candle()

            if candle is None:
                break

            self._process_candle(candle, data, candle_count)
            candle_count += 1

            # Update equity curve
            self._update_equity_curve()

        # Close any open position
        if self._position_manager.is_positioned:
            self._close_position(
                data.iloc[-1]["close"],
                data.index[-1],
                "END_OF_BACKTEST"
            )

        end_time = datetime.now()

        logger.info(f"Backtest complete: {candle_count} candles processed, "
                   f"{self._position_manager.num_trades} trades executed")

        # Generate report
        records = self._position_manager.get_trade_history()
        stats = Statistics.calculate_from_records(records, self._config.leverage)

        report = TradeReport(
            symbol=self._config.symbol,
            timeframe=self._config.timeframe,
            start_time=start_time,
            end_time=end_time,
            statistics=stats,
            trade_records=records
        )

        return BacktestResult(
            config=self._config,
            start_time=start_time,
            end_time=end_time,
            total_candles=candle_count,
            report=report,
            equity_curve=self._equity_curve.copy(),
            drawdown_curve=self._compute_drawdown_curve()
        )

    def _compute_indicators_full(self, data: pd.DataFrame) -> pd.DataFrame:
        """Compute indicators for entire dataset.

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with computed indicators
        """
        try:
            indicators = compute_all_indicators(
                close=data["close"],
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
                data[col] = indicators[col]

            # Fill NaN values
            data.ffill(inplace=True)
            data.fillna(0, inplace=True)

        except Exception as e:
            logger.error(f"Error computing indicators: {e}")

        return data

    def _process_candle(
        self,
        candle: pd.Series,
        data: pd.DataFrame,
        candle_index: int
    ) -> None:
        """Process a single candle.

        Args:
            candle: Current candle data
            data: Full dataset
            candle_index: Index of current candle
        """
        current_price = float(candle["close"])

        if self._position_manager.is_positioned:
            self._check_exit_conditions(current_price, candle.name, data, candle_index)
        else:
            self._check_entry_condition(data, candle_index)

    def _check_entry_condition(
        self,
        data: pd.DataFrame,
        candle_index: int
    ) -> None:
        """Check for entry signal.

        Args:
            data: Full dataset
            candle_index: Current candle index
        """
        if candle_index < 30:
            return

        # Get data window up to current candle
        data_window = data.iloc[:candle_index + 1].copy()

        # Create mock trader context
        context = self._create_trader_context(data_window)

        # Check strategy entry signal
        should_enter, position_type = self._strategy.entry_signal(context)

        if should_enter and position_type is not None:
            current_price = float(data.iloc[candle_index]["close"])
            self._open_position(position_type, current_price, data.index[candle_index])

    def _check_exit_conditions(
        self,
        current_price: float,
        current_time: datetime,
        data: pd.DataFrame,
        candle_index: int
    ) -> None:
        """Check for exit signals.

        Args:
            current_price: Current market price
            current_time: Current candle timestamp
            data: Full dataset
            candle_index: Current candle index
        """
        position = self._position_manager.position

        # Calculate current profit
        metrics = self._risk_manager.calculate_current_profit(
            position, current_price
        )

        # Check stop loss
        if self._risk_manager.check_stop_loss(metrics):
            self._close_position(current_price, current_time, "SL")
            return

        # Check take profit
        if self._risk_manager.check_take_profit(metrics):
            self._close_position(current_price, current_time, "TP")
            return

        # Check strategy exit signal
        data_window = data.iloc[:candle_index + 1].copy()
        context = self._create_trader_context(data_window)

        if self._strategy.exit_signal(context):
            self._close_position(current_price, current_time, "STRATEGY")

    def _open_position(
        self,
        position_type: PositionType,
        entry_price: float,
        entry_time: datetime
    ) -> None:
        """Open a new position.

        Args:
            position_type: LONG or SHORT
            entry_price: Entry price
            entry_time: Entry timestamp
        """
        qty = self._calculate_position_size(entry_price)

        position = Position(
            symbol=self._config.symbol,
            position_type=position_type,
            entry_price=entry_price,
            entry_time=entry_time,
            qty=qty,
            leverage=self._config.leverage
        )

        try:
            self._position_manager.enter_position(position)
        except ValueError as e:
            logger.error(f"Failed to open position: {e}")

    def _close_position(
        self,
        exit_price: float,
        exit_time: datetime,
        reason: str
    ) -> None:
        """Close current position.

        Args:
            exit_price: Exit price
            exit_time: Exit timestamp
            reason: Exit reason
        """
        record = self._position_manager.exit_position(
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=reason
        )

        if record:
            self._balance += record.profit * record.position.qty

    def _calculate_position_size(self, entry_price: float) -> float:
        """Calculate position size.

        Args:
            entry_price: Current entry price

        Returns:
            Position quantity
        """
        balance_for_trade = self._balance * self._config.position_size_pct
        notional_value = balance_for_trade * self._config.leverage
        qty = notional_value / entry_price
        qty = round(qty, 6)

        if qty < 0.001:
            qty = 0.001

        return qty

    def _create_trader_context(self, data_window: pd.DataFrame):
        """Create mock trader context for strategy evaluation.

        Args:
            data_window: Data window for strategy evaluation

        Returns:
            MockTraderContext object
        """
        class MockTraderContext:
            def __init__(self, data_window, position_manager, risk_manager):
                self._data_window = data_window
                self._position_manager = position_manager
                self._risk_manager = risk_manager

            @property
            def data_window(self):
                return self._data_window

            @property
            def current_percentual_profit(self):
                if self._position_manager.is_positioned:
                    # This is approximate for backtesting
                    return 0.0
                return 0.0

            @property
            def is_positioned(self):
                return self._position_manager.is_positioned

            @property
            def position_type(self):
                return self._position_manager.position_type

        return MockTraderContext(
            data_window,
            self._position_manager,
            self._risk_manager
        )

    def _update_equity_curve(self) -> None:
        """Update the equity curve."""
        if self._position_manager.is_positioned:
            position = self._position_manager.position
            current_price = self._data_feed.current_price if self._data_feed.current_time else position.entry_price
            metrics = self._risk_manager.calculate_current_profit(position, current_price)
            equity = self._balance + metrics.unrealized_pnl
        else:
            equity = self._balance

        self._equity_curve.append(equity)

        # Update peak equity
        if equity > self._peak_equity:
            self._peak_equity = equity

    def _compute_drawdown_curve(self) -> List[float]:
        """Compute drawdown curve from equity curve.

        Returns:
            List of drawdown percentages
        """
        drawdowns = []

        for equity in self._equity_curve:
            if self._peak_equity > 0:
                dd = ((self._peak_equity - equity) / self._peak_equity) * 100
            else:
                dd = 0
            drawdowns.append(dd)

        return drawdowns


def run_strategy_backtest(
    strategy: Strategy,
    symbol: str,
    timeframe: str,
    data: pd.DataFrame,
    leverage: int = 10,
    w1: int = 5,
    m1: float = 1.2
) -> BacktestResult:
    """Convenience function to run a quick backtest.

    Args:
        strategy: Trading strategy to test
        symbol: Trading symbol
        timeframe: Timeframe string
        data: Historical OHLCV data as DataFrame
        leverage: Trading leverage
        w1: Bollinger band window
        m1: Bollinger band multiplier

    Returns:
        BacktestResult with complete results

    Example:
        params = StrategyParams(name="test", timeframe="5m", ...)
        strategy = PullbackStrategy(params)

        # Load data
        data = pd.read_csv("BTCUSDT_5m.csv", index_col="date")

        result = run_strategy_backtest(strategy, "BTCUSDT", "5m", data)
        result.report.print_summary()
    """
    config = BacktestConfig(
        symbol=symbol,
        timeframe=timeframe,
        leverage=leverage,
        w1=w1,
        m1=m1
    )

    data_feed = DataFrameDataFeed(symbol, timeframe, data)
    backtester = Backtester(config, strategy, data_feed)

    return backtester.run()
