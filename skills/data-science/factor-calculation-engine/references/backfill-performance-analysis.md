# daily_factors 回填性能分析

## 背景

daily_factors 表中存在一段大缺口：2024-12-04 ~ 2026-06-22，共 **386 个交易日**。

在此期间的表状态：
- 2024-05-31 ~ 2024-12-03: ✅ 已有数据（每日 ~5,045 行）
- 2024-12-04 ~ 2026-06-22: ❌ 缺口（**386 天**）
- 2026-06-23 ~ 2026-07-02: ✅ 已有数据（每日 ~5,206 行）
- 所有数据版本均为 `v1`

## 数据可用性检查

| 数据源 | 覆盖范围 | 缺口期内可用？ |
|-------|---------|:-------------:|
| **daily_kline** | 2019-12-31 ~ 2026-06-26 | ✅ 全覆盖 |
| **moneyflow_daily (ths)** | 2007-01-04 ~ 2026-06-26 (14,232,731 行) | ✅ **全程覆盖** |
| **all_ashare_stocks.csv** | InnerCode↔SecuCode 映射 | ✅ |

## 版本兼容性

| 检查项 | 结果 |
|--------|------|
| daily_factors.data_version | 全部 `v1` |
| factor_meta.version | 全部 `v1` |
| factor_meta.updated_at | 全部 `2026-07-01 17:25:58`（同一天注册） |

⚠️ **`factor_meta.updated_at` 只在 `cmd_init` 时设置，运行时从不更新**。不能依赖此字段判断计算方法是否已变更。

## 窗口需求（按指标）

| 指标 | 最大滚动窗口 | 说明 |
|------|------------|------|
| calc_gs_signal | EMA(close,99) + MA(27) + SUM(C,26) | 需 **99+ 个数据点**才能让牛熊线（mj30）收敛 |
| calc_zhuli_radar | SMA(13) + SUM(26) + MA(11) | 26 天 |
| calc_ai_activity | COUNT(10) + HHV/LLV(2) | 10 天 |
| calc_dark_pool | REF(C,1) + 资金流合并 | 仅需当日 |
| calc_zhuli_holdings | 全序列递推（for 循环从 i=0） | 需 **完整历史** |
| cross_zero | REF(radar_zhuli, 1) | 1 天 |

当前 `cmd_backfill` 使用 `data_start = day - timedelta(days=130)` ≈ 90 个交易日。这能覆盖大部分指标，但 GS 信号的 EMA_99 在前 99 天会有 NaN 输入（不过公式有 fallback）。

## 计算瓶颈

### `calc_zhuli_holdings` 的 Python for 循环

```python
X1 = np.full(n, 50.0)
ret = np.zeros(n)
for i in range(n):   # ← Python 循环，非向量化
    if i == 0:
        X1[i] = 50.0
    else:
        X1[i] = np.clip(X1[i-1] + DDX[i] * 0.1, 0, 100)
    # ... 5-level conditional branching
```

这是 **唯一非向量化的热点**：5,200 只 × 90 行 = **468,000 次 Python 迭代/天**。其他 4 个指标全部是 numpy 向量化。

## 单日耗时分解

| 阶段 | 操作 | 耗时 |
|------|------|------|
| batch_load_data | 2× SQL（130 天 K 线 + 资金流） | 3-5s |
| compute_factors × 5,200 | 5 个指标（numpy + for 循环） | 8-15s |
| batch_compute_and_write | INSERT OR REPLACE (500行/批) | 2-3s |
| **单日合计** | | **15-25s** |

## 回填总耗时

| 模式 | 公式 | 预计耗时 |
|------|------|---------|
| 串行 | 386 天 × 20s | **~2.1 小时** |
| 8 worker 并行 | 386 天 ÷ 8 × 20s | **~16 分钟** |
| DB 写入量 | 386 天 × 5,200 行 × 176 字节 | **~350 MB** |

## 关键 SQL

```sql
-- 查缺口起始
SELECT MIN(trade_date) FROM daily_factors;  -- 2024-05-31
SELECT MAX(trade_date) FROM daily_factors;  -- 2026-07-02

-- 按月统计覆盖
SELECT SUBSTR(trade_date,1,7) AS yyyymm, 
       COUNT(DISTINCT trade_date) AS dates, COUNT(*) AS rows 
FROM daily_factors GROUP BY yyyymm ORDER BY yyyymm;

-- 查历史全量覆盖日期
SELECT DISTINCT date FROM daily_kline 
WHERE date >= '2024-12-04' AND date <= '2026-06-22'
  AND length(stock_code)=6 AND stock_code GLOB '[036]*';

-- 验证资金流覆盖
SELECT COUNT(DISTINCT date) FROM moneyflow_daily 
WHERE date >= '2025-01-01' AND date <= '2025-01-31' AND data_source='ths';
```

## 执行命令

```bash
cd ~/my_quant_system
~/.pyenv/versions/3.11.11/bin/python3 scripts/import_daily_factors.py \
  backfill --start 2024-12-04 --end 2026-06-22
```

## 数据完整性验证

回填后运行 validate 检查覆盖率和异常值：

```bash
~/.pyenv/versions/3.11.11/bin/python3 scripts/import_daily_factors.py \
  validate --date 2026-06-22
```

期望结果：
- 覆盖率 > 90%（~5,200 只）
- 各因子 NULL 比例 < 10%
- outliers 0 个
