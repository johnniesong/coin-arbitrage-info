# Source Generated with Decompyle++
# File: binance_api.pyc (Python 3.9)

import requests
import time
import hmac
import hashlib
import logging
from enum import Enum
from threading import Lock
from config import common_config
from datetime import datetime

class OrderStatus(Enum):
    NEW = 'NEW'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'
    CANCELED = 'CANCELED'
    PENDING_CANCEL = 'PENDING_CANCEL'
    REJECTED = 'REJECTED'
    EXPIRED = 'EXPIRED'


class OrderType(Enum):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'
    STOP = 'STOP'


class RequestMethod(Enum):
    '''
    请求的方法.
    '''
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


class Interval(Enum):
    '''
    请求的K线数据..
    '''
    MINUTE_1 = '1m'
    MINUTE_3 = '3m'
    MINUTE_5 = '5m'
    MINUTE_15 = '15m'
    MINUTE_30 = '30m'
    HOUR_1 = '1h'
    HOUR_2 = '2h'
    HOUR_4 = '4h'
    HOUR_6 = '6h'
    HOUR_8 = '8h'
    HOUR_12 = '12h'
    DAY_1 = '1d'
    DAY_3 = '3d'
    WEEK_1 = '1w'
    MONTH_1 = '1M'


class OrderSide(Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class TransferType(Enum):
    '''
        划转类型
    '''
    MAIN_UMFUTURE = 'MAIN_UMFUTURE'
    UMFUTURE_MAIN = 'UMFUTURE_MAIN'


class BinanceApi(object):
    
    def __init__(self, api_key, secret, host=None, timeout=5, try_counts =5):
        self.api_key = api_key
        self.secret = secret
        self.host = host if host else 'https://api.binance.com'
        self.recv_window = 10000
        self.timeout = timeout
        self.order_count_lock = Lock()
        self.order_count = 1000000
        self.try_counts = try_counts
        self.proxies = {
            'http': 'socks5://127.0.0.1:7890',
            'https': 'socks5://127.0.0.1:7890'
        }


    def build_parameters(self, params: dict):
        keys = list(params.keys())
        keys.sort()
        return '&'.join([f"{key}={params[key]}" for key in params.keys()])

    def request(self, req_method: RequestMethod, path: str, requery_dict=None, verify=False):
        url = self.host + path

        if verify:
            query_str = self._sign(requery_dict)
            url += '?' + query_str
        elif requery_dict:
            url += '?' + self.build_parameters(requery_dict)
        headers = {"X-MBX-APIKEY": self.api_key}

        for i in range(0, self.try_counts):
            try:
                response = requests.request(req_method.value, url=url, headers=headers, timeout=self.timeout,
                                            proxies=self.proxies
                                            )
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"请求没有成功 spot, code: {response.status_code}, text: {response.text} 继续尝试请求")
            except Exception as error:
                print(f"请求:{path}, 发生了错误: {error}, 时间: {datetime.now()}")
                time.sleep(3)

    def get_server_time(self):
        path = '/api/v3/time'
        return self.request(req_method=RequestMethod.GET, path=path)

    def get_exchange_info(self):

        """
        return:
         the exchange info in json format:
        {'timezone': 'UTC', 'serverTime': 1570802268092, 'rateLimits':
        [{'rateLimitType': 'REQUEST_WEIGHT', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200},
        {'rateLimitType': 'ORDERS', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200}],
         'exchangeFilters': [], 'symbols':
         [{'symbol': 'BTCUSDT', 'status': 'TRADING', 'maintMarginPercent': '2.5000', 'requiredMarginPercent': '5.0000',
         'baseAsset': 'BTC', 'quoteAsset': 'USDT', 'pricePrecision': 2, 'quantityPrecision': 3, 'baseAssetPrecision': 8,
         'quotePrecision': 8,
         'filters': [{'minPrice': '0.01', 'maxPrice': '100000', 'filterType': 'PRICE_FILTER', 'tickSize': '0.01'},
         {'stepSize': '0.001', 'filterType': 'LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
         {'stepSize': '0.001', 'filterType': 'MARKET_LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
         {'limit': 200, 'filterType': 'MAX_NUM_ORDERS'},
         {'multiplierDown': '0.8500', 'multiplierUp': '1.1500', 'multiplierDecimal': '4', 'filterType': 'PERCENT_PRICE'}],
         'orderTypes': ['LIMIT', 'MARKET', 'STOP'], 'timeInForce': ['GTC', 'IOC', 'FOK', 'GTX']}]}

        """

        path = '/api/v3/exchangeInfo'
        return self.request(req_method=RequestMethod.GET, path=path)

    def get_order_book(self, symbol, limit=5):
        """
        :param symbol: BTCUSDT, BNBUSDT ect, 交易对.
        :param limit: market depth.
        :return: return order_book in json 返回订单簿，json数据格式.
        """
        limits = [5, 10, 20, 50, 100, 500, 1000]
        if limit not in limits:
            limit = 5

        path = "/api/v3/depth"
        query_dict = {"symbol": symbol,
                      "limit": limit
                      }

        return self.request(RequestMethod.GET, path, query_dict)

    def get_kline(self, symbol, interval: Interval, start_time=None, end_time=None, limit=500, max_try_time=10):
        """
        获取K线数据.
        :param symbol:
        :param interval:
        :param start_time:
        :param end_time:
        :param limit:
        :param max_try_time:
        :return:
        """
        path = "/api/v3/klines"

        query_dict = {
            "symbol": symbol,
            "interval": interval.value,
            "limit": limit
        }

        if start_time:
            query_dict['startTime'] = start_time

        if end_time:
            query_dict['endTime'] = end_time

        for i in range(max_try_time):
            data = self.request(RequestMethod.GET, path, query_dict)
            if isinstance(data, list) and len(data):
                return data

    def get_latest_price(self, symbol):
        """
        :param symbol: 获取最新的价格.
        :return: {'symbol': 'BTCUSDT', 'price': '9168.90000000'}

        """
        path = "/api/v3/ticker/price"
        query_dict = {"symbol": symbol}
        return self.request(RequestMethod.GET, path, query_dict)

    def get_ticker(self, symbol):
        """
        :param symbol: 交易对
        :return: 返回的数据如下:
        {
        'symbol': 'BTCUSDT', 'bidPrice': '9168.50000000', 'bidQty': '1.27689900',
        'askPrice': '9168.51000000', 'askQty': '0.93307800'
        }
        """
        path = "/api/v3/ticker/bookTicker"
        query_dict = {"symbol": symbol}
        return self.request(RequestMethod.GET, path, query_dict)

    def get_all_tickers(self):
        """
        :param symbol: 交易对
        :return: 返回的数据如下:
        {
        'symbol': 'BTCUSDT', 'bidPrice': '9168.50000000', 'bidQty': '1.27689900',
        'askPrice': '9168.51000000', 'askQty': '0.93307800'
        }
        """
        path = "/api/v3/ticker/bookTicker"
        return self.request(RequestMethod.GET, path)

    def get_client_order_id(self):
        """
        generate the client_order_id for user.
        :return:
        """
        with self.order_count_lock:
            self.order_count += 1
            return "x-A6SIDXVS" + str(self.get_current_timestamp()) + str(self.order_count)

    def get_current_timestamp(self):
        """
        获取系统的时间.
        :return:
        """
        return int(time.time() * 1000)

    def _sign(self, params):
        """
        签名的方法， signature for the private request.
        :param params: request parameters
        :return:
        """

        query_string = self.build_parameters(params)
        hex_digest = hmac.new(self.secret.encode('utf8'), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
        return query_string + '&signature=' + str(hex_digest)

    def place_order(self, symbol: str, order_side: OrderSide, order_type: OrderType, quantity: float, price: float,
                    client_order_id: str = None, time_inforce="GTC", stop_price=0):
        """

        :param symbol: 交易对名称
        :param order_side: 买或者卖， BUY or SELL
        :param order_type: 订单类型 LIMIT or other order type.
        :param quantity: 数量
        :param price: 价格.
        :param client_order_id: 用户的订单ID
        :param time_inforce:
        :param stop_price:
        :return:
        """

        path = '/api/v3/order'

        if client_order_id is None:
            client_order_id = self.get_client_order_id()

        params = {
            "symbol": symbol,
            "side": order_side.value,
            "type": order_type.value,
            "quantity": quantity,
            "price": price,
            "recvWindow": self.recv_window,
            "timestamp": self.get_current_timestamp(),
            "newClientOrderId": client_order_id
        }

        if order_type == OrderType.LIMIT:
            params['timeInForce'] = time_inforce

        if order_type == OrderType.MARKET:
            if params.get('price'):
                del params['price']

        if order_type == OrderType.STOP:
            if stop_price > 0:
                params["stopPrice"] = stop_price
            else:
                raise ValueError("stopPrice must greater than 0")

        return self.request(RequestMethod.POST, path=path, requery_dict=params, verify=True)

    def get_order(self, symbol: str, client_order_id: str = ""):
        """
        获取订单状态.
        :param symbol:
        :param client_order_id:
        :return:
        """
        path = "/api/v3/order"
        prams = {"symbol": symbol, "timestamp": self.get_current_timestamp()}
        if client_order_id:
            prams["origClientOrderId"] = client_order_id

        return self.request(RequestMethod.GET, path, prams, verify=True)

    def get_all_orders(self, symbol:str):
        path = "/api/v3/allOrders"
        prams = {"symbol": symbol, "timestamp": self.get_current_timestamp()}

        return self.request(RequestMethod.GET, path, prams, verify=True)

    def cancel_order(self, symbol, client_order_id):
        """
        撤销订单.
        :param symbol:
        :param client_order_id:
        :return:
        """
        path = "/api/v3/order"
        params = {"symbol": symbol, "timestamp": self.get_current_timestamp(),
                  "origClientOrderId": client_order_id
                  }

        for i in range(0, 3):
            try:
                order = self.request(RequestMethod.DELETE, path, params, verify=True)
                return order
            except Exception as error:
                print(f'cancel order error:{error}')
        return

    def get_open_orders(self, symbol=None):
        """
        获取所有的订单.
        :param symbol: BNBUSDT, or BTCUSDT etc.
        :return:
        """
        path = "/api/v3/openOrders"

        params = {"timestamp": self.get_current_timestamp()}
        if symbol:
            params["symbol"] = symbol

        return self.request(RequestMethod.GET, path, params, verify=True)

    def cancel_open_orders(self, symbol):
        """
        撤销某个交易对的所有挂单
        :param symbol: symbol
        :return: return a list of orders.
        """
        path = "/api/v3/openOrders"

        params = {"timestamp": self.get_current_timestamp(),
                  "recvWindow": self.recv_window,
                  "symbol": symbol
                  }

        return self.request(RequestMethod.DELETE, path, params, verify=True)

    def get_account_info(self):
        """
        {'feeTier': 2, 'canTrade': True, 'canDeposit': True, 'canWithdraw': True, 'updateTime': 0, 'totalInitialMargin': '0.00000000',
        'totalMaintMargin': '0.00000000', 'totalWalletBalance': '530.21334791', 'totalUnrealizedProfit': '0.00000000',
        'totalMarginBalance': '530.21334791', 'totalPositionInitialMargin': '0.00000000', 'totalOpenOrderInitialMargin': '0.00000000',
        'maxWithdrawAmount': '530.2133479100000', 'assets':
        [{'asset': 'USDT', 'walletBalance': '530.21334791', 'unrealizedProfit': '0.00000000', 'marginBalance': '530.21334791',
        'maintMargin': '0.00000000', 'initialMargin': '0.00000000', 'positionInitialMargin': '0.00000000', 'openOrderInitialMargin': '0.00000000',
        'maxWithdrawAmount': '530.2133479100000'}]}
        :return:
        """
        path = "/api/v3/account"
        params = {"timestamp": self.get_current_timestamp(),
                  "recvWindow": self.recv_window
                  }
        return self.request(RequestMethod.GET, path, params, verify=True)

    
    def get_my_trade(self = None, symbol = None, limit = None):
        '''
        获取成交历史.
        :param symbol:
        :param limit:
        :return:
        '''
        path = '/api/v3/myTrades'
        prams = {
            'symbol': symbol,
            'timestamp': self.get_current_timestamp(),
            'limit': limit }
        return self.request(RequestMethod.GET, path, prams, verify=True)


    def get_all_ticker_price(self):
        """
        :param symbol: 获取最新的价格.
        :return: {'symbol': 'BTCUSDT', 'price': '9168.90000000'}

        """
        path = '/api/v3/ticker/price'
        return self.request(RequestMethod.GET, path)


    def get_simple_earn_flexible_list(self,asset,size=100):
        """
            查询赚币活期产品列表 (USER_DATA)
        """
        path = '/sapi/v1/simple-earn/flexible/list'
        timestamp = self.get_current_timestamp()
        if asset==None:
            params = {"timestamp": timestamp, "size": size}
        else:
            params = {"timestamp": timestamp, "asset": asset, "size": size}
        return self.request(RequestMethod.GET, path,params, verify=True)

    def get_simple_earn_flexible_rate(self,productId,startTime,endTime,current,size=100):
        """
            查询赚币活期产品费率 (USER_DATA)
            startTime和endTime的最大间隔为3个月
            如果startTime和endTime均未发送，则默认返回最近30天记录
            如果发送了startTime但未发送endTime，则将返回从startTime开始的接下来30天的数据
            如果发送了endTime，但未发送startTime，则会返回endTime之前30天的数据
        """
        timestamp=self.get_current_timestamp()
        path = '/sapi/v1/simple-earn/flexible/history/rateHistorye'
        params={"productId": productId, "startTime": startTime, "endTime": endTime, "current": current, "timestamp": timestamp, "size": size}
        return self.request(RequestMethod.GET, path,params, verify=True)


if __name__ == '__main__':
    # import pandas as pd

    key ="x'x'x"
    secret = "x'x'x"
    binance = BinanceApi(key, secret)

    # import datetime
    # print(datetime.datetime.now())

    # data = binance.get_kline('BTCUSDT', Interval.HOUR_1, limit=100)
    # print(data)
    # print(isinstance(data, list))
    #
    # exit()
    timestamp=binance.get_current_timestamp()
    data=binance.get_simple_earn_flexible_list("usdt")
    #data=binance.get_simple_earn_flexible_rate("USDT001",timestamp,timestamp,1)
    print(data)
