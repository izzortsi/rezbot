"""Trading components module.

This module contains the core trading components that were split
from the ThreadedATrader god class:
- PositionManager: Thread-safe position state management
- StreamProcessor: WebSocket data processing
- IndicatorProcessor: Process pool interface for indicator computation
- TradeExecutor: Thread-safe API calls
- RiskManager: Profit/loss calculations
"""

from .position_manager import (
    Position,
    TradeRecord,
    PositionManager,
)

from .trade_executor import (
    OrderSide,
    OrderResult,
    TradeExecutor,
)

from .risk_manager import (
    RiskParameters,
    ProfitMetrics,
    RiskManager,
)

from .indicator_processor import (
    IndicatorProcessor,
)

from .stream_processor import (
    StreamConfig,
    StreamProcessor,
)

__all__ = [
    # Position management
    "Position",
    "TradeRecord",
    "PositionManager",
    # Trade execution
    "OrderSide",
    "OrderResult",
    "TradeExecutor",
    # Risk management
    "RiskParameters",
    "ProfitMetrics",
    "RiskManager",
    # Data processing
    "IndicatorProcessor",
    "StreamConfig",
    "StreamProcessor",
]
