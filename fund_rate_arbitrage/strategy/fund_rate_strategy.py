'''
币安资金费率套利策略
'''
import logging
#import telebot#https://pypi.org/project/pyTelegramBotAPI/  用这个代替
import datetime
from api.binance_api import BinanceApi, OrderType, OrderSide, TransferType
from api.binance_future_api import BinanceFutureApi
from config import fund_rate_config, common_config
from fund_rate_arbitrage.util.utils import round_to, day_diff, is_timestamp_over_days
from time import time
import time as tm

class FundRateStrategy(object):
    
    def __init__(self):
        '''
            初始化资金费率
        '''
        self.binance_spot_api = BinanceApi(fund_rate_config.api_key, fund_rate_config.api_secret, **('api_key', 'secret'))
        self.binance_future_api = BinanceFutureApi(fund_rate_config.api_key, fund_rate_config.api_secret, **('api_key', 'secret'))
        #self.tele_bot = telebot.TeleBot(common_config.tele_token, **('token',))
        self.init_business_info()
        self.risk_radio = 0

    
    def check_server(self):
        '''
            检查服务是否可用
        '''
        spot_exchange_info = self.binance_spot_api.get_exchange_info()
        spot_exchange_symbol_list = spot_exchange_info['symbols']
        spot_trade_symbol_info_list = []
        for i in range(len(spot_exchange_symbol_list)):
            exchange_symbol = spot_exchange_symbol_list[i]
            if exchange_symbol['status'] == 'TRADING':
                spot_trade_symbol_info_list.append(exchange_symbol['symbol'])
                if not spot_trade_symbol_info_list:
                    return False
                future_exchange_info = self.binance_future_api.get_exchange_info()
                future_exchange_symbol_list = future_exchange_info['symbols']
                future_trade_symbol_info_list = []
                for i in range(len(future_exchange_symbol_list)):
                    exchange_symbol = future_exchange_symbol_list[i]
                    if exchange_symbol['status'] == 'TRADING':
                        future_trade_symbol_info_list.append(exchange_symbol['symbol'])
                        if not future_trade_symbol_info_list:
                            return False
                        return None

    
    def init_business_info(self):
        '''
        初始化业务信息
        :return:
        '''
        print('初始化业务参数')
        if fund_rate_config.init_flag:
            self.business = {
                'start_date': fund_rate_config.init_start_date }
            self.business['init_spot_total_value'] = fund_rate_config.init_spot_total_value
            self.business['init_future_total_value'] = fund_rate_config.init_future_total_value
        else:
            (business_json, position_list) = self.statistics()
            self.business = {
                'start_date': str(datetime.date.today()) }
            self.business['init_spot_total_value'] = business_json['spot_total_value']
            self.business['init_future_total_value'] = business_json['totalMarginBalance']

    
    def business_log(self):
        '''
            打印日志
        :return:
        '''
        print('打印日志')
        (business_json, position_list) = self.statistics()
        init_value = round_to(float(self.business['init_spot_total_value']) + float(self.business['init_future_total_value']), fund_rate_config.spot_price_asset_precision)
        current_value = round_to(float(business_json['spot_total_value']) + float(business_json['totalMarginBalance']), fund_rate_config.spot_price_asset_precision)
        income_value = round_to(current_value - init_value, fund_rate_config.spot_price_asset_precision)
        self.business['current_value'] = current_value
        self.business['current_count'] = len(position_list)
        leverage = fund_rate_config.trade_symbol_leverage
        amount = float(self.business['current_value'])
        count = fund_rate_config.position_symbol_pool_count
        deposit_max_position_amount = round_to((amount * leverage / (leverage + 1) / count) * 1.5, 0.001)
        withdraw_max_position_amount = round_to((amount * leverage / (leverage + 1) / count) * 1.8, 0.001)
        self.business['withdraw_max_position_amount'] = withdraw_max_position_amount
        self.business['deposit_max_position_amount'] = deposit_max_position_amount
        self.set_funding_rate(position_list)
        if position_list:
            for i in range(len(position_list)):
                trade_symbol_info = position_list[i]
                (deposit_premium_rate, withdraw_premium_rate) = self.get_premium_rate(trade_symbol_info)
                position_list[i]['deposit_premium_rate'] = deposit_premium_rate
                position_list[i]['withdraw_premium_rate'] = withdraw_premium_rate
        (business_json_sport, spot_position_symbol_json_list_sport) = self.get_spot_business_info()
        (position_list_future, position_symbol_list_future) = self.get_position()
        spot_position_symbol_json_list_only = None(None((lambda spot_position = None: spot_position['asset'] + fund_rate_config.spot_price_asset not in position_symbol_list_future), spot_position_symbol_json_list_sport))
        (trade_symbol_list, trade_symbol_info_list) = self.get_trade_symbol_list(fund_rate_config.trade_symbol_pool_count)
        low_funding_rate = fund_rate_config.withdraw_min_fund_rate
        if trade_symbol_info_list:
            low_symbol_info = trade_symbol_info_list[-1]
            low_funding_rate = low_symbol_info['lastFundingRate']
        if trade_symbol_info_list:
            for i in range(len(trade_symbol_info_list)):
                trade_symbol_info = trade_symbol_info_list[i]
                (deposit_premium_rate, withdraw_premium_rate) = self.get_premium_rate(trade_symbol_info)
                trade_symbol_info_list[i]['deposit_premium_rate'] = deposit_premium_rate
                trade_symbol_info_list[i]['withdraw_premium_rate'] = withdraw_premium_rate
        risk_radio = 0
        if float(business_json['totalPositionInitialMargin']) > 0:
            risk_radio = round_to(((float(business_json['totalPositionInitialMargin']) - float(business_json['totalMarginBalance'])) / float(business_json['totalPositionInitialMargin'])) * 100, 0.01)
        if risk_radio < 0:
            risk_radio = 0
        self.risk_radio = risk_radio
        logging.info('\n')
        logging.info('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>币安资金费率套利系统开始<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')
        day = day_diff(self.business['start_date'], str(datetime.date.today()))
        logging.info('--------------------------------------------配置信息--------------------------------------------')
        logging.info(f'''开始日期:{self.business['start_date']},当前日期:{datetime.date.today()},运行天数={round_to(day, 0.1)}''')
        logging.info(f'''交易池最大数量:{fund_rate_config.trade_symbol_pool_count},最大持仓数量:{fund_rate_config.position_symbol_pool_count},当前持仓数量:{len(position_list)}''')
        logging.info(f'''杠杆倍数:{fund_rate_config.trade_symbol_leverage},单次下单金额:{fund_rate_config.single_max_trade_amount},合约最小上架天数:{fund_rate_config.fund_rate_history_count}''')
        logging.info(f'''单个币种持仓金额:{deposit_max_position_amount}-{withdraw_max_position_amount}''')
        logging.info(f'''开仓检查-开仓资金费率下限:{'{:.5f}'.format(fund_rate_config.deposit_min_fund_rate)},开仓溢价率下限:{fund_rate_config.deposit_min_premium_rate},开仓金额上限:{deposit_max_position_amount}''')
        logging.info(f'''平仓检查-平仓资金费率下限:{'{:.5f}'.format(fund_rate_config.withdraw_min_fund_rate)},平仓溢价率下限:{fund_rate_config.withdraw_min_premium_rate},平仓金额下限:{withdraw_max_position_amount}''')
        logging.info(f'''持仓检查-末位资金费率:{low_funding_rate},末位溢价率下限:{'{:.5f}'.format(fund_rate_config.last_eliminate_min_premium_rate)}''')
        logging.info(f'''持仓检查-最大仓位:{self.business['withdraw_max_position_amount']},最大仓位溢价率下限:{'{:.5f}'.format(fund_rate_config.reduce_min_premium_rate)}''')
        logging.info(f'''持仓检查-最大合约风险敞口率:{fund_rate_config.future_risk_warning_threshold}%,当前合约风险敞口率:{risk_radio}%''')
        rate = (float(income_value) / float(init_value)) * 100
        day_rate = rate / float(day)
        if risk_radio >= float(fund_rate_config.future_risk_warning_threshold) and common_config.tele_flag:
            formatted_text = f'''合约风险告警\n合约总金额:{'{:.2f}'.format(float(business_json['totalMarginBalance']))}\n合约持仓金额:{'{:.2f}'.format(float(business_json['totalPositionInitialMargin']))}\n合约风险敞口:{risk_radio}%\n'''
            #self.tele_bot.send_message(common_config.chat_id, formatted_text, **('chat_id', 'text'))
            logging.warning(formatted_text)
        logging.info('--------------------------------------------账户信息--------------------------------------------')
        logging.info(f'''当前金额:{'{:.2f}'.format(current_value)},初始金额:{'{:.2f}'.format(init_value)},收益额: {'{:.4f}'.format(income_value)},收益率:{round_to(rate, 0.0001)}%''')
        logging.info(f'''现货总金额:{'{:.2f}'.format(float(business_json['spot_total_value']))},现货持仓金额:{'{:.2f}'.format(float(business_json['spot_total_position']))},现货可用金额:{'{:.2f}'.format(float(business_json['spot_total_free']))}''')
        logging.info(f'''合约总金额:{'{:.2f}'.format(float(business_json['totalMarginBalance']))},合约持仓金额:{'{:.2f}'.format(float(business_json['totalPositionInitialMargin']))},合约可用金额:{'{:.2f}'.format(float(business_json['availableBalance']))}''')
        logging.info('--------------------------------------------收益信息--------------------------------------------')
        logging.info(f'''总计 收益额:{'{:.4f}'.format(income_value)},收益率:{round_to(rate, 0.0001)}%,日化收益率:{round_to(day_rate, 0.0001)}%,月化收益率:{round_to(day_rate * 30, 0.0001)}%,年化收益率:{round_to(day_rate * 365, 0.0001)}%''')
        if position_list:
            position_list.sort((lambda rate: float(rate['lastFundingRate'])), True, **('key', 'reverse'))
            next_fund_amount = 0
            for i in range(len(position_list)):
                position = position_list[i]
                spot_price = position['spot_price'] if 'spot_price' in position else '0'
                next_fund_amount += float(spot_price) * abs(float(position['positionAmt'])) * float(position['lastFundingRate'])
            rate = round_to((next_fund_amount / current_value) * 100, 0.0001)
            logging.info(f'''当次 收益额:{'{:.4f}'.format(next_fund_amount)},收益率:{rate}%,日化收益率:{round_to(rate * 3, 0.0001)}%,月化收益率:{round_to(rate * 3 * 30, 0.0001)}%,年化收益率:{round_to(rate * 3 * 365, 0.0001)}%''')
            logging.info('--------------------------------------------持仓明细--------------------------------------------')
            for i in range(len(position_list)):
                position = position_list[i]
                spot_amt = position['spot_amt'] if 'spot_amt' in position else '0'
                spot_price = position['spot_price'] if 'spot_price' in position else '0'
                logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(position['symbol'])},资费:{'{:<10}'.format(position['lastFundingRate'])},金额:{'{:<6}'.format(round_to(float(spot_price) * abs(float(position['positionAmt'])), 0.01))},价格:{'{:<6}'.format(round_to(float(spot_price), 1e-05))},平溢:{'{:<8}'.format(round_to(position['withdraw_premium_rate'], 1e-05))},仓位:{round_to(spot_amt, 0.0001)} {round_to(position['positionAmt'], 0.0001)}''')
        if spot_position_symbol_json_list_only:
            logging.info('--------------------------------------------只有现货币种--------------------------------------------')
            for i in range(len(spot_position_symbol_json_list_only)):
                spot_position_symbol_json = spot_position_symbol_json_list_only[i]
                if 'spot_price' in spot_position_symbol_json:
                    amount = round_to(float(spot_position_symbol_json['free']) * float(spot_position_symbol_json['spot_price']), 0.0001)
                    logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<10}'.format(spot_position_symbol_json['asset'])}, 数量:{'{:<10}'.format(spot_position_symbol_json['free'])},现价:{'{:<10}'.format(spot_position_symbol_json['spot_price'])},金额:{'{:<6}'.format(amount)}''')
                else:
                    logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<10}'.format(spot_position_symbol_json['asset'])}, 数量:{'{:<10}'.format(spot_position_symbol_json['free'])}''')
        logging.info('--------------------------------------------币种挑选--------------------------------------------')
        if trade_symbol_info_list:
            for i in range(len(trade_symbol_info_list)):
                trade_symbol_info = trade_symbol_info_list[i]
                logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<10}'.format(trade_symbol_info['symbol'])}, 资费:{'{:<10}'.format(trade_symbol_info['lastFundingRate'])}, 现价:{'{:<10}'.format(round_to(float(trade_symbol_info['markPrice']), 1e-05))}, 开溢:{round_to(trade_symbol_info['deposit_premium_rate'], 1e-05)}''')
        logging.info('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>币安资金费率套利系统结束<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')
        logging.info('\n')
        tm.sleep(6)

    
    def statistics(self):
        '''
        账户信息统计
        :return:
        '''
        (business_json, spot_position_symbol_json_list) = self.get_spot_business_info()
        future_account_info = self.binance_future_api.get_account_info()
        (position_list, position_symbol_list) = self.get_position()
        business_json['totalMarginBalance'] = future_account_info['totalMarginBalance']
        business_json['totalPositionInitialMargin'] = future_account_info['totalPositionInitialMargin']
        business_json['availableBalance'] = future_account_info['maxWithdrawAmount']
        business_json['totalUnrealizedProfit'] = future_account_info['totalUnrealizedProfit']
        if position_list:
            for i in range(len(position_list)):
                future_position = position_list[i]
                for j in range(len(spot_position_symbol_json_list)):
                    spot_position = spot_position_symbol_json_list[j]
                    if future_position['symbol'] == spot_position['asset'] + fund_rate_config.spot_price_asset:
                        future_position['spot_amt'] = round_to(float(spot_position['free']) + float(spot_position['locked']), fund_rate_config.spot_price_asset_precision)
                        future_position['spot_price'] = spot_position['spot_price']
                        return (business_json, position_list)

    
    def get_spot_business_info(self):
        '''
        统计现货账户信息
        :return:
        '''
        spot_account_info = self.binance_spot_api.get_account_info()
        spot_account_balance_list = spot_account_info['balances']
        spot_position_symbol_json_list = []
        spot_position_symbol_list = []
        for i in range(len(spot_account_balance_list)):
            spot_account_balance = spot_account_balance_list[i]
            if not float(spot_account_balance['free']) != 0:
                if float(spot_account_balance['locked']) != 0:
                    spot_position_symbol_json_list.append(spot_account_balance)
                    spot_position_symbol_list.append(spot_account_balance['asset'] + fund_rate_config.spot_price_asset)
                    spot_ticker_price_json_list = self.binance_spot_api.get_all_ticker_price()
                    spot_position_symbol_ticker_price_json_list = []
                    for i in range(len(spot_ticker_price_json_list)):
                        ticker_price_json = spot_ticker_price_json_list[i]
                        if ticker_price_json['symbol'] in spot_position_symbol_list:
                            spot_position_symbol_ticker_price_json_list.append(ticker_price_json)
                            for i in range(len(spot_position_symbol_json_list)):
                                spot_position_symbol_json = spot_position_symbol_json_list[i]
                                for j in range(len(spot_position_symbol_ticker_price_json_list)):
                                    spot_position_symbol_ticker_price_json = spot_position_symbol_ticker_price_json_list[j]
                                    if spot_position_symbol_json['asset'] + fund_rate_config.spot_price_asset == spot_position_symbol_ticker_price_json['symbol']:
                                        spot_position_symbol_json['spot_price'] = spot_position_symbol_ticker_price_json['price']
                                        spot_total_value = 0
                                        spot_total_free = 0
                                        spot_total_position = 0
                                        for i in range(len(spot_position_symbol_json_list)):
                                            spot_position_symbol_json = spot_position_symbol_json_list[i]
                                            if spot_position_symbol_json['asset'] == fund_rate_config.spot_price_asset:
                                                spot_total_value += float(spot_position_symbol_json['free']) + float(spot_position_symbol_json['locked'])
                                                spot_total_free = float(spot_position_symbol_json['free']) + float(spot_position_symbol_json['locked'])
                                            elif 'spot_price' in spot_position_symbol_json:
                                                spot_total_value += (float(spot_position_symbol_json['free']) + float(spot_position_symbol_json['locked'])) * float(spot_position_symbol_json['spot_price'])
                                                spot_total_position += (float(spot_position_symbol_json['free']) + float(spot_position_symbol_json['locked'])) * float(spot_position_symbol_json['spot_price'])
                                                business_json = {
                                                    'spot_total_value': round_to(spot_total_value, fund_rate_config.spot_price_asset_precision) }
                                                business_json['spot_total_free'] = round_to(spot_total_free, fund_rate_config.spot_price_asset_precision)
                                                business_json['spot_total_position'] = round_to(spot_total_position, fund_rate_config.spot_price_asset_precision)
                                                return (business_json, spot_position_symbol_json_list)

    
    def get_history_fund_rate_average(self, symbol, quantity):
        history_fund_rate_list = self.binance_future_api.get_history_funding_rate(symbol, quantity)
        history_fund_rate_sum = 0
        history_fund_rate_average = 0
        if history_fund_rate_list and len(history_fund_rate_list) == quantity:
            for i in range(len(history_fund_rate_list)):
                history_fund_rate_sum += float(history_fund_rate_list[i]['fundingRate'])
            history_fund_rate_average = round_to(history_fund_rate_sum / len(history_fund_rate_list), 1e-06)
        return history_fund_rate_average

    
    def deposit_one_symbol(self, symbol_info, order_amount, position_symbol_list, i):
        '''
            对某个交易对投入进行现货买入 合约卖出
        :param symbol_info:
        :param order_amount:
        :return:
        '''
        self.binance_future_api.post_leverage(symbol_info['symbol'], fund_rate_config.trade_symbol_leverage)
        spot_ticker = self.binance_spot_api.get_ticker(symbol_info['symbol'])
        future_ticker = self.binance_future_api.get_ticker(symbol_info['symbol'])
        spot_buy_order_price = float(spot_ticker['askPrice'])
        future_sell_order_price = float(future_ticker['bidPrice'])
        future_price_asset_free = self.get_future_price_asset_free()
        new_order_quantity = self.get_new_order_quantity(future_price_asset_free, future_sell_order_price, order_amount, spot_buy_order_price, symbol_info)
        spot_buy_amount = spot_buy_order_price * new_order_quantity
        future_sell_amount = future_sell_order_price * new_order_quantity
        if new_order_quantity >= float(symbol_info['spot_quantity_min_qty']) and new_order_quantity >= float(symbol_info['future_quantity_min_qty']) and spot_buy_amount >= float(symbol_info['spot_notional_amount']) and future_sell_amount >= float(symbol_info['future_notional_amount']):
            (deposit_premium_rate, withdraw_premium_rate) = self.get_premium_rate(symbol_info)
            if deposit_premium_rate > fund_rate_config.deposit_min_premium_rate:
                self.deposit_order(symbol_info, new_order_quantity, spot_buy_order_price, future_sell_order_price)
                logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第6关:双重检查单币种溢价率-victory 当前开仓溢价率充足[{'{:<10}'.format(deposit_premium_rate)}>{fund_rate_config.deposit_min_premium_rate}]''')
                if symbol_info['symbol'] not in position_symbol_list:
                    self.business['current_count'] = self.business['current_count'] + 1
                return None
            logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第6关:双重检查单币种溢价率-defeat 当前开仓溢价率不足[{'{:<10}'.format(deposit_premium_rate)}<{fund_rate_config.deposit_min_premium_rate}]''')
        else:
            logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第6关:订单成交数量-defeat 当前开仓数量[{'{:<10}'.format(new_order_quantity)}]，开仓金额[{'{:<10}'.format(future_sell_amount)}]''')

    
    def get_new_order_quantity(self, future_price_asset_free, future_sell_order_price, order_amount, spot_buy_order_price, symbol_info):
        '''
            计算最大下单量
        :param future_price_asset_free:
        :param future_sell_order_price:
        :param order_amount:
        :param spot_buy_order_price:
        :param symbol_info:
        :return:
        '''
        if future_price_asset_free < float(fund_rate_config.single_max_trade_amount):
            return 0
        quantity_precision = float(symbol_info['spot_quantity_precision']) if None(symbol_info['spot_quantity_precision']) >= float(symbol_info['future_quantity_precision']) else float(symbol_info['future_quantity_precision'])
        spot_order_quantity = round_to(order_amount / spot_buy_order_price, quantity_precision)
        future_order_quantity = round_to(future_price_asset_free / future_sell_order_price, quantity_precision)
        if future_order_quantity <= spot_order_quantity:
            new_order_quantity = future_order_quantity
        else:
            new_order_quantity = spot_order_quantity
        return new_order_quantity

    
    def get_future_price_asset_free(self):
        future_account_info = self.binance_future_api.get_account_info()
        future_balance_list = future_account_info['assets']
        future_price_asset_free = 0
        for i in range(len(future_balance_list)):
            if future_balance_list[i]['asset'] == fund_rate_config.future_price_asset:
                future_price_asset_free = round_to(float(future_balance_list[i]['availableBalance']), fund_rate_config.future_price_asset_precision)
            
            return future_price_asset_free

    
    def get_spot_price_asset_free(self):
        '''
            获取现货可用余额
        :return:
        '''
        spot_account_info = self.binance_spot_api.get_account_info()
        spot_price_asset_free = 0
        spot_balance_list = spot_account_info['balances']
        for i in range(len(spot_balance_list)):
            if spot_balance_list[i]['asset'] == fund_rate_config.spot_price_asset:
                spot_price_asset_free = round_to(float(spot_balance_list[i]['free']), fund_rate_config.spot_price_asset_precision)
            
            return spot_price_asset_free

    
    def deposit_order(self, symbol_info, new_order_quantity, spot_order_price, future_order_price):
        '''
            现货和合约下单投入
            上涨行情 先买现货 再卖出合约
            :param spot_order_price:
            :param future_order_price:
            :param new_order_quantity:
            :return:
        '''
        spot_buy_order = self.binance_spot_api.place_order(symbol_info['symbol'], OrderSide.BUY, OrderType.MARKET, round_to(new_order_quantity, symbol_info['spot_quantity_precision']), round_to(spot_order_price, symbol_info['spot_price_precision']), **('symbol', 'order_side', 'order_type', 'quantity', 'price'))
        future_sell_order = self.binance_future_api.place_order(symbol_info['symbol'], OrderSide.SELL.value, OrderType.MARKET.value, round_to(new_order_quantity, symbol_info['future_quantity_precision']), round_to(future_order_price, symbol_info['future_price_precision']), **('symbol', 'order_side', 'order_type', 'quantity', 'price'))
        logging.info(f'''{symbol_info['symbol']}开仓成功''')
        logging.info(f'''现货下买单:quantity={new_order_quantity},price={spot_order_price}''')
        logging.info(f'''合约下卖单:quantity={new_order_quantity},price={future_order_price}''')

    
    def get_premium_rate(self, symbol_info):
        '''
            计算合约和现货的溢价率
        :param symbol_info:
        :return:
        '''
        spot_ticker = self.binance_spot_api.get_ticker(symbol_info['symbol'])
        future_ticker = self.binance_future_api.get_ticker(symbol_info['symbol'])
        deposit_premium_rate = 0
        withdraw_premium_rate = 0
        if spot_ticker and future_ticker:
            deposit_premium_rate = round_to((float(future_ticker['bidPrice']) - float(spot_ticker['askPrice'])) / float(future_ticker['bidPrice']), 1e-06)
            withdraw_premium_rate = round_to((float(spot_ticker['bidPrice']) - float(future_ticker['askPrice'])) / float(spot_ticker['bidPrice']), 1e-06)
        return (deposit_premium_rate, withdraw_premium_rate)

    
    def withdraw_order(self, position, premium_rate):
        '''
        对某个交易对进行平仓
        :param premium_rate:
        :param position:
        :return:
        '''
        symbol = position['symbol']
        (deposit_premium_rate, withdraw_premium_rate) = self.get_premium_rate(position)
        if withdraw_premium_rate < premium_rate:
            logging.info(f'''币种:{symbol} 平仓溢价率={'{:<8}'.format(withdraw_premium_rate)},不能操作。''')
            return None
        quantity_asset = None.replace(fund_rate_config.spot_price_asset, '')
        quantity_precision = float(position['spot_quantity_precision']) if float(position['spot_quantity_precision']) >= float(position['future_quantity_precision']) else float(position['future_quantity_precision'])
        spot_account_info = self.binance_spot_api.get_account_info()
        spot_quantity_asset_free = 0
        spot_quantity_list = spot_account_info['balances']
        for i in range(len(spot_quantity_list)):
            if spot_quantity_list[i]['asset'] == quantity_asset:
                spot_quantity_asset_free = round_to(float(spot_quantity_list[i]['free']), quantity_precision)
            
            future_account_info = self.binance_future_api.get_account_info()
            future_position_list = future_account_info['positions']
            future_quantity_free = 0
            for i in range(len(future_position_list)):
                if future_position_list[i]['symbol'] == symbol:
                    future_quantity_free = round_to(float(future_position_list[i]['positionAmt']), quantity_precision)
                
        new_order_quantity_free = abs(future_quantity_free) if abs(future_quantity_free) <= spot_quantity_asset_free else spot_quantity_asset_free
        spot_ticker = self.binance_spot_api.get_ticker(symbol)
        spot_sell_order_price = float(spot_ticker['bidPrice'])
        max_order_quantity = round_to(fund_rate_config.single_max_trade_amount / spot_sell_order_price, quantity_precision)
        min_order_quantity = round_to(fund_rate_config.single_min_trade_amount / spot_sell_order_price, quantity_precision)
        new_order_quantity = new_order_quantity_free if new_order_quantity_free <= max_order_quantity + min_order_quantity else max_order_quantity
        trade_amount = spot_sell_order_price * new_order_quantity
        if new_order_quantity > min_order_quantity and new_order_quantity >= float(position['spot_quantity_min_qty']) and new_order_quantity >= float(position['future_quantity_min_qty']) and trade_amount >= float(position['spot_notional_amount']) and trade_amount >= float(position['future_notional_amount']):
            (deposit_premium_rate, withdraw_premium_rate) = self.get_premium_rate(position)
            if withdraw_premium_rate < premium_rate:
                logging.info(f'''币种:{symbol} 平仓溢价率={'{:<8}'.format(withdraw_premium_rate)},不能操作。''')
                return None
            spot_ticker = self.binance_spot_api.get_ticker(position['symbol'])
            future_ticker = self.binance_future_api.get_ticker(position['symbol'])
            spot_sell_order_price = float(spot_ticker['bidPrice'])
            future_buy_order_price = float(future_ticker['askPrice'])
            spot_sell_order = self.binance_spot_api.place_order(symbol, OrderSide.SELL, OrderType.MARKET, round_to(new_order_quantity, float(position['spot_quantity_precision'])), spot_sell_order_price)
            future_buy_order = self.binance_future_api.place_order(symbol, OrderSide.BUY.value, OrderType.MARKET.value, round_to(new_order_quantity, float(position['future_quantity_precision'])), future_buy_order_price)
            logging.info(f'''{symbol}平仓完成,平仓溢价率={'{:<8}'.format(withdraw_premium_rate)}>{'{:<8}'.format(premium_rate)}''')
            logging.info(f'''现货下卖单:quantity={new_order_quantity},price={spot_sell_order_price}''')
            logging.info(f'''合约下买单:quantity={new_order_quantity},price={future_buy_order_price}''')

    
    def get_trade_symbol_precision_list(self, trade_symbol_list):
        '''
            获取交易对交易精度
        :param trade_symbol_list:
        :return:
        '''
        trade_symbol_precision_list = []
        exchange_info = self.binance_spot_api.get_exchange_info()
        exchange_symbol_list = exchange_info['symbols']
        if exchange_symbol_list:
            for i in range(len(exchange_symbol_list)):
                inner_symbol_info = exchange_symbol_list[i]
                if inner_symbol_info['symbol'] in trade_symbol_list:
                    trade_symbol = { }
                    trade_symbol['symbol'] = inner_symbol_info['symbol']
                    filter_list = inner_symbol_info['filters']
                    for j in range(len(filter_list)):
                        filter = filter_list[j]
                        if filter['filterType'] == 'PRICE_FILTER':
                            trade_symbol['spot_price_precision'] = filter['tickSize']
                        if filter['filterType'] == 'LOT_SIZE':
                            trade_symbol['spot_quantity_precision'] = filter['stepSize']
                            trade_symbol['spot_quantity_min_qty'] = filter['minQty']
                        if filter['filterType'] == 'NOTIONAL':
                            trade_symbol['spot_notional_amount'] = filter['minNotional']
                            trade_symbol_precision_list.append(trade_symbol)
                            future_exchangeInfo = self.binance_future_api.get_exchange_info()
                            future_symbol_list = future_exchangeInfo['symbols']
                            if future_symbol_list:
                                for i in range(len(future_symbol_list)):
                                    inner_symbol_info = future_symbol_list[i]
                                    if inner_symbol_info['symbol'] in trade_symbol_list:
                                        for j in range(len(trade_symbol_precision_list)):
                                            trade_symbol = trade_symbol_precision_list[j]
                                            if trade_symbol['symbol'] == inner_symbol_info['symbol']:
                                                trade_symbol['future_price_precision'] = 10 ** (-int(inner_symbol_info['pricePrecision']))
                                                trade_symbol['future_quantity_precision'] = 10 ** (-int(inner_symbol_info['quantityPrecision']))
                                                filters = inner_symbol_info['filters']
                                                for filter in filters:
                                                    if filter['filterType'] == 'LOT_SIZE':
                                                        trade_symbol['future_quantity_min_qty'] = filter['minQty']
                                                    if filter['filterType'] == 'MIN_NOTIONAL':
                                                        trade_symbol['future_notional_amount'] = filter['notional']
                                                        return trade_symbol_precision_list

    
    def get_trade_symbol_precision(self, symbol):
        '''
            获取交易对交易精度
        :param trade_symbol:
        :return:
        '''
        trade_symbol = { }
        exchange_info = self.binance_spot_api.get_exchange_info()
        exchange_symbol_list = exchange_info['symbols']
        if exchange_symbol_list:
            for i in range(len(exchange_symbol_list)):
                inner_symbol_info = exchange_symbol_list[i]
                if inner_symbol_info['symbol'] == symbol:
                    trade_symbol['symbol'] = inner_symbol_info['symbol']
                    filter_list = inner_symbol_info['filters']
                    for j in range(len(filter_list)):
                        filter = filter_list[j]
                        if filter['filterType'] == 'PRICE_FILTER':
                            trade_symbol['spot_price_precision'] = filter['tickSize']
                        if filter['filterType'] == 'LOT_SIZE':
                            trade_symbol['spot_quantity_precision'] = filter['stepSize']
                            trade_symbol['spot_quantity_min_qty'] = filter['minQty']
                        if filter['filterType'] == 'NOTIONAL':
                            trade_symbol['spot_notional_amount'] = filter['minNotional']
                            return trade_symbol

    
    def get_trade_symbol_list(self, trade_symbol_count):
        '''
            获取投资交易对
        :return:
        '''
        trade_symbol_list = []
        trade_symbol_info_list = []
        spot_exchange_info = self.binance_spot_api.get_exchange_info()
        spot_exchange_symbol_list = spot_exchange_info['symbols']
        spot_trade_symbol_info_list = []
        for i in range(len(spot_exchange_symbol_list)):
            exchange_symbol = spot_exchange_symbol_list[i]
            if exchange_symbol['status'] == 'TRADING':
                spot_trade_symbol_info_list.append(exchange_symbol['symbol'])
                future_exchange_info = self.binance_future_api.get_exchange_info()
                future_exchange_symbol_list = future_exchange_info['symbols']
                future_trade_symbol_info_list = []
                for i in range(len(future_exchange_symbol_list)):
                    exchange_symbol = future_exchange_symbol_list[i]
                    if exchange_symbol['status'] == 'TRADING' and is_timestamp_over_days(exchange_symbol['onboardDate'], fund_rate_config.fund_rate_history_count):
                        future_trade_symbol_info_list.append(exchange_symbol['symbol'])
                        all_symbol_list = self.binance_future_api.get_all_funding_rate()
                        if all_symbol_list:
                            all_symbol_list.sort((lambda rate: rate['lastFundingRate']), True, **('key', 'reverse'))
                            for i in range(len(all_symbol_list)):
                                inner_symbol_info = all_symbol_list[i]
                                current_fund_rate = float(inner_symbol_info['lastFundingRate'])
                                if current_fund_rate < fund_rate_config.deposit_min_fund_rate:
                                    pass
                                elif str(inner_symbol_info['symbol']).endswith('USDT') and inner_symbol_info['symbol'] in spot_trade_symbol_info_list and inner_symbol_info['symbol'] in future_trade_symbol_info_list:
                                    trade_symbol_list.append(inner_symbol_info['symbol'])
                                    trade_symbol_info_list.append(inner_symbol_info)
                                    if len(trade_symbol_list) >= trade_symbol_count:
                                        pass
                                    
                                    return (trade_symbol_list, trade_symbol_info_list)

    
    def deposit(self):
        '''
        筛选投资币种
        :return:
        '''
        logging.info(f'''''')
        print('筛选投资币种')
        (trade_symbol_list, trade_symbol_info_list) = self.get_trade_symbol_list(fund_rate_config.trade_symbol_pool_count)
        print('投资品种=' + str(trade_symbol_list))
        trade_symbol_precision_list = self.get_trade_symbol_precision_list(trade_symbol_list)
        self.set_funding_rate(trade_symbol_precision_list)
        (position_list, position_symbol_list) = self.get_position()
        print('检查开仓')
        logging.info('-----------------------------------------开仓检查开始-----------------------------------------')
        logging.info(f'''开仓检查 开仓资金费率下限:{'{:.5f}'.format(fund_rate_config.deposit_min_fund_rate)},开仓溢价率下限:{fund_rate_config.deposit_min_premium_rate},开仓金额上限:{self.business['deposit_max_position_amount']}''')
        if trade_symbol_precision_list:
            for i in range(len(trade_symbol_list)):
                trade_symbol = trade_symbol_list[i]
                for j in range(len(trade_symbol_precision_list)):
                    symbol_info = trade_symbol_precision_list[j]
                    if trade_symbol == symbol_info['symbol']:
                        (deposit_premium_rate, withdraw_premium_rate) = self.get_premium_rate(symbol_info)
                        logging.info('')
                        logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第1关:检查资金费率-victory,当前资金费率[{'{:<10}'.format(symbol_info['lastFundingRate'])}>={'{:.5f}'.format(fund_rate_config.deposit_min_fund_rate)}]''')
                        if deposit_premium_rate < fund_rate_config.deposit_min_premium_rate:
                            logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第2关:检查开仓溢价率-defeat 当前开仓溢价率不足[{'{:<10}'.format(str(deposit_premium_rate))}<{fund_rate_config.deposit_min_premium_rate}]''')
                            continue
                    logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第2关:检查开仓溢价率-victory 当前开仓溢价率充足[{'{:<10}'.format(str(deposit_premium_rate))}>{fund_rate_config.deposit_min_premium_rate}]''')
                    (is_less_max_position_amount, max_position_amount, current_amount) = self.is_less_max_position_amount(symbol_info['symbol'])
                    if not is_less_max_position_amount:
                        logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第3关:检查单币种持仓金额-defeat 当前币种持仓金额已满[{round_to(current_amount, 0.0001)}>={max_position_amount}]''')
                        continue
                    logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第3关:检查单币种持仓金额-victory 当前币种持仓金额未满[{round_to(current_amount, 0.0001)}<{max_position_amount}]''')
                    spot_order_amount = self.get_spot_price_asset_free()
                    if spot_order_amount < float(fund_rate_config.single_max_trade_amount) + float(fund_rate_config.single_min_trade_amount):
                        logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第4关:检查USDT余额-defauat USDT现货余额不足[{round_to(spot_order_amount, 0.01)}<{float(fund_rate_config.single_max_trade_amount) + float(fund_rate_config.single_min_trade_amount)}]''')
                        continue
                    logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第4关:检查USDT余额-victory USDT现货余额充足[{round_to(spot_order_amount, 0.01)}>{float(fund_rate_config.single_max_trade_amount) + float(fund_rate_config.single_min_trade_amount)}]''')
                    if spot_order_amount > fund_rate_config.single_max_trade_amount + fund_rate_config.single_min_trade_amount:
                        spot_order_amount = fund_rate_config.single_max_trade_amount
                    if spot_order_amount > fund_rate_config.single_min_trade_amount:
                        count = self.business['current_count']
                        if count >= fund_rate_config.position_symbol_pool_count and trade_symbol not in position_symbol_list:
                            logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第5关:检查持仓币种-defeat 不在持仓品种中,且当前持仓数已满:[{count}={fund_rate_config.position_symbol_pool_count}]''')
                            continue
                    if trade_symbol in position_symbol_list:
                        logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第5关:检查持仓币种-victory 在持仓品种中。''')
                    if count < fund_rate_config.position_symbol_pool_count and trade_symbol not in position_symbol_list:
                        logging.info(f'''{'{:<2}'.format(i + 1)},币种:{'{:<9}'.format(symbol_info['symbol'])},第5关:检查持仓币种-victory 不在持仓品种中,但当前持仓数未满[{count}<{fund_rate_config.position_symbol_pool_count}]''')
                    self.deposit_one_symbol(symbol_info, spot_order_amount, position_symbol_list, i)
        logging.info('-----------------------------------------开仓检查结束-----------------------------------------')

    
    def withdraw(self):
        '''
        平仓逻辑
        :return:
        '''
        print('获取持仓品种')
        logging.info(f'''''')
        (position_list, position_symbol_list) = self.get_position()
        self.set_funding_rate(position_list)
        self.set_precision(position_list, position_symbol_list)
        print('平仓检查')
        logging.info(f'''平仓检查 平仓资金费率下限:{'{:.5f}'.format(fund_rate_config.withdraw_min_fund_rate)},平仓溢价率下限:{fund_rate_config.withdraw_min_premium_rate}''')
        position_list.sort((lambda rate: float(rate['lastFundingRate'])), False, **('key', 'reverse'))
        for i in range(len(position_list)):
            inner_position = position_list[i]
            last_funding_rate = float(inner_position['lastFundingRate'])
            if last_funding_rate < fund_rate_config.withdraw_min_fund_rate:
                logging.info(f'''币种:{inner_position['symbol']} 当前资金费率={'{:.6f}'.format(last_funding_rate)},需要平仓。''')
                self.withdraw_order(inner_position, fund_rate_config.withdraw_min_premium_rate)
                return None

    
    def set_precision(self, position_list, position_symbol_list):
        '''
        设置交易对的精度信息
        :param position_list:
        :param position_symbol_list:
        :return:
        '''
        all_symbol_precision_list = self.get_trade_symbol_precision_list(position_symbol_list)
        for i in range(len(all_symbol_precision_list)):
            symbol_precision = all_symbol_precision_list[i]
            for j in range(len(position_list)):
                inner_position = position_list[j]
                if symbol_precision['symbol'] == inner_position['symbol']:
                    inner_position['spot_price_precision'] = symbol_precision['spot_price_precision']
                    inner_position['spot_quantity_precision'] = symbol_precision['spot_quantity_precision']
                    inner_position['future_price_precision'] = symbol_precision['future_price_precision']
                    inner_position['future_quantity_precision'] = symbol_precision['future_quantity_precision']
                    inner_position['spot_quantity_min_qty'] = symbol_precision['spot_quantity_min_qty']
                    inner_position['future_quantity_min_qty'] = symbol_precision['future_quantity_min_qty']
                    inner_position['spot_notional_amount'] = symbol_precision['spot_notional_amount']
                    inner_position['future_notional_amount'] = symbol_precision['future_notional_amount']
                    return None

    
    def set_funding_rate(self, position_list):
        '''
        设置交易品种的资金费率
        :param position_list:
        :return:
        '''
        all_symbol_funding_rate_list = self.binance_future_api.get_all_funding_rate()
        for i in range(len(all_symbol_funding_rate_list)):
            symbol_funding_rate = all_symbol_funding_rate_list[i]
            for j in range(len(position_list)):
                inner_position = position_list[j]
                if symbol_funding_rate['symbol'] == inner_position['symbol']:
                    position_list[j]['lastFundingRate'] = symbol_funding_rate['lastFundingRate']
                    position_list[j]['nextFundingTime'] = symbol_funding_rate['nextFundingTime']
                    return None

    
    def get_position(self):
        future_account_json = self.binance_future_api.get_account_info()
        totalPositionInitialMargin = future_account_json['totalPositionInitialMargin']
        all_position_list = future_account_json['positions']
        position_list = []
        position_symbol_list = []
        for i in range(len(all_position_list)):
            position = all_position_list[i]
            if float(position['positionAmt']) != 0:
                position['totalPositionInitialMargin'] = totalPositionInitialMargin
                position_list.append(position)
                position_symbol_list.append(position['symbol'])
                return (position_list, position_symbol_list)

    
    def transfer(self):
        '''
        账户划转逻辑
        :return:
        '''
        print('账户划转')
        spot_price_asset_free = self.get_spot_price_asset_free()
        future_account_info = self.binance_future_api.get_account_info()
        future_price_asset_free = round_to(float(future_account_info['maxWithdrawAmount']), fund_rate_config.spot_price_asset_precision)
        future_price_asset_free = future_price_asset_free if future_price_asset_free > 0 else 0
        target_price_asset_free = round_to((spot_price_asset_free + future_price_asset_free) / 2, fund_rate_config.spot_price_asset_precision)
        if target_price_asset_free < spot_price_asset_free:
            spot_to_future_amount = round_to(spot_price_asset_free - target_price_asset_free, fund_rate_config.spot_price_asset_precision)
            if spot_to_future_amount > float(fund_rate_config.single_min_trade_amount):
                self.binance_spot_api.transfer(TransferType.MAIN_UMFUTURE, fund_rate_config.spot_price_asset, spot_to_future_amount)
        if target_price_asset_free < future_price_asset_free:
            future_to_spot_amount = round_to(future_price_asset_free - target_price_asset_free, fund_rate_config.spot_price_asset_precision)
            if future_to_spot_amount > float(fund_rate_config.single_min_trade_amount):
                self.binance_spot_api.transfer(TransferType.UMFUTURE_MAIN, fund_rate_config.spot_price_asset, future_to_spot_amount)

    
    def transaction_fee(self):
        spot_account_info = self.binance_spot_api.get_account_info()
        spot_bnb_asset_free = 0
        spot_balance_list = spot_account_info['balances']
        for i in range(len(spot_balance_list)):
            if spot_balance_list[i]['asset'] == 'BNB':
                spot_bnb_asset_free = round_to(float(spot_balance_list[i]['free']), 0.003)
            
            future_bnb_asset_free = 0
            future_account_info = self.binance_future_api.get_account_info()
            future_asset_list = future_account_info['assets']
            for i in range(len(future_asset_list)):
                if future_asset_list[i]['asset'] == 'BNB':
                    future_bnb_asset_free = round_to(float(future_asset_list[i]['walletBalance']), 0.003)
                
        future_bnb_asset_free = future_bnb_asset_free if future_bnb_asset_free > 0 else 0
        bnb_price_info = self.binance_spot_api.get_ticker_price('BNBUSDT')
        price = float(bnb_price_info['price'])
        spot_bnb_asset_amount = float(spot_bnb_asset_free) * price
        future_bnb_asset_amount = float(future_bnb_asset_free) * price
        spot_usdt_asset_free = self.get_spot_price_asset_free()
        if spot_bnb_asset_amount < 10 and float(spot_usdt_asset_free) > 21:
            spot_buy_amount = round_to(20 / price, 0.001)
            logging.info(f'''现货BNB余额不足，需要买入 [{spot_buy_amount}]个BNB''')
            spot_buy_order = self.binance_spot_api.place_order('BNBUSDT', OrderSide.BUY, OrderType.MARKET, spot_buy_amount, price, **('symbol', 'order_side', 'order_type', 'quantity', 'price'))
        if future_bnb_asset_amount < 10 and spot_bnb_asset_amount > 10:
            spot_to_future_amount = round_to(10 / price, 0.001)
            logging.info(f'''合约BNB余额不足，需要从现货转入[{spot_to_future_amount}]个BNB''')
            self.binance_spot_api.transfer(TransferType.MAIN_UMFUTURE, 'BNB', spot_to_future_amount)

    
    def is_less_max_position_amount(self, symbol):
        positionAmt = 0
        future_account_json = self.binance_future_api.get_account_info()
        all_position_list = future_account_json['positions']
        for i in range(len(all_position_list)):
            position = all_position_list[i]
            if position['symbol'] == symbol:
                positionAmt = abs(float(position['positionAmt']))
            
            price_info = self.binance_spot_api.get_ticker_price(symbol)
            price = float(price_info['price'])
            leverage = fund_rate_config.trade_symbol_leverage
            amount = float(self.business['current_value'])
            count = fund_rate_config.position_symbol_pool_count
            max_position_amount = round_to((amount * leverage / (leverage + 1) / count) * 1.5, 0.001)
            return (float(positionAmt * price) < float(max_position_amount), max_position_amount, positionAmt * price)

    
    def balance(self):
        '''
        # 检查仓位 相差大于50u 需要进行平仓
        # 平衡 一个币种上涨过多 大于3000 就卖掉一份
        :return:
        '''
        logging.info(f'''''')
        print('监控持仓进行仓位平衡')
        (position_list, position_symbol_list) = self.get_position()
        self.set_precision(position_list, position_symbol_list)
        (business_json_sport, spot_position_symbol_json_list_sport) = self.get_spot_business_info()
        (position_list_future, position_symbol_list_future) = self.get_position()
        spot_position_symbol_json_list_only = None(None((lambda spot_position = None: spot_position['asset'] + fund_rate_config.spot_price_asset not in position_symbol_list_future), spot_position_symbol_json_list_sport))
        spot_account_info = self.binance_spot_api.get_account_info()
        all_spot_balance_list = spot_account_info['balances']
        all_spot_balance_list = list(filter((lambda spot_balance: float(spot_balance['free']) > 0), all_spot_balance_list))
        spot_balance_list = None(None((lambda spot_balance = None: spot_balance['asset'] + fund_rate_config.spot_price_asset in position_symbol_list), all_spot_balance_list))
        for i in range(len(position_list)):
            future_position = position_list[i]
            for j in range(len(spot_balance_list)):
                spot_balance = spot_balance_list[j]
                if future_position['symbol'] == spot_balance['asset'] + fund_rate_config.spot_price_asset:
                    future_position['spot_quantity'] = spot_balance['free']
                    if fund_rate_config.difference_check_flag:
                        logging.info('持仓检查-现货合约仓位一致性')
                        for i in range(len(position_list)):
                            future_position = position_list[i]
                            difference = float(future_position['spot_quantity']) - abs(float(future_position['positionAmt']))
                            ticker_price_info = self.binance_spot_api.get_ticker_price(future_position['symbol'])
                            price = float(ticker_price_info['price'])
                            if abs(difference) * price >= fund_rate_config.single_min_trade_amount and future_position['symbol'] != 'BNBUSDT' and future_position['symbol'] != 'BTCUSDT':
                                max_quantity = float(fund_rate_config.single_max_trade_amount) / price
                                if difference > 0:
                                    difference = abs(difference) if abs(difference) < max_quantity else max_quantity
                                    difference = round_to(difference, float(future_position['spot_quantity_precision']))
                                    self.binance_spot_api.place_order(future_position['symbol'], OrderSide.SELL, OrderType.MARKET, difference, price, **('symbol', 'order_side', 'order_type', 'quantity', 'price'))
                                    logging.info(f'''{future_position['symbol']}现货比期货数量多 现货卖出 {difference}''')
                                if difference < 0:
                                    difference = abs(difference) if abs(difference) < max_quantity else max_quantity
                                    difference = round_to(abs(difference), float(future_position['future_quantity_precision']))
                                    self.binance_future_api.place_order(future_position['symbol'], OrderSide.BUY.value, OrderType.MARKET.value, difference, price, **('symbol', 'order_side', 'order_type', 'quantity', 'price'))
                                    logging.info(f'''{future_position['symbol']}期货比现货数量多: 期货需要买入{difference} ''')
                            if abs(float(future_position['positionAmt'])) * price < 10:
                                self.binance_future_api.place_order(future_position['symbol'], OrderSide.BUY.value, OrderType.MARKET.value, abs(float(future_position['positionAmt'])), True, price, **('symbol', 'order_side', 'order_type', 'quantity', 'reduce_only', 'price'))
                                logging.info(f'''{future_position['symbol']}合约持仓金额小于10u,需要平仓{abs(float(future_position['positionAmt']))} ''')
                                if spot_position_symbol_json_list_only:
                                    for i in range(len(spot_position_symbol_json_list_only)):
                                        spot_balance = spot_position_symbol_json_list_only[i]
                                        if 'spot_price' in spot_balance and spot_balance['asset'] == 'BNB' or spot_balance['asset'] == 'USDT':
                                            continue
                                        spot_symbol = spot_balance['asset'] + fund_rate_config.spot_price_asset
                                        ticker_price_info = self.binance_spot_api.get_ticker_price(spot_symbol)
                                        price = 0
                                        if ticker_price_info:
                                            price = float(ticker_price_info['price'])
                                        quantity = float(spot_balance['free'])
                                        trade_amount = price * quantity
                                        precision = self.get_trade_symbol_precision(spot_symbol)
                                        if trade_amount > 10 or trade_amount > fund_rate_config.single_max_trade_amount * 5:
                                            trade_amount = fund_rate_config.single_max_trade_amount * 5
                                            quantity = trade_amount / price
                                        quantity = round_to(quantity, precision['spot_quantity_precision'])
                                        self.binance_spot_api.place_order(spot_symbol, OrderSide.SELL, OrderType.MARKET, quantity, price, **('symbol', 'order_side', 'order_type', 'quantity', 'price'))
                                        logging.info(f'''{spot_symbol}现货比期货数量多 现货卖出 {quantity}''')
        self.set_funding_rate(position_list)
        (trade_symbol_list, trade_symbol_info_list) = self.get_trade_symbol_list(fund_rate_config.trade_symbol_pool_count)
        print('投资品种=' + str(trade_symbol_list))
        trade_symbol_precision_list = self.get_trade_symbol_precision_list(trade_symbol_list)
        self.set_funding_rate(trade_symbol_precision_list)
        low_funding_rate = fund_rate_config.withdraw_min_fund_rate
        if trade_symbol_info_list:
            low_symbol_info = trade_symbol_info_list[-1]
            low_funding_rate = low_symbol_info['lastFundingRate']
        logging.info('')
        logging.info(f'''持仓检查-末位淘汰 末位资金费率:{low_funding_rate},末位溢价率下限:{'{:.5f}'.format(fund_rate_config.last_eliminate_min_premium_rate)}''')
        position_list.sort((lambda rate: float(rate['lastFundingRate'])), False, **('key', 'reverse'))
        for i in range(len(position_list)):
            future_position = position_list[i]
            current_funding_rate = future_position['lastFundingRate']
            if float(current_funding_rate) < float(low_funding_rate) and future_position['symbol'] not in trade_symbol_list:
                logging.info(f'''币种:{future_position['symbol']} 当前资金费率={future_position['lastFundingRate']} 需要末位淘汰。''')
                self.withdraw_order(future_position, fund_rate_config.last_eliminate_min_premium_rate)
                risk_radio = 0
                (business_json, _) = self.statistics()
                if float(business_json['totalPositionInitialMargin']) > 0:
                    risk_radio = round_to(((float(business_json['totalPositionInitialMargin']) - float(business_json['totalMarginBalance'])) / float(business_json['totalPositionInitialMargin'])) * 100, 0.01)
        if risk_radio < 0:
            risk_radio = 0
        if risk_radio >= float(fund_rate_config.future_risk_warning_threshold):
            logging.info('')
            logging.info(f'''持仓检查-仓位上限 最大仓位:{self.business['withdraw_max_position_amount']},最大仓位溢价率下限:{'{:.5f}'.format(fund_rate_config.reduce_min_premium_rate)}''')
            for i in range(len(position_list)):
                future_position = position_list[i]
                ticker_price_info = self.binance_spot_api.get_ticker_price(future_position['symbol'])
                price = float(ticker_price_info['price'])
                quantity = abs(float(future_position['positionAmt']))
                leverage = fund_rate_config.trade_symbol_leverage
                amount = float(self.business['current_value'])
                count = fund_rate_config.position_symbol_pool_count
                max_position_amount = round_to((amount * (leverage / leverage + 1) / count) * 1.8, 0.001)
                if abs(quantity) * price >= max_position_amount:
                    logging.info(f'''币种:{future_position['symbol']} 当前持仓={round_to(abs(quantity) * price, 0.0001)} 持仓上限={max_position_amount} 需要最大仓位减仓''')
                    self.withdraw_order(future_position, fund_rate_config.reduce_min_premium_rate)
                    return None

    
    def get_recent_funding_fee(self, symbol):
        try:
            transactions = self.binance_future_api.get_latest_funding_fee(symbol, 1, **('symbol', 'limit'))
            for transaction in transactions:
                return float(transaction['income'])

        except Exception as e:
            e = float(transaction['income'])
            print(f'''获取资金流水失败: {e}''')
        finally:
            return 0



    
    def job(self):
        '''
        更新[最近一次资金费率总额]
        :return:
        '''
        total_funding_fee = 0
        (position_list, position_symbol_list) = self.get_position()
        for symbol in position_symbol_list:
            fee = self.get_recent_funding_fee(symbol)
            total_funding_fee += fee
        self.resent_total_funding_fee = total_funding_fee

    
    def calculate_resent_funding(self):
        current_timestamp = time()
        if float(current_timestamp) > float(self.next_calculate_funding_time):
            self.job()
            self.next_calculate_funding_time = float(current_timestamp) + 14400

    
    def dust_transfer(self):
        '''
        小额资产替换bnb
        :return:
        '''
        dust_info = self.binance_spot_api.get_dust_info()
        spot_ticker = self.binance_spot_api.get_ticker('BNBUSDT')
        spot_sell_order_price = float(spot_ticker['bidPrice'])
        asset_list = []
        dust_list = dust_info['details']
        if dust_list:
            for i in range(len(dust_list)):
                dust = dust_list[i]
                to_bnb = dust['toBNB']
                if spot_sell_order_price * float(to_bnb) < 5:
                    asset_list.append(dust['asset'])
                    if asset_list:
                        logging.info(f'''小额资产兑换bnb,兑换列表{asset_list}''')
                        assert_list_string = ','.join(asset_list)
                        self.binance_spot_api.do_dust(assert_list_string)

    
    def trade(self):
        '''
            策略主方法
                监控日志输出
                根据风险利率更新交易配置
                检查服务是否可用
                挑选币种进行开仓
                监控持仓进行平仓
                监控持仓进行仓位平衡
                现货和合约之间划转

        :return:
        '''
        self.business_log()
        fund_rate_config.update_config(self.risk_radio)
        trade_able_flag = self.check_server()
        if not trade_able_flag:
            return None
        if None == fund_rate_config.mode:
            self.transfer()
            self.transaction_fee()
            self.deposit()
        self.withdraw()
        self.balance()


