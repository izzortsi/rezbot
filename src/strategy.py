import numpy as np
import time


class MacdStrategy:
    def __init__(
        self,
        name,
        timeframe,
        take_profit,
        stoploss,
        entry_window,
        exit_window,
        macd_params={"fast": 12, "slow": 26, "signal": 9},
    ):
        self.name = name
        self.timeframe = timeframe
        self.stoploss = stoploss
        self.take_profit = take_profit
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.macd_params = macd_params

    def entry_signal(self, trader):

        if np.alltrue(trader.data_window.histogram.tail(self.entry_window) < 0):
            return True
        else:
            return False

    def exit_signal(self, trader):

        condition1 = trader.current_percentual_profit >= self.take_profit

        condition2 = np.alltrue(trader.data_window.histogram.tail(self.exit_window) > 0)
        check = condition1 and condition2

        return check

    def stoploss_check(self, trader):

        check = trader.current_percentual_profit <= self.stoploss

        return check


class TAStrategy:
    def __init__(
        self,
        name,
        timeframe,
        take_profit,
        stoploss,
        entry_window,
        exit_window,
        macd_params={"fast": 12, "slow": 26, "signal": 9},
    ):
        self.name = name
        self.timeframe = timeframe
        self.stoploss = stoploss
        self.take_profit = take_profit
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.macd_params = macd_params

    def entry_signal(self, trader):

        if (
            np.alltrue(trader.data_window.histogram.tail(self.entry_window) < 0)
            and trader.ta_handler.signal == 1
        ):
            trader.position_type = 1
            return True
        elif (
            np.alltrue(trader.data_window.histogram.tail(self.entry_window) > 0)
            and trader.ta_handler.signal == -1
        ):
            trader.position_type = -1
            return True
        else:
            return False

    def exit_signal(self, trader):

        condition1 = trader.current_percentual_profit >= self.take_profit

        # condition2 = np.alltrue(
        #     trader.data_window.histogram.tail(self.exit_window) > 0)
        check = condition1  # and condition2

        return check

    def stoploss_check(self, trader):

        condition1 = trader.current_percentual_profit <= self.stoploss
        condition2 = trader.position_type == -trader.ta_handler.signal
        check = condition1 and condition2

        return check
