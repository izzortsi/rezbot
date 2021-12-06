# %%

from src import *
from src.threaded_manager import ThreadedManager
from src.threaded_atrader import ThreadedATrader
from src.strategy import * #MacdStrategy, TrendReversalStrategy
import argparse

# %%
parser = argparse.ArgumentParser()
parser.add_argument("-r", "--rate", default=1, type=int)
parser.add_argument("-sl", "--stoploss", default=-0.2, type=float)
parser.add_argument("-tp", "--takeprofit", default=6, type=float)
parser.add_argument("-ew", "--entry_window", default=1, type=int)
parser.add_argument("-xw", "--exit_window", default=0, type=int)
parser.add_argument("-L", "--leverage", default=5, type=int)
parser.add_argument("-R", "--is_real", default=False, type=bool)
parser.add_argument("-Q", "--qty", default=1, type=float)
parser.add_argument("-S", "--symbol", default="sandusdt", type=str)
parser.add_argument("-tf", "--timeframe", default="30m", type=str)
parser.add_argument("-s", "--strategy", default=1, type=int)
parser.add_argument("-w1", "--window_1", default=5, type=int)
parser.add_argument("-m1", "--multiplier_1", default=1.2, type=float)
args = parser.parse_args()

rate = args.rate
tp = args.takeprofit
sl = args.stoploss
leverage = args.leverage
ew = args.entry_window
xw = args.exit_window
is_real = args.is_real
qty = args.qty
symbol = args.symbol
tf = args.timeframe
strategy = args.strategy
m1 = args.multiplier_1
w1 = args.window_1
# %%

# from src.grabber import *
# from src.strategy import *
if __name__ == "__main__":

    m = ThreadedManager(
        API_KEY,
        API_SECRET,
        tf=tf,
        rate=rate,
    )

    # macd_params = {"fast": 7, "slow": 14, "signal": 5}
    if strategy == 1:
        strategy_params = ["pullback", tf, tp, sl, ew, xw]
        strat = PullbackStrategy(*strategy_params)
    elif strategy == 2:
        strategy_params = ["pullback_reversal", tf, tp, sl, ew, xw]
        strat = PullbackReversalStrategy(*strategy_params)      
    elif strategy == 3:
        strategy_params = ["volatility", tf, tp, sl, ew, xw]
        strat = VolatilityStrategy(*strategy_params)
    # %%

    symbols = ["ethusdt", "bnbusdt", "btcusdt", "adausdt", "axsusdt", "dotusdt"]

    # %%
    t = m.start_trader(strat, symbol, leverage=leverage, is_real=is_real, qty=qty, w1 = w1, m1=m1)
    # t1 = m.start_trader(strat, symbols[1], leverage=leverage, is_real=is_real, qty=qty)
    # t2 = m.start_trader(strat, symbols[2], leverage=leverage, is_real=is_real, qty=qty)
    # t3 = m.start_trader(strat, symbols[3], leverage=leverage, is_real=is_real, qty=qty)
    # if symbol != "":
    #     t4 = m.start_trader(strat, symbol, leverage=leverage, is_real=is_real, qty=qty)
# %%
# rate = 60
# m = ThreadedManager(API_KEY, API_SECRET, rate=rate)
# # %%
# symbols = ["ethusdt", "bnbusdt", "btcusdt", "xrpusdt"]
# strategy_params = ["macd", "1m", 1.5, -0.2, 3, 0]
# strat = TAStrategy(*strategy_params)
# # tp = args.takeprofit
# # sl = args.stoploss
# leverage = 50
# # ew = args.entry_window
# # xw = args.exit_window
# is_real = False
# # %%

# t1 = m.start_trader(
#     strat, symbols[0], leverage=leverage, is_real=is_real)
# # %%

# t2 = m.start_trader(
#     strat, symbols[1], leverage=leverage, is_real=is_real)
# # %%
