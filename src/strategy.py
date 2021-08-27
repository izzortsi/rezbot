import numpy as np
import time


class Strategy1:
    def __init__(
        self,
        name,
        timeframe,
        stoploss_parameter,
        take_profit,
        entry_window,
        exit_window,
        macd_params={"fast": 12, "slow": 26, "signal": 9},
    ):
        self.name = name
        self.timeframe = timeframe
        self.stoploss_parameter = stoploss_parameter
        self.take_profit = take_profit
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.macd_params = macd_params

    def entry_signal(self, trader, data_window):

        if np.alltrue(data_window.histogram.tail(self.entry_window) < 0):
            return True
        else:
            return False

    def exit_signal(self, trader, data_window, entry_price):
        exit_price = data_window.close.values[-1]
        
        leveraged_diff = (
            ((exit_price - entry_price - (exit_price + entry_price)*0.0002)/entry_price) * 100
        ) * trader.leverage

        condition1 = leveraged_diff >= self.take_profit
        condition2 = np.alltrue(data_window.histogram.tail(self.exit_window) > 0)
        check = condition1 and condition2
        
        return check


class Strategy2:
    def __init__(
        self,
        name,
        timeframe,
        stoploss_parameter,
        take_profit,
        entry_window,
        exit_window,
        macd_params={"fast": 7, "slow": 13, "signal": 5},
    ):
        self.name = name
        self.timeframe = timeframe
        self.stoploss_parameter = stoploss_parameter
        self.take_profit = take_profit
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.macd_params = macd_params

    def entry_signal(self, trader, data_window):

        if np.alltrue(data_window.histogram.tail(self.entry_window) >= 0):
            return True
        else:
            return False

    def exit_signal(self, trader, data_window, entry_price):

        exit_price = data_window.close.values[-1]
        
        leveraged_diff = (
            ((exit_price - entry_price - (exit_price + entry_price)*0.0002)/entry_price) * 100
        ) * trader.leverage

        condition1 = leveraged_diff >= self.take_profit
        # condition2 = np.alltrue(data_window.histogram.tail(self.exit_window) <= 0)
        check = condition1  # and condition2
        return condition1

    def stoploss_check(self, trader, data_window, entry_price):

        exit_price = data_window.close.values[-1]
        
        leveraged_diff = (
            ((exit_price - entry_price - (exit_price + entry_price)*0.0002)/entry_price) * 100
        ) * trader.leverage

        check = leveraged_diff <= self.stoploss_parameter

        return check


class Strategy3:
    def __init__(
        self,
        name,
        timeframe,
        stoploss_parameter,
        take_profit,
        entry_window,
        exit_window,
        macd_params={"fast": 12, "slow": 26, "signal": 9},
    ):
        self.name = name
        self.timeframe = timeframe
        self.stoploss_parameter = stoploss_parameter
        self.take_profit = take_profit
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.macd_params = macd_params
        self.minmax = lambda series: (series - series.min()) / (
            series.max() - series.min()
        )

    def entry_signal(self, trader, data_window):

        self.to_be_normalized = data_window.histogram.tail(self.macd_params["slow"])
        self.normalized_hist = self.minmax(self.to_be_normalized)
        # self.description = self.normalized_hist.describe()
        norm_tail = self.normalized_hist.tail(self.entry_window)
        description = norm_tail.describe()

        if np.alltrue(norm_tail >= description["mean"] - description["25%"]) and (
            np.alltrue(norm_tail <= description["mean"] + description["25%"])
        ):
            return True
        else:
            return False

    def exit_signal(self, trader, data_window, entry_price):

        exit_price = data_window.close.values[-1]
        
        leveraged_diff = (
            ((exit_price - entry_price - (exit_price + entry_price)*0.0002)/entry_price) * 100
        ) * trader.leverage

        condition1 = leveraged_diff >= self.take_profit
        # condition2 = np.alltrue(data_window.histogram.tail(self.exit_window) <= 0)
        check = condition1  # and condition2
        return condition1

    def stoploss_check(self, trader, data_window, entry_price):

        exit_price = data_window.close.values[-1]
        
        leveraged_diff = (
            ((exit_price - entry_price - (exit_price + entry_price)*0.0002)/entry_price) * 100
        ) * trader.leverage

        check1 = leveraged_diff <= self.stoploss_parameter
        norm_tail = self.normalized_hist.tail(self.exit_window)
        diffs = np.array(
            [norm_tail[i] - norm_tail[i - 1] for i, k in enumerate(norm_tail[1:])]
        )
        if np.sum(diffs) < 0:
            return check1 and True
