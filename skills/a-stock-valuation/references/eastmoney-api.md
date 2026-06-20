# 东方财富 API 数据获取参考

> 基于 2026-06-16/17 实战踩坑记录。东方财富的免费 API 不稳定，需要掌握重试策略和备用数据源。

## API 端点

### 1. K线数据（最稳定 ✅）

```
URL: https://push2his.eastmoney.com/api/qt/stock/kline/get
参数: secid={market}.{code}, klt=101(日线), fqt=1(前复权), lmt=1(最新1条)
工具: web_extract（几乎总能成功）
```

**示例**（平安银行）：
```
https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000001&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&end=20500101&lmt=1&fmt=json
```

返回格式：klines 数组每项为 `日期,开盘,收盘,最高,最低,成交量,成交额,换手率`

### 2. 实时报价（不稳定 ⚠️）

```
URL: https://push2.eastmoney.com/api/qt/stock/get
参数: secid={market}.{code}, fields=f57,f58,f43,f169,f170,f46,f44,f60,f116,f117,f162,f167,f168,f100
工具: curl 和 web_extract 交替重试
```

**字段说明**：
| 字段 | 含义 | 单位 |
|------|------|------|
| f57 | 股票代码 | - |
| f58 | 股票名称 | - |
| f43 | 最新价 | 分（÷100=元） |
| f60 | 昨收 | 分 |
| f169 | 涨跌额 | 分 |
| f170 | 涨跌幅 | 分（÷100=%） |
| f116 | 总市值 | 分（÷100=元） |
| f117 | 流通市值 | 分 |
| f162 | PE(动) | 分（÷100） |
| f167 | 量比 | 分（÷100） |
| f168 | 换手率 | 分（÷100） |

### 3. 行业分类（经常宕机 ❌）

```
URL: https://push2.eastmoney.com/api/qt/stock/get
参数: fields=f127,f128,f129
状态: 2026-06-17 测试期间全员 502/504，curl/execcode/web_extract 均不可用
```

**备用方案**：Tushare `stock_basic` 接口（申万行业分类），限频 1次/分钟。
或：新浪/同花顺页面抓取申万分类。

## 失败模式与对策

| 失败 | 现象 | 对策 |
|------|------|------|
| 502 Bad Gateway | 报价/行业接口 | **不要反复重试同一工具**，直接降级到搜狐备用 |
| 504 Timeout | web_extract 超时 20s | 换 curl 单独重试 |
| exit code 52 | curl 无响应 | 意味着该股票/接口在 push2 上彻底被封，切搜狐 |
| 空响应 | curl 返回空文件 | 字段组合可能触发 bug，换工具 |
| Tushare 40203 | daily_basic 1次/小时，stock_basic 1次/分钟 | 只在其他途径全失败时才用，不浪费配额 |
| 特定股票被"拉黑" | 300750/600276 持续 502 而其他正常 | 这些股票路由到故障后端，直接切搜狐 |

## 批量拉取策略

1. 先用 `web_extract` 并行拉取所有 K 线（最稳，一次 4 个 URL）
2. 用 `curl` 拉取报价，失败换 `web_extract`，再失败切**搜狐**
3. 行业分类：**不用** push2 的 `f127/f128/f129`（几乎必挂），直接用本地申万映射表或多源验证
4. 每类数据保持 **2 个独立来源**：push2 + 搜狐/Tushare

## 备用数据源：搜狐证券

东方财富 push2 不稳定时，搜狐证券个股页是最佳兜底：

```
URL: https://q.stock.sohu.com/cn/{CODE}/index.shtml
工具: web_extract（静态 HTML，非 JS 渲染，稳定）
```

**一次调用可拿到**：收盘价、PE(TTM)、总市值、EV、ROE、毛利率、换手率、主营业务构成、分析师目标价。

**示例**（宁德时代）：
```
web_extract https://q.stock.sohu.com/cn/300750/index.shtml
→ PE=23.64, 市值=1.87万亿, EV=2.19万亿, ROE=21.9%, 毛利率=24.8%
```

搜狐页面数据远多于 push2 报价接口，代价是页面更大、解析更慢。建议作为兜底备用，非首选。

## 行业分类获取（push2 f127/f128 不可用）

push2 的行业字段（`fields=f127,f128,f129`）在 2026-06-17 测试中**全员 502**，curl/web_extract 均无法获取。

**替代方案**：
1. **本地申万映射表**（推荐）— 一次性拉取全市场分类存 JSON，后续零 API 调用
2. **web_search 交叉验证** — 搜"股票名 申万行业分类"，新浪/同花顺页面均可确认
3. **Tushare stock_basic**（兜底）— 限频 1次/分钟，作为最后手段

## Tushare 频率限制（实测）

| 接口 | 实际限频 | 备注 |
|------|---------|------|
| `stock_basic` | **1次/分钟** | 适用于基础信息 |
| `daily_basic` | **1次/小时** | 适用于 PE/PB/市值等日指标 |

## 数据缓存目录

所有原始 JSON 缓存到 `~/.hermes/skills/a-stock-valuation/data/{code}_{type}.json`：
- `{code}_quote.json` — 实时报价
- `{code}_industry.json` — 行业分类
- `{code}_kline.json` — 日K线
