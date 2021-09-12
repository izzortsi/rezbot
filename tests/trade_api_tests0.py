# %%

import pandas as pd
import json
from src.tradingview_handlers import ThreadedTAHandler
import unicorn_binance_rest_api as ubr
import unicorn_binance_websocket_api as ubw
import unicorn_binance_rest_api.unicorn_binance_rest_api_enums as enums
from unicorn_binance_rest_api.unicorn_binance_rest_api_exceptions import *
import os
import threading
import time
import tradingview_ta as ta

# %%


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
        # self.threaded_handler = self.start_threaded_handler()
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
th = ThreadedTAHandler("bnbusdt", ["1m", "5m"], 1)

# %%


API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")


# %%

brm = ubr.BinanceRestApiManager(
    api_key=API_KEY, api_secret=API_SECRET, exchange="binance.com-futures"
)
bwsm = ubw.BinanceWebSocketApiManager(
    output_default="UnicornFy", exchange="binance.com-futures"
)

# %%


info_data = brm.get_exchange_info()


# %%
ex_info

# %%


def f_price(price):
    return f"{price:.2f}"


# %%
symbol = "bnbusdt"


# %%
# SIDE = "BUY"
S = "SELL"
B = "BUY"


# %%
def compute_exit(entry_price, target_profit, side, entry_fee=0.04, exit_fee=0.04):
    if side == "BUY":
        exit_price = (
            entry_price
            * (1 + target_profit / 100 + entry_fee / 100)
            / (1 - exit_fee / 100)
        )
    elif side == "SELL":
        exit_price = (
            entry_price
            * (1 - target_profit / 100 - entry_fee / 100)
            / (1 + exit_fee / 100)
        )
    return exit_price


# %%
ep = 499.86
sl_p = compute_exit(ep, 0.1, side="SELL")
# %%
100 * (sl_p - ep) / ep
# %%

sl_p
# %%
xp = compute_exit(ep, 1, side="BUY")
# %%
100 * (xp - ep) / ep
# %%
xp

# %%
handler = ThreadedTAHandler("BNBUSDT", ["1m", "5m"], rate=60)
# %%
handler.signal
# %%
handler.printing = True
# %%
handler.summary
# %%
handler.stop()

# %%


class OrderMaker:
    def __init__(self, client):
        self.client = client
        self.is_positioned = False
        self.side = None
        self.counterside = None
        self.entry_price = None
        self.tp_price = None
        self.qty = None

    def send_order(self, symbol, tp, qty, side="BUY", protect=False, sl=None):
        if side == "SELL":
            self.side = "SELL"
            self.counterside = "BUY"
        elif side == "BUY":
            self.side = "BUY"
            self.counterside = "SELL"

        if not self.is_positioned:
            try:
                new_position = self.client.futures_create_order(
                    symbol=symbol,
                    side=self.side,
                    type="MARKET",
                    quantity=qty,
                    priceProtect=protect,
                    workingType="CONTRACT_PRICE",
                )
            except BinanceAPIException as error:
                print(type(error))
                print("positioning, ", error)
            else:
                self.is_positioned = True
                self.position = self.client.futures_position_information(symbol=symbol)
                self.entry_price = float(self.position[0]["entryPrice"])
                self.qty = self.position[0]["positionAmt"]
                # tp_price = f_tp_price(price, tp, lev, side=side)
                # sl_price = f_sl_price(price, sl, lev, side=side)
                self.tp_price = f_price(
                    compute_exit(self.entry_price, tp, side=self.side)
                )

                print(
                    f"""price: {self.entry_price}
                          tp_price: {self.tp_price}
                          """
                )

                try:
                    self.tp_order = self.client.futures_create_order(
                        symbol=symbol,
                        side=self.counterside,
                        type="LIMIT",
                        price=self.tp_price,
                        workingType="CONTRACT_PRICE",
                        quantity=self.qty,
                        reduceOnly=True,
                        priceProtect=protect,
                        timeInForce="GTC",
                    )
                except BinanceAPIException as error:
                    print(type(error))
                    print("tp order, ", error)
                if sl is not None:
                    self.sl_price = f_price(
                        compute_exit(self.entry_price, sl, side=self.counterside)
                    )
                    try:
                        self.sl_order = self.client.futures_create_order(
                            symbol=symbol,
                            side=self.counterside,
                            type="LIMIT",
                            price=self.sl_price,
                            workingType="CONTRACT_PRICE",
                            quantity=self.qty,
                            reduceOnly=True,
                            priceProtect=protect,
                            timeInForce="GTC",
                        )
                    except BinanceAPIException as error:
                        print(type(error))
                        print("sl order, ", error)

    def send_tp_order(self, symbol, side, tp, protect=False):
        if side == "SELL":
            counterside = "BUY"
        elif side == "BUY":
            counterside = "SELL"
        self.position = self.client.futures_position_information(symbol=symbol)
        self.entry_price = float(self.position[0]["entryPrice"])
        self.qty = self.position[0]["positionAmt"]
        # tp_price = f_tp_price(price, tp, lev, side=side)
        # sl_price = f_sl_price(price, sl, lev, side=side)
        self.tp_price = f_price(compute_exit(self.entry_price, tp, side=side))

        try:
            self.tp_order = self.client.futures_create_order(
                symbol=symbol,
                side=counterside,
                type="LIMIT",
                price=self.tp_price,
                workingType="CONTRACT_PRICE",
                quantity=self.qty,
                reduceOnly=True,
                priceProtect=protect,
                timeInForce="GTC",
            )
        except BinanceAPIException as error:
            print(type(error))
            print("tp order, ", error)


# %%
omaker = OrderMaker(brm)
# %%
omaker.is_positioned = False
# %%

handler.summary
# %%
omaker.send_order(symbol, 0.1, 0.02, side=B)

# %%
omaker.send_tp_order(symbol, B, 0.04)
# %%
handler.stop()
ep = omaker.entry_price
tpp = float(omaker.tp_price)
100 * (tpp - ep) / ep

# %%
o = omaker.tp_order

# %%
o

# %%


# %%
orders
# %%

o["orderId"]
# %%
brm.futures_get_order(symbol=symbol.upper(), orderId=o["orderId"])


# %%
