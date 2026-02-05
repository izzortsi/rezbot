"""Thread-safe configuration management.

This module provides thread-safe configuration classes for managing
API credentials and other settings. It uses python-dotenv to load
environment variables from a .env file.
"""

import os
from dataclasses import dataclass
from threading import Lock
from typing import Optional
from pathlib import Path
import logging

# Try to load dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

logger = logging.getLogger(__name__)


def _load_env_file():
    """Load environment variables from .env file.

    This function loads environment variables from:
    1. .env in the current working directory
    2. .env in the project root (parent of src directory)

    It only runs once to avoid repeated loading.
    """
    if not DOTENV_AVAILABLE:
        return

    # Already loaded check
    if getattr(_load_env_file, "_loaded", False):
        return

    # Load from current directory
    load_dotenv()

    # Also try to load from project root
    try:
        project_root = Path(__file__).parent.parent
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            logger.debug(f"Loaded .env from {env_file}")
    except Exception:
        pass

    _load_env_file._loaded = True


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

        Reads BINANCE_API_KEY and BINANCE_API_SECRET from environment variables.
        Automatically loads .env file if python-dotenv is available.

        Priority (highest to lowest):
        1. Explicitly passed environment variables
        2. Variables loaded from .env file
        3. System environment variables

        Environment Variables:
            BINANCE_API_KEY: Binance API key
            BINANCE_API_SECRET: Binance API secret

        For backwards compatibility, also checks:
            API_KEY: Binance API key (deprecated)
            API_SECRET: Binance API secret (deprecated)

        Args:
            exchange: The exchange to connect to

        Returns:
            A new ApiConfig instance

        Raises:
            ValueError: If required environment variables are not set
        """
        # Load .env file if available
        _load_env_file()

        # Try new variable names first
        api_key = os.environ.get("BINANCE_API_KEY")
        api_secret = os.environ.get("BINANCE_API_SECRET")

        # Fall back to old variable names for backwards compatibility
        if not api_key:
            api_key = os.environ.get("API_KEY")
        if not api_secret:
            api_secret = os.environ.get("API_SECRET")

        if not api_key:
            raise ValueError(
                "BINANCE_API_KEY environment variable not set. "
                "Either set it directly, export it, or add it to a .env file."
            )

        if not api_secret:
            raise ValueError(
                "BINANCE_API_SECRET environment variable not set. "
                "Either set it directly, export it, or add it to a .env file."
            )

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
            ValueError: If BINANCE_API_KEY or BINANCE_API_SECRET
                        environment variables are not set and no config
                        was explicitly set
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


def load_env_file(env_file: Optional[str] = None) -> None:
    """Manually load environment variables from a .env file.

    This function is useful if you want to explicitly load a specific
    .env file rather than relying on automatic loading.

    Args:
        env_file: Path to the .env file. If None, searches for .env
                  in current directory and project root.

    Raises:
        ImportError: If python-dotenv is not installed
    """
    if not DOTENV_AVAILABLE:
        raise ImportError(
            "python-dotenv is not installed. "
            "Install it with: pip install python-dotenv"
        )

    if env_file:
        load_dotenv(env_file)
        logger.info(f"Loaded .env from {env_file}")
    else:
        _load_env_file()
        logger.info("Loaded .env from default locations")
