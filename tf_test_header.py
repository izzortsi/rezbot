from src.grabber import DataGrabber
from unicorn_binance_rest_api import BinanceRestApiManager
from auxiliary_functions import *
from src import *
from get_indicators import *

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
import tensorflow as tf
from window_generator import *

# %%

mpl.rcParams["figure.figsize"] = (8, 6)
mpl.rcParams["axes.grid"] = False
# %%
sym = "BNBUSDT"
tframe = "15m"
FEATURE = "close"
# %%

client, k, s = make_client(new=True)
grabber = DataGrabber(client)
# %%

candles_df = grabber.get_historical_data(
    symbol=sym, tframe=tframe, startTime="2 month ago", endTime="now", limit=2000
)

len(candles_df)
# %%

df = get_indicators(candles_df)
# %%


# %%
column_indices = {name: i for i, name in enumerate(df.columns)}
num_features = df.shape[1]


def train_val_test(df):

    n = len(df)
    train_df = df[0 : int(n * 0.7)]
    val_df = df[int(n * 0.7) : int(n * 0.9)]
    test_df = df[int(n * 0.9) :]

    return train_df, val_df, test_df


# %%
train_df, val_df, test_df = train_val_test(df)
# %%


def normalize_data(train_df, val_df, test_df):

    train_mean = train_df.mean()
    train_std = train_df.std()

    train_df = (train_df - train_mean) / train_std
    val_df = (val_df - train_mean) / train_std
    test_df = (test_df - train_mean) / train_std
    df_std = (df - train_mean) / train_std
    df_std = df_std.melt(var_name="Column", value_name="Normalized")

    return train_df, val_df, test_df, df_std


# %%
train_df, val_df, test_df, df_std = normalize_data(train_df, val_df, test_df)

# %%
plt.figure(figsize=(12, 6))
ax = sns.violinplot(x="Column", y="Normalized", data=df_std)
_ = ax.set_xticklabels(df.keys(), rotation=90)

# %%


# def default_generator(train_df, val_df, test_df):
#     return lambda input_width, label_width, shift: WindowGenerator(
#         input_width,
#         label_width,
#         shift,
#         train_df,
#         val_df,
#         test_df,
#         label_columns=[FEATURE],
#     )


# %%
w_gen = default_generator(train_df, val_df, test_df, [FEATURE])
# %%

single_step_window = w_gen(input_width=1, label_width=1, shift=1)
single_step_window
# %%
wide_window = w_gen(input_width=24, label_width=24, shift=1)
wide_window
# %%

MAX_EPOCHS = 50


def compile_and_fit(model, window, patience=2):
    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=patience, mode="min"
    )

    model.compile(
        loss=tf.losses.MeanSquaredError(),
        optimizer=tf.optimizers.Adam(),
        metrics=[tf.metrics.MeanAbsoluteError()],
    )

    history = model.fit(
        window.train,
        epochs=MAX_EPOCHS,
        validation_data=window.val,
        callbacks=[early_stopping],
    )
    return history


# %%


class Baseline(tf.keras.Model):
    def __init__(self, label_index=None):
        super().__init__()
        self.label_index = label_index

    def call(self, inputs):
        if self.label_index is None:
            return inputs
        result = inputs[:, :, self.label_index]
        return result[:, :, tf.newaxis]


baseline = Baseline(label_index=column_indices[f"{FEATURE}"])

baseline.compile(
    loss=tf.losses.MeanSquaredError(), metrics=[tf.metrics.MeanAbsoluteError()]
)

val_performance = {}
performance = {}
val_performance["Baseline"] = baseline.evaluate(single_step_window.val)
performance["Baseline"] = baseline.evaluate(single_step_window.test, verbose=0)

# %%
linear = tf.keras.Sequential([tf.keras.layers.Dense(units=1)])
# %%

history = compile_and_fit(linear, single_step_window)

val_performance["Linear"] = linear.evaluate(single_step_window.val)
performance["Linear"] = linear.evaluate(single_step_window.test, verbose=0)

wide_window.plot(linear)

# %%
plt.bar(x=range(len(train_df.columns)), height=linear.layers[0].kernel[:, 0].numpy())
axis = plt.gca()
axis.set_xticks(range(len(train_df.columns)))
_ = axis.set_xticklabels(train_df.columns, rotation=90)
# %%

dense = tf.keras.Sequential(
    [
        tf.keras.layers.Dense(units=64, activation="relu"),
        tf.keras.layers.Dense(units=64, activation="relu"),
        tf.keras.layers.Dense(units=1),
    ]
)

history = compile_and_fit(dense, single_step_window)

val_performance["Dense"] = dense.evaluate(single_step_window.val)
performance["Dense"] = dense.evaluate(single_step_window.test, verbose=0)
# %%
wide_window.plot(dense)
# %%
CONV_WIDTH = 3
conv_window = w_gen(input_width=CONV_WIDTH, label_width=1, shift=1)

conv_window
# %%
multi_step_dense = tf.keras.Sequential(
    [
        # Shape: (time, features) => (time*features)
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(units=32, activation="relu"),
        tf.keras.layers.Dense(units=32, activation="relu"),
        tf.keras.layers.Dense(units=1),
        # Add back the time dimension.
        # Shape: (outputs) => (1, outputs)
        tf.keras.layers.Reshape([1, -1]),
    ]
)
# %%
history = compile_and_fit(multi_step_dense, conv_window)

IPython.display.clear_output()
val_performance["Multi step dense"] = multi_step_dense.evaluate(conv_window.val)
performance["Multi step dense"] = multi_step_dense.evaluate(conv_window.test, verbose=0)
# %%

conv_window.plot(multi_step_dense)
# %%
conv_model = tf.keras.Sequential(
    [
        tf.keras.layers.Conv1D(
            filters=32, kernel_size=(CONV_WIDTH,), activation="relu"
        ),
        tf.keras.layers.Dense(units=32, activation="relu"),
        tf.keras.layers.Dense(units=1),
    ]
)
# %%
history = compile_and_fit(conv_model, conv_window)

IPython.display.clear_output()
val_performance["Conv"] = conv_model.evaluate(conv_window.val)
performance["Conv"] = conv_model.evaluate(conv_window.test, verbose=0)
# %%
LABEL_WIDTH = 24
INPUT_WIDTH = LABEL_WIDTH + (CONV_WIDTH - 1)
wide_conv_window = w_gen(
    input_width=INPUT_WIDTH,
    label_width=LABEL_WIDTH,
    shift=1,
)

wide_conv_window
# %%
wide_conv_window.plot(conv_model)
# %%
lstm_model = tf.keras.models.Sequential(
    [
        # Shape [batch, time, features] => [batch, time, lstm_units]
        tf.keras.layers.LSTM(32, return_sequences=True),
        # Shape => [batch, time, features]
        tf.keras.layers.Dense(units=1),
    ]
)
# %%
history = compile_and_fit(lstm_model, wide_window)

IPython.display.clear_output()
val_performance["LSTM"] = lstm_model.evaluate(wide_window.val)
performance["LSTM"] = lstm_model.evaluate(wide_window.test, verbose=0)
# %%
wide_window.plot(lstm_model)

# %%

x = np.arange(len(performance))
width = 0.3
metric_name = "mean_absolute_error"
metric_index = lstm_model.metrics_names.index("mean_absolute_error")
val_mae = [v[metric_index] for v in val_performance.values()]
test_mae = [v[metric_index] for v in performance.values()]

plt.ylabel("mean_absolute_error [T (degC), normalized]")
plt.bar(x - 0.17, val_mae, width, label="Validation")
plt.bar(x + 0.17, test_mae, width, label="Test")
plt.xticks(ticks=x, labels=performance.keys(), rotation=45)
_ = plt.legend()
# %%

for name, value in performance.items():
    print(f"{name:12s}: {value[1]:0.4f}")
# %%


class ResidualWrapper(tf.keras.Model):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def call(self, inputs, *args, **kwargs):
        delta = self.model(inputs, *args, **kwargs)

        # The prediction for each time step is the input
        # from the previous time step plus the delta
        # calculated by the model.
        return inputs + delta


# %%

residual_lstm = ResidualWrapper(
    tf.keras.Sequential(
        [
            tf.keras.layers.LSTM(32, return_sequences=True),
            tf.keras.layers.Dense(
                num_features,
                # The predicted deltas should start small.
                # Therefore, initialize the output layer with zeros.
                kernel_initializer=tf.initializers.zeros(),
            ),
        ]
    )
)
# %%

history = compile_and_fit(residual_lstm, wide_window)

IPython.display.clear_output()
val_performance["Residual LSTM"] = residual_lstm.evaluate(wide_window.val)
performance["Residual LSTM"] = residual_lstm.evaluate(wide_window.test, verbose=0)
# %%
wide_window.plot(residual_lstm)

# %%

OUT_STEPS = 3
multi_window = w_gen(input_width=24, label_width=OUT_STEPS, shift=OUT_STEPS)

multi_window.plot()
multi_window

# %%


class MultistepRepeatBaseline(tf.keras.Model):
    def __init__(self, label_index=None):
        super().__init__()
        self.label_index = label_index

    def call(self, inputs):
        if self.label_index is None:
            return inputs
        result = inputs[:, -(OUT_STEPS):, self.label_index]
        return result[:, :, tf.newaxis]


# %%

msr_baseline = MultistepRepeatBaseline(label_index=column_indices["close"])


msr_baseline.compile(
    loss=tf.losses.MeanSquaredError(), metrics=[tf.metrics.MeanAbsoluteError()]
)


val_performance = {}
performance = {}
val_performance["MultistepRepeatBaseline"] = msr_baseline.evaluate(multi_window.val)
performance["MultistepRepeatBaseline"] = msr_baseline.evaluate(
    multi_window.test, verbose=0
)

# %%
multi_window.plot(msr_baseline)
# %%


class MultistepRepeatLastBaseline(tf.keras.Model):
    def __init__(self, label_index=None):
        super().__init__()
        self.label_index = label_index

    def call(self, inputs):
        if self.label_index is None:
            return inputs
        result = inputs[:, -1:, self.label_index]
        return tf.tile(result[:, :, tf.newaxis], [1, OUT_STEPS, 1])


msrl_baseline = MultistepRepeatLastBaseline(label_index=column_indices["close"])


msrl_baseline.compile(
    loss=tf.losses.MeanSquaredError(), metrics=[tf.metrics.MeanAbsoluteError()]
)
# %%


val_performance = {}
performance = {}
val_performance["MultistepRepeatLastBaseline"] = msrl_baseline.evaluate(
    multi_window.val
)
performance["MultistepRepeatLastBaseline"] = msrl_baseline.evaluate(
    multi_window.test, verbose=0
)

# %%
multi_window.plot(msrl_baseline)
# %%
multi_linear_model = tf.keras.Sequential(
    [
        # Take the last time-step.
        # Shape [batch, time, features] => [batch, 1, features]
        tf.keras.layers.Lambda(lambda x: x[:, -1:, :]),
        # Shape => [batch, 1, out_steps*features]
        tf.keras.layers.Dense(
            OUT_STEPS * num_features, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features]
        tf.keras.layers.Reshape([OUT_STEPS, num_features]),
    ]
)
# %%

history = compile_and_fit(multi_linear_model, multi_window)

IPython.display.clear_output()
multi_val_performance["Linear"] = multi_linear_model.evaluate(multi_window.val)
multi_performance["Linear"] = multi_linear_model.evaluate(multi_window.test, verbose=0)
multi_window.plot(multi_linear_model)
# %%
multi_dense_model = tf.keras.Sequential(
    [
        # Take the last time step.
        # Shape [batch, time, features] => [batch, 1, features]
        tf.keras.layers.Lambda(lambda x: x[:, -1:, :]),
        # Shape => [batch, 1, dense_units]
        tf.keras.layers.Dense(512, activation="relu"),
        # Shape => [batch, out_steps*features]
        tf.keras.layers.Dense(
            OUT_STEPS * num_features, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features]
        tf.keras.layers.Reshape([OUT_STEPS, num_features]),
    ]
)
# %%

history = compile_and_fit(multi_dense_model, multi_window)

IPython.display.clear_output()
multi_val_performance["Dense"] = multi_dense_model.evaluate(multi_window.val)
multi_performance["Dense"] = multi_dense_model.evaluate(multi_window.test, verbose=0)
multi_window.plot(multi_dense_model)
# %%
CONV_WIDTH = 3
multi_conv_model = tf.keras.Sequential(
    [
        # Shape [batch, time, features] => [batch, CONV_WIDTH, features]
        tf.keras.layers.Lambda(lambda x: x[:, -CONV_WIDTH:, :]),
        # Shape => [batch, 1, conv_units]
        tf.keras.layers.Conv1D(256, activation="relu", kernel_size=(CONV_WIDTH)),
        # Shape => [batch, 1,  out_steps*features]
        tf.keras.layers.Dense(
            OUT_STEPS * num_features, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features]
        tf.keras.layers.Reshape([OUT_STEPS, num_features]),
    ]
)
# %%

history = compile_and_fit(multi_conv_model, multi_window)

IPython.display.clear_output()

multi_val_performance["Conv"] = multi_conv_model.evaluate(multi_window.val)
multi_performance["Conv"] = multi_conv_model.evaluate(multi_window.test, verbose=0)
multi_window.plot(multi_conv_model)
# %%
multi_lstm_model = tf.keras.Sequential(
    [
        # Shape [batch, time, features] => [batch, lstm_units].
        # Adding more `lstm_units` just overfits more quickly.
        tf.keras.layers.LSTM(32, return_sequences=False),
        # Shape => [batch, out_steps*features].
        tf.keras.layers.Dense(
            OUT_STEPS * num_features, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features].
        tf.keras.layers.Reshape([OUT_STEPS, num_features]),
    ]
)
# %%

history = compile_and_fit(multi_lstm_model, multi_window)

IPython.display.clear_output()

multi_val_performance["LSTM"] = multi_lstm_model.evaluate(multi_window.val)
multi_performance["LSTM"] = multi_lstm_model.evaluate(multi_window.test, verbose=0)
multi_window.plot(multi_lstm_model)
# %%


class FeedBack(tf.keras.Model):
    def __init__(self, units, out_steps):
        super().__init__()
        self.out_steps = out_steps
        self.units = units
        self.lstm_cell = tf.keras.layers.LSTMCell(units)
        # Also wrap the LSTMCell in an RNN to simplify the `warmup` method.
        self.lstm_rnn = tf.keras.layers.RNN(self.lstm_cell, return_state=True)
        self.dense = tf.keras.layers.Dense(num_features)


feedback_model = FeedBack(units=32, out_steps=OUT_STEPS)
# %%


def warmup(self, inputs):
    # inputs.shape => (batch, time, features)
    # x.shape => (batch, lstm_units)
    x, *state = self.lstm_rnn(inputs)

    # predictions.shape => (batch, features)
    prediction = self.dense(x)
    return prediction, state


FeedBack.warmup = warmup
# %%
prediction, state = feedback_model.warmup(multi_window.example[0])
prediction.shape
# %%


def call(self, inputs, training=None):
    # Use a TensorArray to capture dynamically unrolled outputs.
    predictions = []
    # Initialize the LSTM state.
    prediction, state = self.warmup(inputs)

    # Insert the first prediction.
    predictions.append(prediction)

    # Run the rest of the prediction steps.
    for n in range(1, self.out_steps):
        # Use the last prediction as input.
        x = prediction
        # Execute one lstm step.
        x, state = self.lstm_cell(x, states=state, training=training)
        # Convert the lstm output to a prediction.
        prediction = self.dense(x)
        # Add the prediction to the output.
        predictions.append(prediction)

    # predictions.shape => (time, batch, features)
    predictions = tf.stack(predictions)
    # predictions.shape => (batch, time, features)
    predictions = tf.transpose(predictions, [1, 0, 2])
    return predictions


FeedBack.call = call
# %%


history = compile_and_fit(feedback_model, multi_window)

IPython.display.clear_output()
multi_val_performance["AR LSTM"] = feedback_model.evaluate(multi_window.val)
multi_performance["AR LSTM"] = feedback_model.evaluate(multi_window.test, verbose=0)
multi_window.plot(feedback_model)
