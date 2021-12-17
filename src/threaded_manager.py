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
import matplotlib.pyplot as plt
import matplotlib.animation as animation

class ThreadedManager:
    def __init__(self, api_key, api_secret, rate=1, tf="5m"):

        self.client = Client(
            api_key=api_key, api_secret=api_secret, exchange="binance.com-futures"
        )
        self.bwsm = BinanceWebSocketApiManager(
            output_default="UnicornFy", exchange="binance.com-futures"
        )

        self.rate = rate  # debbug purposes. will be removed
        self.tf = tf
        self.traders = {}
        self.ta_handlers = {}

        self.is_monitoring = False

    def start_trader(self, strategy, symbol, leverage=1, is_real=False, qty=0.002, w1=5, m1=1.2):

        trader_name = name_trader(strategy, symbol)

        if trader_name not in self.get_traders():

            handler = ThreadedTAHandler(symbol, [self.tf], self.rate)
            self.ta_handlers[trader_name] = handler

            trader = ThreadedATrader(
                self, trader_name, strategy, symbol, leverage, is_real, qty, w1=w1, m1=m1,
            )
            self.traders[trader.name] = trader
            trader.ta_handler = handler
            
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
            avg volatility: {(trader.data_window.close_std/trader.data_window.close_ema).mean()*100}%
            number of trades: {trader.num_trades}
            is positioned? {trader.is_positioned}
            position type: {trader.position_type}
            entry price: {trader.entry_price}
            last price: {trader.last_price}
            TV signals: {[s["RECOMMENDATION"] for s in self.ta_handlers[name].summary]}, {self.ta_handlers[name].signal}
            current percentual profit (unleveraged): {trader.current_percentual_profit}
            cummulative leveraged profit: {trader.cum_profit}
            
            {trader.data_window.tail(3)}
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
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring(sleep)

    def stop_monitoring(self):
        self.is_monitoring = False

    def plot_dw(self, trader):

        data = trader.data_window
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        close_line, = ax.plot(data.close)
        close_ema_line, = ax.plot(data.close_ema)
        cs_line, = ax.plot(data.cs, "g--")
        ci_line, = ax.plot(data.ci, "r--")

        

        def animate(i, trader):
                
            data = trader.data_window
            close_line.set_ydata(data.close)
            close_ema_line.set_ydata(data.close_ema)
            cs_line.set_ydata(data.cs)
            ci_line.set_ydata(data.ci)
            return close_line, close_ema_line, cs_line, ci_line,
            # tf_as_seconds = interval_to_milliseconds(self.trader.strategy.timeframe) * 0.001
            # if (
            #     (trader.data_window.date.values[-1] - trader.data_window.date.values[-2])
            #         >= pd.Timedelta(f"{tf_as_seconds / trader.manager.rate} seconds")
            #     ):
            #         data = trader.data_window
            #         ax.cla()
            #         ax.plot(data.close)
            #         ax.plot(data.close_ema)
            #         ax.plot(data.cs, "g--")
            #         ax.plot(data.ci, "r--")
            # else:
                

# 
        ani = animation.FuncAnimation(fig, animate, fargs=(trader, ), interval=100, blit=True)
        plt.show()

    # def plot_dw(self, trader):
    #     data = trader.data_window
    #     fig = plt.figure()
    #     ax = fig.add_subplot(1, 1, 1)
    #     ax.plot(data.close)
    #     ax.plot(data.close_ema)
    #     ax.plot(data.cs, "g--")
    #     ax.plot(data.ci, "r--")
    #     plt.show()
# import unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager as ubwam
# import datetime as dt


# import matplotlib.animation as animation

# binance_websocket_api_manager = ubwam.BinanceWebSocketApiManager()
# binance_websocket_api_manager.create_stream("trade", "btcusdt", output="UnicornFy")

# xs = []
# ys = []
# title = "Live BTC Price @ Binance.com"
# fig = plt.figure()
# fig.canvas.set_window_title(title)
# ax = fig.add_subplot(1, 1, 1)

# print("Please wait a few seconds until enough data has been received!")














