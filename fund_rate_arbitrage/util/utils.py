'''
'''
import time
from decimal import Decimal
import logging

def round_to(value = None, target = None):
    '''
    Round price to price tick value.
    '''
    value = Decimal(str(value))
    target = Decimal(str(target))
    rounded = float(int(value / target) * target)
    return rounded


def day_diff(day1, day2):
    time_array1 = time.strptime(day1, '%Y-%m-%d')
    timestamp_day1 = int(time.mktime(time_array1))
    time_array2 = time.strptime(day2, '%Y-%m-%d')
    timestamp_day2 = int(time.mktime(time_array2))
    result = (timestamp_day2 - timestamp_day1) // 60 // 60 // 24
    return result

from datetime import datetime,timezone
from math import ceil

def is_timestamp_over_days(timestamp_ms, days_threshold = (30,)):
    timestamp_sec = timestamp_ms / 1000
    timestamp_dt = datetime.utcfromtimestamp(timestamp_sec)
    current_time = datetime.utcnow()
    time_difference = current_time - timestamp_dt
    return time_difference.days > days_threshold


def calculate_days_to_expiry(contract_expiry_str):
    # 将合约交割时间字符串 "YYMMDDHH" 格式转换为 datetime 对象
    # 这里假设时间为早上8点，格式为24小时制
    contract_expiry_datetime = datetime.strptime(contract_expiry_str + "08", '%y%m%d%H')

    # 确保我们使用 UTC timezone
    contract_expiry_datetime = contract_expiry_datetime.replace(tzinfo=timezone.utc)

    # 获取当前UTC时间
    current_datetime = datetime.now(timezone.utc)

    # 计算时间差
    delta = contract_expiry_datetime - current_datetime

    # 返回剩余天数（向上取整，即使只剩几小时也视为一整天）
    return max(1, ceil(delta.total_seconds() / (60 * 60 * 24)))


if __name__ == '__main__':
    print(calculate_days_to_expiry("240628"))