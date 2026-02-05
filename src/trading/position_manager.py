"""Thread-safe position state management.

This module provides classes for managing trading positions with
proper thread synchronization.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import IntEnum
import logging

from ..strategies.base import PositionType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Position:
    """Immutable position data.

    This class represents an open trading position with all relevant
    information. It is immutable to prevent accidental modification.

    Attributes:
        symbol: Trading symbol (e.g., "BTCUSDT")
        position_type: LONG (1) or SHORT (-1)
        entry_price: Price at which position was entered
        entry_time: Timestamp when position was entered
        qty: Quantity of the position
        leverage: Leverage multiplier
    """
    symbol: str
    position_type: PositionType
    entry_price: float
    entry_time: datetime
    qty: float
    leverage: int

    @property
    def is_long(self) -> bool:
        """Check if this is a long position."""
        return self.position_type == PositionType.LONG

    @property
    def is_short(self) -> bool:
        """Check if this is a short position."""
        return self.position_type == PositionType.SHORT

    @property
    def side(self) -> str:
        """Get the side as a string."""
        return "LONG" if self.is_long else "SHORT"

    def __repr__(self) -> str:
        """String representation of the position."""
        return (
            f"Position({self.symbol}, {self.side}, "
            f"entry={self.entry_price}, qty={self.qty}, lev={self.leverage})"
        )


@dataclass
class TradeRecord:
    """Record of a completed trade.

    This class stores information about a closed trade including
    entry/exit details and profit calculations.

    Attributes:
        position: The position that was closed
        exit_price: Price at which position was exited
        exit_time: Timestamp when position was exited
        exit_reason: Reason for exit ("TP" for take profit, "SL" for stop loss)
        profit: Absolute profit amount
        percentual_profit: Profit as percentage of entry
        leveraged_profit: Profit multiplied by leverage
    """
    position: Position
    exit_price: float
    exit_time: datetime
    exit_reason: str  # "TP" or "SL"
    profit: float
    percentual_profit: float
    leveraged_profit: float

    @property
    def is_profitable(self) -> bool:
        """Check if trade was profitable."""
        return self.profit > 0

    @property
    def side(self) -> str:
        """Get the side as a string."""
        return "LONG" if self.position.is_long else "SHORT"

    def __repr__(self) -> str:
        """String representation of the trade record."""
        return (
            f"TradeRecord({self.position.symbol}, {self.side}, "
            f"entry={self.position.entry_price}, exit={self.exit_price}, "
            f"pnl={self.leveraged_profit:.2f}%, reason={self.exit_reason})"
        )


class PositionManager:
    """Thread-safe position state management.

    This class manages the current trading position and trade history
    with proper thread synchronization using locks.

    Example:
        pm = PositionManager()

        position = Position(
            symbol="BTCUSDT",
            position_type=PositionType.LONG,
            entry_price=50000.0,
            entry_time=datetime.now(),
            qty=0.001,
            leverage=10
        )
        pm.enter_position(position)

        # Later...
        record = pm.exit_position(
            exit_price=51000.0,
            exit_time=datetime.now(),
            exit_reason="TP"
        )
    """

    def __init__(self):
        """Initialize the position manager."""
        self._lock = threading.RLock()
        self._current_position: Optional[Position] = None
        self._trade_history: List[TradeRecord] = []

    def enter_position(self, position: Position) -> None:
        """Enter a new position.

        Args:
            position: The position to enter

        Raises:
            ValueError: If already in a position
        """
        with self._lock:
            if self._current_position is not None:
                raise ValueError(
                    f"Already in position: {self._current_position}. "
                    f"Cannot enter new position: {position}"
                )
            self._current_position = position
            logger.info(f"Entered position: {position}")

    def exit_position(
        self,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str
    ) -> Optional[TradeRecord]:
        """Exit current position and create trade record.

        Args:
            exit_price: Price at which position is exited
            exit_time: Timestamp of exit
            exit_reason: "TP" (take profit) or "SL" (stop loss)

        Returns:
            TradeRecord if position was open, None otherwise
        """
        with self._lock:
            if self._current_position is None:
                logger.warning("No position to exit")
                return None

            pos = self._current_position

            # Calculate profits
            if pos.is_long:
                profit = (exit_price - pos.entry_price) - 0.0004 * (exit_price + pos.entry_price)
                pct_profit = (profit / pos.entry_price) * 100
            else:  # SHORT
                profit = -1 * (exit_price - pos.entry_price) - 0.0004 * (exit_price + pos.entry_price)
                pct_profit = (profit / exit_price) * 100

            record = TradeRecord(
                position=pos,
                exit_price=exit_price,
                exit_time=exit_time,
                exit_reason=exit_reason,
                profit=profit,
                percentual_profit=pct_profit,
                leveraged_profit=pct_profit * pos.leverage
            )

            self._trade_history.append(record)
            self._current_position = None

            logger.info(f"Exited position: {record}")
            return record

    @property
    def is_positioned(self) -> bool:
        """Check if currently in a position (thread-safe).

        Returns:
            True if in a position, False otherwise
        """
        with self._lock:
            return self._current_position is not None

    @property
    def position(self) -> Optional[Position]:
        """Get current position (thread-safe).

        Returns:
            Current Position or None if flat
        """
        with self._lock:
            return self._current_position

    @property
    def position_type(self) -> Optional[PositionType]:
        """Get current position type (thread-safe).

        Returns:
            PositionType.LONG, PositionType.SHORT, or None if flat
        """
        with self._lock:
            if self._current_position:
                return self._current_position.position_type
            return None

    @property
    def entry_price(self) -> Optional[float]:
        """Get current position entry price (thread-safe).

        Returns:
            Entry price or None if flat
        """
        with self._lock:
            if self._current_position:
                return self._current_position.entry_price
            return None

    @property
    def symbol(self) -> Optional[str]:
        """Get current position symbol (thread-safe).

        Returns:
            Symbol or None if flat
        """
        with self._lock:
            if self._current_position:
                return self._current_position.symbol
            return None

    def get_trade_history(self) -> List[TradeRecord]:
        """Get a copy of the trade history (thread-safe).

        Returns:
            List of TradeRecord objects
        """
        with self._lock:
            return self._trade_history.copy()

    def get_cumulative_profit(self) -> float:
        """Calculate cumulative leveraged profit (thread-safe).

        Returns:
            Sum of all leveraged profits from closed trades
        """
        with self._lock:
            return sum(t.leveraged_profit for t in self._trade_history)

    @property
    def num_trades(self) -> int:
        """Get number of completed trades (thread-safe).

        Returns:
            Number of trades in history
        """
        with self._lock:
            return len(self._trade_history)

    def clear_history(self) -> None:
        """Clear trade history (thread-safe).

        This is useful for resetting statistics.
        """
        with self._lock:
            self._trade_history.clear()
            logger.info("Trade history cleared")
