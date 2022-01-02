# %% 
from tradingview_ta import TA_Handler, Interval, Exchange
import tradingview_ta

# from binance import binance_f
from unicorn_binance_rest_api import *
import os
# %%

key = os.environ.get("API_KEY")
secret = os.environ.get("API_SECRET")

client = BinanceRestApiManager(api_key = key, api_secret = secret, exchange="binance.com-futures")
# %%
sym = "ADABUSD"
 
# %%
handler = TA_Handler(
    symbol=sym,
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
    signals = {}
    for handler_key in handlers:
        tf = handler_key.split("_")[1]
        handler = handlers[f"{handler_key}"]
        analysis_tf = handler.get_analysis()
        recommendation = analysis_tf.summary["RECOMMENDATION"]
        print(f"{tf}: {recommendation}")
        signals[tf] = recommendation
    return signals
    


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
tfs = ["1m", "5m", "15m", "30m", "1h", "4h"]

# %%
handlers = make_handlers(sym, tfs)
handlers

# %%
signals = check_signals(handlers)


# %%
def convert_signals(signals: dict):
    numeric_signals = {}
    for k in signals:
        if signals[k] == "STRONG SELL":
            numeric_signals[k] = -2
        elif signals[k] == "SELL":
            numeric_signals[k] = -1
        elif signals[k] == "NEUTRAL":
            numeric_signals[k] = 0
        elif signals[k] == "BUY":
            numeric_signals[k] = 1
        elif signals[k] == "STRONG BUY":
            numeric_signals[k] = 2
    return numeric_signals
# %%
numeric_signals = convert_signals(signals)
numeric_signals
# %%
