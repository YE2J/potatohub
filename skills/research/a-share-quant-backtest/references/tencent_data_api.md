# 腾讯 ifzq 历史K线API

## 端点

```
GET http://ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,{start},{end},{max},{qfq}
```

## 参数说明

| 参数 | 示例 | 说明 |
|------|------|------|
| market | `sz` | sz=深市(0/3开头), sh=沪市(6开头) |
| code | `000988` | 股票代码，不带市场前缀 |
| start | `2024-01-01` | 开始日期 |
| end | `2026-06-13` | 结束日期 |
| max | `800` | 最大记录数，超过800可能导致截断 |
| qfq | `qfq` | 前复权参数(不加则返回不复权) |

## 请求示例

```bash
# 前复权日线
curl 'http://ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000988,day,2024-01-01,2026-06-13,800,qfq'

# 不复权日线
curl 'http://ifzq.gtimg.cn/appstock/app/kline/kline?param=sz000988,day,2024-01-01,2026-06-13,800'
```

## 响应格式

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "sz000988": {
      "qfqday": [
        ["2025-02-19", "43.302", "45.152", "45.162", "42.852", "621768.000"],
        ...
      ],
      "qt": { ... },
      "mx_price": ...,
      "prec": ...,
      "version": "1.010"
    }
  }
}
```

## K线记录格式

每条K线是一个数组: `[date, open, close, high, low, volume, ...]`

第7个元素（如果存在）是除权息信息对象:
```json
{"nd": "2025", "fh_sh": "2.5", "djr": "2026-06-11", "cqr": "2026-06-12", "FHcontent": "10派2.5元"}
```

## 不支持的端点

| 端点 | 状态 |
|------|------|
| `qt.gtimg.cn/q=sz000988` | ❌ 实时行情，非K线 |
| `web.ifzq.gtimg.cn` | ❌ DNS解析失败 |

## 限制

- 单次最多~800条记录（约2.5年）
- 数据延迟: 一般在收盘后30分钟内更新当日数据
- 前复权(qfq)版本偶有分钟级延迟比不复权版本更慢
- 未验证是否支持分钟线(由 skill `分钟级数据分析` 覆盖)
