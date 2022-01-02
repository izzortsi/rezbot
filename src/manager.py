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
from src.atrader import ATrader


class Manager:
    def __init__(self, api_key, api_secret, rate=1):
        self.traders = {}
        self.client = Client(
            api_key=api_key,
            api_secret=api_secret,
            exchange="binance.com-futures",
        )
        self.bwsm = BinanceWebSocketApiManager(
            output_default="UnicornFy", exchange="binance.com-futures"
        )
        self.rate = rate  # debbug purposes. will be removed

    def start_trader(self, strategy, symbol, leverage=1, is_real=False, qty=0.002):

        trader_name = name_trader(strategy, symbol)

        if trader_name not in self.get_traders():
            trader = ATrader(self, strategy, symbol, leverage, is_real, qty)
            trader._start_new_stream()
            self.traders[trader.name] = trader
            return trader
        else:
            print("Redundant trader. No new thread was created.\n")
            print("Try changing some of the strategy's parameters.\n")

    def get_traders(self):
        return list(self.traders.items())

    def close_traders(self, traders=None):
        """
        fecha todos os traders e todas as posições; pra emerg
        """
        if traders is None:
            # fecha todos os traders
            for name, trader in self.get_traders():
                trader.stop()
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

    def performance_check(self):
        pass

    def market_overview(self):
        """
        isso aqui pode fazer bastante coisa, na verdade pode ser mais sensato
        fazer uma classe que faça as funções e seja invocada aqui.
        mas, em geral, a idéia é pegar várias métricas de várias coins, algo que
        sugira com clareza o sentimento do mercado. eventualmente, posso realmente
        usar ML ou alguma API pra pegar sentiment analysis do mercado
        """
        pass
