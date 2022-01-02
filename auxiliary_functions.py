import os
from unicorn_binance_rest_api import BinanceRestApiManager
from src import *

# %%


def make_client(new=True):
    key, secret = os.environ.get("API_KEY"), os.environ.get("API_SECRET")
    if not new:
        client = BinanceRestApiManager(api_key=key, api_secret=secret)
    else:
        client = BinanceRestApiManager(
            api_key=key, api_secret=secret, exchange="binance.com-futures"
        )
    return client, key, secret


def derivative(df, variable, length=1):
    return df[variable] - df[variable].shift(length)


def sec_derivative(df, variable, length=1):
    return (
        derivative(df, variable) - derivative(df.shift(length), variable, length=length)
    ) / 2


def force(df, length=1):
    # it's the same as ta.mom
    velocity = derivative(df, "close", length=length)
    acceleration = sec_derivative(df, "close", length=length)
    mass = df.volume
    mass_dot = derivative(df, "volume", length=length)
    F = mass_dot * velocity + mass * acceleration
    return F


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


def check_next_vals(df, target, n=5, tp=1):
    df[target] = 0
    closes = df.close
    for i, c in enumerate(closes):

        if np.all((c - closes[i + 1 :].head(n)) > 0):
            df[target].iloc[i] = 1
        elif np.all((c - closes[i + 1 :].head(n)) < 0):
            df[target].iloc[i] = -1


# %%


def check_next_vals_tp(df, target, n=7, tp=1):
    df[target] = 0
    closes = df.close
    for i, c_i in enumerate(closes):
        for c_j in closes[i + 1 :].head(n):
            if 100 * (c_j - c_i) / c_i >= tp:
                df[target].iloc[i] = 1
            elif 100 * (c_j - c_i) / c_i <= -tp:
                df[target].iloc[i] = -1
