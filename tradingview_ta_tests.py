from tradingview_ta import TA_Handler, Interval, Exchange
import tradingview_ta

from unicorn_binance_rest_api import *
import os

# %%

key = os.environ.get("API_KEY")
secret = os.environ.get("API_SECRET")

client = BinanceRestApiManager()
# %%

handler = TA_Handler(
    symbol="SUSHIUSDT",
    exchange="binance",
    screener="crypto",
    interval="1m",
    timeout=None,
)
# %%


def make_handlers(pair, timeframes: list[str]):
    handlers = {}
    for tf in timeframes:
        h_tf = TA_Handler(
            symbol=pair,
            exchange="binance",
            screener="crypto",
            interval=tf,
            timeout=None,
        )
        handlers[f"h_{tf}"] = h_tf

    return handlers


# %%
def check_signals(handlers):
    signal = True
    for handler_key in handlers:
        handler = handlers[f"{handler_key}"]
        analysis_tf = handler.get_analysis()
        recommendation = analysis_tf.summary["RECOMMENDATION"]
        print(recommendation)
        if "BUY" not in recommendation:
            signal = not signal
    return signal


# %%

analysis = handler.get_analysis()
# %%
analysis.indicators
analysis.summary
analysis.indicators["Mom"]
analysis.indicators["RSI"]
analysis.indicators["MACD.macd"]
analysis.indicators["MACD.signal"]

# %%
tfs = ["1m", "5m"]

# %%
handlers = make_handlers("BNBUSDT", tfs)
handlers

# %%
check_signals(handlers)
