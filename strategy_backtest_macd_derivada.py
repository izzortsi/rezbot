##
from binance.client import Client
from grabber import *
import numpy as np
from bokeh.io import output_file, save
import pandas as pd
##

#parametros

API_KEY = ""
API_SECRET = ""
symbol="BTCUSDT"
tframe="15m"
fromdate="1 month ago"
todate = "5 day ago"
stoploss_parameter = -1.0
take_profit = 2.5
n1=4
n2=4
e1 = 20
e2 = 20
##

##
##
replaced_fromdate = fromdate.replace(" ", "-")
nowdate = lambda: "Now" if todate == None else todate.replace(" ", "-")
filename = f"{symbol}_{tframe}_from={replaced_fromdate}_to={nowdate()}.txt"

##
client = Client(api_key=API_KEY, api_secret=API_SECRET)
grab = GrabberMACD(client)
##

df = grab.compute_indicators(symbol=symbol, tframe=tframe, fromdate=fromdate, todate=todate)

##
class Backtester:

    def __init__(self, client, df, E, X, stoploss_check, bperiod, speriod):
        self.log = []
        self.client = client
        self.df = df
        self.E = E
        self.X = X
        self.stoploss_check = stoploss_check
        self.S = False
        self.Ops = []
        self.profits = []
        self.Entry = [None, None]
        self.eXit = [None, None]
        self.bperiod = bperiod
        self.speriod = speriod
        self.stoploss = None
        self.opscount = 0
        self.trades = []
        

        self.entrydates = []
        self.exitdates = []
        self.entryprices = []
        self.exitprices = []

    def strategy(self, i, dates, prices, indicators):

        price = prices.iloc[i]
        time = dates[i]
        t0, buy_price = self.Entry

        if (self.S and self.X(i, self.stoploss, buy_price, prices, indicators, self.speriod)):
            #ordem de venda
            #aqui vai ser order = ...
            #e if (order["status"] == "FILLED") return (order["orderId"], order["transactTime"], order["price"])
            #else tem que ver issae
            sell_price = float(price)
            eXit = [time, sell_price]
            profit = (sell_price - buy_price)
            percentual_profit = ((sell_price - buy_price)/buy_price)*100
            self.profits.append(percentual_profit)
            res_time = str(time - t0)
            print(f"vendeu a {sell_price} em {time}. Diferença absoluta de: {profit}; Diferença percentual: {percentual_profit}%. Tempo de resolução: {res_time} ")
            
            self.log[self.opscount].append(f"({self.opscount}) vendeu a {sell_price} em {time}. Diferença absoluta de: {profit}; Diferença percentual: {percentual_profit}%. Tempo de resolução: {res_time}.\n")
            self.trades[-1].append(time)
            self.opscount += 1

            self.exitdates.append(time)
            self.exitprices.append(price)

            self.S = not(self.S)

            return self.Entry, self.eXit, profit, res_time, self.S #tem que ver melhor que que precisa retornar

        elif (not(self.S) and self.E(i, prices, indicators, self.bperiod)):

            self.Entry = [time, price]
            print(f"comprou a {price} em {time}")
            self.log.append([f"({self.opscount}) comprou a {price} em {time}.\n"])

            self.entrydates.append(time)
            self.entryprices.append(price)

            self.trades.append([time])
            self.S = not(self.S)

            return None

        else:
            if self.S and self.stoploss_check(i, self.stoploss, buy_price, prices, indicators):
                sell_price = float(price)
                eXit = [time, sell_price]
                profit = (sell_price - buy_price)
                percentual_profit = ((sell_price - buy_price)/buy_price)*100
                #self.profits.append(percentual_profit)
                global stoploss_parameter
                self.profits.append(stoploss_parameter)
                res_time = str(time - t0)
                print(f"Stop-loss: vendeu a {sell_price} em {time}. Diferença absoluta de: {profit}; Diferença percentual: {percentual_profit}%. Tempo de resolução: {res_time} ")

                self.log[self.opscount].append(f"({self.opscount}) STOP-LOSS: Vendeu a {sell_price} em {time}. Diferença absoluta de: {profit}; Diferença percentual: {percentual_profit}%. Tempo de resolução: {res_time}.\n")
                self.trades[-1].append(time)
                self.opscount += 1
                
                self.exitdates.append(time)
                self.exitprices.append(price)
                
                self.S = not(self.S)
                return self.Entry, self.eXit, profit, res_time, self.S

    def backtest(self):

        prices = self.df["close"]
        indicators = self.df.loc[:, self.df.columns != "close"]
        dates = prices.index

        dataset_size = len(dates)
        i = 26 + max(self.bperiod, self.speriod) #26 é o maior número de Nans nas dataframes

        while (i <= dataset_size - 1):
            #print(self.S)
            action = self.strategy(i, dates, prices, indicators)

            if action != None:
                self.Ops.append(action[:-1])

            i += 1

        total_profit = 0
        for profit in self.profits:
            total_profit += profit

        print(f"Lucro percentual aproximado: {total_profit}")
        with open(f"{filename}", "w") as log:
            for i, trade in enumerate(self.log):

                log.writelines(trade)

        log = open(f"{filename}", "a")
        log.write(f"Lucro percentual total: {total_profit}%.")
        log.close()            

        csv_data = []
        for (a, b, c, d, e) in zip(self.entrydates, self.entryprices, self.exitdates, self.exitprices, self.profits):
            csv_data.append([a, b, c, d, e])
            
        csv_name = filename.replace(".txt", ".csv")
        dftrades = pd.DataFrame(data = csv_data, columns = ["entry_date", "entry_price", "exit_date", "exit_price", "profit"])
        dftrades.to_csv(f'{csv_name}', index = False)

        return total_profit, self.trades


##
#entry conditions
def E(i, prices, indicators, period):
    macd = indicators["macd"]
    histogram = indicators["histogram"]
    signal = indicators["signal"]

    if (np.alltrue(histogram.iloc[:i].tail(period) < 0)):
        difs = []
        for h in histogram.iloc[:i].tail(period):
            absdif = abs(histogram.iloc[i] - h)
            difs.append(absdif)
        check = True
        for i, dif in enumerate(difs[1:]):
            if dif > difs[i]:
                check = False
        if check:
            global e1
            if (difs[-1] < e1):
                return True
            else:
                return False
    else:
        return False
    
#stoploss conditions
def stoploss_check(i, stoploss, buy_price, prices, indicators):
    global stoploss_parameter
    return ((prices.iloc[i]/buy_price - 1)*100 <= stoploss_parameter)

#exit conditions
def X(i, stoploss, buy_price, prices, indicators, period):
    
    macd = indicators["macd"]
    histogram = indicators["histogram"]
    signal = indicators["signal"]
    global take_profit
    if (
        ((prices.iloc[i]/buy_price - 1)*100 >= take_profit) and #pelo menos `take_profit` de lucro
        (np.alltrue(histogram.iloc[:i].tail(period) > 0))
        ):

        difs = []
        for h in histogram.iloc[:i].tail(period):
            absdif = abs(histogram.iloc[i] - h)
            difs.append(absdif)
        check = True
        for i, dif in enumerate(difs[1:]):
            if dif > difs[i]:
                check = False
        if check:
            global e2
            if (difs[-1] < e2):
                return True
            else:
                return False
        return True
    else:
        return False
    
    
    



##
backtester = Backtester(client, df, E, X, stoploss_check, n1, n2)
total_profit, trades = backtester.backtest()
##

from looker import Looker

##
replaced_fromdate = fromdate.replace(" ", "-")
nowdate = lambda: "Now" if todate == None else todate.replace(" ", "-")
output_file(f"{symbol}_{tframe}_from={replaced_fromdate}_to={nowdate()}.html")

looker = Looker(df, symbol, tframe, fromdate)

##
p = looker.look(trades=trades)
##
save(p)


##
