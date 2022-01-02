# %%
from unicorn_binance_rest_api import BinanceRestApiManager
import os

# %%

k = os.environ.get("API_KEY")
s = os.environ.get("API_SECRET")


brm = BinanceRestApiManager(
    api_key="2e038ae363f8d577c24e97a16efcee5b9c52cb16a9962ae300fa9444a0873927",
    api_secret="24c4a92e55c08a4a127de09149d0fec9b863b88233b362d824f005f8cbdcea39",
    exchange="binance.com-futures-testnet",
)

# %%
brm.get_open_orders()
