from src import *
from src.grabber import DataGrabber
from src.stream_processer import StreamProcesser
from unicorn_binance_rest_api.unicorn_binance_rest_api_exceptions import *
import threading
from src.symbols_formats import FORMATS


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

        if self.is_real:
            if self.symbol.upper() in FORMATS.keys():

                format = FORMATS[self.symbol.upper()]

                qty_precision = int(format["quantityPrecision"])
                price_precision = int(format["pricePrecision"])
                print(qty_precision)
                print(price_precision)
                notional = 5
                min_qty = 1 / 10 ** qty_precision

                ticker = self.client.get_symbol_ticker(symbol=self.symbol.upper())
                price = float(ticker["price"])
                multiplier = qty * np.ceil(notional / (price * min_qty))
                # f"{float(value):.{decimal_count}f}"

                self.qty = f"{float(multiplier*min_qty):.{qty_precision}f}"
                self.price_formatter = lambda x: f"{float(x):.{price_precision-1}f}"
                print(min_qty)
                print(self.qty)
                print(self.price_formatter(price))

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
        self.tp_order = None
        self.current_profit = None
        self.current_percentual_profit = None
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

        self._start_new_stream()
        self.start()

    def run(self):

        while self.keep_running:
            self.stream_processer._process_stream_data()
            if self.is_real:
                self._really_act_on_signal_limit()
            else:
                self._test_act_on_signal()
            self._drop_trades_to_csv()

    def stop(self):
        self.keep_running = False
        self.bwsm.stop_stream(self.stream_id)
        del self.manager.traders[self.name]
        # self.worker._delete()

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

        df = pd.concat([date, klines, df], axis=1)
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

        if self.is_positioned:

            self._set_current_profits()

            if self.strategy.stoploss_check(self):
                # print("sl")

                self.exit_price = self.last_price
                self.exit_time = self.data_window.date.values[-1]

                self._register_trade_data(f"SL")
                self._change_position()
                self.entry_price = None
                self.exit_price = None

            elif self.strategy.exit_signal(self):
                # print("tp")

                self.exit_price = self.last_price
                self.exit_time = self.data_window.date.values[-1]

                self._register_trade_data(f"TP")
                self._change_position()
                self.entry_price = None
                self.exit_price = None

        else:
            if self.strategy.entry_signal(self):
                self.entry_price = self.data_window.close.values[-1]
                self.entry_time = self.data_window.date.values[-1]
                self.logger.info(
                    f"ENTRY: E:{self.entry_price} at t:{self.entry_time}; type: {self.position_type}"
                )
                self._change_position()

    def _set_current_profits(self):

        self.last_price = self.data_window.close.values[-1]

        if self.position_type == 1:

            self.current_profit = (self.last_price - self.entry_price) - 0.0004 * (
                self.last_price + self.entry_price
            )
            self.current_percentual_profit = (
                self.current_profit / self.entry_price
            ) * 100

        elif self.position_type == -1:

            self.current_profit = -1 * (self.last_price - self.entry_price) - 0.0004 * (
                self.last_price + self.entry_price
            )
            self.current_percentual_profit = (
                self.current_profit / self.last_price
            ) * 100

    def _register_trade_data(self, tp_or_sl):

        self.cum_profit += self.current_percentual_profit * self.leverage
        self.confirmatory_data.append(
            {
                "TP/SL": f"{tp_or_sl}",
                "type": f"{'LONG' if self.position_type == 1 else 'SHORT'}",
                "entry_time": self.entry_time,
                "entry_price": self.entry_price,
                "exit_time": self.exit_time,
                "exit_price": self.exit_price,
                "percentual_difference": self.current_percentual_profit,
                "leveraged percentual_difference": self.current_percentual_profit
                * self.leverage,
                "cumulative_profit": self.cum_profit,
            }
        )

        self.logger.info(
            f"{tp_or_sl}: abs: {self.current_profit}; leveraged %: {self.current_percentual_profit*self.leverage}%; cum_profit: {self.cum_profit}%"
        )

    def _set_actual_profits(self):

        self.current_profit = self.position_type * (
            self.exit_price - self.entry_price
        ) - 0.0004 * (self.exit_price + self.entry_price)

        if self.position_type == 1:
            self.current_percentual_profit = (
                self.current_profit / self.entry_price
            ) * 100
        elif self.position_type == -1:
            self.current_percentual_profit = (
                self.current_profit / self.exit_price
            ) * 100

    def _really_act_on_signal_limit(self):

        if not self.is_positioned:
            if self.strategy.entry_signal(self):
                self.send_orders()
                self._change_position()

        elif self.is_positioned:
            self._set_current_profits()
            if self.strategy.stoploss_check(self):
                try:
                    self._close_position()
                    self._set_actual_profits()
                    self._register_trade_data("SL")
                    self._change_position()
                    self.entry_price = None
                    self.exit_price = None
                except BinanceAPIException as error:
                    self.logger.info(f"sl order, {error}")

            elif self.tp_order is not None:

                self.tp_order = self.client.futures_get_order(
                    symbol=self.symbol.upper(), orderId=self.tp_order["orderId"]
                )
                if self.tp_order["status"] == "FILLED":
                    self.exit_price = float(self.tp_order["avgPrice"])
                    self.qty = self.tp_order["executedQty"]
                    self.exit_time = to_datetime_tz(
                        self.tp_order["updateTime"], unit="ms"
                    )
                    self._set_actual_profits()
                    self._register_trade_data(f"TP")
                    self._change_position()
                    self.entry_price = None
                    self.exit_price = None

    def send_orders(self, protect=False):

        if self.position_type == -1:
            side = "SELL"
            counterside = "BUY"
        elif self.position_type == 1:
            side = "BUY"
            counterside = "SELL"

        try:
            new_position = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type="MARKET",
                quantity=self.qty,
                priceProtect=protect,
                workingType="CONTRACT_PRICE",
            )

        except BinanceAPIException as error:
            print(type(error))
            print("positioning, ", error)
        else:
            self.position = self.client.futures_position_information(
                symbol=self.symbol
            )[-1]
            print(self.position)
            self.entry_price = float(self.position["entryPrice"])
            self.entry_time = to_datetime_tz(self.position["updateTime"], unit="ms")
            # self.qty = self.position[0]["positionAmt"]
            self.tp_price = compute_exit(self.entry_price, self.take_profit, side=side)
            self.logger.info(
                f"ENTRY: E:{self.entry_price} at t:{self.entry_time}; type: {self.position_type}"
            )
            tp_price = self.price_formatter(self.tp_price)
            print(tp_price)
            try:
                self.tp_order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side=counterside,
                    type="LIMIT",
                    price=tp_price,
                    workingType="CONTRACT_PRICE",
                    quantity=self.qty,
                    reduceOnly=True,
                    priceProtect=protect,
                    timeInForce="GTC",
                )
            except BinanceAPIException as error:

                print("tp order, ", error)

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
            self.exit_time = to_datetime_tz(self.closing_order["updateTime"], unit="ms")
