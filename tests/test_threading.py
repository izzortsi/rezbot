"""Unit tests for StoppableThread."""

import unittest
import threading
import time

from src.concurrency.threading import StoppableThread


class TestStoppableThread(unittest.TestCase):
    """Test cases for StoppableThread base class."""

    def test_thread_lifecycle(self):
        """Test thread start and stop lifecycle."""
        thread = StoppableThread(name="test-thread")

        self.assertFalse(thread.should_stop())
        self.assertFalse(thread._stop_event.is_set())

        thread.start()
        self.assertTrue(thread.is_alive())

        thread.stop()
        thread.wait_stopped(timeout=5.0)
        time.sleep(0.1)  # Small delay to ensure thread has fully terminated
        self.assertFalse(thread.is_alive())

    def test_should_stop_flag(self):
        """Test should_stop flag behavior."""
        thread = StoppableThread()

        thread.start()
        self.assertFalse(thread.should_stop())

        thread.stop()
        self.assertTrue(thread.should_stop())

        thread.wait_stopped(timeout=5.0)

    def test_wait_stopped_timeout(self):
        """Test wait_stopped with timeout."""
        thread = StoppableThread()

        thread.start()

        # Request stop but don't wait indefinitely
        thread.stop()

        # Should complete within timeout
        result = thread.wait_stopped(timeout=5.0)
        self.assertTrue(result)

    def test_thread_name(self):
        """Test thread naming."""
        thread = StoppableThread(name="custom-name")
        self.assertEqual(thread.name, "custom-name")


class WorkerThread(StoppableThread):
    """Example worker thread for testing."""

    def _run_impl(self):
        """Simulate some work."""
        counter = 0
        while not self.should_stop():
            counter += 1
            if counter >= 5:
                break
            time.sleep(0.01)


class TestWorkerThread(unittest.TestCase):
    """Test cases for concrete StoppableThread implementations."""

    def test_worker_completes(self):
        """Test that worker thread completes its work."""
        worker = WorkerThread()
        worker.start()

        worker.wait_stopped(timeout=5.0)
        time.sleep(0.01)  # Small delay to ensure thread has fully terminated
        self.assertFalse(worker.is_alive())

    def test_multiple_workers(self):
        """Test multiple worker threads running concurrently."""
        workers = [WorkerThread() for _ in range(5)]

        for worker in workers:
            worker.start()

        # Stop all workers
        for worker in workers:
            worker.stop()

        # Wait for all to complete
        for worker in workers:
            worker.wait_stopped(timeout=5.0)
            time.sleep(0.01)  # Small delay after each worker stops

        # All should be stopped
        for worker in workers:
            self.assertFalse(worker.is_alive())


if __name__ == '__main__':
    unittest.main()
