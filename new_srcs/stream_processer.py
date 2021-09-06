from src import *
import threading
import time


class StreamProcesser(threading.Thread):
    def __init__(self, trader):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.trader = trader
        self.start()

    def run(self):
        while self.trader.keep_running:
            self._process_stream_data()

    def _process_stream_data(self):

        time.sleep(0.1)

        if self.trader.bwsm.is_manager_stopping():
            exit(0)

        data_from_stream_buffer = self.trader.bwsm.pop_stream_data_from_stream_buffer(
            self.trader.stream_name
        )

        if data_from_stream_buffer is False:
            time.sleep(0.01)
            return

        try:
            if data_from_stream_buffer["event_type"] == "kline":

                kline = data_from_stream_buffer["kline"]

                o = float(kline["open_price"])
                h = float(kline["high_price"])
                l = float(kline["low_price"])
                c = float(kline["close_price"])
                # v = float(kline["base_volume"])
                #
                # num_trades = int(kline["number_of_trades"])
                # is_closed = bool(kline["is_closed"])

                last_index = self.trader.data_window.index[-1]

                self.trader.now = time.time()
                self.trader.now_time = to_datetime_tz(
                    self.trader.now)
                self.trader.last_price = c

                dohlcv = pd.DataFrame(
                    np.atleast_2d(
                        np.array([self.trader.now_time, o, h, l, c])),
                    columns=["date", "open",
                             "high", "low", "close"],
                    index=[last_index],
                )

                tf_as_seconds = (
                    interval_to_milliseconds(
                        self.trader.strategy.timeframe) * 0.001
                )

                new_close = dohlcv.close
                self.trader.data_window.close.update(new_close)

                macd = self.trader.grabber.compute_indicators(
                    self.trader.data_window.close, **self.trader.strategy.macd_params
                )

                date = dohlcv.date
                new_row = pd.concat(
                    [date, macd.tail(1)],
                    axis=1,
                )

                if (
                    int(self.trader.now - self.trader.init_time)
                    >= tf_as_seconds / self.trader.manager.rate
                ):

                    self.trader.data_window.drop(
                        index=[0], axis=0, inplace=True)
                    self.trader.data_window = self.trader.data_window.append(
                        new_row, ignore_index=True
                    )

                    self.trader.running_candles.append(dohlcv)
                    self.trader.init_time = time.time()

                else:
                    self.trader.data_window.update(new_row)

        except Exception as e:
            self.trader.logger.info(f"{e}")
