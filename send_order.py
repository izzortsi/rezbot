position = brm.futures_position_information(symbol=symbol)
price = float(position[0]["entryPrice"])
qty = position[0]["positionAmt"]
# tp_price = f_tp_price(price, tp, lev, side=side)
# sl_price = f_sl_price(price, sl, lev, side=side)
tp_price = compute_exit(price, 0.5, side="BUY", exit_fee=0.02)
tp_price = f_price(tp_price)
print(
    f"""price: {price}
        tp_price: {tp_price}
        qty: {qty}
        """
)
# %%

tp_order = brm.futures_create_order(
    symbol="BNBUSDT",
    side="SELL",
    type="LIMIT",
    price=tp_price,
    workingType="CONTRACT_PRICE",
    quantity=qty,
    reduceOnly=True,
    priceProtect=False,
    timeInForce="GTC",
)


sl_price = compute_exit(price, 0.14, side="SELL", exit_fee=0.02)
# %%
100 * (sl_price - price) / price
# %%

sl_price = f_price(sl_price)
# %%

sl_price

# %%

sl_order = brm.futures_create_order(
    symbol="BNBUSDT",
    side="SELL",
    type="LIMIT",
    price=sl_price,
    workingType="CONTRACT_PRICE",
    quantity=qty,
    reduceOnly=True,
    priceProtect=False,
    timeInForce="GTC",
)
# %%
(0.02 * 499.83) * 0.0004


def send_order(tp, qty, side="BUY", protect=False):
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
        qty = position[0]["positionAmt"]
        # tp_price = f_tp_price(price, tp, lev, side=side)
        # sl_price = f_sl_price(price, sl, lev, side=side)
        tp_price = compute_exit(price, tp, side=counterside, exit_fee=0.02)

        print(
            f"""price: {price}
                  tp_price: {tp_price}
                  """
        )

        try:
            tp_order = brm.futures_create_order(
                symbol=symbol,
                side=counterside,
                type="LIMIT",
                price=tp_price,
                workingType="CONTRACT_PRICE",
                quantity=qty,
                reduceOnly=True,
                priceProtect=protect,
                timeInForce="GTC",
            )
        except BinanceAPIException as error:
            print(type(error))
            print("tp order, ", error)
        else:
            return position, tp_order
