# %%

from src import *
from src.manager import Manager
from src.atrader import ATrader
from src.strategy import *
import argparse

# %%
parser = argparse.ArgumentParser()
parser.add_argument("-s", "--symbol", default="ethusdt", type=str)
parser.add_argument("-tf", "--timeframe", default="1m", type=str)
parser.add_argument("-r", "--rate", default=1, type=int)
parser.add_argument("-sl", "--stoploss", default=-0.2, type=float)
parser.add_argument("-tp", "--takeprofit", default=1.5, type=float)
parser.add_argument("-ew", "--entry_window", default=2, type=int)
parser.add_argument("-xw", "--exit_window", default=1, type=int)
parser.add_argument("-S", "--strategy", default=1, type=int)
parser.add_argument("-L", "--leverage", default=1, type=int)
parser.add_argument("-R", "--is_real", default=False, type=bool)
parser.add_argument("-Q", "--qty", default="0.002", type=str)
args = parser.parse_args()

strategy = args.strategy
symbol = args.symbol
timeframe = args.timeframe
rate = args.rate
tp = args.takeprofit
sl = args.stoploss
leverage = args.leverage
ew = args.entry_window
xw = args.exit_window
is_real = args.is_real
qty = args.qty
# %%

# from src.grabber import *
# from src.strategy import *
if __name__ == "__main__":

    m = Manager(API_KEY, API_SECRET, rate=rate)

    # params = {"fast": 7, "slow": 14, "signal": 5}

    # strategy1 = Strategy("macd", "ethusdt", "1m", -0.33, 3.5, 2, 2, macd_params=params)
    # strategy2 = Strategy("macd", "bnbusdt", "1m", -0.33, 3.5, 2, 2, macd_params=params)
    # strategy_params = ["macd", "1m", -0.2, 1.5, 2, 1]
    strategy_params = ["macd", timeframe, sl, tp, ew, xw]
    if strategy == 1:
        strat = Strategy1(*strategy_params)
    elif strategy == 2:
        strat = Strategy2(*strategy_params)
    elif strategy == 3:
        strat = Strategy3(*strategy_params)
    # strategy2 = Strategy("macd", "1m", -0.2, 1.5, 2, 1)
    # strategy3 = Strategy("macd", "1m", -0.2, 1.5, 2, 1)

    # %%

    symbols = ["ethusdt", "bnbusdt", "btcusdt"]

    # %%

    t1 = m.start_trader(strat, symbols[0], leverage=leverage)
    t2 = m.start_trader(strat, symbols[1], leverage=leverage)
    # t3 = m.start_trader(strat, syms[2], leverage=leverage)

# %%
