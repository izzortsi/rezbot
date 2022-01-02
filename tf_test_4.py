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
import tensorflow as tf

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

# %%
data


# data.index = range(0, 1000-33)
df = data

# %%
column_indices = {name: i for i, name in enumerate(df.columns)}
num_features = df.shape[1]
# %%

train_df, val_df, test_df = train_val_test(df)
train_df, val_df, test_df, df_std = normalize_data(df, train_df, val_df, test_df)

# %%
plt.figure(figsize=(12, 6))
ax = sns.violinplot(x="Column", y="Normalized", data=df_std)
_ = ax.set_xticklabels(df.keys(), rotation=90)


# %%
FEATURE = "close"
MAX_EPOCHS = 100


single_step_window, wide_window, w_gen = common_windows(
    train_df, val_df, test_df, ["close"]
)


# %%
for example_inputs, example_labels in single_step_window.train.take(1):
    print(f"Inputs shape (batch, time, features): {example_inputs.shape}")
    print(f"Labels shape (batch, time, features): {example_labels.shape}")


# %%
class Baseline(tf.keras.Model):
    def __init__(self, label_index=None):
        super().__init__()
        self.label_index = label_index

    def call(self, inputs):
        if self.label_index is None:
            return inputs
        result = inputs[:, :, self.label_index]
        print(result)
        return result[:, :, tf.newaxis]


# %%
baseline = Baseline(label_index=column_indices["close"])


baseline.compile(
    loss=tf.losses.MeanSquaredError(), metrics=[tf.metrics.MeanAbsoluteError()]
)


val_performance = {}
performance = {}
val_performance["Baseline"] = baseline.evaluate(single_step_window.val)
performance["Baseline"] = baseline.evaluate(single_step_window.test, verbose=0)


# %%
single_step_window.val

# %%

wide_window

# %%
print("Input shape:", wide_window.example[0].shape)
print("Output shape:", baseline(wide_window.example[0]).shape)
wide_window.plot(baseline)

# %%
"""LINEAR MODEL"""

linear = tf.keras.Sequential([tf.keras.layers.Dense(units=1)])
print("Input shape:", single_step_window.example[0].shape)
print("Output shape:", linear(single_step_window.example[0]).shape)
# %%

# %%


history = compile_and_fit(linear, single_step_window)

val_performance["Linear"] = linear.evaluate(single_step_window.val)
performance["Linear"] = linear.evaluate(single_step_window.test, verbose=0)

# %%
print("Input shape:", wide_window.example[0].shape)
print("Output shape:", baseline(wide_window.example[0]).shape)
wide_window.plot(linear)

# %%

plt.bar(x=range(len(train_df.columns)), height=linear.layers[0].kernel[:, 0].numpy())
axis = plt.gca()
axis.set_xticks(range(len(train_df.columns)))
_ = axis.set_xticklabels(train_df.columns, rotation=90)
# %%
"""DENSE"""
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
"MULTISTEP DENSE"
CONV_WIDTH = 12
OUT_WIDTH = 1
conv_window = w_gen(input_width=CONV_WIDTH, label_width=OUT_WIDTH, shift=OUT_WIDTH)

conv_window


conv_window.plot()
plt.title(f"Given {CONV_WIDTH} x {tframe} of inputs, predict {tframe} into the future.")

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
        tf.keras.layers.Reshape([OUT_WIDTH, -1]),
    ]
)
print("Input shape:", conv_window.example[0].shape)
print("Output shape:", multi_step_dense(conv_window.example[0]).shape)

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

print("Conv model on `conv_window`")
print("Input shape:", conv_window.example[0].shape)
print("Output shape:", conv_model(conv_window.example[0]).shape)

# %%
history = compile_and_fit(conv_model, conv_window)

IPython.display.clear_output()
val_performance["Conv"] = conv_model.evaluate(conv_window.val)
performance["Conv"] = conv_model.evaluate(conv_window.test, verbose=0)

# %%
print("Wide window")
print("Input shape:", wide_window.example[0].shape)
print("Labels shape:", wide_window.example[1].shape)
print("Output shape:", conv_model(wide_window.example[0]).shape)

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

print("Wide conv window")


print("Input shape:", wide_conv_window.example[0].shape)
print("Labels shape:", wide_conv_window.example[1].shape)
print("Output shape:", conv_model(wide_conv_window.example[0]).shape)

wide_conv_window.plot(conv_model)
# %%
lstm_model = tf.keras.models.Sequential(
    [
        # Shape [batch, time, features] => [batch, time, lstm_units]
        tf.keras.layers.LSTM(32, return_sequences=True),
        tf.keras.layers.Conv1D(
            filters=32, kernel_size=(CONV_WIDTH,), activation="relu"
        ),
        tf.keras.layers.Dense(units=32),
        tf.keras.layers.Dense(units=1),
    ]
)

print("Input shape:", wide_window.example[0].shape)
print("Output shape:", lstm_model(wide_window.example[0]).shape)
# %%
history = compile_and_fit(lstm_model, wide_conv_window)

IPython.display.clear_output()
val_performance["LSTM"] = lstm_model.evaluate(wide_conv_window.val)
performance["LSTM"] = lstm_model.evaluate(wide_conv_window.test, verbose=0)
# %%

wide_conv_window.plot(lstm_model)

# %%
x = np.arange(len(performance))
width = 0.3
metric_name = "mean_absolute_error"
metric_index = lstm_model.metrics_names.index("mean_absolute_error")
val_mae = [v[metric_index] for v in val_performance.values()]
test_mae = [v[metric_index] for v in performance.values()]

plt.ylabel(f"mean_absolute_error {FEATURE}, normalized]")
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
print("Wide window")
print("Input shape:", wide_window.example[0].shape)
print("Labels shape:", wide_window.example[1].shape)
print("Output shape:", residual_lstm(wide_window.example[0]).shape)
# %%

history = compile_and_fit(residual_lstm, wide_window)
# %%

IPython.display.clear_output()
val_performance["Residual LSTM"] = residual_lstm.evaluate(wide_window.val)
performance["Residual LSTM"] = residual_lstm.evaluate(wide_window.test, verbose=0)
# %%
wide_window.plot(residual_lstm)

# %%
x = np.arange(len(performance))
width = 0.3

metric_name = "mean_absolute_error"
metric_index = lstm_model.metrics_names.index("mean_absolute_error")
val_mae = [v[metric_index] for v in val_performance.values()]
test_mae = [v[metric_index] for v in performance.values()]

plt.bar(x - 0.17, val_mae, width, label="Validation")
plt.bar(x + 0.17, test_mae, width, label="Test")
plt.xticks(ticks=x, labels=performance.keys(), rotation=45)
plt.ylabel("MAE (average over all outputs)")
_ = plt.legend()
# %%

for name, value in performance.items():
    print(f"{name:12s}: {value[1]:0.4f}")

# %%

"""AGORA SIM MULTISTEP"""
INPUT_WIDTH = 24
OUT_STEPS = 12
# num_features = 1
# %%

multi_window = w_gen(
    input_width=INPUT_WIDTH,
    label_width=OUT_STEPS,
    shift=OUT_STEPS,
)

# %%
multi_window
# %%

multi_window.plot()

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


multi_val_performance = {}
multi_performance = {}
multi_val_performance["MultistepRepeatBaseline"] = msr_baseline.evaluate(
    multi_window.val
)
multi_performance["MultistepRepeatBaseline"] = msr_baseline.evaluate(
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


val_performance["MultistepRepeatLastBaseline"] = msrl_baseline.evaluate(
    multi_window.val
)
performance["MultistepRepeatLastBaseline"] = msrl_baseline.evaluate(
    multi_window.test, verbose=0
)

# %%
multi_window.plot(msrl_baseline)
# %%

"""MULTILINEAR"""

multi_linear_model = tf.keras.Sequential(
    [
        # Take the last time-step.
        # Shape [batch, time, features] => [batch, 1, features]
        tf.keras.layers.Lambda(lambda x: x[:, -2:, :]),
        # Shape => [batch, 1, out_steps*features]
        tf.keras.layers.Dense(
            OUT_STEPS * 1, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features]
        tf.keras.layers.Reshape([OUT_STEPS, -1]),
    ]
)

history = compile_and_fit(multi_linear_model, multi_window)
# %%

IPython.display.clear_output()
multi_val_performance["Linear"] = multi_linear_model.evaluate(multi_window.val)
multi_performance["Linear"] = multi_linear_model.evaluate(multi_window.test, verbose=0)
multi_window.plot(multi_linear_model)
# %%

"""MULTIDENSE"""
multi_dense_model = tf.keras.Sequential(
    [
        # Take the last time step.
        # Shape [batch, time, features] => [batch, 1, features]
        tf.keras.layers.Lambda(lambda x: x[:, -1:, :]),
        # Shape => [batch, 1, dense_units]
        tf.keras.layers.Dense(512, activation="relu"),
        # Shape => [batch, out_steps*features]
        tf.keras.layers.Dense(
            OUT_STEPS * 1, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features]
        tf.keras.layers.Reshape([OUT_STEPS, -1]),
    ]
)

history = compile_and_fit(multi_dense_model, multi_window)

IPython.display.clear_output()
multi_val_performance["Dense"] = multi_dense_model.evaluate(multi_window.val)
multi_performance["Dense"] = multi_dense_model.evaluate(multi_window.test, verbose=0)
# %%

multi_window.plot(multi_dense_model)

# %%
"""MULTICONV"""
CONV_WIDTH = 5
multi_conv_model = tf.keras.Sequential(
    [
        # Shape [batch, time, features] => [batch, CONV_WIDTH, features]
        tf.keras.layers.Lambda(lambda x: x[:, -CONV_WIDTH:, :]),
        # Shape => [batch, 1, conv_units]
        tf.keras.layers.Conv1D(256, activation="relu", kernel_size=(CONV_WIDTH)),
        # Shape => [batch, 1,  out_steps*features]
        tf.keras.layers.Dense(
            OUT_STEPS * 1, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features]
        tf.keras.layers.Reshape([OUT_STEPS, -1]),
    ]
)

history = compile_and_fit(multi_conv_model, multi_window)

IPython.display.clear_output()

multi_val_performance["Conv"] = multi_conv_model.evaluate(multi_window.val)
multi_performance["Conv"] = multi_conv_model.evaluate(multi_window.test, verbose=0)

# %%

multi_window.plot(multi_conv_model)

# %%

"""MULTILSTM"""
multi_lstm_model = tf.keras.Sequential(
    [
        # Shape [batch, time, features] => [batch, lstm_units].
        # Adding more `lstm_units` just overfits more quickly.
        tf.keras.layers.LSTM(32, return_sequences=False),
        # Shape => [batch, out_steps*features].
        tf.keras.layers.Dense(
            OUT_STEPS * 1, kernel_initializer=tf.initializers.zeros()
        ),
        # Shape => [batch, out_steps, features].
        tf.keras.layers.Reshape([OUT_STEPS, -1]),
    ]
)

history = compile_and_fit(multi_lstm_model, multi_window)

IPython.display.clear_output()

multi_val_performance["LSTM"] = multi_lstm_model.evaluate(multi_window.val)
multi_performance["LSTM"] = multi_lstm_model.evaluate(multi_window.test, verbose=0)

# %%

multi_window.plot(multi_lstm_model)


# %%

"""AUTOREGRESSIVE"""


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
    # Initialize the LSTM state.3
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
print(
    "Output shape (batch, time, features): ",
    feedback_model(multi_window.example[0]).shape,
)
# %%

history = compile_and_fit(feedback_model, multi_window)

IPython.display.clear_output()

multi_val_performance["AR LSTM"] = feedback_model.evaluate(multi_window.val)
multi_performance["AR LSTM"] = feedback_model.evaluate(multi_window.test, verbose=0)


# %%

multi_val_performance["AR LSTM"] = feedback_model.evaluate(multi_window.val)
multi_performance["AR LSTM"] = feedback_model.evaluate(multi_window.test, verbose=0)
# %%

multi_window.plot(feedback_model)

multi_val_performance["AR LSTM"] = feedback_model.evaluate(multi_window.val)
multi_performance["AR LSTM"] = feedback_model.evaluate(multi_window.test, verbose=0)
# %%

x = np.arange(len(multi_performance))
width = 0.3

metric_name = "mean_absolute_error"
metric_index = lstm_model.metrics_names.index("mean_absolute_error")
val_mae = [v[metric_index] for v in multi_val_performance.values()]
test_mae = [v[metric_index] for v in multi_performance.values()]

plt.bar(x - 0.17, val_mae, width, label="Validation")
plt.bar(x + 0.17, test_mae, width, label="Test")
plt.xticks(ticks=x, labels=multi_performance.keys(), rotation=45)
plt.ylabel(f"MAE (average over all times and outputs)")
_ = plt.legend()
# %%
for name, value in multi_performance.items():
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
    print(f"{name:8s}: {value[1]:0.4f}")
