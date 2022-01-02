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

mpl.rcParams["figure.figsize"] = (12, 8)
mpl.rcParams["axes.grid"] = False

# %%

m = Manager(API_KEY, API_SECRET, rate=1)
# %%

grabber = DataGrabber(m.client)
# %%
df = grabber.get_data()
# %%
p1, p2, p3 = 3, 7, 13
lengths = [p1, p2, p3]


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


# %%
macd = df.ta.macd()
macd = macd.MACDh_12_26_9


# %%
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


def l_force(length):
    return force(df, length=length)


# %%


indicators_list = each_indicator(
    [df.ta.cmf, df.ta.cti, df.ta.stdev, df.ta.inertia, l_force]
)

indicators_list
# %%
cmfs = each_period(df.ta.cmf)
ctis = each_period(df.ta.cti)
stdevs = each_period(df.ta.stdev, lengths=[6, 14, 26])
inertias = each_period(df.ta.inertia)
# %%


# %%


def blabla(length):
    return force(df, length=length)


f1.name

blabla(length=13)
# %%
# f_1 = force(df)
# f1 = force(df)
# f1.plot()
# f2 = force(df, length=7)
# f2.plot()
# f3 = force(df, length=13)
# f3.plot()
# plt.subplots()
# plt.subplot(f)
# df.plot(subplots=True)

indicators = pd.concat([*indicators_list, macd, df.close], axis=1)

indicators.dropna()


indicators.plot(subplots=True)
