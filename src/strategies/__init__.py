"""Trading strategies module.

This module contains the base Strategy abstract class and all
concrete strategy implementations.

Usage:
    from src.strategies import PullbackStrategy, StrategyParams

    params = StrategyParams(
        name="pullback",
        timeframe="30m",
        take_profit=6,
        stoploss=-0.2,
        entry_window=1,
        exit_window=0
    )
    strategy = PullbackStrategy(params)
"""

from .base import (
    Strategy,
    StrategyParams,
    TraderContext,
    PositionType,
)

from .macd_strategies import (
    MacdStrategy,
    MacdStrategy_0,
    MacdTAStrategy,
    TrendReversalStrategy,
    TAStrategy,
)

from .pullback_strategies import (
    PullbackStrategy,
    PullbackStrategy_1,
    PullbackReversalStrategy,
    VolatilityStrategy,
)

__all__ = [
    # Base types
    "Strategy",
    "StrategyParams",
    "TraderContext",
    "PositionType",
    # MACD strategies
    "MacdStrategy",
    "MacdStrategy_0",
    "MacdTAStrategy",
    "TrendReversalStrategy",
    "TAStrategy",
    # Pullback strategies
    "PullbackStrategy",
    "PullbackStrategy_1",
    "PullbackReversalStrategy",
    "VolatilityStrategy",
]
