"""Paper trading engine for strategy testing without real money.

This module provides a complete paper trading system that simulates
trading without actual API calls. It includes:

- PaperTrader: Simulates live trading with virtual positions
- Backtester: Tests strategies against historical data
- DataFeed: Provides historical/simulated market data
- Reporting: Generates trade statistics and reports
"""

from .trading_engine import PaperTrader, PaperConfig
from .backtester import Backtester, BacktestConfig, BacktestResult
from .data_feed import HistoricalDataFeed, CSVDataFeed
from .reporting import TradeReport, Statistics

__all__ = [
    "PaperTrader",
    "PaperConfig",
    "Backtester",
    "BacktestConfig",
    "BacktestResult",
    "HistoricalDataFeed",
    "CSVDataFeed",
    "TradeReport",
    "Statistics",
]
