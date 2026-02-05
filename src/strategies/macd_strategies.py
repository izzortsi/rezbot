"""MACD-based trading strategies.

This module contains strategies that primarily use MACD (Moving Average
Convergence Divergence) indicators for generating trading signals.
"""

import numpy as np
import pandas_ta as ta
from typing import Tuple, Optional
import logging

from .base import Strategy, StrategyParams, TraderContext, PositionType

logger = logging.getLogger(__name__)


class MacdStrategy(Strategy):
    """Standard MACD strategy with histogram confirmation.

    Entry conditions:
    - Long: Histogram negative and turning positive (increasing)
    - Short: Histogram positive and turning negative (decreasing)

    Exit conditions:
    - Take profit met AND histogram changing direction
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal based on MACD histogram."""
        if not self.validate_data_window(trader.data_window):
            logger.warning("Invalid data window for MACD strategy")
            return False, None

        hist_tail = trader.data_window.histogram.tail(self.entry_window)

        # Long entry: histogram negative and turning positive
        if (np.alltrue(hist_tail <= 0) and
            np.alltrue(ta.increasing(hist_tail).values == 1)):
            return True, PositionType.LONG

        # Short entry: histogram positive and turning negative
        elif (np.alltrue(hist_tail >= 0) and
              np.alltrue(ta.decreasing(hist_tail).values == 1)):
            return True, PositionType.SHORT

        return False, None

    def exit_signal(self, trader: TraderContext) -> bool:
        """Generate exit signal."""
        profit_target_met = trader.current_percentual_profit >= self.take_profit
        if not profit_target_met:
            return False

        hist_tail = trader.data_window.histogram.tail(self.entry_window)

        if trader.position_type == PositionType.LONG:
            return (np.alltrue(hist_tail > 0) and
                    ta.decreasing(hist_tail).values[-1])
        elif trader.position_type == PositionType.SHORT:
            return (np.alltrue(hist_tail < 0) and
                    ta.increasing(hist_tail).values[-1])
        return False

    def stoploss_check(self, trader: TraderContext) -> bool:
        """Check stop loss condition."""
        return trader.current_percentual_profit <= self.stoploss


class MacdStrategy_0(MacdStrategy):
    """Simplified MACD strategy without trend confirmation.

    Entry conditions:
    - Long: All histogram values in entry window are negative
    - Short: All histogram values in entry window are positive
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal (simplified version)."""
        if not self.validate_data_window(trader.data_window):
            logger.warning("Invalid data window for MACD strategy")
            return False, None

        hist_tail = trader.data_window.histogram.tail(self.entry_window)

        # Long entry: all histogram values negative
        if np.alltrue(hist_tail < 0):
            return True, PositionType.SHORT
        # Short entry: all histogram values positive
        elif np.alltrue(hist_tail > 0):
            return True, PositionType.LONG

        return False, None


class MacdTAStrategy(MacdStrategy):
    """MACD strategy with TradingView TA handler confirmation.

    Entry conditions:
    - MACD entry conditions met AND TA handler signal confirms direction

    Exit conditions:
    - Take profit met AND histogram changing direction
    - OR Stop loss with opposite TA signal
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal with TA handler confirmation."""
        base_signal, pos_type = super().entry_signal(trader)

        if not base_signal or pos_type is None:
            return False, None

        # Confirm with TA handler signal
        ta_handler = getattr(trader, 'ta_handler', None)
        if ta_handler is None:
            logger.warning("TA handler not available for confirmation")
            return False, None

        if pos_type == PositionType.LONG and ta_handler.signal != 1:
            return False, None
        if pos_type == PositionType.SHORT and ta_handler.signal != -1:
            return False, None

        return True, pos_type

    def stoploss_check(self, trader: TraderContext) -> bool:
        """Enhanced stop loss with TA confirmation."""
        sl_hit = trader.current_percentual_profit <= self.stoploss
        if not sl_hit:
            return False

        ta_handler = getattr(trader, 'ta_handler', None)
        if ta_handler is None:
            return sl_hit

        # Confirm with opposite TA signal
        if trader.position_type == PositionType.LONG:
            return ta_handler.signal == -1
        elif trader.position_type == PositionType.SHORT:
            return ta_handler.signal == 1
        return sl_hit


class TrendReversalStrategy(Strategy):
    """Trend reversal strategy using MACD histogram.

    Entry conditions:
    - Long: Histogram negative, with reversal in last 2 candles
    - Short: Histogram positive, with reversal in last 2 candles
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal based on trend reversal."""
        if not self.validate_data_window(trader.data_window):
            logger.warning("Invalid data window for trend reversal strategy")
            return False, None

        hist = trader.data_window.histogram

        # Long entry: negative histogram with reversal
        if (np.alltrue(hist.tail(self.entry_window) <= 0) and
            ta.increasing(hist.tail(2)).values[-1] == 1 and
            ta.decreasing(hist.tail(2)).values[-2] == 1):
            return True, PositionType.LONG

        # Short entry: positive histogram with reversal
        elif (np.alltrue(hist.tail(self.entry_window) >= 0) and
              ta.decreasing(hist.tail(2)).values[-1] == 1 and
              ta.increasing(hist.tail(2)).values[-2] == 1):
            return True, PositionType.SHORT

        return False, None

    def exit_signal(self, trader: TraderContext) -> bool:
        """Generate exit signal (take profit only)."""
        return trader.current_percentual_profit >= self.take_profit

    def stoploss_check(self, trader: TraderContext) -> bool:
        """Check stop loss condition."""
        return trader.current_percentual_profit <= self.stoploss


class TAStrategy(Strategy):
    """TradingView TA-only strategy.

    Entry conditions:
    - Long: TA handler signal is BUY (1)
    - Short: TA handler signal is SELL (-1)

    Exit conditions:
    - Take profit met
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal based purely on TA handler."""
        ta_handler = getattr(trader, 'ta_handler', None)
        if ta_handler is None:
            logger.warning("TA handler not available")
            return False, None

        if ta_handler.signal == 1:
            return True, PositionType.LONG
        elif ta_handler.signal == -1:
            return True, PositionType.SHORT

        return False, None

    def exit_signal(self, trader: TraderContext) -> bool:
        """Generate exit signal (take profit only)."""
        return trader.current_percentual_profit >= self.take_profit

    def stoploss_check(self, trader: TraderContext) -> bool:
        """Check stop loss condition."""
        return trader.current_percentual_profit <= self.stoploss
