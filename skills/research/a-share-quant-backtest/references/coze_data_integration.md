# Coze/恒生聚源 数据源集成方案

## 架构概览

```
Coze Agent (恒生聚源 MCP)
    ↓ 每日 01:05 (系统 crontab)
coze_incremental_update.py
    ↓ 写入 dz_dailyquote 表 (5527只全A股, ~132万行)
StockDataManager.load_to_dataframe()
    ↓ InnerCode 映射加载 → SQL 查询 → OHLCV 标准化
回测/指标引擎 (bridge.py → indicators → backtest_v4)
```

## dz_dailyquote 表结构

```sql
CREATE TABLE dz_dailyquote (
    ID INTEGER,
    InnerCode INTEGER NOT NULL,
    TradingDay TEXT NOT NULL,       -- 日期 (YYYY-MM-DD)
    PrevClosePrice REAL,            -- 昨收
    OpenPrice REAL,                 -- 今开
    HighPrice REAL,                 -- 最高
    LowPrice REAL,                  -- 最低
    ClosePrice REAL,                -- 收盘
    TurnoverVolume REAL,            -- 成交量 (股)
    TurnoverValue REAL,             -- 成交额 (元)
    TurnoverDeals INTEGER,          -- 成交笔数
    PRIMARY KEY (InnerCode, TradingDay)
);
```

## InnerCode 映射加载

恒生聚源用 InnerCode (int) 标识股票，回测系统用 stock_code (str, 如 "000988")。
映射文件: `~/my_quant_system/all_ashare_stocks.csv` (5528行)

### 映射加载模式: 函数属性静态缓存

```python
@staticmethod
def _load_inner_code_map() -> dict:
    if hasattr(StockDataManager._load_inner_code_map, "_cache"):
        return StockDataManager._load_inner_code_map._cache
    # 首次加载: 读 CSV → 构建 {SecuCode: InnerCode} 映射
    # 结果存入函数属性 _cache, 后续调用直接返回
    ...
    StockDataManager._load_inner_code_map._cache = code_map
    return code_map
```

**优势**: 无需类实例、无需全局变量、Python 进程生命周期内自动生效。
**适用于**: 任何需要从 CSV/SQLite 加载一次性映射的场景。

## 字段映射

| dz_dailyquote | 标准化列名 | 备注 |
|--------------|-----------|------|
| TradingDay | date | YYYY-MM-DD 格式 |
| OpenPrice | open | — |
| HighPrice | high | — |
| LowPrice | low | — |
| ClosePrice | close | 原始不复权收盘价 |
| TurnoverVolume | volume | 单位: 股 (与 daily_kline 一致) |
| TurnoverValue | amount | 单位: 元 (与 daily_kline 一致) |
| PrevClosePrice | (衍生) | 用于计算 pct_change / change / amplitude |

### 衍生字段计算

```python
df["pct_change"] = ((df["close"] - df["PrevClosePrice"]) / df["PrevClosePrice"] * 100).round(2)
df["change"]    = (df["close"] - df["PrevClosePrice"]).round(3)
df["amplitude"] = ((df["high"] - df["low"]) / df["PrevClosePrice"] * 100).round(2)
```

- **pct_change**: 标准涨跌幅公式，与通达信一致
- **amplitude**: (最高-最低)/昨收×100，与通达信一致
- **注意**: dz_dailyquote 数据是不复权的原始成交价。通达信指标公式 (GS/主力雷达/AI活跃度) 只依赖原始 OHLCV，不受复权影响

## Fallback 链路

```
load_to_dataframe(code, start, end)
  ├── ① dz_dailyquote (主数据源) — 5527只全A股, 2025-06-23 起
  │   ├── InnerCode 映射存在? → 查询 dz_dailyquote
  │   └── CSV 不存在 / InnerCode 无映射 / 查询异常 → 跳转到 ②
  ├── ② daily_kline (历史 fallback) — 腾讯API旧数据, 覆盖更早历史
  │   └── 表无数据 → 跳转到 ③
  └── ③ Parquet (最终 fallback) — 最旧备份
```

**设计原则**: 链路自动降级，不抛异常。回测期间某个数据源出问题不影响已有结果。

## 复权说明

⚠️ **2026-06-24 致命问题已修复**：恒生聚源 dz_dailyquote 提供的是**不复权原始价**，而通达信指标（GS信号/主力雷达/MACD等）基于前复权价格计算。除权除息日不复权价格会导致假信号。

**修复方案**：`_load_from_dz_dailyquote()` 中自动 LEFT JOIN `adj_factors` 表（Tushare 复权因子），计算 `adjusted_price = raw_price × adj_factor`，PrevClosePrice 用前一日 adj_factor 调整后重算衍生字段。Volume 不做复权。

详见 `references/adj_factor_pipeline.md`。

## 数据覆盖

| 维度 | 数值 |
|------|------|
| 股票数 | 5,527 只（全 A 股） |
| 时间范围 | 2025-06-23 起（约 1 年） |
| 总行数 | ~132.5 万 |
| 更新频率 | 每日 01:05 增量（系统 crontab） |
| 数据源质量 | 恒生聚源（专业金融数据供应商） |

## 已知限制

1. **仅覆盖1年历史** (2025-06-23 起) — 更早的回测通过 daily_kline fallback
2. **Coze PAT 30天有效期** — `~/.coze_token` 约需每月续期，`coze_incremental_update.py` 已有 PAT 过期检测
3. **dz_dailyquote 为不复权数据** — 已通过 `adj_factors` 表 + 前复权计算修复。`pull_adj_factors.py` 可批量拉取复权因子
4. **日期格式不一致** — `dz_dailyquote.TradingDay` 用 `YYYY-MM-DD`，查询时需转换参数格式
