"""CPU-bound technical indicator computation functions.

These functions are designed to run in separate processes via the
ProcessPool to bypass the Python GIL for CPU-intensive operations.

Note: These functions must be importable and pickleable for multiprocessing.
Avoid using class instances or closures - only use pure functions with
serializable arguments.
"""

import pandas as pd
import pandas_ta as ta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Dict[str, pd.Series]:
    """Compute MACD indicators - CPU-bound, runs in separate process.

    Args:
        close: Close price series
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line EMA period

    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' Series
    """
    macd_result = ta.macd(close, fast=fast, slow=slow, signal=signal)

    # The column names are generated dynamically based on parameters
    # Format: MACD_{fast}_{slow}_{signal}, MACDs_{fast}_{slow}_{signal}, MACDh_{fast}_{slow}_{signal}
    suffix = f"{fast}_{slow}_{signal}"

    return {
        "macd": macd_result[f"MACD_{suffix}"],
        "signal": macd_result[f"MACDs_{suffix}"],
        "histogram": macd_result[f"MACDh_{suffix}"]
    }


def compute_bollinger_bands(
    close: pd.Series,
    window: int = 5,
    multiplier: float = 1.2
) -> Dict[str, pd.Series]:
    """Compute Bollinger Bands - CPU-bound, runs in separate process.

    Args:
        close: Close price series
        window: EMA window for mean and std deviation
        multiplier: Standard deviation multiplier for bands

    Returns:
        Dictionary with 'close_ema', 'close_std', 'upper_band', 'lower_band'
    """
    close_ema = close.ewm(span=window).mean()
    close_std = close.ewm(span=window).std()

    return {
        "close_ema": close_ema,
        "close_std": close_std,
        "upper_band": close_ema + multiplier * close_std,  # cs (ceiling/superior)
        "lower_band": close_ema - multiplier * close_std   # ci (floor/inferior)
    }


def compute_all_indicators(
    close: pd.Series,
    w1: int = 5,
    m1: float = 1.2,
    macd_params: Optional[Dict[str, int]] = None
) -> pd.DataFrame:
    """Compute all indicators - CPU-bound main function.

    This is the primary function called by the process pool for
    indicator computation. It computes MACD, Bollinger Bands,
    and derived indicators.

    Args:
        close: Close price series
        w1: EMA window for Bollinger Bands
        m1: Standard deviation multiplier for Bollinger Bands
        macd_params: Dictionary with 'fast', 'slow', 'signal' values

    Returns:
        DataFrame with all indicator columns ready for use

    Example:
        result = compute_all_indicators(data_window.close, w1=5, m1=1.2)
        # Returns DataFrame with: close, cs, close_ema, ci, close_std,
        #                       histogram, hist_ema
    """
    if macd_params is None:
        macd_params = {"fast": 12, "slow": 26, "signal": 9}

    # Validate inputs
    if len(close) < max(macd_params["slow"], w1 * 2):
        logger.warning(f"Insufficient data points: {len(close)}")
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=[
            "close", "cs", "close_ema", "ci", "close_std", "histogram", "hist_ema"
        ])

    # Compute MACD indicators
    macd_results = compute_macd(close, **macd_params)
    bb_results = compute_bollinger_bands(close, window=w1, multiplier=m1)

    # Compute histogram EMA for trend confirmation
    hist_ema = macd_results["histogram"].ewm(span=w1).mean()
    hist_ema.name = "hist_ema"

    # Rename bands to match existing naming convention
    bb_results["upper_band"].name = "cs"
    bb_results["lower_band"].name = "ci"
    macd_results["histogram"].name = "histogram"
    bb_results["close_ema"].name = "close_ema"
    bb_results["close_std"].name = "close_std"

    # Combine all indicators into a single DataFrame
    result_df = pd.concat([
        close.rename("close"),
        bb_results["upper_band"],   # cs
        bb_results["close_ema"],     # close_ema
        bb_results["lower_band"],   # ci
        bb_results["close_std"],     # close_std
        macd_results["histogram"],  # histogram
        hist_ema                    # hist_ema
    ], axis=1)

    return result_df


def compute_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Compute RSI indicator - CPU-bound.

    Args:
        close: Close price series
        length: RSI period

    Returns:
        RSI Series
    """
    rsi = ta.rsi(close, length=length)
    rsi.name = "rsi"
    return rsi


def compute_ema(close: pd.Series, length: int = 20) -> pd.Series:
    """Compute EMA indicator - CPU-bound.

    Args:
        close: Close price series
        length: EMA period

    Returns:
        EMA Series
    """
    ema = ta.ema(close, length=length)
    ema.name = f"ema_{length}"
    return ema


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14
) -> pd.Series:
    """Compute Average True Range - CPU-bound.

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        length: ATR period

    Returns:
        ATR Series
    """
    atr = ta.atr(high, low, close, length=length)
    atr.name = "atr"
    return atr
