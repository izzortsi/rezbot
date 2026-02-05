"""Concurrency primitives for hybrid threading/multiprocessing model.

This module provides base classes and managers for coordinating I/O-bound
operations (threads) and CPU-bound operations (processes).
"""

from .threading import StoppableThread
from .multiprocessing import ProcessPoolManager

__all__ = [
    "StoppableThread",
    "ProcessPoolManager",
]
