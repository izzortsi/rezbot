"""Test suite for rezbot trading bot.

This module contains unit tests for the refactored components.
"""

import unittest
import threading
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.concurrency.threading import StoppableThread
from src.concurrency.multiprocessing import ProcessPoolManager
from src.config import ConfigManager, ApiConfig
from src.strategies.base import Strategy, StrategyParams, PositionType
from src.strategies import (
    PullbackStrategy,
    PullbackReversalStrategy,
    MacdStrategy,
)
from src.trading import (
    Position,
    PositionManager,
    TradeRecord,
    OrderSide,
    OrderResult,
    TradeExecutor,
    RiskParameters,
    ProfitMetrics,
    RiskManager,
    IndicatorProcessor,
    StreamConfig,
    StreamProcessor,
)
