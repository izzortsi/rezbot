"""Unit tests for ProcessPoolManager."""

import unittest
import time

from src.concurrency.multiprocessing import ProcessPoolManager


def simple_task(x: int, y: int) -> int:
    """Simple task for testing."""
    return x + y


def slow_task(duration: float) -> int:
    """Task that takes a specific duration."""
    time.sleep(duration)
    return 42


class TestProcessPoolManager(unittest.TestCase):
    """Test cases for ProcessPoolManager."""

    def test_initialization(self):
        """Test process pool manager initialization."""
        pool = ProcessPoolManager(max_workers=2)

        self.assertFalse(pool.is_running)
        self.assertEqual(pool.max_workers, 2)

    def test_start_stop(self):
        """Test starting and stopping the pool."""
        pool = ProcessPoolManager(max_workers=2)

        pool.start()
        self.assertTrue(pool.is_running)

        pool.stop(wait=True)
        self.assertFalse(pool.is_running)

    def test_submit_task(self):
        """Test submitting a task to the pool."""
        pool = ProcessPoolManager(max_workers=2)
        pool.start()

        future = pool.submit(simple_task, 5, 10)

        result = future.result(timeout=5)
        self.assertEqual(result, 15)

        pool.stop(wait=True)

    def test_submit_batch(self):
        """Test submitting multiple tasks at once."""
        pool = ProcessPoolManager(max_workers=4)
        pool.start()

        args_list = [(1, 2), (3, 4), (5, 6)]
        kwargs_list = [{}] * 3

        futures = pool.submit_batch(simple_task, args_list, kwargs_list)

        results = [f.result(timeout=5) for f in futures]
        self.assertEqual(results, [3, 7, 11])

        pool.stop(wait=True)

    def test_shared_state(self):
        """Test shared state dictionary."""
        pool = ProcessPoolManager(max_workers=2)
        pool.start()

        state = pool.shared_state
        self.assertIsNotNone(state)

        # Can write to shared state
        state["test_key"] = "test_value"
        self.assertEqual(state["test_key"], "test_value")

        pool.stop(wait=True)

    def test_not_started_error(self):
        """Test that submitting without starting raises error."""
        pool = ProcessPoolManager(max_workers=2)

        with self.assertRaises(RuntimeError):
            pool.submit(simple_task, 1, 2)

    def test_context_manager(self):
        """Test using pool as context manager."""
        with ProcessPoolManager(max_workers=2) as pool:
            self.assertTrue(pool.is_running)

            future = pool.submit(simple_task, 10, 20)
            result = future.result(timeout=5)
            self.assertEqual(result, 30)

        # Pool should be stopped after context
        self.assertFalse(pool.is_running)

    def test_slow_task_timeout(self):
        """Test handling of slow tasks with timeout."""
        pool = ProcessPoolManager(max_workers=2)
        pool.start()

        future = pool.submit(slow_task, 0.1)

        # Should complete within timeout
        result = future.result(timeout=5)
        self.assertEqual(result, 42)

        pool.stop(wait=True)


if __name__ == '__main__':
    unittest.main()
