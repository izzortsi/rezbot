from src import *
import threading
import time
import pandas_ta as ta

class StreamProcesser:
    def __init__(self, trader):

        self.trader = trader

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
                v = float(kline["base_volume"])
                #
                # num_trades = int(kline["number_of_trades"])
                # is_closed = bool(kline["is_closed"])

                last_index = self.trader.data_window.index[-1]

                self.trader.now = time.time()
                self.trader.now_time = to_datetime_tz(self.trader.now)
                self.trader.last_price = c

                dohlcv = pd.DataFrame(
                    np.atleast_2d(np.array([self.trader.now_time, o, h, l, c, v])),
                    columns=["date", "open", "high", "low", "close", "volume"],
                    index=[last_index],
                )

                tf_as_seconds = (
                    interval_to_milliseconds(self.trader.strategy.timeframe) * 0.001
                )

                new_close = dohlcv.close
                self.trader.data_window.close.update(new_close)

                # indicators = self.trader.grabber.compute_indicators(
                #     self.trader.data_window.close, **self.trader.strategy.macd_params
                # )
                macd = ta.macd(self.trader.data_window.close)
                # macd = ta.macd(self.trader.data_window.close, **self.trader.strategy.macd_params)
                # print(self.trader.strategy.macd_params)
                hist = macd["MACDh_12_26_9"]
                hist.name = "histogram"
                c = self.trader.data_window.close
                close_ema = c.ewm(span=self.trader.w1).mean()
                close_ema.name = "close_ema"
                close_std = c.ewm(span=self.trader.w1).std()
                close_std.name = "close_std"
                cs = close_ema + self.trader.m1*close_std
                cs.name = "cs"
                ci = close_ema - self.trader.m1*close_std
                ci.name = "ci"
                hist_ema = hist.ewm(span=self.trader.w1).mean()
                hist_ema.name = "hist_ema"
                indicators = pd.concat([c, cs, close_ema, ci, close_std, hist, hist_ema], axis=1)
                date = dohlcv.date

                new_row = pd.concat(
                    [date, indicators.tail(1)],
                    axis=1,
                )

                if (
                    (self.trader.data_window.date.values[-1] - self.trader.data_window.date.values[-2])
                    >= pd.Timedelta(f"{tf_as_seconds / self.trader.manager.rate} seconds")
                ):

                    self.trader.data_window.drop(index=[0], axis=0, inplace=True)
                    self.trader.data_window = self.trader.data_window.append(
                        new_row, ignore_index=True
                    )

                    self.trader.running_candles.append(dohlcv)
                    self.trader.init_time = time.time()

                else:
                    self.trader.data_window.update(new_row)

        except Exception as e:
            self.trader.logger.info(f"{e}")
