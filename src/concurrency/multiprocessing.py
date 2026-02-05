"""Multiprocessing primitives for CPU-bound operations."""

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, Future
from multiprocessing import Manager
from typing import Optional, Callable, Any, Dict
import logging

logger = logging.getLogger(__name__)


class ProcessPoolManager:
    """Manages process pool for CPU-bound operations.

    This class provides a process pool for running CPU-intensive tasks
    like indicator calculations and ML model inference. It uses
    multiprocessing.Manager for safe cross-process state sharing.

    Example:
        pool = ProcessPoolManager(max_workers=4)
        pool.start()

        # Submit async task
        future = pool.submit(compute_indicators, data, fast=12, slow=26)

        # Get result when ready
        result = future.result(timeout=1.0)

        pool.stop(wait=True)
    """

    def __init__(self, max_workers: Optional[int] = None):
        """Initialize the process pool manager.

        Args:
            max_workers: Maximum number of worker processes.
                       None or 0 means CPU count - 1 (leave one for main).
        """
        if max_workers is None or max_workers == 0:
            self._max_workers = max(1, mp.cpu_count() - 1)
        else:
            self._max_workers = max_workers

        self._executor: Optional[ProcessPoolExecutor] = None
        self._manager: Optional[Manager] = None
        self._shared_state: Optional[Dict] = None
        self._is_running = False

    @property
    def max_workers(self) -> int:
        """Get the maximum number of worker processes."""
        return self._max_workers

    @property
    def is_running(self) -> bool:
        """Check if the process pool is currently running."""
        return self._is_running

    def start(self) -> None:
        """Initialize the process pool.

        Creates the ProcessPoolExecutor and Manager for shared state.
        Must be called before submitting any tasks.
        """
        if self._is_running:
            logger.warning("Process pool already running")
            return

        self._manager = Manager()
        self._shared_state = self._manager.dict()
        self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        self._is_running = True

        logger.info(f"Process pool started with {self._max_workers} workers")

    def stop(self, wait: bool = True) -> None:
        """Shutdown the process pool.

        Args:
            wait: If True, wait for all pending futures to complete.
                  If False, cancel pending futures and shutdown immediately.
        """
        if not self._is_running:
            return

        logger.info("Stopping process pool...")

        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None

        if self._manager is not None:
            self._manager.shutdown()
            self._manager = None
            self._shared_state = None

        self._is_running = False
        logger.info("Process pool stopped")

    def submit(self, fn: Callable[..., Any], *args, **kwargs) -> Future:
        """Submit a task to the process pool.

        Args:
            fn: The function to execute in a worker process
            *args: Positional arguments to pass to fn
            **kwargs: Keyword arguments to pass to fn

        Returns:
            A Future object representing the pending result

        Raises:
            RuntimeError: If the process pool has not been started
        """
        if not self._is_running:
            raise RuntimeError(
                "Process pool not started. Call start() before submitting tasks."
            )

        return self._executor.submit(fn, *args, **kwargs)

    def submit_batch(
        self,
        fn: Callable[..., Any],
        args_list: list[tuple],
        kwargs_list: Optional[list[dict]] = None
    ) -> list[Future]:
        """Submit multiple tasks to the process pool.

        Args:
            fn: The function to execute for each task
            args_list: List of argument tuples, one per task
            kwargs_list: Optional list of keyword argument dicts, one per task

        Returns:
            List of Future objects, one per task

        Raises:
            RuntimeError: If the process pool has not been started
        """
        if not self._is_running:
            raise RuntimeError(
                "Process pool not started. Call start() before submitting tasks."
            )

        if kwargs_list is None:
            kwargs_list = [{}] * len(args_list)

        if len(args_list) != len(kwargs_list):
            raise ValueError("args_list and kwargs_list must have the same length")

        futures = []
        for args, kwargs in zip(args_list, kwargs_list):
            future = self._executor.submit(fn, *args, **kwargs)
            futures.append(future)

        return futures

    @property
    def shared_state(self) -> Dict:
        """Get the shared state dictionary for cross-process communication.

        Returns:
            A multiprocessing.Manager.dict() that can be used to share
            state between processes safely.

        Raises:
            RuntimeError: If the process pool has not been started
        """
        if not self._is_running:
            raise RuntimeError(
                "Process pool not started. Call start() before accessing shared state."
            )
        return self._shared_state

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop(wait=True)
        return False
