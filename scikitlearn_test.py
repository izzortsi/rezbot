from sklearn.gaussian_process.kernels import RBF
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import minmax_scale, StandardScaler
from sklearn.neural_network import MLPClassifier
from src.grabber import DataGrabber
from unicorn_binance_rest_api import BinanceRestApiManager
from auxiliary_functions import *
from src import *
from get_indicators import *
from window_generator import *

# %%
import os
import datetime

import IPython
import IPython.display
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# %%

mpl.rcParams["figure.figsize"] = (12, 10)
mpl.rcParams["axes.grid"] = False
# %%
sym = "BNBUSDT"
tframe = "15m"
# %%
client, k, s = make_client(new=True)
# %%
grabber = DataGrabber(client)

# %%

klines = grabber.get_historical_data(
    symbol=sym, tframe=tframe, startTime="2 month ago", endTime="now", limit=2000
)

# %%

# %%

len(klines)
# %%


data = get_indicators(klines)

df = data

check_next_vals(klines, "label")
klines[["close", "label"]].plot(subplots=True)
# %%
y = np.array(klines.label.tail(967))
y += 1
# %%
X = np.array(data)
X

# %%
len(X)
len(y)
# %%

# %%
X = np.asarray(X, "float32")
scaler = StandardScaler()
X = scaler.fit_transform(X)
# %%
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, shuffle=True)
# %%
rbfsvm = SVC(gamma=2, C=1)

rbfgp = GaussianProcessClassifier(1.0 * RBF(1.0))
# Training
rbfsvm.fit(X_train, y_train)
rbfgp.fit(X_train, y_train)
# %%

print("Training set score: %f" % rbfsvm.score(X_train, y_train))
print("Test set score: %f" % rbfsvm.score(X_test, y_test))
Y_pred = rbfsvm.predict(X_test)
plt.plot(Y_test)
plt.plot(Y_pred)
# %%

print("Training set score: %f" % rbfgp.score(X_train, y_train))
print("Test set score: %f" % rbfgp.score(X_test, y_test))
Y_pred = rbfgp.predict(X_test)
plt.plot(Y_test)
plt.plot(Y_pred)
