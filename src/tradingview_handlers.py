# %%

import threading
from tradingview_ta import TA_Handler, Interval, Exchange
import tradingview_ta
import time
import numpy as np
import pandas as pd

substring_check = np.frompyfunc((lambda s, array: s in array), 2, 1)


# class ThreadedTAHandler(threading.Thread):
#     def __init__(self, symbol, tframes, rate):
#         threading.Thread.__init__(self)
#         self.symbol = symbol
#         self.tframes = tframes
#         self.rate = rate
#         self.summary = []
#         self.signal = 0
#         self.handlers = {}
#         self.make_handlers()
#         # self.threaded_handler = self.start_threaded_handler()
#         self.keep_alive = True
#         self.daemon = True
#         self.printing = False
#         self.start()
#
#     def run(self):
#         while self.keep_alive:
#             self.check_signals()
#             if self.printing:
#                 print(self.summary, self.signal)
#             time.sleep(60 / self.rate)
#
#     def stop(self):
#         self.keep_alive = False
#
#     def make_handlers(self):
#
#         for tf in self.tframes:
#             h_tf = TA_Handler(
#                 symbol=self.symbol,
#                 exchange="binance",
#                 screener="crypto",
#                 interval=tf,
#                 timeout=None,
#             )
#             self.handlers[f"h_{tf}"] = h_tf
#
#     def check_signals(self):
#
#         summary = []
#         recommendations = []
#
#         for handler_key in self.handlers:
#             handler = self.handlers[f"{handler_key}"]
#             analysis_tf = handler.get_analysis()
#             handler_summary = analysis_tf.summary
#             summary.append(handler_summary)
#             recommendations.append(handler_summary["RECOMMENDATION"])
#         recommendations = np.array(recommendations)
#
#         if np.all(substring_check("BUY", recommendations)):
#             self.signal = 1
#         elif np.all(substring_check("SELL", recommendations)):
#             self.signal = -1
#         else:
#             self.signal = 0
#
#         self.summary = summary
#
#
# # # %%
# th = ThreadedTAHandler("bnbusdt", ["1m", "5m"], 60)
# # th.start()
# # th.isDaemon()
# # th.summary
# #
# # # %%
# th.printing = True
# # %%
# th.is_alive()
# # %%
# th.summarysymbols
# # %%symbols


class Analyst(threading.Thread):
    def __init__(self, manager, interval, strategy=None):

        threading.Thread.__init__(self)
        self.setDaemon(True)

        self.manager = manager
        self.symbols = self.manager.symbols
        self.symbols_tv = [f"binance:{symbol}" for symbol in self.symbols]
        self.strategy = strategy
        self.interval = interval
        self.rate = self.manager.rate

        self.analysises = None

        # self.keep_alive = self.manager.keep_alive

        self.is_printing = False
        self.start()

    def run(self):
        while self.manager.keep_alive:
            self.analysises = get_multiple_analysis(
                screener="crypto", interval=self.interval, symbols=self.symbols_tv
            )
            # print(self.interval, self.symbols_tv)
            self.process_analysises()

            time.sleep(60 / self.rate)

    def stop(self):
        self.keep_alive = False

    def process_analysises(self):

        for symbol, analysis in zip(self.symbols, self.analysises.values()):

            self.manager.summaries[symbol][self.interval] = analysis.summary
            # self.indicators[symbol] = {
            #     indicator: analysis.indicators[indicator]
            #     for indicator in self.strategy.indicators}

            indicators = {
                "open": analysis.indicators["open"],
                # "high": analysis.indicators["high"],
                # "low": analysis.indicators["low"],
                "close": analysis.indicators["close"],
                "volume": analysis.indicators["volume"],
                "momentum": analysis.indicators["Mom"],
                "RSI": analysis.indicators["RSI"],
                "MACD_histogram": analysis.indicators["MACD.macd"]
                - analysis.indicators["MACD.signal"],
            }

            self.manager.indicators[symbol][self.interval] = indicators
            # recommendations.append(handler_summary["RECOMMENDATION"])
            # recommendations = np.array(recommendations)

            if (
                indicators["momentum"] >= 0
                and indicators["MACD_histogram"] <= 0
                and "BUY" in analysis.summary["RECOMMENDATION"]
            ):

                self.manager.signals[symbol][self.interval] = "BUY"

            elif (
                indicators["momentum"] <= 0
                and indicators["MACD_histogram"] >= 0
                and "SELL" in analysis.summary["RECOMMENDATION"]
            ):

                self.manager.signals[symbol][self.interval] = "SELL"

            else:

                self.manager.signals[symbol][self.interval] = "NEUTRAL"

            self.manager.signals_df = pd.DataFrame.from_dict(self.signals)
