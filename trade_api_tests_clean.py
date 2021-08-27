import unicorn_binance_rest_api as ubr
import unicorn_binance_websocket_api as ubw
import unicorn_binance_rest_api.unicorn_binance_rest_api_enums as enums
from unicorn_binance_rest_api.unicorn_binance_rest_api_exceptions import *
import os
import threading
import time

# %%


api_key = os.environ.get("API_KEY")
api_secret = os.environ.get("API_SECRET")

brm = ubr.BinanceRestApiManager(api_key=api_key, api_secret=api_secret)
bwsm = ubw.BinanceWebSocketApiManager(
    output_default="UnicornFy", exchange="binance.com-futures"
)

# %%
symbol = "bnbusdt"
if symbol == "bnbusdt":
    qty = 0.01
elif symbol == "ethusdt":
    qty = 0.001

# %%


def f_tp_price(price, tp, lev, side="BUY"):
    if side == "BUY":
        return f"{(price * (1+(tp/lev)/100)):.2f}"
    elif side == "SELL":
        return f"{(price * (1-(tp/lev)/100)):.2f}"


def f_sl_price(price, sl, lev, side="BUY"):
    if side == "BUY":
        return f"{(price * (1+(sl/lev)/100)):.2f}"
    elif side == "SELL":
        return f"{(price * (1-(sl/lev)/100)):.2f}"


# %%

lev = 75

# %%

sl = -5
sl / lev
tp = 15
tp / lev

# %%


# %%
ticker = brm.get_symbol_ticker(symbol=symbol.upper())
price = float(ticker["price"])

tp_price = f_tp_price(price, tp, lev)
sl_price = f_sl_price(price, sl, lev)
tp_price
sl_price
# price

brm.futures_change_leverage(symbol=symbol, leverage=lev)
# %%
# SIDE = "BUY"
S = "SELL"
B = "BUY"
# %%
def send_order(tp, sl, side="BUY", protect=False):
    if side == "SELL":
        counterside = "BUY"
    elif side == "BUY":
        counterside = "SELL"

    try:
        new_position = brm.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=qty,
            priceProtect=protect,
            workingType="CONTRACT_PRICE",
        )
        print(new_position)
    except BinanceAPIException as error:
        print(type(error))
        print("positioning, ", error)
    else:
        position = brm.futures_position_information(symbol=symbol)
        price = float(position[0]["entryPrice"])
        tp_price = f_tp_price(price, tp, lev, side=side)
        sl_price = f_sl_price(price, sl, lev, side=side)
        print(
            f"""price: {price}
                  tp_price: {tp_price}
                  sl_price: {sl_price}"""
        )

        try:
            stop_order = brm.futures_create_order(
                symbol=symbol,
                side=counterside,
                type="STOP_MARKET",
                stopPrice=sl_price,
                workingType="CONTRACT_PRICE",
                quantity=qty,
                reduceOnly=True,
                priceProtect=protect,
                timeInForce="GTE_GTC",
            )
        except BinanceAPIException as error:
            if error.code == -2021:
                print(type(error))
                print("sl order, ", error)
                # try:
                #     stop_order = brm.futures_create_order(
                #         symbol=symbol,
                #         side=counterside,
                #         type="STOP_MARKET",
                #         stopPrice=sl_price,
                #         workingType="CONTRACT_PRICE",
                #         quantity=qty,
                #         reduceOnly=True,
                #         priceProtect=protect,
                #         timeInForce="GTE_GTC",
                #     )
                # except BinanceAPIError as error:
                #     print(type(error))
                #     print("sl order 2, ", error)
        else:
            try:
                tp_order = brm.futures_create_order(
                    symbol=symbol,
                    side=counterside,
                    type="TAKE_PROFIT_MARKET",
                    stopPrice=tp_price,
                    workingType="CONTRACT_PRICE",
                    quantity=qty,
                    reduceOnly=True,
                    priceProtect=protect,
                    timeInForce="GTE_GTC",
                )
            except BinanceAPIException as error:

                print(type(error))
                print("tp order, ", error)
    return


# %%
qty*=2
# %%

send_order(tp, sl, side=B, protect=False)
# %%
position = brm.futures_position_information(symbol=symbol)
price = float(position[0]["entryPrice"])
tp_price = f_tp_price(price, tp, lev, side=B)
sl_price = f_sl_price(price, sl, lev, side=B)
print(
        f"""price: {price}
        tp_price: {tp_price}
        sl_price: {sl_price}"""
)

# %%
new_position = brm.futures_create_order(
    symbol=symbol,
    side=B,
    type="MARKET",
    quantity=qty,
    priceProtect=False,
    workingType="CONTRACT_PRICE",
    newOrderRespType="RESULT",
)

# %%
new_position
# %%

close_order = brm.futures_create_order(
            symbol=symbol,
            side=S,
            type="MARKET",
            workingType="CONTRACT_PRICE",
            quantity=qty,
            reduceOnly=True,
            priceProtect=False,
            newOrderRespType="RESULT",
)


# %%
close_order
# %%
tp_order2 = brm.futures_create_order(
    symbol="ETHUSDT",
    side="SELL",
    type="TAKE_PROFIT_MARKET",
    stopPrice=tp_price,
    workingType="MARK_PRICE",
    quantity=qty,
    reduceOnly=True,
    priceProtect=True,
    timeInForce="GTE_GTC",
)

# %%




# %%
new_position
position = brm.futures_position_information(symbol=symbol)


# %%
position
# %%


# %%
tp_order2 = None
# %%
print(tp_order2)
# %%

new_position

# %%


stop_order["orderId"]
brm.futures_get_order(symbol="ethusdt", orderId=stop_order["orderId"])
brm.futures_get_order(symbol="ethusdt", orderId=tp_order["orderId"])
brm.futures_cancel_all_open_orders

# %%

stop_order = brm.futures_create_order(
    symbol="ETHUSDT",
    side="SELL",
    type="STOP_MARKET",
    stopPrice=sl_price,
    workingType="MARK_PRICE",
    quantity=qty,
    reduceOnly=True,
    priceProtect=True,
    timeInForce="GTE_GTC",
)


# %%
bwsm.create_stream()

<pair>_<contractType>@continuousKline_<interval>

# %%
userdata = bwsm.pop_stream_data_from_stream_buffer("userData")
userdata
userdata = []
keep_streaming = True


def save_user_data(bwsm, stream_buffer_name):

    while True:
        time.sleep(1)
        data_from_stream = bwsm.pop_stream_data_from_stream_buffer(stream_buffer_name)
        userdata.append(data_from_stream)


# %%

thread = threading.Thread(target=save_user_data, args=(bwsm, "userData"))
thread.keep_streaming = True
thread.start()

userdata
worker_thread.keep_streaming
worker_thread.is_alive()
ubwa_com_im.create_stream(
    "arr", "!userData", symbols="trxbtc", api_key=api_key, api_secret=api_secret
)



# %%

import pandas as pd
import pandas_ta as ta
import numpy.random as npr

# %%

randarr = npr.randn(50)
df = pd.DataFrame(data=randarr, columns=["series"])


# %%
series = df.series.tail(26)


# %%
minmax = lambda series: (series - series.min())/(series.max() - series.min())


from backtest.hist_grabber import HistoricalMACDGrabber

mgrab = HistoricalMACDGrabber(brm)


# %%
mgrab.get_data(symbol="BNBUSDT", tframe="15m", fromdate="1 day ago")
df = mgrab.compute_indicators()
normalized_hist = minmax(df.histogram)
normalized_hist.tail(30).describe()["25%"]
norm_tail = normalized_hist.tail(30)
description = norm_tail.describe()
description['mean'] - description['25%']
