### 交割合约规则

https://www.binance.com/zh-CN/support/faq/%E4%BA%A4%E5%89%B2%E5%90%88%E7%B4%84%E7%9A%84%E6%B8%85%E7%AE%97%E8%88%87%E4%BA%A4%E5%89%B2-a3401595e1734084959c61491bc0dbe3
交割流程
季度合約在到期時，會進行交割。系統採用價差交割（現金交割）方式交割。
系統會將到期未平倉合約，以結算價進行平倉。
交割前10分鐘無法開倉，只能減倉或平倉。
結算時刻計算所有未實現盈虧轉成已實現盈虧(暫停5〜10秒)，交割會產生手續費，此手續費也會計入已實現盈虧*，需扣掉交割手續費。
*已實現盈虧 = 倉位大小 * 合約乘數 * （1 / 開倉價 - 1 / 結算價) - 倉位大小*合約乘數* 交割手續費 /結算價
已實現盈虧將計入賬戶餘額，交割清算完成。
交割完成後，該季度合約將關閉，同時產生新的季度合約（同幣種，新合約名稱），新合約上線內10分鐘搭配限價制度*，10分鐘後恢復正常:
*價格上限 = 價格指數 * (1+10%)；價格下限 = 價格指數 * (1-10%)。