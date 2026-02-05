"""Binance client wrapper using binance-sdk-derivatives-trading-usds-futures.

This module provides a thin wrapper around the official Binance SDK
for USDT-M Futures trading, maintaining compatibility with existing
rezbot code patterns.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Try to import from new SDK, use fallback for testing/paper trading
try:
    from binance_common.configuration import ConfigurationRestAPI, ConfigurationWebSocketStreams
    from binance_common.constants import (
        DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
        DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL,
        DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_PROD_URL,
        DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_TESTNET_URL,
    )
    from binance_sdk_derivatives_trading_usds_futures import DerivativesTradingUsdsFutures
    from binance_common.exceptions import (
        ClientError,
        UnauthorizedError,
        TooManyRequestsError,
        RateLimitBanError,
        ServerError,
        NetworkError,
        BadRequestError,
    )
    SDK_AVAILABLE = True
except ImportError:
    # Fallback for testing/paper trading when SDK is not installed
    SDK_AVAILABLE = False

    # Create dummy exceptions
    class ClientError(Exception):
        pass
    class UnauthorizedError(Exception):
        pass
    class TooManyRequestsError(Exception):
        pass
    class RateLimitBanError(Exception):
        pass
    class ServerError(Exception):
        pass
    class NetworkError(Exception):
        pass
    class BadRequestError(Exception):
        pass

logger = logging.getLogger(__name__)


@dataclass
class BinanceClientConfig:
    """Configuration for Binance client."""
    api_key: str
    api_secret: str
    testnet: bool = False
    timeout_ms: int = 10000
    retries: int = 3
    keep_alive: bool = True

    @property
    def rest_url(self) -> str:
        return DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL if self.testnet else DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL

    @property
    def ws_url(self) -> str:
        return DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_TESTNET_URL if self.testnet else DERIVATIVES_TRADING_USDS_FUTURES_WS_STREAMS_PROD_URL


class BinanceRestClient:
    """REST API client for Binance USDT-M Futures.

    This class wraps the new binance-sdk-derivatives-trading-usds-futures
    and provides methods compatible with the old unicorn-binance-rest-api
    interface used by rezbot.
    """

    # Parameter name mapping for order creation
    _ORDER_PARAMS = {
        "symbol", "side", "type", "quantity", "price",
        "reduceOnly", "priceProtect", "workingType",
        "timeInForce", "stopPrice", "closePosition",
        "activationPrice", "callbackRate", "newOrderRespType"
    }

    def __init__(self, config: BinanceClientConfig):
        """Initialize the Binance REST client.

        Args:
            config: BinanceClientConfig with credentials and settings
        """
        self.config = config

        # Configure REST API
        self._rest_config = ConfigurationRestAPI(
            api_key=config.api_key,
            api_secret=config.api_secret,
            base_path=config.rest_url,
            timeout=config.timeout_ms,
            retries=config.retries,
            keep_alive=config.keep_alive,
        )

        # Initialize SDK client
        self._client = DerivativesTradingUsdsFutures(config_rest_api=self._rest_config)
        logger.info(f"Binance REST client initialized (testnet={config.testnet})")

    def _handle_error(self, e: Exception) -> None:
        """Log and re-raise SDK errors."""
        if isinstance(e, UnauthorizedError):
            logger.error(f"Authentication failed: {e}")
        elif isinstance(e, (TooManyRequestsError, RateLimitBanError)):
            logger.warning(f"Rate limit: {e}")
        elif isinstance(e, BadRequestError):
            logger.error(f"Bad request: {e}")
        elif isinstance(e, (ServerError, NetworkError)):
            logger.error(f"Server/Network error: {e}")
        else:
            logger.error(f"Unexpected error: {e}")
        raise

    def _unwrap_data(self, data) -> Any:
        """Unwrap SDK response data.

        The SDK wraps responses in objects with an 'actual_instance' attribute.
        This method extracts the actual data for easier access.
        """
        # If data has actual_instance attribute, unwrap it
        if hasattr(data, 'actual_instance') and data.actual_instance is not None:
            actual = data.actual_instance
            # If actual_instance is a dict, return it as is
            if isinstance(actual, dict):
                return actual
            # Otherwise return the actual instance object
            return actual
        # For lists, try to unwrap each element
        elif isinstance(data, list):
            return [self._unwrap_data(item) for item in data]
        return data

    def futures_change_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a symbol."""
        try:
            response = self._client.rest_api.change_initial_leverage(symbol=symbol, leverage=leverage)
            data = self._unwrap_data(response.data())
            return {
                "symbol": symbol,
                "leverage": leverage,
                "maxNotionalValue": str(getattr(data, 'max_notional_value', 'NA')),
            }
        except Exception as e:
            self._handle_error(e)

    def futures_create_order(self, **params) -> Dict[str, Any]:
        """Create a new order."""
        try:
            # Map parameter names from camelCase to snake_case
            mapped_params = self._map_order_params(params)
            response = self._client.rest_api.new_order(**mapped_params)
            data = self._unwrap_data(response.data())

            return {
                "orderId": str(data.order_id),
                "symbol": data.symbol,
                "status": data.status,
                "clientOrderId": data.client_order_id,
                "price": str(getattr(data, 'price', 0)),
                "avgPrice": str(getattr(data, 'avg_price', 0)),
                "executedQty": str(getattr(data, 'executed_qty', 0)),
                "cummulativeQuoteQty": str(getattr(data, 'cumulative_quote_qty', 0)),
            }
        except Exception as e:
            self._handle_error(e)

    def _map_order_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Map camelCase parameter names to snake_case for the SDK."""
        mapping = {
            "reduceOnly": "reduce_only",
            "priceProtect": "price_protect",
            "workingType": "working_type",
            "timeInForce": "time_in_force",
            "stopPrice": "stop_price",
            "closePosition": "close_position",
            "activationPrice": "activation_price",
            "callbackRate": "callback_rate",
            "newOrderRespType": "new_order_resp_type",
        }
        mapped = {}
        for key, value in params.items():
            new_key = mapping.get(key, key)
            mapped[new_key] = value
        return mapped

    def futures_position_information(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get current position information."""
        try:
            response = self._client.rest_api.position_information_v2(symbol=symbol)
            data = self._unwrap_data(response.data())
            return [
                {
                    "symbol": pos.symbol,
                    "positionAmount": getattr(pos, 'position_amt', getattr(pos, 'position_amount', '0')),
                    "entryPrice": str(getattr(pos, 'entry_price', '0')),
                    "leverage": str(pos.leverage),
                    "unrealizedProfit": str(getattr(pos, 'unrealized_profit', '0')),
                }
                for pos in data
            ]
        except Exception as e:
            self._handle_error(e)

    def futures_get_order(self, symbol: str, orderId: str) -> Dict[str, Any]:
        """Get order details."""
        try:
            response = self._client.rest_api.query_order(symbol=symbol, order_id=int(orderId))
            data = self._unwrap_data(response.data())
            return {
                "orderId": str(data.order_id),
                "symbol": data.symbol,
                "status": data.status,
                "price": str(getattr(data, 'price', 0)),
                "avgPrice": str(getattr(data, 'avg_price', 0)),
                "executedQty": str(getattr(data, 'executed_qty', 0)),
            }
        except Exception as e:
            self._handle_error(e)

    def get_symbol_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get symbol price ticker."""
        try:
            response = self._client.rest_api.symbol_price_ticker(symbol=symbol)
            data = self._unwrap_data(response.data())
            return {"symbol": data.symbol, "price": str(data.price)}
        except Exception as e:
            self._handle_error(e)

    def futures_mark_price_klines(self, **params) -> List[Any]:
        """Get kline/candlestick data."""
        try:
            kline_params = {
                "symbol": params.get("symbol"),
                "interval": params.get("interval"),
            }
            if "limit" in params:
                kline_params["limit"] = params["limit"]
            if "startTime" in params or "start_time" in params:
                kline_params["start_time"] = params.get("start_time") or params.get("startTime")
            if "endTime" in params or "end_time" in params:
                kline_params["end_time"] = params.get("end_time") or params.get("endTime")

            response = self._client.rest_api.kline_candlestick_data(**kline_params)
            # Klines returns data directly as a list of lists, no unwrapping needed
            return response.data()
        except Exception as e:
            self._handle_error(e)

    def ping(self) -> Dict[str, Any]:
        """Test connectivity."""
        try:
            self._client.rest_api.check_server_time()
            return {}
        except Exception as e:
            self._handle_error(e)


def create_binance_client(api_key: str, api_secret: str, testnet: bool = False) -> BinanceRestClient:
    """Create a Binance REST client.

    Args:
        api_key: Binance API key
        api_secret: Binance API secret
        testnet: Use testnet instead of production

    Returns:
        BinanceRestClient instance
    """
    config = BinanceClientConfig(api_key=api_key, api_secret=api_secret, testnet=testnet)
    return BinanceRestClient(config)
