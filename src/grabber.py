# %%
# from unicorn_binance_rest_api.unicorn_binance_rest_api_manager import (
#     BinanceRestApiManager as Client,
# )
from src import *

import pandas as pd
import pandas_ta as ta

# %%


class DataGrabber:
    def __init__(self, client):
        self.client = client

    def get_data(
        self, symbol="BTCUSDT", tframe="1h", limit=None, startTime=None, endTime=None
    ):
        klines = self.client.futures_klines(
            symbol=symbol,
            interval=tframe,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
        )
        return self.trim_data(klines)

    def get_historical_data(
        self, symbol="BTCUSDT", tframe="1h", limit=500, startTime=None, endTime=None
    ):
        klines = self.client.get_historical_klines(
            symbol, tframe, startTime, end_str=endTime, limit=limit
        )
        return self.trim_data(klines)

    def trim_data(self, klines):

        df = pd.DataFrame(data=klines)
        DOHLCV = df.iloc[:, [0, 1, 2, 3, 4, 5]]
        dates = to_datetime_tz(DOHLCV[0], unit="ms")
        OHLCV = DOHLCV.iloc[:, [1, 2, 3, 4, 5]].astype("float64")

        DOHLCV = pd.concat([dates, OHLCV], axis=1)
        DOHLCV.columns = ["date", "open", "high", "low", "close", "volume"]
        return DOHLCV

    def compute_indicators(self, ohlcv, is_macd=True, indicators=[], **params):

        if is_macd:

            c = ohlcv
            values = [str(value) for value in list(params.values())]
            macd = ta.macd(c, **params)
            lengths = "_".join(values)
            macd.rename(
                columns={
                    f"MACD_{lengths}": "macd",
                    f"MACDh_{lengths}": "histogram",
                    f"MACDs_{lengths}": "signal",
                },
                inplace=True,
            )

            df = pd.concat([c, macd], axis=1)
            return df
        else:

            c = ohlcv["close"]
            h = ohlcv["high"]
            l = ohlcv["low"]
            v = ohlcv["volume"]

            cs = ta.vwma(h, v, length=3)
            cs.rename("csup", inplace=True)

            cm = ta.vwma(c, v, length=3)
            cm.rename("cmed", inplace=True)

            ci = ta.vwma(l, v, length=3)
            ci.rename("cinf", inplace=True)

            df = pd.concat([cs, ci, c, cm, v], axis=1)

            return df
