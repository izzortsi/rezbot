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
from tensorflow import keras
import tensorflow as tf

# %%
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from tensorflow.keras import layers
from tensorflow.keras.layers.experimental import preprocessing

# %%

mpl.rcParams["figure.figsize"] = (8, 6)
mpl.rcParams["axes.grid"] = False
# %%
sym = "BNBUSDT"
tframe = "15m"
# %%
client, k, s = make_client(new=True)
# %%
grabber = DataGrabber(client)

# %%

candles_df = grabber.get_historical_data(
    symbol=sym, tframe=tframe, startTime="2 month ago", endTime="now", limit=2000
)

# %%
len(candles_df)
# %%


data = get_indicators(candles_df)

df = data
# %%

std_scaler = StandardScaler()
F_scaled = std_scaler.fit_transform(np.array(data.EMA_FORCE_15.array).reshape(-1, 1))
plt.plot(F_scaled)
plt.sbuplots()
plt.subplot(211).plot(F_scaled)
plt.subplot(211).plot(df.close)


def train_val_test(df):

    n = len(df)
    train_df = df[0 : int(n * 0.7)]
    val_df = df[int(n * 0.7) : int(n * 0.9)]
    test_df = df[int(n * 0.9) :]

    return train_df, val_df, test_df


def normalize_data(df, train_df, val_df, test_df):

    train_mean = train_df.mean()
    train_std = train_df.std()

    train_df = (train_df - train_mean) / train_std
    val_df = (val_df - train_mean) / train_std
    test_df = (test_df - train_mean) / train_std
    df_std = (df - train_mean) / train_std
    df_std = df_std.melt(var_name="Column", value_name="Normalized")

    return train_df, val_df, test_df, df_std


# %%


def check_next_vals(df, n=5, tp=1):
    df.label = 0
    closes = df.close
    for i, c in enumerate(closes):

        if np.all((c - closes[i + 1 :].head(n)) > 0):
            df.label.iloc[i] = 2
        elif np.all((c - closes[i + 1 :].head(n)) < 0):
            df.label.iloc[i] = 1


# %%


def check_next_vals_tp(df, n=7, tp=1):
    df.label = 0
    closes = df.close
    for i, c_i in enumerate(closes):
        for c_j in closes[i + 1 :].head(n):
            if 100 * (c_j - c_i) / c_i >= tp:
                df.label.iloc[i] = 2
            elif 100 * (c_j - c_i) / c_i <= -tp:
                df.label.iloc[i] = 1


# %%

candles_df["label"] = 0

check_next_vals_tp(candles_df)
candles_df.label.plot()
data["label"] = candles_df.label.astype(int)
# %%
data.label.plot()
# %%
train, val, test = train_val_test(data)
ntrain, nval, ntest, dfstd = normalize_data(
    data.drop("label", axis=1),
    train.drop("label", axis=1),
    val.drop("label", axis=1),
    test.drop("label", axis=1),
)
# %%
ntrain["label"] = train.label
nval["label"] = val.label
ntest["label"] = test.label
# %%
_, wide_window, w_gen = common_windows(ntrain, nval, ntest, ["label"])

# %%
num_classes = 3
window = w_gen(input_width=12, label_width=1, shift=1)
window.example[0].shape
# %%

model_ = tf.keras.Sequential(
    [
        tf.keras.layers.Conv1D(filters=64, kernel_size=3),
        tf.keras.layers.ReLU(),
        tf.keras.layers.Conv1D(filters=64, kernel_size=3),
        tf.keras.layers.ReLU(),
        tf.keras.layers.Conv1D(filters=64, kernel_size=3),
        tf.keras.layers.ReLU(),
        tf.keras.layers.GlobalAveragePooling1D(),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ]
)

model = tf.keras.Sequential(
    [
        tf.keras.layers.Conv1D(filters=64, kernel_size=3),
        tf.keras.layers.ReLU(),
        tf.keras.layers.Conv1D(filters=64, kernel_size=3),
        tf.keras.layers.ReLU(),
        tf.keras.layers.GlobalAveragePooling1D(),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ]
)
epochs = 100
batch_size = 32
# %%

callbacks = [
    keras.callbacks.ModelCheckpoint(
        "best_model.h5", save_best_only=True, monitor="val_loss"
    ),
    keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=20, min_lr=0.0001
    ),
    keras.callbacks.EarlyStopping(monitor="val_loss", patience=50, verbose=1),
]
# %%

model.compile(
    optimizer="adam",
    loss="sparse_categorical_crossentropy",
    metrics=["sparse_categorical_accuracy"],
)
# %%

history = model.fit(
    window.train,
    epochs=epochs,
    callbacks=callbacks,
    validation_data=window.val,
    verbose=1,
)
# %%

# %%
model.evaluate(window.val)
model.evaluate(window.test)
window.plot(model)

# %%
to_predict = tf.convert_to_tensor(window.test_df.drop("label", axis=1).iloc[0:32])
# %%


model.predict(to_predict)
