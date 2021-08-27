import numpy as np
import time


class Strategy:
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

    def stoploss_check(self, trader, data_window, entry_price):

        exit_price = data_window.close.values[-1]
        
        leveraged_diff = (
            ((exit_price - entry_price - (exit_price + entry_price)*0.0002)/entry_price) * 100
        ) * trader.leverage

        check = leveraged_diff <= self.stoploss_parameter

        return check
