import unicorn_binance_rest_api as ubr
import unicorn_binance_websocket_api as ubw
import unicorn_binance_rest_api.unicorn_binance_rest_api_enums as enums
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
# create_stream(["kline_1m"], markets)
stream1_id = bwsm.create_stream(["kline_1s"], [symbol], stream_buffer_name="buffername")
# stream1_id = bwsm.create_stream("markPriceKline_1m", f'{symbol}_perp', stream_buffer_name="mark_klines_perp")
bwsm.stream_list
# <pair>_<contractType>@continuousKline_<interval>

# %%
def save_user_data(bwsm, data):

    while True:
        time.sleep(0.1)
        if bwsm.is_manager_stopping():
            exit(0)

        data_from_stream_buffer = bwsm.pop_stream_data_from_stream_buffer()
        if data_from_stream_buffer is False:
            time.sleep(0.01)
        else:
            print(data_from_stream_buffer)
            data.append(data_from_stream_buffer)


# %%
data = []
wthread = threading.Thread(
    target=save_user_data,
    args=(
        bwsm,
        data,
    ),
)
wthread.start()
wthread.is_alive()
data


# %%
channel = "kline" + "_" + "1s"
market = symbol

stream_name = channel + "@" + market

stream_id = bwsm.create_stream(channel, market, stream_buffer_name=stream_name)

# %%
bwsm

bwsm.is_alive()
