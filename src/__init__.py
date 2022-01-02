import json
import logging
import os
import time
import threading
import numpy as np
import pandas as pd
import pandas_ta as ta
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime
from urllib.parse import urlencode

from unicorn_binance_rest_api.unicorn_binance_rest_api_manager import (
    BinanceRestApiManager as Client,
)
from unicorn_binance_rest_api.unicorn_binance_rest_api_helpers import (
    interval_to_milliseconds,
)
from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import (
    BinanceWebSocketApiManager,
)

# CONSTANTS

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

# AUXILIARY FUNCTIONS


# def futures_mark_price_klines(self, **params):
#     """Kline/candlestick bars for a symbol. Klines are uniquely identified by their open time.
#     https://binance-docs.github.io/apidocs/futures/en/#kline-candlestick-data-market_data
#     """
#     return self._request_futures_api("get", "markPriceKlines", data=params)

# def futures_continuous_klines(self, **params):
#     """Kline/candlestick bars for a symbol. Klines are uniquely identified by their open time.
#     https://binance-docs.github.io/apidocs/futures/en/#kline-candlestick-data-market_data
#     """
#     return self._request_futures_api("get", "continuousKlines ", data=params)

def futures_place_batch_order(self, **params):
    """Send in new orders.
    https://binance-docs.github.io/apidocs/delivery/en/#place-multiple-orders-trade
    To avoid modifying the existing signature generation and parameter order logic,
    the url encoding is done on the special query param, batchOrders, in the early stage.
    """
    query_string = urlencode(params)
    query_string = query_string.replace("%27", "%22")
    params["batchOrders"] = query_string[12:]
    return self._request_futures_api("post", "batchOrders", True, data=params)


# Client.futures_mark_price_klines = futures_mark_price_klines
# Client.futures_continuous_klines = futures_continuous_klines
Client.futures_place_batch_order = futures_place_batch_order


def name_trader(strategy, symbol):
    return "_".join([strategy.name, symbol, strategy.timeframe])


def to_percentual(exit_price, entry_price, leverage=1):
    """
    Converts a difference in values to a percentual difference.

    Args:
        exit_price (float or integer)
        entry_price (float or integer)
        leverage (int)
    Returns:
        float: ((exit_price - entry_price) / entry_price) * 100 * leverage
    """
    return ((exit_price - entry_price) / entry_price) * 100 * leverage


UTCM3 = -pd.Timedelta("3:00:00")


def to_datetime_tz(arg, timedelta=-pd.Timedelta("03:00:00"), unit="s", **kwargs):
    """
    to_datetime_tz(arg, timedelta=-pd.Timedelta("03:00:00"), unit="s", **kwargs)

    Args:
        arg (float): epochtime
        timedelta (pd.Timedelta): timezone correction
        unit (string): unit in which `arg` is
        **kwargs: pd.to_datetime remaining kwargs
    Returns:
    pd.Timestamp: a timestamp corrected by the given timedelta
    """
    ts = pd.to_datetime(arg, unit=unit)
    return ts + timedelta


def strf_epoch(epochtime, fmt="%j-%y_%H-%M-%S"):
    """
    returns: string
    """

    """
    epochtime to string using datetime
    signature: def strf_epoch(epochtime, fmt="%j-%y_%H-%M-%S")

    Args:
        epochtime (float): epochtime as float in seconds
        fmt (string): format for the timestamp string
    Returns:
        string: stringfied epochtime: datetime.fromtimestamp(epochtime).strftime(fmt)
    """

    return datetime.fromtimestamp(epochtime).strftime(fmt)


def f_tp_price(price, tp, lev, side="BUY"):
    if side == "BUY":
        return f"{(price * (1+(tp/lev)/100)):.2f}"
    elif side == "SELL":
        return f"{(price * (1-(tp/lev)/100)):.2f}"


def f_sl_price(price, sl, lev, side="BUY"):
    if side == "BUY":
        return f"{(price * (1+(sl/lev)/100)):.2f}"
    elif side == "SELL":
        return f"{(price * (1-(sl/lev)/100)):.2f}"  # sl is supposed negative


# LOGGER CONFIG
LOG_DATEFORMAT = "%j-%y_%H-%M-%S"

if not os.path.exists("logs"):
    os.mkdir("logs")

logs_for_this_run = os.path.join("logs", strf_epoch(time.time()))

if not os.path.exists(logs_for_this_run):
    os.mkdir(logs_for_this_run)

# %%

formatter = logging.Formatter("%(asctime)s %(message)s")


def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""

    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


def rows_to_csv(rows: list, num_rows: int, path: str):
    for i, row in enumerate(rows[-num_rows:]):
        if i == 0:
            row.to_csv(path, header=True, mode="w", index=False)
        elif i > 0:
            row.to_csv(path, header=False, mode="a", index=False)
