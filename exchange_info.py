import json


# %%
with open("exchangeInfo.json") as f:
    data = json.load(f)

# %%
symbols_dict = {}
symbols_filters = {}

# %%
data["symbols"][0]["filters"][0]
# %%

for symbol_data in data["symbols"]:
    if symbol_data["contractType"] == "PERPETUAL" and (
        symbol_data["quoteAsset"] == "USDT" or symbol_data["quoteAsset"] == "BUSD"
    ):

        symbol = symbol_data["symbol"]
        symbols_dict[symbol] = symbol_data
        ticksize = len(str(float(symbol_data["filters"][0]["tickSize"])).split(".")[-1])
        print(
            symbol,
            float(symbol_data["filters"][0]["tickSize"]),
            symbol_data["pricePrecision"],
            ticksize,
        )
        symbols_filters[symbol] = {
            "pricePrecision": symbol_data["pricePrecision"],
            "quantityPrecision": symbol_data["quantityPrecision"],
            "tickSize": ticksize,
        }


# %%
len(symbols_dict)
len(data["symbols"])

# %%
with open("symbols_data.txt", "w") as json_file:
    json.dump(symbols_dict, json_file)


# %%

with open("symbols_filters.txt", "w") as json_file:
    json.dump(symbols_filters, json_file)
