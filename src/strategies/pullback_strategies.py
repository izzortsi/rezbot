"""Pullback-based trading strategies.

This module contains strategies that identify pullback opportunities
within trends using Bollinger Bands and MACD confirmation.
"""

import numpy as np
import pandas_ta as ta
from typing import Tuple, Optional
import logging

from .base import Strategy, StrategyParams, TraderContext, PositionType

logger = logging.getLogger(__name__)


class PullbackStrategy(Strategy):
    """Pullback strategy using lower Bollinger Band.

    Entry conditions:
    - Long: Close price <= lower band (ci) AND histogram positive
    - Short: Not implemented in this version

    Exit conditions:
    - Take profit met
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal based on pullback to lower band."""
        if not self.validate_data_window(trader.data_window):
            logger.warning("Invalid data window for pullback strategy")
            return False, None

        data = trader.data_window

        # Long entry: pullback to lower band with positive histogram momentum
        if (data.close.values[-1] <= data.ci.values[-1] and
            data.histogram.values[-1] > data.histogram.values[-2]):
            return True, PositionType.LONG

        return False, None

    def exit_signal(self, trader: TraderContext) -> bool:
        """Generate exit signal (take profit only)."""
        return trader.current_percentual_profit >= self.take_profit

    def stoploss_check(self, trader: TraderContext) -> bool:
        """Check stop loss condition."""
        return trader.current_percentual_profit <= self.stoploss


class PullbackStrategy_1(PullbackStrategy):
    """Pullback strategy with histogram EMA confirmation.

    Entry conditions:
    - Long: Close <= lower band, all histogram values >= 0, histogram EMA increasing
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal with histogram EMA confirmation."""
        if not self.validate_data_window(trader.data_window):
            logger.warning("Invalid data window for pullback strategy")
            return False, None

        data = trader.data_window

        # Long entry with additional confirmations
        if (data.close.values[-1] <= data.ci.values[-1] and
            np.alltrue(data.histogram.tail(self.entry_window) >= 0) and
            ta.increasing(data.hist_ema, length=self.entry_window)):
            return True, PositionType.LONG

        return False, None


class PullbackReversalStrategy(Strategy):
    """Pullback reversal strategy with histogram direction confirmation.

    Entry conditions:
    - Long: Histogram increasing, histogram EMA increasing, close <= lower band
    - Short: Histogram decreasing, histogram EMA decreasing, close >= upper band

    Exit conditions:
    - Take profit met
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal with reversal confirmation."""
        if not self.validate_data_window(trader.data_window):
            logger.warning("Invalid data window for pullback reversal strategy")
            return False, None

        data = trader.data_window

        # Long entry: pullback to lower band with momentum reversal
        if (data.histogram.values[-1] > data.histogram.values[-2] and
            data.hist_ema.values[-1] > data.hist_ema.values[-2] and
            data.close.values[-1] <= data.ci.values[-1]):
            return True, PositionType.LONG

        # Short entry: pullback to upper band with momentum reversal
        elif (data.histogram.values[-1] < data.histogram.values[-2] and
              data.hist_ema.values[-1] < data.hist_ema.values[-2] and
              data.close.values[-1] >= data.cs.values[-1]):
            return True, PositionType.SHORT

        return False, None

    def exit_signal(self, trader: TraderContext) -> bool:
        """Generate exit signal (take profit only)."""
        return trader.current_percentual_profit >= self.take_profit

    def stoploss_check(self, trader: TraderContext) -> bool:
        """Check stop loss condition."""
        return trader.current_percentual_profit <= self.stoploss


class VolatilityStrategy(Strategy):
    """Volatility breakout strategy with TA confirmation.

    Entry conditions:
    - Long: Close <= lower band AND TA signal is BUY
    - Short: Close >= upper band AND TA signal is SELL

    Exit conditions:
    - Take profit met
    """

    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Generate entry signal based on volatility breakout."""
        if not self.validate_data_window(trader.data_window):
            logger.warning("Invalid data window for volatility strategy")
            return False, None

        data = trader.data_window
        ta_handler = getattr(trader, 'ta_handler', None)

        if ta_handler is None:
            logger.warning("TA handler not available for volatility strategy")
            return False, None

        # Long entry: break lower band with TA confirmation
        if (data.close.values[-1] <= data.ci.values[-1] and
            ta_handler.signal == 1):
            return True, PositionType.LONG

        # Short entry: break upper band with TA confirmation
        elif (data.close.values[-1] >= data.cs.values[-1] and
              ta_handler.signal == -1):
            return True, PositionType.SHORT

        return False, None

    def exit_signal(self, trader: TraderContext) -> bool:
        """Generate exit signal (take profit only)."""
        return trader.current_percentual_profit >= self.take_profit

    def stoploss_check(self, trader: TraderContext) -> bool:
        """Check stop loss condition."""
        return trader.current_percentual_profit <= self.stoploss
