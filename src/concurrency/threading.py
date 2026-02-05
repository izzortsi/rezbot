"""Threading primitives for graceful shutdown management."""

import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StoppableThread(threading.Thread):
    """Base thread class with graceful shutdown support.

    This class provides a standard pattern for threads that can be
    stopped gracefully. Subclasses should override _run_impl() instead
    of run() to implement their logic.

    Example:
        class MyWorker(StoppableThread):
            def _run_impl(self):
                while not self.should_stop():
                    # Do work here
                    pass

        worker = MyWorker()
        worker.start()
        # Later...
        worker.stop()  # Request stop
        worker.wait_stopped(timeout=5.0)  # Wait for completion
    """

    def __init__(self, name: Optional[str] = None, daemon: bool = False):
        """Initialize a stoppable thread.

        Args:
            name: Optional thread name
            daemon: Whether this should be a daemon thread
        """
        super().__init__(name=name, daemon=daemon)
        self._stop_event = threading.Event()
        self._stopped_event = threading.Event()

    def stop(self) -> None:
        """Request thread to stop.

        This sets the stop flag that should be checked via should_stop()
        in the thread's main loop. Does not immediately terminate the thread.
        """
        self._stop_event.set()
        logger.info(f"Thread {self.name} stop requested")

    def wait_stopped(self, timeout: Optional[float] = None) -> bool:
        """Wait for thread to complete shutdown.

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if thread stopped before timeout, False if timeout elapsed.
        """
        return self._stopped_event.wait(timeout=timeout)

    def should_stop(self) -> bool:
        """Check if stop was requested.

        This should be called periodically in _run_impl() to check if
        the thread should exit its main loop.

        Returns:
            True if stop was requested, False otherwise.
        """
        return self._stop_event.is_set()

    def run(self) -> None:
        """Main thread entry point.

        This wraps _run_impl() to ensure proper cleanup of the
        stopped event regardless of how the thread exits.
        """
        try:
            self._run_impl()
        finally:
            self._stopped_event.set()
            logger.info(f"Thread {self.name} completed shutdown")

    def _run_impl(self) -> None:
        """Implement actual thread logic here in subclasses.

        This method should periodically check should_stop() and
        exit when it returns True.
        """
        raise NotImplementedError(f"{self.__class__.__name__}._run_impl() not implemented")
