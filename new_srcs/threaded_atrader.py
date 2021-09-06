from src import *
from src.grabber import DataGrabber
from src.stream_processer import StreamProcesser
from unicorn_binance_rest_api.unicorn_binance_rest_api_exceptions import *
import threading


class ThreadedATrader(threading.Thread):
    def __init__(self, manager, name, strategy, symbol, leverage, is_real, qty):

        threading.Thread.__init__(self)

        self.setDaemon(True)

        self.name = name
        self.manager = manager
        self.bwsm = manager.bwsm
        self.client = manager.client
        self.strategy = strategy
        self.symbol = symbol
        self.leverage = leverage
        self.is_real = is_real
        self.ta_handler = self.manager.ta_handlers[self.name]

        if self.is_real:
            if self.symbol == "ethusdt" or self.symbol == "ETHUSDT":
                min = 0.001
                ticker = self.client.get_symbol_ticker(
                    symbol=self.symbol.upper())
                price = float(ticker["price"])
                multiplier = qty*np.ceil(5 / (price * min))
                self.qty = f"{(multiplier*min):.3f}"
                self.price_formatter = lambda x: f"{x:.3f}"
            elif self.symbol == "bnbusdt" or self.symbol == "BNBUSDT":
                min = 0.01
                ticker = self.client.get_symbol_ticker(
                    symbol=self.symbol.upper())
                price = float(ticker["price"])
                multiplier = qty*np.ceil(5 / (price * min))
                self.qty = f"{(multiplier*min):.2f}"
                self.price_formatter = lambda x: f"{x:.2f}"
            elif self.symbol == "btcusdt" or self.symbol == "BTCUSDT":
                min = 0.001
                ticker = self.client.get_symbol_ticker(
                    symbol=self.symbol.upper())
                price = float(ticker["price"])
                multiplier = qty*np.ceil(5 / (price * min))
                self.qty = f"{(multiplier*min):.3f}"
                self.price_formatter = lambda x: f"{x:.3f}"
            else:
                raise Exception(
                    "symbol not allowed"
                )

            self.client.futures_change_leverage(
                symbol=self.symbol, leverage=self.leverage
            )

        # self.profits = []
        self.cum_profit = 0
        self.num_trades = 0

        self.stoploss = strategy.stoploss
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
        self.ta_signal = self.ta_handler.signal
        self.ta_summary = self.ta_handler.summary
        # self.data = None

        self.start_time = time.time()  # wont change, used to compute uptime
        self.init_time = time.time()
        self.now = time.time()

        self.is_positioned = False
        self.position = None
        self.position_type = None
        self.entry_price = None
        self.entry_time = None
        self.exit_price = None
        self.exit_time = None
        self.last_price = None
        self.now_time = None
        self.opening_order = None
        self.closing_order = None
        self.current_profit = None
        self.current_percentual_profit = None
        # self.uptime = None

        strf_init_time = strf_epoch(self.init_time, fmt="%H-%M-%S")
        self.name_for_logs = f"{self.name}-{strf_init_time}"

        self.logger = setup_logger(
            f"{self.name}-logger",
            os.path.join(logs_for_this_run, f"{self.name_for_logs}.log"),
        )
        self.csv_log_path = os.path.join(
            logs_for_this_run, f"{self.name_for_logs}.csv")
        self.csv_log_path_candles = os.path.join(
            logs_for_this_run, f"{self.name_for_logs}_candles.csv"
        )
        self.confirmatory_data = []

        self._start_new_stream()
        self.start()

    def run(self):

        while self.keep_running:
            if self.is_real:
                self._really_act_on_signal()
            else:
                self._test_act_on_signal()
            self._drop_trades_to_csv()

    def stop(self):
        self.keep_running = False
        self.bwsm.stop_stream(self.stream_id)
        del self.manager.traders[self.name]
        # self.worker._delete()

    def is_alive(self):
        return self.worker.is_alive()

    def _side_from_int(self):
        if self.position_type == -1:
            return "SELL", "BUY"
        elif self.position_type == 1:
            return "BUY", "SELL"

    def _drop_trades_to_csv(self):
        updated_num_trades = len(self.confirmatory_data)
        # print(updated_num_trades)
        if updated_num_trades == 1 and self.num_trades == 0:
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

        self.stream_name = stream_name
        self.stream_processer = StreamProcesser(self)
        self.stream_id = stream_id

    def _test_act_on_signal(self):
        """
        aqui eu tenho que
        1) mudar o sinal de entrada pra incluir as duas direçoes
        2) essa é a função que faz os trades, efetivamente. falta isso
        """
        self.ta_signal = self.ta_handler.signal
        self.ta_summary = self.ta_handler.summary

        if self.is_positioned:

            self._set_current_profits()

            if self.strategy.stoploss_check(self):
                # print("sl")

                self._register_trade_data(f"SL")

                self._change_position()
                self.entry_price = None

            elif self.strategy.exit_signal(self):
                # print("tp")

                self._register_trade_data(f"TP")

                self._change_position()
                self.entry_price = None

        else:
            if self.strategy.entry_signal(self):
                self.entry_price = self.data_window.close.values[-1]
                self.entry_time = self.data_window.date.values[-1]
                self.logger.info(
                    f"ENTRY: E:{self.entry_price} at t:{self.entry_time}; signal: {self.ta_handler.signal}; type: {self.position_type}")
                self._change_position()

    def _set_current_profits(self):

        self.last_price = self.data_window.close.values[-1]

        self.current_profit = (
            self.position_type * (
                self.last_price - self.entry_price)
            - 0.0004 * (self.last_price + self.entry_price)
        )

        if self.position_type == 1:
            self.current_percentual_profit = (
                self.current_profit / self.entry_price) * 100
        elif self.position_type == -1:
            self.current_percentual_profit = (
                self.current_profit / self.last_price) * 100

    def _register_trade_data(self, tp_or_sl):

        exit_price = self.last_price
        exit_time = self.data_window.date.values[-1]
        self.cum_profit += self.current_percentual_profit * self.leverage
        self.confirmatory_data.append(
            {
                "TP/SL": f"{tp_or_sl}",
                "type": f"{'LONG' if self.position_type == 1 else 'SHORT'}",
                "entry_time": self.entry_time,
                "entry_price": self.entry_price,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "percentual_difference": self.current_percentual_profit,
                "leveraged percentual_difference": self.current_percentual_profit * self.leverage,
                "cumulative_profit": self.cum_profit,
            }
        )

        self.logger.info(
            f"{tp_or_sl}: Δabs: {self.current_profit}; leveraged Δ%: {self.current_percentual_profit*self.leverage}%; cum_profit: {self.cum_profit}%"
        )

    def _set_actual_profits(self):

        self.current_profit = (
            self.position_type * (
                self.exit_price - self.entry_price)
            - 0.0004 * (self.exit_price + self.entry_price)
        )

        if self.position_type == 1:
            self.current_percentual_profit = (
                self.current_profit / self.entry_price) * 100
        elif self.position_type == -1:
            self.current_percentual_profit = (
                self.current_profit / self.exit_price) * 100

    def _really_act_on_signal(self):
        """
        aqui eu tenho que
        1) mudar o sinal de entrada pra incluir as duas direçoes
        2) essa é a função que faz os trades, efetivamente. falta isso
        """
        if not self.is_positioned:
            if self.strategy.entry_signal(self):
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

            self._set_current_profits()

            if self.strategy.exit_signal(self):
                try:
                    self._close_position()
                    self._set_actual_profits()
                    self._register_trade_data("TP")
                    self._change_position()
                except BinanceAPIException as error:
                    self.logger.info(f"tp order, {error}")
            elif self.strategy.stoploss_check(self):
                try:
                    self._close_position()
                    self._set_actual_profits()
                    self._register_trade_data("SL")
                    self._change_position()
                except BinanceAPIException as error:
                    self.logger.info(f"sl order, {error}")

    def _start_position(self):
        """lembrar de settar/formatar quantity etc pro caso geral, com qualquer
        coin"""
        side, _ = self._side_from_int()
        self.position = self.client.futures_create_order(
            symbol=self.symbol,
            side=side,
            type="MARKET",
            quantity=self.qty,
            priceProtect=False,
            workingType="MARK_PRICE",
            newOrderRespType="RESULT",
        )
        if self.position["status"] == "FILLED":
            self.entry_price = float(self.position["avgPrice"])
            self.qty = self.position["executedQty"]
            self.entry_time = to_datetime_tz(
                self.position["updateTime"], unit="ms")

    def _close_position(self):
        _, counterside = self._side_from_int()
        self.closing_order = self.client.futures_create_order(
            symbol=self.symbol,
            side=counterside,
            type="MARKET",
            workingType="MARK_PRICE",
            quantity=self.qty,
            reduceOnly=True,
            priceProtect=False,
            newOrderRespType="RESULT",
        )
        if self.closing_order["status"] == "FILLED":
            self.exit_price = float(self.closing_order["avgPrice"])
            self.exit_time = to_datetime_tz(
                self.closing_order["updateTime"], unit="ms")
