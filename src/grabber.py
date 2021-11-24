# %%
# from unicorn_binance_rest_api.unicorn_binance_rest_api_manager import (
#     BinanceRestApiManager as Client,
# )
from src import *

# import pandas as pd
# import pandas_ta as ta

# %%


class DataGrabber:
    def __init__(self, client):
        self.client = client

    def get_data(
        self, symbol="BTCUSDT", tframe="1h", limit=None, startTime=None, endTime=None
    ):
        klines = self.client.futures_mark_price_klines(
            symbol=symbol,
            interval=tframe,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
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

    def compute_indicators(self, ohlcv, w1=5, w2=10, **params):
        
        

        # df = pd.concat([c, macd], axis=1)


        c = ohlcv["close"]
        h = ohlcv["high"]
        l = ohlcv["low"]
        v = ohlcv["volume"]

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

        price_pos = (c-l)/(h-l)
        pmean1 = c.ewm(span=w1).mean()
        pstd1 = c.ewm(span=w1).std()


        # cs = ta.vwma(h, v, length=3)
        # cs.rename("csup", inplace=True)
        # cm = ta.vwma(c, v, length=3)
        # cm.rename("cmed", inplace=True)
        # ci = ta.vwma(l, v, length=3)
        # ci.rename("cinf", inplace=True)
        
        # ind_df = pd.concat([cs, cm, ci, macd], axis=1)
        ind_df = pd.concat([macd, price_pos, pmean1, pstd1], axis=1)

        
        # df = pd.concat([cs, ci, c, cm, v], axis=1)

        return ind_df
