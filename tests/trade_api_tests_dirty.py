import unicorn_binance_rest_api as ubr
import unicorn_binance_websocket_api as ubw
import unicorn_binance_rest_api.unicorn_binance_rest_api_enums as enums
import os
import threading
import time


API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

brm = ubr.BinanceRestApiManager(api_key=API_KEY, api_secret=API_SECRET)
bwsm = ubw.BinanceWebSocketApiManager(
    output_default="UnicornFy", exchange="binance.com-futures"
)


channel = "kline_1m"
market = "ethusdt"

stream_name = channel + "@" + market

stream_id = bwsm.create_stream(channel, market, stream_buffer_name=stream_name)


# bwsm.stop_manager_with_all_streams()
# brm.get_asset_balance(asset="BRL")

# brm.futures_account_balance()
# brm.futures_change_margin_type(symbol="bnbusdt", marginType="ISOLATED")
# brm.futures_change_leverage(symbol="bnbusdt", leverage=5)

# brm.futures_create_order(
#     symbol="BNBUSDT",
#     side="SELL",
#     type="TAKE_PROFIT_MARKET",
#     stopPrice=450.10,
#     workingType="MARK_PRICE",
#     closePosition=True,
# )


data = []


def print_stream_data_from_stream_buffer(bwsm):
    while True:

        if bwsm.is_manager_stopping():
            exit(0)

        data_from_stream_buffer = bwsm.pop_stream_data_from_stream_buffer(stream_name)

        if data_from_stream_buffer is False:
            time.sleep(0.01)
        else:

            try:
                if data_from_stream_buffer["event_type"] == "kline":
                    # print(data_from_stream_buffer["event_type"])
                    global data
                    data.append(float(data_from_stream_buffer["kline"]["close_price"]))
            except:
                print(data_from_stream_buffer)


# %%
worker_thread = threading.Thread(
    target=print_stream_data_from_stream_buffer, args=(bwsm,)
)
worker_thread.start()


# %%
data
# %%
len(data)
# %%

position = brm.futures_position_information(symbol="ethusdt")
price = float(position[0]["entryPrice"])
price

# %%
"""
tem que considerar a leverage na diferença de preço
"""
lev = 7
sl = 2 / lev
sl / 100
tp = 4 / 7
tp / 100
tp_price = f"{(price * (1+tp/100)):.2f}"
sl_price = f"{(price * (1-sl/100)):.2f}"
tp_price
sl_price
# %%

brm.futures_create_order(
    symbol="ETHUSDT",
    side="BUY",
    type="MARKET",
    quantity=0.002,
    workingType="MARK_PRICE",
)

# %%

brm.futures_create_order(
    symbol="ETHUSDT",
    side="SELL",
    type="STOP_MARKET",
    stopPrice=sl_price,
    workingType="MARK_PRICE",
    closePosition=True,
)

# %%

brm.futures_create_order(
    symbol="ETHUSDT",
    side="SELL",
    type="TAKE_PROFIT_MARKET",
    stopPrice=tp_price,
    workingType="MARK_PRICE",
    closePosition=True,
)


# %%

# listen_key = brm.stream_get_listen_key()
# user_stream_id = bwsm.create_stream('arr', '!userData', symbols="ethusdt", api_key=API_KEY, api_secret=API_SECRET, stream_buffer_name="user_stream")
# # %%
# user_stream_id
#
# # %%
# data_from_stream_buffer = bwsm.pop_stream_data_from_stream_buffer("user_stream")
# # %%
# data_from_stream_buffer

# %%

user_data = []
user_stream_name = "user_datastream"


def print_stream_user_data(bwsm):
    while True:

        if bwsm.is_manager_stopping():
            exit(0)

        data_from_stream_buffer = bwsm.pop_stream_data_from_stream_buffer(
            user_stream_name
        )

        if data_from_stream_buffer is False:
            time.sleep(0.01)
        else:

            try:
                # print(data_from_stream_buffer["event_type"])
                global user_data
                data.append(data_from_stream_buffer)
            except:
                print(data_from_stream_buffer)


# %%
user_stream_id = bwsm.create_stream(
    "arr",
    "!userData",
    symbols="ethusdt",
    api_key=API_KEY,
    api_secret=API_SECRET,
    stream_buffer_name="user_datastream",
)

# start a worker process to move the received stream_data from the stream_buffer to a print function
worker_thread = threading.Thread(target=print_stream_user_data, args=(bwsm,))
worker_thread.start()

# %%
user_data
# %%


# order_id = 8389765505256860493
# sym = "ETHUSDT"
# brm.futures_get_order(symbol=sym, orderId=8389765505256860493)
# brm.futures_get_open_orders(symbol=sym)
# brm.futures_create_order(
#     symbol="BNBUSDT",
#     side="SELL",
#     type="MARKET",
#     quantity=0.05,
#     price=450.10,
#     stopPrice=499.79,
#     workingType="MARK_PRICE",
# )

# %%
def futures_place_batch_order(self, **params):
    """Send in new orders.
    https://binance-docs.github.io/apidocs/delivery/en/#place-multiple-orders-trade
    To avoid modifying the existing signature generation and parameter order logic,
    the url encoding is done on the special query param, batchOrders, in the early stage.
    """
    query_string = urlencode(params)
    query_string = query_string.replace("%27", "%22")
    params["batchOrders"] = query_string[12:]
    return self._request_futures_api("post", "batchOrders", True, data=params)


# %%

brm

brm.futures_place_batch_order = futures_place_batch_order

# %%

from urllib.parse import urlencode
import json

# %%

# orders = json.dumps(batchOrders)
# orders
# # %%
#
# brm.futures_place_batch_order(brm, batchOrders=orders)

# %%


# %%
batchOrders = [
    {
        "symbol": "ETHUSDT",
        "side": "SELL",
        "type": "STOP_MARKET",
        "stopPrice": f"{(price * 0.9919):.2f}",
        "workingType": "MARK_PRICE",
        "closePosition": True,
    },
    {
        "symbol": "ETHUSDT",
        "side": "SELL",
        "type": "TAKE_PROFIT_MARKET",
        "stopPrice": f"{(price * 1.03):.2f}",
        "workingType": "MARK_PRICE",
        "closePosition": True,
    },
]


orders = json.dumps(batchOrders)

# %%

brm.futures_place_batch_order(brm, batchOrders=orders)

# %%


# %%
import hmac
import time
import hashlib
import requests
import json
from urllib.parse import urlencode

""" This is a very simple script working on Binance API

- work with USER_DATA endpoint with no third party dependency
- work with testnet

Provide the API key and secret, and it's ready to go

Because USER_DATA endpoints require signature:
- call `send_signed_request` for USER_DATA endpoints
- call `send_public_request` for public endpoints

```python

python futures.py

```

"""

KEY = API_KEY
SECRET = API_SECRET
BASE_URL = "https://fapi.binance.com"  # production base url
# BASE_URL = "https://testnet.binancefuture.com"  # testnet base url

""" ======  begin of functions, you don't need to touch ====== """


def hashing(query_string):
    return hmac.new(
        SECRET.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def get_timestamp():
    return int(time.time() * 1000)


def dispatch_request(http_method):
    session = requests.Session()
    session.headers.update(
        {"Content-Type": "application/json;charset=utf-8", "X-MBX-APIKEY": KEY}
    )
    return {
        "GET": session.get,
        "DELETE": session.delete,
        "PUT": session.put,
        "POST": session.post,
    }.get(http_method, "GET")


# used for sending request requires the signature
def send_signed_request(http_method, url_path, payload={}):
    query_string = urlencode(payload)
    # replace single quote to double quote
    query_string = query_string.replace("%27", "%22")
    if query_string:
        query_string = "{}&timestamp={}".format(query_string, get_timestamp())
    else:
        query_string = "timestamp={}".format(get_timestamp())

    url = (
        BASE_URL + url_path + "?" + query_string + "&signature=" + hashing(query_string)
    )
    print("{} {}".format(http_method, url))
    params = {"url": url, "params": {}}
    response = dispatch_request(http_method)(**params)
    return response.json()


# used for sending public data request
def send_public_request(url_path, payload={}):
    query_string = urlencode(payload, True)
    url = BASE_URL + url_path
    if query_string:
        url = url + "?" + query_string
    print("{}".format(url))
    response = dispatch_request("GET")(url=url)
    return response.json()


""" ======  end of functions ====== """

### public data endpoint, call send_public_request #####
# get klines
response = send_public_request(
    "/fapi/v1/klines", {"symbol": "BTCUSDT", "interval": "1d"}
)
print(response)


# get account informtion
# if you can see the account details, then the API key/secret is correct
response = send_signed_request("GET", "/fapi/v2/account")
print(response)


### USER_DATA endpoints, call send_signed_request #####
# place an order
# if you see order response, then the parameters setting is correct
# if it has response from server saying some parameter error, please adjust the parameters according the market.
params = {
    "symbol": "BNBUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "timeInForce": "GTC",
    "quantity": 1,
    "price": "15",
}
response = send_signed_request("POST", "/fapi/v1/order", params)
print(response)

# place batch orders
# if you see order response, then the parameters setting is correct
# if it has response from server saying some parameter error, please adjust the parameters according the market.

# %%

params = {
    "batchOrders": [
        {
            "symbol": "ETHUSDT",
            "side": "SELL",
            "type": "STOP_MARKET",
            "stopPrice": f"{(price * 0.9919):.2f}",
            "workingType": "MARK_PRICE",
            "closePosition": True,
        },
        {
            "symbol": "ETHUSDT",
            "side": "SELL",
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": f"{(price * 1.03):.2f}",
            "workingType": "MARK_PRICE",
            "closePosition": True,
        },
    ]
}

# %%
orders = json.dumps(params)

# %%

response = send_signed_request("POST", "/fapi/v1/batchOrders", params)
print(response)
