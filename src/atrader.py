from src import *
from src.grabber import DataGrabber
from unicorn_binance_rest_api.unicorn_binance_rest_api_exceptions import *


class ATrader:
    def __init__(self, manager, strategy, symbol, leverage, is_real, qty):

        self.manager = manager
        self.bwsm = manager.bwsm
        self.client = manager.client
        self.strategy = strategy
        self.symbol = symbol
        self.leverage = leverage
        self.is_real = is_real

        if self.symbol == "ethusdt" or self.symbol == "ETHUSDT":
            min = 0.001
            ticker = self.client.get_symbol_ticker(symbol=self.symbol.upper())
            price = float(ticker["price"])
            multiplier = np.ceil(5 / (price * min))
            self.qty = f"{(multiplier*min):.3f}"
        elif self.symbol == "bnbusdt" or self.symbol == "BNBUSDT":
            min = 0.01
            ticker = self.client.get_symbol_ticker(symbol=self.symbol.upper())
            price = float(ticker["price"])
            multiplier = np.ceil(5 / (price * min))
            self.qty = f"{(multiplier*min):.2f}"
        elif self.symbol == "btcusdt" or self.symbol == "BTCUSDT":
            min = 0.001
            ticker = self.client.get_symbol_ticker(symbol=self.symbol.upper())
            price = float(ticker["price"])
            multiplier = np.ceil(5 / (price * min))
            self.qty = f"{(multiplier*min):.3f}"
        else:
            raise Exception(
                "as of now the only allowed symbols are 'ethusdt' and 'bnbusdt'"
            )

        self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)

        self.name = name_trader(strategy, self.symbol)
        # self.profits = []
        self.cum_profit = 0
        self.num_trades = 0

        self.stoploss = strategy.stoploss_parameter
        self.take_profit = strategy.take_profit
        self.entry_window = strategy.entry_window
        self.exit_window = strategy.exit_window
        self.macd_params = strategy.macd_params

        self.keep_running = True
        self.stream_id = None
        self.stream_name = None

        self.grabber = DataGrabber(self.client)
        self.data_window = self._get_initial_data_window()
        self.running_candles = []  # self.data_window.copy(deep=True)
        # self.data = None

        self.start_time = time.time()  # wont change, used to compute uptime
        self.init_time = time.time()
        self.now = time.time()

        self.is_positioned = False
        self.position = None
        self.entry_price = None
        self.entry_time = None
        self.exit_price = None
        self.exit_time = None
        self.last_price = None
        self.now_time = None
        self.close_order = None
        # self.uptime = None

        strf_init_time = strf_epoch(self.init_time, fmt="%H-%M-%S")
        self.name_for_logs = f"{self.name}-{strf_init_time}"

        self.logger = setup_logger(
            f"{self.name}-logger",
            os.path.join(logs_for_this_run, f"{self.name_for_logs}.log"),
        )
        self.csv_log_path = os.path.join(logs_for_this_run, f"{self.name_for_logs}.csv")
        self.csv_log_path_candles = os.path.join(
            logs_for_this_run, f"{self.name_for_logs}_candles.csv"
        )
        self.confirmatory_data = []

    def stop(self):
        self.keep_running = False
        self.bwsm.stop_stream(self.stream_id)
        del self.manager.traders[self.name]
        # self.worker._delete()

    def is_alive(self):
        return self.worker.is_alive()

    def status(self):
        status = (
            self.is_alive(),
            self.is_positioned,
        )
        print(
            f"""uptime: {to_datetime_tz(self.now) - to_datetime_tz(self.start_time)};
              Δ%*leverage: {to_percentual(self.last_price, self.entry_price, leverage = self.leverage)}
              leverage: {self.leverage};
              status: Alive? Positioned? {status}
              """
        )
        # print(f"Is alive? {status[0]}; Is positioned? {status[1]}")
        return status

    def rows_to_csv(self):
        for i, row in enumerate(self.running_candles):
            if i == 0:
                row.to_csv(
                    self.csv_log_path_candles, header=True, mode="w", index=False
                )
            elif i > 0:
                row.to_csv(
                    self.csv_log_path_candles, header=False, mode="a", index=False
                )

    def _drop_trades_to_csv(self):
        updated_num_trades = len(self.confirmatory_data)
        # print(updated_num_trades)
        if updated_num_trades == 1:
            row = pd.DataFrame.from_dict(self.confirmatory_data)
            # print(row)
            row.to_csv(
                self.csv_log_path,
                header=True,
                mode="w",
                index=False,
            )
            self.num_trades += 1

        elif (updated_num_trades > 1) and (updated_num_trades > self.num_trades):
            # print(int(self.now - self.start_time))
            row = pd.DataFrame.from_dict([self.confirmatory_data[-1]])
            # print(row)
            row.to_csv(
                self.csv_log_path,
                header=False,
                mode="a",
                index=False,
            )
            self.num_trades += 1

    def _change_position(self):
        self.is_positioned = not self.is_positioned
        # time.sleep(0.1)

    def _get_initial_data_window(self):
        klines = self.grabber.get_data(
            symbol=self.symbol,
            tframe=self.strategy.timeframe,
            limit=2 * self.macd_params["slow"],
        )
        last_kline_row = self.grabber.get_data(
            symbol=self.symbol, tframe=self.strategy.timeframe, limit=1
        )
        klines = klines.append(last_kline_row, ignore_index=True)
        date = klines.date

        df = self.grabber.compute_indicators(
            klines.close, is_macd=True, **self.strategy.macd_params
        )

        df = pd.concat([date, df], axis=1)
        return df

    def _start_new_stream(self):

        channel = "kline" + "_" + self.strategy.timeframe
        market = self.symbol

        stream_name = channel + "@" + market

        stream_id = self.bwsm.create_stream(
            channel, market, stream_buffer_name=stream_name
        )

        worker = threading.Thread(
            target=self._process_stream_data,
            args=(),
        )
        worker.setDaemon(True)
        worker.start()

        self.stream_name = stream_name
        self.worker = worker
        self.stream_id = stream_id

    def _process_stream_data(self):

        while self.keep_running:
            time.sleep(0.2)
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
                            np.atleast_2d(np.array([self.now_time, o, h, l, c])),
                            columns=[
                                "date",
                                "open",
                                "high",
                                "low",
                                "close",
                            ],
                            index=[last_index],
                        )

                        tf_as_seconds = (
                            interval_to_milliseconds(self.strategy.timeframe) * 0.001
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

                            self.data_window.drop(index=[0], axis=0, inplace=True)
                            self.data_window = self.data_window.append(
                                new_row, ignore_index=True
                            )

                            self.running_candles.append(dohlcv)
                            self.init_time = time.time()
                        else:
                            self.data_window.update(new_row)

                        self._act_on_signal()
                        self._drop_trades_to_csv()

                except Exception as e:
                    self.logger.info(f"{e}")

    def _act_on_signal(self):
        """
        aqui eu tenho que
        1) mudar o sinal de entrada pra incluir as duas direçoes
        2) essa é a função que faz os trades, efetivamente. falta isso
        """

        if not self.is_positioned:
            if self.strategy.entry_signal(self, self.data_window):
                try:
                    self._start_position()
                    self.logger.info(
                        f"ENTRY: E:{self.entry_price} at t:{self.entry_time}"
                    )
                    self._change_position()
                except BinanceAPIException as error:
                    # print(type(error))
                    self.logger.info(f"positioning,  {error}")
        else:
            if self.strategy.exit_signal(self, self.data_window, self.entry_price):
                try:
                    self._close_position()
                    self._register_trade_data("TP")
                    self._change_position()
                except BinanceAPIException as error:
                    self.logger.info(f"tp order, {error}")
            elif self.strategy.stoploss_check(self, self.data_window, self.entry_price):
                try:
                    self._close_position()
                    self._register_trade_data("SL")
                    self._change_position()
                except BinanceAPIException as error:
                    self.logger.info(f"sl order, {error}")

    def _start_position(self):
        """lembrar de settar/formatar quantity etc pro caso geral, com qualquer
        coin"""

        self.position = self.client.futures_create_order(
            symbol=self.symbol,
            side="BUY",
            type="MARKET",
            quantity=self.qty,
            priceProtect=False,
            workingType="MARK_PRICE",
            newOrderRespType="RESULT",
        )
        if self.position["status"] == "FILLED":
            self.entry_price = float(self.position["avgPrice"])
            self.qty = self.position["executedQty"]
            self.entry_time = to_datetime_tz(self.position["updateTime"], unit="ms")

    def _close_position(self):
        self.close_order = self.client.futures_create_order(
            symbol=self.symbol,
            side="SELL",
            type="MARKET",
            workingType="MARK_PRICE",
            quantity=self.qty,
            reduceOnly=True,
            priceProtect=False,
            newOrderRespType="RESULT",
        )
        if self.close_order["status"] == "FILLED":
            self.exit_price = float(self.close_order["avgPrice"])
            self.exit_time = to_datetime_tz(self.close_order["updateTime"], unit="ms")

    def _register_trade_data(self, tp_or_sl):
        profit = (self.exit_price - self.entry_price) - 0.0002 * (
            self.entry_price + self.exit_price
        )
        percentual_profit = (profit / self.entry_price) * 100 * self.leverage

        self.cum_profit += percentual_profit
        self.confirmatory_data.append(
            {
                "type": f"{tp_or_sl}",
                "entry_time": self.entry_time,
                "entry_price": self.entry_price,
                "exit_time": self.exit_time,
                "exit_price": self.exit_price,
                "percentual_difference": percentual_profit,
                "cumulative_profit": self.cum_profit,
            }
        )

        self.logger.info(
            f"{tp_or_sl}: Δabs: {profit}; Δ%: {percentual_profit}%; cum_profit: {self.cum_profit}%"
        )

    def live_plot(self):

        fig = plt.figure()
        title = f"live {self.symbol} price @ binance.com"

        fig.canvas.set_window_title(title)
        ax = fig.add_subplot(1, 1, 1)

        def animate(i):

            data = self.data_window

            xs = data.date
            ys = data.close
            ax.clear()
            ax.plot(xs, ys, "k")
            plt.xticks(rotation=45, ha="right")
            plt.subplots_adjust(bottom=0.30)
            plt.title(title)
            plt.ylabel("USDT Value")

        ani = animation.FuncAnimation(fig, animate, interval=1)
        plt.show()
        plt.show()
