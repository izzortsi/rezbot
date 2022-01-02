# %%


import pandas as pd
import numpy as np
import tensorflow as tf
from scipy import stats
from tensorflow.python.ops import rnn, rnn_cell
from sklearn.metrics import roc_auc_score
from src.grabber import DataGrabber
from unicorn_binance_rest_api import BinanceRestApiManager
from auxiliary_functions import *
from src import *
from get_indicators import *

# %%


def read_data():
    sym = "BNBUSDT"
    tframe = "15m"

    client, k, s = make_client(new=True)
    grabber = DataGrabber(client)
    klines = grabber.get_historical_data(
        symbol=sym, tframe=tframe, startTime="2 month ago", endTime="now", limit=2000
    )
    data = get_indicators(klines)

    check_next_vals(klines, "label")

    y = np.array(klines.label.tail(967))
    y += 1

    X = np.array(data)
    return X, y, data, klines


def windows(data, window_size):
    start = 0
    while start < len(data):
        yield start, start + window_size
        start += window_size // 2


def extract_segments(data, label, window_size=30):
    segments = np.empty((0, (window_size + 1)))
    labels = np.empty((0))
    for (start, end) in windows(data, window_size):
        if len(data[start:end]) == (window_size + 1):
            signal = data[start:end]
            segments = np.vstack([segments, signal])
            labels = np.append(label[start:end])
    return segments, labels


# %%
win_size = 10
"""
MIMIC-III dataset can possibly be use to train and test the model.
But beware this is not the data set used by the authors of the paper.
For dataset description and format please see Section 3: Data Description in the paper.
"""
X, y, data, klines = read_data()

data[1:3]
# %%

segments, labels = extract_segments(data, win_size)
labels = np.asarray(pd.get_dummies(labels), dtype=np.int8)
reshaped_segments = segments.reshape([len(segments), (win_size + 1), 1])
# %%


train_test_split = np.random.rand(len(reshaped_segments)) < 0.80
train_x = reshaped_segments[train_test_split]
train_y = labels[train_test_split]
test_x = reshaped_segments[~train_test_split]
test_y = labels[~train_test_split]

# %%

graph = tf.Graph()
learning_rate = 0.001
training_epochs = 100
batch_size = 10
total_batches = train_x.shape[0] // batch_size

n_input = 1
n_steps = 10
n_hidden = 64
n_classes = 3

alpha = 0.5
# %%


def weight_variable(shape):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial)


def bias_variable(shape):
    initial = tf.constant(0.0, shape=shape)
    return tf.Variable(initial)


def LSTM(x, weight, bias):
    cell = rnn_cell.LSTMCell(n_hidden, state_is_tuple=True)
    multi_layer_cell = tf.nn.rnn_cell.MultiRNNCell([cell] * 2)
    output, state = tf.nn.dynamic_rnn(multi_layer_cell, x, dtype=tf.float32)
    output_flattened = tf.reshape(output, [-1, n_hidden])
    output_logits = tf.add(tf.matmul(output_flattened, weight), bias)
    output_all = tf.nn.sigmoid(output_logits)
    output_reshaped = tf.reshape(output_all, [-1, n_steps, n_classes])
    output_last = tf.gather(tf.transpose(output_reshaped, [1, 0, 2]), n_steps - 1)
    # output = tf.transpose(output, [1, 0, 2])
    # last = tf.gather(output, int(output.get_shape()[0]) - 1)
    # output_last = tf.nn.sigmoid(tf.matmul(last, weight) + bias)
    return output_last, output_all


# %%


weight = weight_variable([n_hidden, n_classes])
bias = bias_variable([n_classes])
y_last, y_all = LSTM(x, weight, bias)
