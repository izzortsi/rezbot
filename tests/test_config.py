"""Unit tests for configuration management."""

import os
import unittest

from src.config import ConfigManager, ApiConfig


class TestApiConfig(unittest.TestCase):
    """Test cases for ApiConfig."""

    def test_creation(self):
        """Test creating ApiConfig."""
        config = ApiConfig(
            api_key="test_key",
            api_secret="test_secret",
            exchange="binance.com-futures"
        )

        self.assertEqual(config.api_key, "test_key")
        self.assertEqual(config.api_secret, "test_secret")
        self.assertEqual(config.exchange, "binance.com-futures")

    def test_validate(self):
        """Test ApiConfig validation."""
        config = ApiConfig("key", "secret")

        self.assertTrue(config.validate())

    def test_validate_empty_key(self):
        """Test validation fails with empty key."""
        config = ApiConfig("", "secret")

        self.assertFalse(config.validate())

    def test_from_env(self):
        """Test loading from environment variables."""
        # Set environment variables temporarily
        old_key = os.environ.get("API_KEY")
        old_secret = os.environ.get("API_SECRET")

        try:
            os.environ["API_KEY"] = "env_key"
            os.environ["API_SECRET"] = "env_secret"

            config = ApiConfig.from_env()

            self.assertEqual(config.api_key, "env_key")
            self.assertEqual(config.api_secret, "env_secret")

        finally:
            # Restore environment
            if old_key is None:
                os.environ.pop("API_KEY", None)
            else:
                os.environ["API_KEY"] = old_key

            if old_secret is None:
                os.environ.pop("API_SECRET", None)
            else:
                os.environ["API_SECRET"] = old_secret

    def test_from_env_missing(self):
        """Test from_env raises error when env vars not set."""
        old_key = os.environ.get("API_KEY")
        old_secret = os.environ.get("API_SECRET")

        try:
            os.environ.pop("API_KEY", None)
            os.environ.pop("API_SECRET", None)

            with self.assertRaises(ValueError):
                ApiConfig.from_env()

        finally:
            if old_key:
                os.environ["API_KEY"] = old_key
            if old_secret:
                os.environ["API_SECRET"] = old_secret


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager singleton."""

    def test_singleton(self):
        """Test that ConfigManager is a singleton."""
        manager1 = ConfigManager()
        manager2 = ConfigManager()

        self.assertIs(manager1, manager2)

    def test_set_get_config(self):
        """Test setting and getting configuration."""
        config = ApiConfig("test_key", "test_secret")

        ConfigManager().set_api_config(config)

        retrieved = ConfigManager().get_api_config()
        self.assertEqual(retrieved.api_key, "test_key")
        self.assertEqual(retrieved.api_secret, "test_secret")

    def test_clear_config(self):
        """Test clearing configuration."""
        config = ApiConfig("test_key", "test_secret")

        ConfigManager().set_api_config(config)
        self.assertTrue(ConfigManager().is_configured)

        ConfigManager().clear_api_config()
        self.assertFalse(ConfigManager().is_configured)

    def test_is_configured(self):
        """Test is_configured property."""
        self.assertFalse(ConfigManager().is_configured)

        ConfigManager().set_api_config(ApiConfig("key", "secret"))
        self.assertTrue(ConfigManager().is_configured)


if __name__ == '__main__':
    unittest.main()
