"""Trade execution and order management.

This module provides the TradeExecutor class for handling trade
execution with proper thread synchronization.
"""

import threading
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import logging

from unicorn_binance_rest_api.unicorn_binance_rest_api_exceptions import BinanceAPIException
from ..symbols_formats import FORMATS

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> "OrderSide":
        """Get the opposite order side."""
        return OrderSide.SELL if self == OrderSide.BUY else OrderSide.BUY


@dataclass
class OrderResult:
    """Result of an order execution.

    Attributes:
        success: Whether the order was successful
        order_id: Order ID if successful
        price: Execution price if successful
        executed_qty: Executed quantity if successful
        error: Error message if unsuccessful
    """
    success: bool
    order_id: Optional[str] = None
    price: Optional[float] = None
    executed_qty: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def success_result(cls, order_id: str, price: float = None, executed_qty: str = None) -> "OrderResult":
        """Create a successful order result."""
        return cls(success=True, order_id=order_id, price=price, executed_qty=executed_qty)

    @classmethod
    def failure_result(cls, error: str) -> "OrderResult":
        """Create a failed order result."""
        return cls(success=False, error=error)


class TradeExecutor:
    """Handles trade execution with thread-safe operations.

    This class wraps Binance API calls for trading operations with
    proper error handling and thread synchronization.

    Example:
        executor = TradeExecutor(
            client=binance_client,
            symbol="BTCUSDT",
            leverage=10,
            is_real=False
        )

        # Enter long position
        result = executor.enter_position(
            side=OrderSide.BUY,
            quantity="0.001"
        )

        # Exit position
        result = executor.close_position(
            side=OrderSide.SELL,
            quantity="0.001"
        )
    """

    def __init__(
        self,
        client,
        symbol: str,
        leverage: int,
        is_real: bool = False
    ):
        """Initialize the trade executor.

        Args:
            client: Binance REST API client
            symbol: Trading symbol
            leverage: Trading leverage
            is_real: Whether using real trading (vs test mode)
        """
        self.client = client
        self.symbol = symbol.upper()
        self.leverage = leverage
        self.is_real = is_real

        self._lock = threading.RLock()
        self._setup_precision()

        # Set leverage if real trading
        if self.is_real:
            self._set_leverage()

    def _setup_precision(self) -> None:
        """Setup quantity and price precision from symbol formats."""
        if self.symbol in FORMATS:
            fmt = FORMATS[self.symbol]
            self._qty_precision = int(fmt["quantityPrecision"])
            self._price_precision = int(fmt["pricePrecision"])

            # Calculate minimum quantity
            self._min_qty = 1 / (10 ** self._qty_precision)

            # Price and quantity formatters
            self._format_price = lambda x: f"{float(x):.{self._price_precision-1}f}"
            self._format_qty = lambda x: f"{float(x):.{self._qty_precision}f}"

            logger.info(f"Setup precision for {self.symbol}: qty={self._qty_precision}, price={self._price_precision}")
        else:
            # Default values
            self._qty_precision = 3
            self._price_precision = 2
            self._min_qty = 0.001
            self._format_price = lambda x: f"{x:.2f}"
            self._format_qty = lambda x: f"{x:.3f}"
            logger.warning(f"Symbol {self.symbol} not in FORMATS, using defaults")

    def _set_leverage(self) -> None:
        """Set leverage for the symbol."""
        try:
            self.client.futures_change_leverage(
                symbol=self.symbol,
                leverage=self.leverage
            )
            logger.info(f"Set leverage for {self.symbol} to {self.leverage}x")
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage: {e}")
            raise

    def calculate_quantity(
        self,
        base_qty: float,
        notional: float = 5
    ) -> str:
        """Calculate order quantity meeting notional requirements.

        Args:
            base_qty: Base quantity
            notional: Minimum notional value (default 5 USDT)

        Returns:
            Formatted quantity string
        """
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            price = float(ticker["price"])

            # Ensure notional requirement
            multiplier = base_qty * max(1, notional / (price * self._min_qty))
            qty = multiplier * self._min_qty

            return self._format_qty(qty)
        except Exception as e:
            logger.error(f"Failed to calculate quantity: {e}")
            return self._format_qty(base_qty)

    def enter_position(
        self,
        side: OrderSide,
        quantity: str,
        protect: bool = False
    ) -> OrderResult:
        """Enter a position with market order.

        Args:
            side: Order side (BUY or SELL)
            quantity: Order quantity (formatted string)
            protect: Whether to enable price protection

        Returns:
            OrderResult with execution details
        """
        with self._lock:
            try:
                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side=side.value,
                    type="MARKET",
                    quantity=quantity,
                    priceProtect=protect,
                    workingType="CONTRACT_PRICE"
                )

                # Get position info
                positions = self.client.futures_position_information(symbol=self.symbol)
                position = positions[-1] if positions else None

                entry_price = float(position["entryPrice"]) if position else None

                logger.info(f"Entered {side.value} position: {self.symbol}, qty={quantity}, price={entry_price}")

                return OrderResult.success_result(
                    order_id=str(order.get("orderId")),
                    price=entry_price,
                    executed_qty=order.get("executedQty")
                )

            except BinanceAPIException as e:
                logger.error(f"Entry order failed: {e}")
                return OrderResult.failure_result(str(e))

    def place_take_profit(
        self,
        side: OrderSide,
        price: float,
        quantity: str,
        protect: bool = False
    ) -> OrderResult:
        """Place take profit limit order.

        Args:
            side: Order side (opposite to position side)
            price: Take profit price
            quantity: Order quantity
            protect: Whether to enable price protection

        Returns:
            OrderResult with execution details
        """
        with self._lock:
            try:
                formatted_price = self._format_price(price)

                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side=side.value,
                    type="LIMIT",
                    price=formatted_price,
                    quantity=quantity,
                    reduceOnly=True,
                    priceProtect=protect,
                    timeInForce="GTC"
                )

                logger.info(f"Placed TP order: {self.symbol}, price={formatted_price}, qty={quantity}")

                return OrderResult.success_result(
                    order_id=str(order.get("orderId")),
                    price=price
                )

            except BinanceAPIException as e:
                logger.error(f"TP order failed: {e}")
                return OrderResult.failure_result(str(e))

    def close_position(
        self,
        side: OrderSide,
        quantity: str,
        protect: bool = False
    ) -> OrderResult:
        """Close position with market order.

        Args:
            side: Order side (opposite to position side)
            quantity: Order quantity
            protect: Whether to enable price protection

        Returns:
            OrderResult with execution details
        """
        with self._lock:
            try:
                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side=side.value,
                    type="MARKET",
                    quantity=quantity,
                    reduceOnly=True,
                    priceProtect=protect,
                    workingType="MARK_PRICE",
                    newOrderRespType="RESULT"
                )

                if order.get("status") == "FILLED":
                    exit_price = float(order.get("avgPrice"))
                    logger.info(f"Closed position: {self.symbol}, price={exit_price}, qty={quantity}")

                    return OrderResult.success_result(
                        order_id=str(order.get("orderId")),
                        price=exit_price,
                        executed_qty=order.get("executedQty")
                    )

                logger.warning(f"Close order not filled: {order}")
                return OrderResult.failure_result("Order not filled")

            except BinanceAPIException as e:
                logger.error(f"Close position failed: {e}")
                return OrderResult.failure_result(str(e))

    def check_order_status(self, order_id: str) -> dict:
        """Check status of existing order.

        Args:
            order_id: Order ID to check

        Returns:
            Dictionary with order status
        """
        try:
            order = self.client.futures_get_order(
                symbol=self.symbol,
                orderId=order_id
            )
            return order
        except BinanceAPIException as e:
            logger.error(f"Failed to check order: {e}")
            return {}
