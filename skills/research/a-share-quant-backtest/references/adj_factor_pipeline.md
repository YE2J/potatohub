# 复权因子管线

## 背景

`dz_dailyquote`（恒生聚源，Coze管道）存储的是**不复权原始价**。通达信指标（GS信号、主力雷达、MACD等）基于前复权价格计算，直接使用不复权价格会在除权除息日产生假信号。

## 架构

```
Tushare adj_factor API → pull_adj_factors.py → adj_factors 表
                                                      ↓
dz_dailyquote ───→ _load_from_dz_dailyquote() ───→ LEFT JOIN adj_factors
                                                      ↓
                                              adjusted_price = raw × adj_factor
```

## adj_factors 表

```sql
CREATE TABLE adj_factors (
    InnerCode INTEGER NOT NULL,
    TradingDay TEXT NOT NULL,       -- YYYY-MM-DD 格式
    adj_factor REAL NOT NULL,
    PRIMARY KEY (InnerCode, TradingDay)
);
```

## 复权计算逻辑（data_manager.py）

1. 从 `dz_dailyquote` 查出原始 OHLCV + PrevClosePrice
2. LEFT JOIN `adj_factors` 获取当日复权因子
3. OHLC 价格 × adj_factor（当日）
4. PrevClosePrice × prev_adj_factor（前一日 adj_factor）
5. 重算 pct_change/change/amplitude
6. Volume 不变（成交股数不受除权影响）
7. adj_factor 缺失 → fillna(1.0) + log warning

## 拉取工具：pull_adj_factors.py

```bash
# 指定股票
python pull_adj_factors.py --codes 000988,301338

# 全量（所有自选股）
python pull_adj_factors.py --all

# 检查覆盖情况
python pull_adj_factors.py --check
```

## Tushare API 限制

- `adj_factor` 接口频率：1次/小时
- 首次拉取建议分批执行，每小时一次
- 全量覆盖 5527 只A股需要较长时间

## 当前覆盖状态（2026-06-30）

| 股票 | InnerCode | adj_factors | 实际影响 |
|------|-----------|-------------|---------|
| 000988 华工科技 | 605 | ✅ 完整（6000行） | 走 dz_dailyquote 路径时影响回测精度 |
| 其余全部 | — | ❌ | **无影响** — `daily_kline`（主fallback）已是前复权数据 |

### 重要说明

**`adj_factors` 缺失不影响回测准确性**。`data_manager.py` 的数据加载优先级：
1. `dz_dailyquote × adj_factor` → adj_factor 缺失时 fall through
2. `daily_kline` → **已是前复权数据**（Coze 腾讯 fqkline API 直接返回前复权价）
3. Parquet（最旧备份）

所以回测中看到 "adj_factors 表无数据，使用原始（不复权）价格" 的警告**仅来自 dz_dailyquote 路径**，不影响已走 daily_kline 路径的策略结果准确性。
