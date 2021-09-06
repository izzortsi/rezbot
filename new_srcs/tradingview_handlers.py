# %%

import threading
from tradingview_ta import TA_Handler, Interval, Exchange
import tradingview_ta
import time
import numpy as np


class ThreadedTAHandler(threading.Thread):
    def __init__(self, symbol, tframes, rate):
        threading.Thread.__init__(self)
        self.symbol = symbol
        self.tframes = tframes
        self.rate = rate
        self.summary = []
        self.signal = 0
        self.handlers = {}
        self.make_handlers()
        #self.threaded_handler = self.start_threaded_handler()
        self.keep_alive = True
        self.daemon = True
        self.printing = False
        self.start()

    def run(self):
        while self.keep_alive:
            self.check_signals()
            if self.printing:
                print(self.summary, self.signal)
            time.sleep(self.rate)

    def stop(self):
        self.keep_alive = False

    def make_handlers(self):

        for tf in self.tframes:
            h_tf = TA_Handler(
                symbol=self.symbol,
                exchange="binance",
                screener="crypto",
                interval=tf,
                timeout=None,
            )
            self.handlers[f"h_{tf}"] = h_tf

    def check_signals(self):

        summary = []
        recommendations = []

        for handler_key in self.handlers:
            handler = self.handlers[f"{handler_key}"]
            analysis_tf = handler.get_analysis()
            handler_summary = analysis_tf.summary
            summary.append(handler_summary)
            recommendations.append(handler_summary["RECOMMENDATION"])
        recommendations = np.array(recommendations)

        if np.alltrue("BUY" in recommendations):
            self.signal = 1
        elif np.alltrue("SELL" in recommendations):
            self.signal = -1
        else:
            self.signal = 0

        self.summary = summary


# %%
# th = ThreadedTAHandler("bnbusdt", ["1m", "5m"], 5)
# th.start()
# th.isDaemon()
# th.summaries

# # %%
# th.is_alive()
# # %%
# th.summary
# # %%
