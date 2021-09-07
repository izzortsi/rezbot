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
                self.logger.info(f"ENTRY: E:{self.entry_price} at t:{self.entry_time}")
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
                self.entry_price = None
                self.exit_price = None
            except BinanceAPIException as error:
                self.logger.info(f"tp order, {error}")
        elif self.strategy.stoploss_check(self):
            try:
                self._close_position()
                self._set_actual_profits()
                self._register_trade_data("SL")
                self._change_position()
                self.entry_price = None
                self.exit_price = None
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
        self.entry_time = to_datetime_tz(self.position["updateTime"], unit="ms")


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
