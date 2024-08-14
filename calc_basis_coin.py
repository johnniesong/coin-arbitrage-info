import os,sys,time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.binance_api import BinanceApi
from api.binance_future_api_coin import BinanceFutureApiCoin
from fund_rate_arbitrage.util.utils import calculate_days_to_expiry

from datetime import datetime, timezone, timedelta
from config import fund_rate_config, common_config
import os
from lib.dingding import send_alert_msg,DINGDING_INFO_API


class CalcFundRateV2:
    def __init__(self,config=fund_rate_config):
        fund_rate_config = config
        ak=fund_rate_config.api_key
        sk=fund_rate_config.api_secret
        self.binance_spot_api = BinanceApi(ak,sk)
        self.binance_future_api_coin = BinanceFutureApiCoin(ak,sk)

    def get_trade_symbol_list(self):
        '''
            获取投资交易对
        :return:
        '''
        trade_symbol_list = []
        exchange_info = self.binance_future_api_coin.get_exchange_info()
        exchange_symbol_list = exchange_info['symbols']
        for i in range(len(exchange_symbol_list)):
            exchange_symbol = exchange_symbol_list[i]
            if exchange_symbol['contractStatus'] == 'TRADING' and (exchange_symbol['contractType']=='CURRENT_QUARTER' or exchange_symbol['contractType']=='NEXT_QUARTER'):

                trade_symbol_list.append((exchange_symbol['symbol'],exchange_symbol['contractType']))

        return trade_symbol_list


    #当前仅用于人工通知提醒用,所以每15分钟检查一次,如果有通知,则静默1H.后续再看是否需要做自动成交.感觉必要性不大.因为很长期.
    def fetch_and_process_data(self,symbol,pair,future_type,period,limit):
        results = {}

        basis_info = self.binance_future_api_coin.get_current_basis(pair, future_type, period, limit=limit)
        if basis_info:
            data = basis_info[0]
            adjusted_annualized_basis_rate=self.calculate_annualized_yield(data,symbol.split("_")[1])
            #adjusted_annualized_basis_rate= float(data["annualizedBasisRate"])
            # 存储处理过的数据
            key = f"{pair}_{future_type}"
            results[key] = adjusted_annualized_basis_rate

        return results

    def calculate_annualized_yield(self,item,contract_expiry_str, cost_percent=0.0025):
        index_price = float(item["indexPrice"])
        basis = float(item["basis"])
        # 设定一年的总天数，大多数加密货币市场视为365天
        days_in_year = 365

        # 计算交割合约购买时的全价 (包含成本)
        total_cost = index_price * (1 + cost_percent)
        # 计算合约的回报
        future_return = index_price + basis - total_cost
        period_to_expiry_days = calculate_days_to_expiry(contract_expiry_str)
        #print(f"future_return:{future_return},full_trade_cost:{cost_percent*index_price}")
        # 计算年化收益率
        annualized_yield = (future_return / total_cost) * (days_in_year / period_to_expiry_days)

        # 格式化输出年化收益率，保留2位小数
        return round(annualized_yield, 5)

    def calculate_annualized_mean(self, symbol,pair, future_type, period, limit):
        # 获取多个数据点
        basis_info_list = self.binance_future_api_coin.get_current_basis(pair, future_type, period, limit=limit)
        #获取上一个交割时间,新的计算需要大于这个交割时间,才是真正当期的
        last_deliver_time=self.binance_future_api_coin.get_current_delivery_price(pair)[0]['deliveryTime']

        total_annualized_basis_rate=0
        count=0
        if basis_info_list:
            for item in basis_info_list:
                adjusted_annualized_basis_rate = self.calculate_annualized_yield(item,symbol.split("_")[1])
                if item['timestamp']>last_deliver_time:
                    total_annualized_basis_rate+=adjusted_annualized_basis_rate
                    count+=1

            mean_annualized_basis_rate = total_annualized_basis_rate / count
            return mean_annualized_basis_rate
        else:
            return None

    def print_sorted_by_annualized_rate(self,data):
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        for key, value in sorted_data:
            print(f"{key}: {value*100:.2f}%")

    #提醒平仓快到期的交割合约
    def withdraw_remind(self):
        return

    def check_and_alert(self, symbol,pair, future_type, period_short, limit_short, period_long, limit_long,multiplier_low,multiplier_high,limit_apy):
        # 获取单个数据点的当前年化基础利率
        result=[]
        current_data = self.fetch_and_process_data(symbol,pair, future_type, period_short, limit_short)
        # 获取多个数据点用于计算均值的年化基础利率
        mean_annualized_basis_rate = self.calculate_annualized_mean(symbol,pair, future_type, period_long, limit_long)

        if current_data and mean_annualized_basis_rate:
            current_rate = list(current_data.values())[0]  # 获取当前年化基础利率
            print(f"当前年化利率: {current_rate*100:.4f}%")
            print(f"均值年化利率: {mean_annualized_basis_rate*100:.4f}%")
            #print(f"当前/均值: {current_rate/mean_annualized_basis_rate:.2f}")
            print(f"高线1: {mean_annualized_basis_rate*multiplier_low*100:.2f}")
            print(f"高线2: {mean_annualized_basis_rate*multiplier_high*100:.2f}")
            print(f"低线1: {mean_annualized_basis_rate / multiplier_low * 100:.2f}")
            print(f"低线2: {mean_annualized_basis_rate / multiplier_high * 100:.2f}")


            alert_message = ""
            if current_rate*100 <limit_apy:
                alert_message = f"没油水"
            else:
                if current_rate > mean_annualized_basis_rate * multiplier_high:
                    alert_message = f"!!无敌：{symbol} 的当前年化率 ({current_rate}) 超过30天均值 ({mean_annualized_basis_rate}) 的{multiplier_high}倍以上。"
                # elif current_rate < mean_annualized_basis_rate / multiplier_high:
                #     alert_message = f"警告：{symbol} 的当前年化率 ({current_rate}) 不到20天均值 ({mean_annualized_basis_rate}) 的一半。"
                elif current_rate > mean_annualized_basis_rate * multiplier_low:
                    alert_message = f"!!可以：{symbol} 的当前年化率 ({current_rate}) 超过30天均值 ({mean_annualized_basis_rate}) 的{multiplier_low}倍以上。"
                # elif current_rate < mean_annualized_basis_rate / multiplier_low:
                #     alert_message = f"提示：{symbol} 的当前年化率 ({current_rate}) 不到20天均值 ({mean_annualized_basis_rate}) 的1.5倍。"
                elif current_rate*100>20:
                    alert_message = f"!!激动：{symbol} 的当前年化率 ({current_rate}) 超过20%。"
                elif current_rate*100>17:
                    alert_message = f"!!挺好：{symbol} 的当前年化率 ({current_rate}) 超过17%。"
                else:
                    alert_message=f"平淡"

            if alert_message:
                print(alert_message)

            result.append({"symbol": symbol, "rate": current_rate, "mean_rate": mean_annualized_basis_rate, "alert_message": alert_message})
        return result

#获取交易对的基差详情,小时级别,支持排序输出
def get_symbol_basis_detail(symbol,order):
    future_types = ["CURRENT_QUARTER", "NEXT_QUARTER"]
    # period = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
    periods = ["1h"]

    fund_rate_config.loads(
        os.path.join(os.path.dirname(os.path.abspath(__file__))) + "/../config/json/fund_rate_config.json")
    calc = CalcFundRateV2(fund_rate_config)

    for future_type in future_types:
        for period in periods:
            print("--------------------future_type:", future_type, "period:", period,"-------------------------------------")
            basis_info = calc.binance_future_api_coin.get_current_basis(symbol, future_type, period, 500)

            if order== "asc":
                sorted_basis_info = sorted(basis_info, key=lambda x: float(x['basisRate']))
            elif order== "desc":
                sorted_basis_info = sorted(basis_info, key=lambda x: float(x['basisRate']), reverse=True)
            else:
                sorted_basis_info = basis_info

            for item in sorted_basis_info:
                adjusted_annualized_basis_rate=item["annualizedBasisRate"]

                print(datetime.fromtimestamp(item["timestamp"] / 1000, timezone.utc))
                if len(adjusted_annualized_basis_rate) > 1:
                    print(f"apy:{float(adjusted_annualized_basis_rate)*100:.4f}%")
                print(f"basisRate:{item['basisRate']}")
                print(f"basis:{item['basis']}")


# 计算所有交易对的年化基础利率,按年化降序排列
def calc_top_basis_coin():
    #future_types = ["CURRENT_QUARTER", "NEXT_QUARTER"]
    # period = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]
    periods = ["15m"]

    fund_rate_config.loads(
        os.path.join(os.path.dirname(os.path.abspath(__file__))) + "/../config/json/fund_rate_config.json")
    calc = CalcFundRateV2(fund_rate_config)

    # 假设这是你要检索的数据历史开始日期
    trade_symbol_list = calc.get_trade_symbol_list()

    # 调用函数并打印结果
    basis_results = {}
    print("--------------------------fetch_and_process_data-------------------------------")
    for symbol,future_type in trade_symbol_list:
        print("symbol:", symbol)
        pair=symbol.split("_")[0]
        for period in periods:
            print("future_type:", future_type, "period:", period)
            basis_results.update(calc.fetch_and_process_data(symbol,pair, future_type, period, 1))

    print("--------------------------print_sorted_by_annualized_rate-------------------------------")
    calc.print_sorted_by_annualized_rate(basis_results)

#计算当前和均值,如果出现激增,则提醒开仓\平仓
def calc_open_or_withdraw_timing():
    #future_types = ["CURRENT_QUARTER", "NEXT_QUARTER"]
    period_short = "15m"
    limit_short = 1
    period_long = "1d"
    limit_long = 30

    multiplier_low = 1.5
    multiplier_high = 2

    limit_apy=11

    fund_rate_config.loads(
        os.path.join(os.path.dirname(os.path.abspath(__file__))) + "/../config/json/fund_rate_config.json")
    calc = CalcFundRateV2(fund_rate_config)

    # 假设这是你要检索的数据历史开始日期
    trade_symbol_list = calc.get_trade_symbol_list()

    print("--------------------------calc_open_or_withdraw_timing-------------------------------")
    total_result=[]
    for symbol,future_type in trade_symbol_list:
        print("symbol:", symbol)
        pair=symbol.split("_")[0]
        print(f"{pair}_{future_type}")
        result=calc.check_and_alert(
            symbol,
            pair,
            future_type,
            period_short,
            limit_short,
            period_long,
            limit_long,
            multiplier_low,
            multiplier_high,
        limit_apy)
        total_result.extend(result)
        print("-----------------------------------------------------------------------------------")

    total_result=sorted(total_result, key=lambda x: x["rate"], reverse=True)

    formatted_string = "symbol      rate      mean_rate      message\n"

    # 迭代列表, 格式化每个元素后添加到字符串中
    for item in total_result:
        line = f"{item['symbol']} {item['rate']*100:.2f}% {item['mean_rate']*100:.2f}% {item['alert_message']}\n"
        formatted_string += line

    print(formatted_string)
    send_alert_msg("信息群",formatted_string,[],DINGDING_INFO_API)

if __name__ == '__main__':
    #calc_top_basis_coin()#计算所有交易对的年化基础利率,按年化降序排列.按需使用
    calc_open_or_withdraw_timing()#计算当前和均值,如果出现激增,则提醒开仓\平仓
    #get_symbol_basis_detail("ETHUSD",order="normal")#获取某个交易对的基差详情.按需使用

