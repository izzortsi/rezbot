"""Risk management and profit calculation.

This module provides the RiskManager class for calculating profits,
take-profit prices, stop-loss prices, and managing risk parameters.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from .position_manager import Position

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskParameters:
    """Risk management parameters.

    Attributes:
        stoploss_pct: Stop loss percentage (negative value)
        take_profit_pct: Take profit percentage (positive value)
        leverage: Trading leverage multiplier
        entry_fee: Trading fee for entry (default 0.04%)
        exit_fee: Trading fee for exit (default 0.04%)
    """
    stoploss_pct: float  # Negative value
    take_profit_pct: float  # Positive value
    leverage: int
    entry_fee: float = 0.04
    exit_fee: float = 0.04

    def __post_init__(self):
        """Validate risk parameters."""
        if self.take_profit_pct <= 0:
            raise ValueError(f"take_profit_pct must be positive, got {self.take_profit_pct}")
        if self.stoploss_pct >= 0:
            raise ValueError(f"stoploss_pct must be negative, got {self.stoploss_pct}")
        if self.leverage < 1:
            raise ValueError(f"leverage must be >= 1, got {self.leverage}")


@dataclass
class ProfitMetrics:
    """Current profit metrics for an open position.

    Attributes:
        profit: Absolute profit amount
        percentual_profit: Profit as percentage of entry (unleveraged)
        leveraged_profit: Profit multiplied by leverage
        current_price: Current market price
        unrealized_pnl: Unrealized profit/loss
    """
    profit: float
    percentual_profit: float
    leveraged_profit: float
    current_price: float
    unrealized_pnl: float

    @property
    def is_profitable(self) -> bool:
        """Check if currently profitable."""
        return self.profit > 0


class RiskManager:
    """Handles risk calculations and checks.

    This class provides methods for calculating take-profit prices,
    stop-loss prices, and current profit metrics.

    Example:
        params = RiskParameters(
            stoploss_pct=-0.2,
            take_profit_pct=6,
            leverage=10
        )
        rm = RiskManager(params)

        # Calculate TP price for long
        tp_price = rm.compute_take_profit_price(50000, PositionType.LONG)

        # Check current profit
        metrics = rm.calculate_current_profit(position, current_price)
        if rm.check_stop_loss(metrics):
            # Exit position
    """

    def __init__(self, params: RiskParameters):
        """Initialize the risk manager.

        Args:
            params: Risk parameters
        """
        self._params = params

    def compute_take_profit_price(
        self,
        entry_price: float,
        position_type
    ) -> float:
        """Calculate take profit price for given profit target.

        Args:
            entry_price: Position entry price
            position_type: LONG or SHORT position type

        Returns:
            Take profit price

        Example:
            tp_long = compute_take_profit_price(50000, PositionType.LONG)
            # Returns price like 53000 for 6% profit on long

            tp_short = compute_take_profit_price(50000, PositionType.SHORT)
            # Returns price like 47000 for 6% profit on short
        """
        tp = self._params.take_profit_pct
        entry_fee = self._params.entry_fee / 100
        exit_fee = self._params.exit_fee / 100

        if position_type.long_side:
            # Long: exit_price > entry_price
            return (
                entry_price * (1 + tp / 100 + entry_fee) /
                (1 - exit_fee)
            )
        else:
            # Short: entry_price > exit_price
            return (
                entry_price * (1 - tp / 100 - entry_fee) /
                (1 + exit_fee)
            )

    def compute_stop_loss_price(
        self,
        entry_price: float,
        position_type
    ) -> float:
        """Calculate stop loss price.

        Args:
            entry_price: Position entry price
            position_type: LONG or SHORT position type

        Returns:
            Stop loss price
        """
        sl = self._params.stoploss_pct  # Negative value
        entry_fee = self._params.entry_fee / 100
        exit_fee = self._params.exit_fee / 100

        if position_type.long_side:
            # Long: stop loss below entry
            return (
                entry_price * (1 + sl / 100 + entry_fee) /
                (1 - exit_fee)
            )
        else:
            # Short: stop loss above entry
            return (
                entry_price * (1 - sl / 100 - entry_fee) /
                (1 + exit_fee)
            )

    def calculate_current_profit(
        self,
        position: Position,
        current_price: float
    ) -> ProfitMetrics:
        """Calculate current profit metrics.

        Args:
            position: The open position
            current_price: Current market price

        Returns:
            ProfitMetrics with current profit information
        """
        fee = self._params.entry_fee / 100

        if position.is_long:
            # Long profit calculation
            profit = (
                (current_price - position.entry_price) -
                fee * (current_price + position.entry_price)
            )
            pct_profit = (profit / position.entry_price) * 100
        else:
            # Short profit calculation
            profit = (
                -1 * (current_price - position.entry_price) -
                fee * (current_price + position.entry_price)
            )
            pct_profit = (profit / current_price) * 100

        leveraged_profit = pct_profit * position.leverage

        return ProfitMetrics(
            profit=profit,
            percentual_profit=pct_profit,
            leveraged_profit=leveraged_profit,
            current_price=current_price,
            unrealized_pnl=profit * position.qty
        )

    def check_stop_loss(self, metrics: ProfitMetrics) -> bool:
        """Check if stop loss is triggered.

        Args:
            metrics: Current profit metrics

        Returns:
            True if stop loss is triggered, False otherwise
        """
        return metrics.percentual_profit <= self._params.stoploss_pct

    def check_take_profit(self, metrics: ProfitMetrics) -> bool:
        """Check if take profit is triggered.

        Args:
            metrics: Current profit metrics

        Returns:
            True if take profit is triggered, False otherwise
        """
        return metrics.percentual_profit >= self._params.take_profit_pct

    @property
    def stoploss_pct(self) -> float:
        """Get stop loss percentage."""
        return self._params.stoploss_pct

    @property
    def take_profit_pct(self) -> float:
        """Get take profit percentage."""
        return self._params.take_profit_pct

    @property
    def leverage(self) -> int:
        """Get leverage."""
        return self._params.leverage
