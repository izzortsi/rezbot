# %%

from binance import Client, BinanceSocketManager
from binance.enums import *
from unicorn_binance_rest_api.unicorn_binance_rest_api_manager import (
    BinanceRestApiManager,
)
import os

# %%

k = os.environ.get("API_KEY")
s = os.environ.get("API_SECRET")

# %%
client = Client(api_key=k, api_secret=s)
bm = BinanceSocketManager(client)
# %%
ks = bm.kline_socket("BNBBTC", interval=KLINE_INTERVAL_1MINUTE)

# %%
ks
ks.connect()
print(ks)
# %%
ex_info = client.get_exchange_info()
symbols = ex_info["symbols"]
symbols


symbols

print(len(ex_info["symbols"]))


brm = BinanceRestApiManager(api_key=k, api_secret=s, exchange="binance-futures.com")
