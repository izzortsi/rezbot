# %%
#
# from unicorn_binance_rest_api.unicorn_binance_rest_api_manager import (
#     BinanceRestApiManager as Client,
# )
#
# from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import (
#     BinanceWebSocketApiManager,
# )
#
# %%


from src import *
from src.threaded_atrader import ThreadedATrader
from src.tradingview_handlers import ThreadedTAHandler
import threading
import time
import asyncio


class ThreadedManager:
    def __init__(self, api_key, api_secret, rate=1):

        self.client = Client(
            api_key=api_key, api_secret=api_secret, exchange="binance.com-futures"
        )
        self.bwsm = BinanceWebSocketApiManager(
            output_default="UnicornFy", exchange="binance.com-futures"
        )

        self.rate = rate  # debbug purposes. will be removed

        self.traders = {}
        self.ta_handlers = {}

        self.is_monitoring = False

    def start_trader(self, strategy, symbol, leverage=1, is_real=False, qty=0.002):

        trader_name = name_trader(strategy, symbol)

        if trader_name not in self.get_traders():

            handler = ThreadedTAHandler(symbol, ["1m"], self.rate)
            self.ta_handlers[trader_name] = handler

            trader = ThreadedATrader(
                self, trader_name, strategy, symbol, leverage, is_real, qty
            )
            self.traders[trader.name] = trader

            return trader
        else:
            print("Redundant trader. No new thread was created.\n")
            print("Try changing some of the strategy's parameters.\n")

    def get_traders(self):
        return list(self.traders.items())

    def get_ta_handlers(self):
        return list(self.ta_handlers.items())

    def close_traders(self, traders=None):
        """
        fecha todos os traders e todas as posições; pra emerg
        """
        if traders is None:
            # fecha todos os traders
            for name, trader in self.get_traders():
                trader.stop()
            for name, handler in self.get_ta_handlers():
                handler.stop()
                del self.ta_handlers[name]

        else:
            # fecha só os passados como argumento
            pass
        pass

    def stop(self, kill=0):
        self.close_traders()
        self.bwsm.stop_manager_with_all_streams()
        if kill == 0:
            os.sys.exit(0)

    def traders_status(self):
        status_list = [trader.status() for _, trader in self.get_traders()]
        return status_list

    def pcheck(self):
        for name, trader in self.get_traders():
            print(
                f"""
            trader: {trader.name}
            number of trades: {trader.num_trades}
            is positioned? {trader.is_positioned}
            position type: {trader.position_type}
            entry price: {trader.entry_price}
            last price: {trader.last_price}
            TV signals: {[s["RECOMMENDATION"] for s in self.ta_handlers[name].summary]}, {self.ta_handlers[name].signal}
            current percentual profit (unleveraged): {trader.current_percentual_profit}
            cummulative leveraged profit: {trader.cum_profit}
                    """
            )

    def market_overview(self):
        """
        isso aqui pode fazer bastante coisa, na verdade pode ser mais sensato
        fazer uma classe que faça as funções e seja invocada aqui.
        mas, em geral, a idéia é pegar várias métricas de várias coins, algo que
        sugira com clareza o sentimento do mercado. eventualmente, posso realmente
        usar ML ou alguma API pra pegar sentiment analysis do mercado
        """
        pass

    def _monitoring(self, sleep):
        while self.is_monitoring:
            self.pcheck()
            time.sleep(sleep)

    def start_monitoring(self, sleep=5):
        self.is_monitoring = True
        self.monitor = threading.Thread(
            target=self._monitoring,
            args=(sleep,),
        )
        self.monitor.setDaemon(True)
        self.monitor.start()
    
    def sm(self, sleep=5):
        self.start_monitoring(sleep)

    def stop_monitoring(self):
        self.is_monitoring = False