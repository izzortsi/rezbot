# %%

import matplotlib as mpl
import matplotlib.pyplot as plt
from src import *
from src.manager import Manager
from src.atrader import ATrader
from src.grabber import DataGrabber
from src.strategy import *
import numpy as np
import pandas_ta as ta

# %%


def derivative(df, variable, length=1):
    return df[variable] - df[variable].shift(length)


def sec_derivative(df, variable, length=1):
    return (
        derivative(df, variable) - derivative(df.shift(length), variable, length=length)
    ) / 2


# %%


def force(df, length=1, is_smoothed=True):
    # it's the same as ta.mom
    velocity = derivative(df, "close", length=length)
    acceleration = sec_derivative(df, "close", length=length)
    mass = df.volume
    mass_dot = derivative(df, "volume", length=length)
    F = mass_dot * velocity + mass * acceleration
    if is_smoothed:
        F = ta.ema(F, length=length + 2)
        F.name = f"EMA_FORCE_{length+2}"
        return F
    F.name = f"FORCE_{length}"
    return F


def each_period(ta_fun, lengths=[3, 7, 13]):
    series = []
    for length in lengths:
        series.append(ta_fun(length=length))
    return series


def each_indicator(ta_funs, lengths=[3, 7, 13]):
    series = []
    for ta_fun in ta_funs:
        series += each_period(ta_fun, lengths=lengths)
    return series


# %%
def get_indicators(df):
    def l_force(length):
        return force(df, length=length)

    indicators_list = []

    macd = df.ta.macd()
    macd = macd.MACDh_12_26_9
    indicators_list.append(macd)
    # indicators_list = each_indicator(
    #     [df.ta.cmf, df.ta.cti, df.ta.stdev, df.ta.inertia, l_force]
    # )

    indicators_list += each_period(df.ta.cmf)
    indicators_list += each_period(df.ta.cti)
    indicators_list += each_period(df.ta.stdev, lengths=[6, 14, 26])
    indicators_list += each_period(df.ta.inertia, lengths=[3, 14])
    indicators_list += each_period(l_force)

    indicators = pd.concat([*indicators_list, df.close], axis=1).dropna()

    return indicators
