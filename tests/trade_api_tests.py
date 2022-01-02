
# %%

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

def f_tp_price(price, tp, lev, side="BUY", with_fee = True):
    if with_fee:
        if side == "BUY":
                return f"{(price * ((1+(tp/lev) + 0.04)/100)):.2f}"
        elif side == "SELL":
                return f"{(price * ((1-(tp/lev)-0.04)/100)):.2f}"
    else:
        if side == "BUY":
                return f"{(price * (1+(tp/lev)/100)):.2f}"
        elif side == "SELL":
                return f"{(price * (1-(tp/lev)/100)):.2f}"


def f_sl_price(price, sl, lev, side="BUY", with_fee=True):
    if with_fee:
        if side == "BUY":
            return f"{(price * ((1+(sl/lev)+0.04)/100)):.2f}"
        elif side == "SELL":
            return f"{(price * ((1-(sl/lev)-0.04)/100)):.2f}"

    else:
        if side == "BUY":
            return f"{(price * (1+(sl/lev)/100)):.2f}"
        elif side == "SELL":
            return f"{(price * (1-(sl/lev)/100)):.2f}"


# %%

symbol = "bnbusdt"
lev = 60

# %%

sl = -3
sl / lev
tp = 10
tp / lev

# %%
if symbol == "bnbusdt":
    qty = 0.01
elif symbol == "ethusdt":
    qty = 0.001

# %%
ticker = brm.get_symbol_ticker(symbol=symbol.upper())
price = float(ticker["price"])

tp_price = f_tp_price(price, tp, lev)
sl_price = f_sl_price(price, sl, lev)
print(f"""tp_price: {tp_price}
price: {price}
sl_price: {sl_price}
""")
# %%
100 * (float(sl_price) - price) / price
# %%
"""
isso aqui é o seguinte: se o min notional é 5usd,
tem q valer q qty * price >= 5usd.

"""
calc_notional = lambda lev, market_value: market_value / lev

# %%
notional = calc_notional(lev, price)
notional

# %%
(qty * price)
qty * price
# %%

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
qty *= 2
send_order(tp, sl, side=S, protect=False)
# %%

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

new_position = brm.futures_create_order(
    symbol=symbol,
    side=S,
    type="MARKET",
    quantity=qty,
    priceProtect=False,
    workingType="CONTRACT_PRICE",
)


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
