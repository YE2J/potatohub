# 腾讯历史K线API参考

## 基本信息

- 域名：`ifzq.gtimg.cn`
- 格式：JSON (UTF-8)
- 限制：支持日期范围控制，~800条以内

## 端点

### 前复权日K线（推荐）
`GET http://ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,{start},{end},{count},qfq`

示例：`sz000988,day,2024-01-01,2026-06-13,800,qfq`

### 不复权日K线
`GET http://ifzq.gtimg.cn/appstock/app/kline/kline?param={market}{code},day,{start},{end},{count}`

示例：`sz000988,day,2024-01-01,2026-06-13,800`

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| market | 深市=sz, 沪市=sh | sz / sh |
| code | 6位代码 | 000988 |
| start/end | 日期范围 | 2024-01-01 |
| count | 最大记录数 | 500（API硬帽，超出只返回最近500条） |

## 市场前缀（关键！）

API 使用**双字母前缀**：深市用 `sz`，沪市用 `sh`。

| 代码开头 | 交易所 | 前缀 |
|---------|--------|------|
| 0, 3, 002, 001 | 深圳 | sz |
| 6, 688, 603, 601, 605 | 上海 | sh |

## 响应字段顺序 (每行)

1. date (str, "2024-01-02")
2. open (str, "43.302")
3. close (str, "45.152")
4. high (str, "45.162")
5. low (str, "42.852")
6. volume (str, "621768.000") — 股数
7. [optional] dict — 除权息信息

## Python代码

```python
import urllib.request, json

# 注意：深市用 sz 前缀，沪市用 sh 前缀（不是单字母 s）
url = f"http://ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000988,day,2024-01-01,2026-06-13,500,qfq"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    obj = json.loads(resp.read().decode("utf-8"))

stock_key = "sz000988"
records = obj["data"][stock_key]["qfqday"]
for rec in records:
    # 前6个字段 = [日期, 开盘, 收盘, 最高, 最低, 成交量]
    # 第7个字段（如果有）是除权息信息字典，必须跳过
    date, open_p, close, high, low, volume = rec[:6]
```

验证结果：每次返回最多 500 条记录，数据每天收盘后更新。
