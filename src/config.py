"""Thread-safe configuration management.

This module provides thread-safe configuration classes for managing
API credentials and other settings.
"""

import os
from dataclasses import dataclass
from threading import Lock
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiConfig:
    """Immutable API configuration.

    This class stores API credentials and related configuration.
    It is immutable to prevent accidental modification.

    Attributes:
        api_key: Binance API key
        api_secret: Binance API secret
        exchange: Exchange to connect to (default: binance.com-futures)
    """

    api_key: str
    api_secret: str
    exchange: str = "binance.com-futures"

    @classmethod
    def from_env(cls, exchange: str = "binance.com-futures") -> "ApiConfig":
        """Create ApiConfig from environment variables.

        Reads API_KEY and API_SECRET from environment variables.

        Args:
            exchange: The exchange to connect to

        Returns:
            A new ApiConfig instance

        Raises:
            ValueError: If required environment variables are not set
        """
        api_key = os.environ.get("API_KEY")
        if not api_key:
            raise ValueError("API_KEY environment variable not set")

        api_secret = os.environ.get("API_SECRET")
        if not api_secret:
            raise ValueError("API_SECRET environment variable not set")

        return cls(api_key=api_key, api_secret=api_secret, exchange=exchange)

    def validate(self) -> bool:
        """Validate that the configuration is valid.

        Returns:
            True if both api_key and api_secret are non-empty
        """
        return bool(self.api_key and self.api_secret)


class ConfigManager:
    """Thread-safe configuration manager singleton.

    This class provides thread-safe access to API configuration using
    the singleton pattern with double-checked locking.

    Example:
        config = ConfigManager().get_api_config()
        print(f"Using API key: {config.api_key[:8]}...")

        # Or set explicitly
        ConfigManager().set_api_config(ApiConfig("key", "secret"))
    """

    _instance: Optional["ConfigManager"] = None
    _lock = Lock()

    def __new__(cls) -> "ConfigManager":
        """Create or return the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                # Double-check inside the lock
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._api_config: Optional[ApiConfig] = None
                    cls._instance._config_lock = Lock()
        return cls._instance

    def set_api_config(self, config: ApiConfig) -> None:
        """Set the API configuration.

        Args:
            config: The ApiConfig to store
        """
        with self._config_lock:
            self._api_config = config
            logger.info("API configuration updated")

    def get_api_config(self) -> ApiConfig:
        """Get the current API configuration.

        If no configuration has been set, this will attempt to load
        from environment variables.

        Returns:
            The current ApiConfig

        Raises:
            ValueError: If API_KEY or API_SECRET environment variables
                        are not set and no config was explicitly set
        """
        with self._config_lock:
            if self._api_config is None:
                self._api_config = ApiConfig.from_env()
                logger.info("API configuration loaded from environment")
            return self._api_config

    def clear_api_config(self) -> None:
        """Clear the stored API configuration.

        This will force the next call to get_api_config() to attempt
        loading from environment variables again.
        """
        with self._config_lock:
            self._api_config = None
            logger.info("API configuration cleared")

    @property
    def is_configured(self) -> bool:
        """Check if API configuration is set.

        Returns:
            True if configuration exists, False otherwise
        """
        with self._config_lock:
            return self._api_config is not None


# Convenience functions for quick access
def get_api_config() -> ApiConfig:
    """Get the current API configuration.

    This is a convenience function that delegates to ConfigManager.

    Returns:
        The current ApiConfig
    """
    return ConfigManager().get_api_config()


def set_api_config(config: ApiConfig) -> None:
    """Set the API configuration.

    This is a convenience function that delegates to ConfigManager.

    Args:
        config: The ApiConfig to store
    """
    ConfigManager().set_api_config(config)
