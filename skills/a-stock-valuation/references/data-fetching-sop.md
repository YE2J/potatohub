# 股票数据获取 SOP

> 基于 2026-06-17 实战总结。目标：在东方财富 API 不稳定的情况下稳定拿到行情+行业+K线。

## 三层降级策略

```
┌──────────────────────────────────┐
│ 第1层：push2 + curl               │
│   → 成功：继续                    │
│   → 502/空：不重试，直接降级       │
└──────────────┬───────────────────┘
               │ 失败
               ▼
┌──────────────────────────────────┐
│ 第2层：push2 + web_extract        │
│   → 成功：继续                    │
│   → 502：切搜狐                    │
└──────────────┬───────────────────┘
               │ 失败
               ▼
┌──────────────────────────────────┐
│ 第3层：搜狐证券个股页              │
│   q.stock.sohu.com/cn/{code}/    │
│   → web_extract，静态HTML稳定     │
└──────────────────────────────────┘
```

## 三类数据的最佳获取路径

### 1. K线数据 → push2his + web_extract（首选，几乎 100% 成功）

```
web_extract URL: https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={market}.{code}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&end=20500101&lmt=1&fmt=json

market: 0=深市, 1=沪市
klines格式: 日期,开盘,收盘,最高,最低,成交量,成交额,换手率
```

### 2. 实时报价 → 先 curl 后搜狐

```
# 首选
curl 'https://push2.eastmoney.com/api/qt/stock/get?secid={market}.{code}&fields=f57,f58,f43,f169,f170,f46,f44,f60,f116,f117,f162,f167,f168,f100'

# 如果 502/空，切搜狐
web_extract https://q.stock.sohu.com/cn/{code}/index.shtml
```

搜狐一次返回：收盘价、PE(TTM)、总市值、EV、ROE、毛利率、换手率。

### 3. 行业分类 → 不用 push2，用申万分类体系

push2 的 `fields=f127,f128,f129` 已确认**不可靠**（全员 502）。

替代方案（按推荐顺序）：
1. **本地申万映射表** — 预先拉取全市场分类，后续零 API
2. **web_search 交叉验证** — "股票名 申万行业分类"
3. **Tushare stock_basic** — 兜底，1次/分钟限频

## Tushare 限频参考

| 接口 | 限频 | 适用 |
|------|------|------|
| `stock_basic` | 1次/分钟 | 查行业、基础信息 |
| `daily_basic` | 1次/小时 | 查 PE/PB/市值 |
| `fina_indicator` | - | 财务指标 |

## 反模式（不要做）

- ❌ 同一 URL 用同一工具反复重试 3+ 次（换工具比等重试更有效）
- ❌ 用 push2 的 f127/f128/f129 查行业（必挂）
- ❌ 批量 curl 并发请求 push2（容易触发风控导致全员 502）
- ❌ 在 Tushare 限频后立即重试（额度按小时/分钟计）
