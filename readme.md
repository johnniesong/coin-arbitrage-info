# 简介
平台基于binance交易所  
主文件:calc_basis_coin.py  运行后会在钉钉群按照年化降序输出值得交易的币种,并给与简单评价
计算的年化已经考虑了交易成本

### 注意
需要修改config中fund_rate_config.json 的 key和 secure_key 信息  
lib/dingding.py 中的API信息,在群里添加机器儿(也可以删除钉钉这部分,直接输出)

### 原理简介
基于期现交割合约的价差套利,做买一倍币,卖1倍币本位的交易,除交易所跑路外,100%无风险,交割期结束前平仓.  
肉眼观察,回测历史数据,非深熊有10%年化,牛市年化可达15-20%,深熊几乎没有价差,无法开仓.


### 输出结果举例
* symbol      rate      mean_rate      message
* ADAUSD_241227 11.77% 10.97% 平淡
* ADAUSD_240927 11.44% 11.15% 平淡
* BTCUSD_241227 11.10% 12.01% 平淡
* LTCUSD_240927 10.91% 12.92% 没油水
* ETHUSD_241227 10.56% 11.54% 没油水
* LTCUSD_241227 10.30% 11.88% 没油水
* ETHUSD_240927 9.37% 12.25% 没油水
* XRPUSD_241227 9.22% 10.94% 没油水
* BTCUSD_240927 8.56% 11.07% 没油水
* XRPUSD_240927 8.51% 11.51% 没油水
* LINKUSD_241227 8.36% 10.97% 没油水
* LINKUSD_240927 8.17% 11.82% 没油水
* BCHUSD_241227 4.33% 6.76% 没油水
* DOTUSD_240927 2.16% 4.68% 没油水
* DOTUSD_241227 1.69% 4.51% 没油水
* BNBUSD_241227 -2.10% -2.33% 没油水
* BCHUSD_240927 -8.76% 4.52% 没油水
* BNBUSD_240927 -8.86% -7.09% 没油水

### 详细原理解释:  
https://zhuanlan.zhihu.com/p/690522832


# 其他
1.交割合约规则(建议阅读):https://www.binance.com/zh-CN/support/faq/%E4%BA%A4%E5%89%B2%E5%90%88%E7%B4%84%E7%9A%84%E6%B8%85%E7%AE%97%E8%88%87%E4%BA%A4%E5%89%B2-a3401595e1734084959c61491bc0dbe3 