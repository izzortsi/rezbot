"""Base strategy classes and types.

This module defines the abstract base class for all trading strategies,
along with supporting types and protocols.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, Optional, Tuple
from enum import IntEnum
import logging

logger = logging.getLogger(__name__)


class PositionType(IntEnum):
    """Position direction enum.

    Attributes:
        LONG: Long position (expecting price to go up)
        SHORT: Short position (expecting price to go down)
        FLAT: No position
    """
    LONG = 1
    SHORT = -1
    FLAT = 0

    @property
    def is_long(self) -> bool:
        """Check if this is a long position."""
        return self == PositionType.LONG

    @property
    def is_short(self) -> bool:
        """Check if this is a short position."""
        return self == PositionType.SHORT

    @property
    def is_flat(self) -> bool:
        """Check if this is flat (no position)."""
        return self == PositionType.FLAT

    def opposite(self) -> "PositionType":
        """Get the opposite position type."""
        if self == PositionType.LONG:
            return PositionType.SHORT
        elif self == PositionType.SHORT:
            return PositionType.LONG
        return PositionType.FLAT


@dataclass(frozen=True)
class StrategyParams:
    """Immutable strategy parameters.

    This dataclass encapsulates all parameters needed to configure
    a trading strategy. It is immutable to prevent accidental modification.

    Attributes:
        name: Strategy name/identifier
        timeframe: Trading timeframe (e.g., "30m", "1h", "4h")
        take_profit: Take profit percentage (positive value)
        stoploss: Stop loss percentage (negative value)
        entry_window: Number of candles to confirm entry signal
        exit_window: Number of candles to confirm exit signal
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period
    """
    name: str
    timeframe: str
    take_profit: float
    stoploss: float
    entry_window: int
    exit_window: int
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    def __post_init__(self):
        """Validate strategy parameters."""
        if self.take_profit <= 0:
            raise ValueError(f"take_profit must be positive, got {self.take_profit}")
        if self.stoploss >= 0:
            raise ValueError(f"stoploss must be negative, got {self.stoploss}")
        if self.entry_window < 1:
            raise ValueError(f"entry_window must be >= 1, got {self.entry_window}")
        if self.exit_window < 0:
            raise ValueError(f"exit_window must be >= 0, got {self.exit_window}")

    @property
    def macd_params(self) -> dict:
        """Get MACD parameters as a dictionary."""
        return {
            "fast": self.macd_fast,
            "slow": self.macd_slow,
            "signal": self.macd_signal
        }


class TraderContext(Protocol):
    """Trader context protocol for type-safe strategy evaluation.

    This protocol defines the interface that strategies expect from
    a trader object. Using a Protocol allows for duck typing while
    maintaining type safety.

    Strategies should only access trader data through the properties
    defined in this protocol.
    """

    @property
    def data_window(self):
        """Current data window with indicators.

        Returns:
            pandas DataFrame with columns: close, histogram, close_ema,
            close_std, cs, ci, hist_ema, etc.
        """
        ...

    @property
    def current_percentual_profit(self) -> float:
        """Current profit percentage (unleveraged).

        Returns:
            Current profit as a percentage
        """
        ...

    @property
    def is_positioned(self) -> bool:
        """Whether currently in a position.

        Returns:
            True if in a position, False otherwise
        """
        ...

    @property
    def position_type(self) -> Optional[PositionType]:
        """Current position type.

        Returns:
            PositionType.LONG, PositionType.SHORT, or None if flat
        """
        ...


class Strategy(ABC):
    """Abstract base class for trading strategies.

    All trading strategies must inherit from this class and implement
    the three abstract methods: entry_signal(), exit_signal(), and
    stoploss_check().

    Strategies should be stateless and deterministic - the same inputs
    should always produce the same signals.

    Example:
        class MyStrategy(Strategy):
            def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
                # Check conditions for entry
                if trader.data_window.histogram.iloc[-1] > 0:
                    return True, PositionType.LONG
                return False, None

            def exit_signal(self, trader: TraderContext) -> bool:
                # Check conditions for exit
                return trader.current_percentual_profit >= self.take_profit

            def stoploss_check(self, trader: TraderContext) -> bool:
                # Check stop loss
                return trader.current_percentual_profit <= self.stoploss
    """

    def __init__(self, params: StrategyParams):
        """Initialize the strategy.

        Args:
            params: Strategy parameters
        """
        self._params = params

    # ============================================================
    # Read-only Properties
    # ============================================================

    @property
    def name(self) -> str:
        """Get strategy name."""
        return self._params.name

    @property
    def timeframe(self) -> str:
        """Get strategy timeframe."""
        return self._params.timeframe

    @property
    def stoploss(self) -> float:
        """Get stop loss percentage (negative value)."""
        return self._params.stoploss

    @property
    def take_profit(self) -> float:
        """Get take profit percentage (positive value)."""
        return self._params.take_profit

    @property
    def entry_window(self) -> int:
        """Get entry confirmation window."""
        return self._params.entry_window

    @property
    def exit_window(self) -> int:
        """Get exit confirmation window."""
        return self._params.exit_window

    @property
    def macd_params(self) -> dict:
        """Get MACD parameters as a dictionary."""
        return self._params.macd_params

    # ============================================================
    # Abstract Methods (must be implemented by subclasses)
    # ============================================================

    @abstractmethod
    def entry_signal(self, trader: TraderContext) -> Tuple[bool, Optional[PositionType]]:
        """Determine entry signal.

        This method is called when not in a position to check if
        we should enter. It should return both whether to enter and
        which direction.

        Args:
            trader: Trader context with current data window and state

        Returns:
            A tuple of (should_enter, position_type):
                - should_enter: True if entry signal is triggered
                - position_type: LONG or SHORT if should_enter is True,
                                None otherwise
        """
        pass

    @abstractmethod
    def exit_signal(self, trader: TraderContext) -> bool:
        """Determine exit signal.

        This method is called when in a position to check if we should
        exit (e.g., take profit).

        Args:
            trader: Trader context with current data window and state

        Returns:
            True if exit signal is triggered, False otherwise
        """
        pass

    @abstractmethod
    def stoploss_check(self, trader: TraderContext) -> bool:
        """Check if stop loss is triggered.

        This method is called when in a position to check if stop loss
        has been hit.

        Args:
            trader: Trader context with current data window and state

        Returns:
            True if stop loss is triggered, False otherwise
        """
        pass

    # ============================================================
    # Optional Helper Methods
    # ============================================================

    def validate_data_window(self, data) -> bool:
        """Validate that data window has required columns.

        Args:
            data: DataFrame to validate

        Returns:
            True if all required columns are present, False otherwise
        """
        required = ['close', 'histogram', 'close_ema', 'close_std', 'cs', 'ci']
        return all(col in data.columns for col in required)

    def __repr__(self) -> str:
        """String representation of the strategy."""
        return (
            f"{self.__class__.__name__}("
            f"name={self.name}, "
            f"timeframe={self.timeframe}, "
            f"tp={self.take_profit}%, "
            f"sl={self.stoploss}%)"
        )
