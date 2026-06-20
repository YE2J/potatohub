# 腾讯行情 API (qt.gtimg.cn)

## 端点

```
https://qt.gtimg.cn/q={market}{code}
```

- `market`: `sh`（6/9 开头）或 `sz`（0/3 开头）
- `code`: 6 位股票代码

## 示例

```bash
curl -s "https://qt.gtimg.cn/q=sh600519"   # 贵州茅台
curl -s "https://qt.gtimg.cn/q=sz000988"   # 华工科技
```

## 返回格式

GBK 编码，`~` 分隔。格式：`v_{market}{code}="字段1~字段2~..."`

## 字段索引

| 索引 | 字段 | 说明 |
|------|------|------|
| 1 | name | 股票名称 |
| 2 | code | 股票代码 |
| 3 | price | 当前价格（元） |
| 4 | prev_close | 昨日收盘价 |
| 5 | open | 今日开盘价 |
| 6 | volume | 成交量（手） |
| 30 | time | 更新时间 (YYYYMMDDHHMMSS) |
| 31 | change | 涨跌额 |
| 32 | change_pct | 涨跌幅 (%) |
| 33 | high | 今日最高 |
| 34 | low | 今日最低 |
| 38 | turnover_rate | 换手率 (%) |
| 39 | pe_ttm | 市盈率 (TTM) |
| 44 | float_mv | 流通市值（亿） |
| 45 | total_mv | 总市值（亿） |
| 46 | pb | 市净率 |

## 特点

- **无反爬、无频率限制**：腾讯官方接口，不封 IP
- **GBK 编码**：必须 `.decode('gbk')`
- **进程级缓存**：同一批次内多次调用同一股票可缓存 60 秒避免重复请求
- **数据为上一个交易日收盘数据**：非实时盘中

## Python 解析示例

```python
import urllib.request
import time

_tencent_cache = {}

def fetch_tencent_quote(stock_code: str) -> dict:
    now = time.time()
    if stock_code in _tencent_cache:
        if now - _tencent_cache[stock_code]['_ts'] < 60:
            return _tencent_cache[stock_code]

    market = 'sh' if stock_code.startswith(('6', '9')) else 'sz'
    url = f"https://qt.gtimg.cn/q={market}{stock_code}"
    
    resp = urllib.request.urlopen(url, timeout=8)
    text = resp.read().decode('gbk')
    s = text.find('"')
    e = text.rfind('"')
    fields = text[s+1:e].split('~')
    
    result = {
        'name': fields[1],
        'price': float(fields[3]) if fields[3] else 0,
        'pe_ttm': float(fields[39]) if len(fields) > 39 and fields[39] else 0,
        'pb': float(fields[46]) if len(fields) > 46 and fields[46] else 0,
        'total_mv': float(fields[45]) if len(fields) > 45 and fields[45] else 0,
        'float_mv': float(fields[44]) if len(fields) > 44 and fields[44] else 0,
        'turnover_rate': float(fields[38]) if len(fields) > 38 and fields[38] else 0,
        'change_pct': float(fields[32]) if len(fields) > 32 and fields[32] else 0,
        '_ts': now,
    }
    _tencent_cache[stock_code] = result
    return result
```

## 已知限制

- 仅提供行情数据，无财务数据（营收、净利等）
- 不提供行业分类
- 不提供历史数据（仅当前快照）
