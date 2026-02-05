"""CPU-bound computation module.

This module contains functions that are designed to run in separate
processes to bypass the GIL for CPU-intensive operations like
technical indicator calculations and ML model inference.
"""

from .indicators import (
    compute_macd,
    compute_bollinger_bands,
    compute_all_indicators,
)

__all__ = [
    "compute_macd",
    "compute_bollinger_bands",
    "compute_all_indicators",
]
