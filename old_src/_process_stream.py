    def _process_stream_data(self):

        while self.keep_running:
            time.sleep(0.1)
            if self.bwsm.is_manager_stopping():
                exit(0)

            data_from_stream_buffer = self.bwsm.pop_stream_data_from_stream_buffer(
                self.stream_name
            )

            if data_from_stream_buffer is False:
                time.sleep(0.01)

            else:
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

                        last_index = self.data_window.index[-1]

                        self.now = time.time()
                        self.now_time = to_datetime_tz(self.now)
                        self.last_price = c

                        dohlcv = pd.DataFrame(
                            np.atleast_2d(
                                np.array([self.now_time, o, h, l, c])),
                            columns=["date", "open", "high", "low", "close"],
                            index=[last_index],
                        )

                        tf_as_seconds = (
                            interval_to_milliseconds(
                                self.strategy.timeframe) * 0.001
                        )

                        new_close = dohlcv.close
                        self.data_window.close.update(new_close)

                        macd = self.grabber.compute_indicators(
                            self.data_window.close, **self.strategy.macd_params
                        )

                        date = dohlcv.date
                        new_row = pd.concat(
                            [date, macd.tail(1)],
                            axis=1,
                        )

                        if (
                            int(self.now - self.init_time)
                            >= tf_as_seconds / self.manager.rate
                        ):

                            self.data_window.drop(
                                index=[0], axis=0, inplace=True)
                            self.data_window = self.data_window.append(
                                new_row, ignore_index=True
                            )

                            self.running_candles.append(dohlcv)
                            self.init_time = time.time()

                        else:
                            self.data_window.update(new_row)

                except Exception as e:
                    self.logger.info(f"{e}")
