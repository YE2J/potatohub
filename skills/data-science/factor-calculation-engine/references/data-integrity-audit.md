# 因子工程数据完整性审计：检查清单

对 A 股因子管线做数据完整性审计时的系统性检查项。每项包含：检查目的、SQL/代码命令、预期结果、常见缺陷。

## 1. 日期格式一致性

### 检查
```sql
-- 查找非标准格式的行
SELECT DISTINCT date FROM daily_kline 
WHERE date NOT GLOB '????-??-??' LIMIT 10;

SELECT COUNT(*) FROM daily_kline 
WHERE date NOT GLOB '????-??-??';
```

### 风险
SQLite 的 `WHERE date >= '2024-01-01'` 在 `YYYYMMDD` vs `YYYY-MM-DD` 混合时 `碰巧` 工作（因 `0` > `-` ASCII 值），但依赖格式混合的方向。若全库格式统一为 `YYYYMMDD` 而查询参数为 `YYYY-MM-DD` 时，**比较结果将反转**，SQL 层静默漏掉整批数据。

### 修复原则
- SQL 层不要依赖混合格式比较
- 要么在入库时统一定为一种格式
- 要么查询时用 `REPLACE(date, '-', '')` 统一为无横线格式
- `_normalize_date()` 的 pandas 层补救仅在后处理阶段生效，无法挽回已被 SQL WHERE 排除的行

## 2. InnerCode ↔ SecuCode 映射完整性

### 背景
`daily_kline.stock_code` 可能同时混合 **InnerCode**（如 `66353`）和 **SecuCode**（如 `601949`）两种编码。`all_ashare_stocks.csv` 文件维护了双向映射。

### 检查
```python
import csv, sqlite3

conn = sqlite3.connect('stock_data.db')
csv_path = 'all_ashare_stocks.csv'

inner_to_secu = {}
secu_to_inner = {}
with open(csv_path) as f:
    for row in csv.DictReader(f):
        inner, secu = row['InnerCode'].strip(), row['SecuCode'].strip()
        if inner and secu:
            inner_to_secu[inner] = secu
            secu_to_inner[secu] = inner

kline_codes = set(r[0] for r in 
    conn.execute('SELECT DISTINCT stock_code FROM daily_kline'))

# 三种命中模式
inner_match = kline_codes & set(inner_to_secu.keys())
secu_match  = kline_codes & set(secu_to_inner.keys())
both        = inner_match & secu_match  # 同时以两种形式存在于 daily_kline

print(f"Total codes in kline: {len(kline_codes)}")
print(f"InnerCode match: {len(inner_match)}")
print(f"SecuCode match:  {len(secu_match)}")
print(f"Both formats:    {len(both)}")
print(f"Only SecuCode (would be DROPPED): {len(secu_match - both)}")
```

### 单向映射缺陷
```python
# 🔴 错误：只尝试 InnerCode→SecuCode
kline_df["secu_code"] = kline_df["stock_code"].map(inner_to_secu)
kline_df = kline_df.dropna(subset=["secu_code"])  # 丢掉 SecuCode 形式的行

# ✅ 正确：双向回退
kline_df["secu_code"] = kline_df["stock_code"].map(inner_to_secu)
unmapped = kline_df["secu_code"].isna()
kline_df.loc[unmapped, "secu_code"] = kline_df.loc[unmapped, "stock_code"]
```

### 连锁影响
单向映射不仅漏股票，还会造成"窗口内行数不足"的误判：
- 股票 601949 同时以 InnerCode `66353` (504行) 和 SecuCode `601949` (485行) 存在于 daily_kline
- 只有 InnerCode 映射成功 → 只能取到 504 行
- 若 SecuCode 形式的行覆盖了 InnerCode 形式缺失的日期段 → 那些日期被丢弃，窗口内行数 < 2 → 全因子 NULL

### 额外检查：CSV 覆盖缺口
```sql
-- daily_kline 中完全不在 CSV 映射表里的代码
SELECT COUNT(DISTINCT stock_code) FROM daily_kline AS k
WHERE k.stock_code NOT IN (
    SELECT InnerCode FROM all_ashare_stocks  -- 等价检查
    UNION SELECT SecuCode FROM all_ashare_stocks
);
```
不在 CSV 中的代码可能是：已退市股票、指数、ETF、非 A 股品种（港股通/美股配股）。

## 3. amount=0 传播路径审计

### 症状
某日全量 amount=0（如 2026-06-26 的 5,510 行全部为 0，同时 close>0 且 volume>0，为 100% 可修复）。

### 修复路径追踪
```
daily_kline.amount=0
  │
  ▼
batch_load_data() ──→ SQL 层 (raw data, unfixed)
  │
  ▼
compute_factors():
  │  ├── df.loc[zero_amt, "amount"] = close * volume    ✅ 修复 df
  │  ├── calc_gs_signal(df)       → 使用已修复 df      ✅
  │  ├── calc_zhuli_radar(df)     → 使用已修复 df      ✅
  │  ├── calc_ai_activity(df)     → 使用已修复 df      ✅
  │  └── amt_map = dict(zip(df["date"], df["amount"]))  ✅
  │       mapped_mf["MONEY"] = mapped_mf["date"].map(amt_map)  ✅ MONEY 已修复
  │
  └── calc_dark_pool(df, mapped_mf):
        └── df.get('amount', ...) → 收到已修复 df     ✅
      calc_zhuli_holdings(df, mapped_mf):
        └── df.get('amount', ...) → 收到已修复 df     ✅
```

**结论**：修复在 `compute_factors` 层面覆盖所有指标路径，MONEY 字段在适配器映射后又被 `amt_map` 覆盖。修复完整。

### 风险边界
修复依赖 `close>0 AND volume>0`。若某日 close 和 volume 也为 0（停牌/未交易），则 `close × volume = 0`，修复无效。

### 建议
- 在 `batch_load_data()` 的 SQL 层或 pandas 加载后立即做统一修复，不下沉到 compute_factors（保持计算函数无副作用）
- 记录 amount=0 修复率到 `factor_run_log.checksum_agg` 或 `factor_data_quality`

## 4. Moneyflow stock_code 格式一致性

### 问题
`moneyflow_daily.stock_code` 同时存在三种格式：
| 格式 | 示例 | 去重数量 |
|------|------|---------|
| 纯 6 位 | `000002` | ~5,972 |
| .SH 后缀 | `600000.SH` | ~2,300 |
| .SZ 后缀 | `000001.SZ` | ~2,885 |
| 空值 | `""` | ~1 |

### 影响
`batch_load_data()` 中 `secu_in_mf = set(mf_df["stock_code"].astype(str).str.strip().unique())` 拿到的是混合格式。与 `secu_in_kline`（纯 6 位）取交集时，`.SH/.SZ` 后缀的代码会丢失匹配。

**注**：因为多数股票同时有纯 6 位格式的行，交集仍能捕获大部分股票。丢失的是**仅以带后缀格式存在**的行。

### 修复
```python
# 加载 moneyflow 后统一格式
mf_df["stock_code"] = mf_df["stock_code"].str.replace(r'\.(SH|SZ|BJ)$', '', regex=True)
```

### 损坏日期行
```sql
SELECT COUNT(*) FROM moneyflow_daily WHERE date NOT GLOB '????-??-??';
-- 可能查到 "003018 2026-06-16" 等将股票代码拼入日期的行
```
这些行是导入 bug 导致的，不会影响任何 WHERE 日期范围查询。

## 5. data_version 语义

### 现状
- `batch_compute_and_write()` 硬编码 `version = "v1"`
- `factor_run_log` 同样写入 `"v1"`
- `factor_meta.version` 也是 `"v1"`（DDL 默认值）

### 问题
- version 无语义：不含日期、不含计算引擎 hash、不含指标算法版本
- 回填和新计算产生同样的 `"v1"`，无法区分
- 升级指标算法后**无法追溯哪些数据需要重算**

### 建议
`data_version` 应包含语义信息，例如：
- `v1.0.0-20260702` — 版本 + 计算日期
- 或由指标函数列表的 SHA256 推导，算法变更时版本自动变化

## 6. 断点续传安全性

### 当前逻辑
```python
# import_daily_factors.py
done_dates = _get_completed_dates(DB_PATH, chunk_start, chunk_end)
pending = [d for d in date_chunk if d not in done_dates]
```
`_get_completed_dates` 查询 `SELECT DISTINCT trade_date FROM daily_factors`。

### 安全缺口

| 风险 | 场景 | 后果 |
|------|------|------|
| **部分写入** | 进程在写入 batch 中间崩溃 | 该日存在但数据不完整，被跳过 |
| **缺少行数校验** | 没有检查 `COUNT(*) = expected` | 静默接受部分数据 |
| **日志与数据分离** | `factor_run_log` 与 `daily_factors` 非同一事务 | DB 异常时日志写入失败不影响回填循环（好），但无法依赖日志恢复 |

### 强化方案
```python
def _is_date_complete(db_path: str, date: str, expected_stocks: int = None) -> bool:
    conn = sqlite3.connect(db_path)
    actual = conn.execute(
        "SELECT COUNT(*) FROM daily_factors WHERE trade_date=?", (date,)
    ).fetchone()[0]
    conn.close()
    if expected_stocks and actual < expected_stocks:
        return False  # 行数不足，需要重算
    return actual > 0
```

## 7. 主力持仓递推初始化

### 机制
`calc_zhuli_holdings` 每天加载 120 天窗口，从 50% 初始值递推：

```python
X1 = np.full(n, 50.0)
for i in range(n):
    if i == 0:
        X1[i] = 50.0
    else:
        X1[i] = np.clip(X1[i-1] + DDX[i] * 0.1, 0, 100)
```

### 收敛分析
- 每个交易日调整量 = `DDX * 0.1`，DDX 典型值 ±0~5%
- 每天变化约 ±0.5% 持仓
- 从 50% 到真实值 20%（30% 漂移）需要约 60 天持续一致信号
- 120 天窗口对绝大部分股票足够收敛

### 不足
- **无跨日持久化**：每天独立开新窗口从 50% 重新递推。若某股 DDX 长期接近 0，终值一直偏近 50%
- **首个 backfill 日期窗口不全**：若 moneyflow 数据起始日接近窗口起始日，前 30~60 天的递推数据不可靠

### 改进方向
- 从 `daily_factors` 读取前一个交易日的 `zhuli_holding` 作为初始值（需处理复权等跳变）
- 或使用更长的窗口（如 250 个交易日）保证收敛

## 8. cross_zero 依赖链脆弱性

### 代码路径
```python
try:
    radar = calc_zhuli_radar(df)
    radar_enriched = radar          # 成功
except:
    radar_enriched = df             # 失败 → df 没有 "radar_zhuli" 列

# cross_zero 使用 radar_enriched
zhuli_series = radar_enriched.get("radar_zhuli", 
    pd.Series([np.nan] * len(df)))  # 降级为全 NaN
```

若 `calc_zhuli_radar` 抛出异常，`radar_enriched = df`（不含 radar_zhuli 列），`cross_zero` 永远返回 None。这是一个**隐蔽的缺失传播**——因子计算失败→cross_zero 静默变 NULL。

### 改进
```python
try:
    radar = calc_zhuli_radar(df)
    radar_enriched = radar
except Exception as e:
    print(f"  [ERR] {stock_code} zhuli_radar: {e}")
    # 创建空列占位，保持 cross_zero 能正常降级为 None
    df["radar_zhuli"] = np.nan
    radar_enriched = df
```

## 9. 股票数差异分析

### 检查命令
```sql
SELECT trade_date, COUNT(*) FROM daily_factors 
GROUP BY trade_date ORDER BY trade_date;
```

### 合理区间
A 股每日有交易的股票数在 **5,000 ~ 5,300** 之间（2024~2026年），年增长约 100~150 只（IPO）。相邻两个交易日的差异通常 < 10 只。

### 异常检测
- 某日突然减少 100+ 只：可能是回填窗口不全（如 2024-05-31 首次回填时 4,287/5,033 只全 NULL）
- 某日突然增加 500+ 只：可能是 InnerCode 映射修复后首次捕获到之前丢失的股票
- 同一日 backfill 和 daily_incremental 产出不一致：可能是数据源时效问题

## 10. 审计运行命令

```bash
# 1. 标准质量校验（覆盖、NULL率、异常值）
python scripts/import_daily_factors.py validate --date 2026-06-26

# 2. 全量回顾
python scripts/import_daily_factors.py validate --date 2024-05-31  # 首批日期
python scripts/import_daily_factors.py validate --date 2026-06-24  # 最新日期

# 3. 日期格式检查
sqlite3 stock_data.db "SELECT DISTINCT substr(date,5,1) FROM daily_kline;"
# 输出 '-' 表示全是 YYYY-MM-DD，输出 '0-9' 表示混杂格式
```

## 参考链接

- DDL: `factor_engine/factor_ddl.sql`
- 核心实现: `strategy_library/factors.py` (574行)
- CLI 入口: `scripts/import_daily_factors.py` (532行)
- 指标函数: `strategy_library/indicators/`
- MoneyflowAdapter: `strategy_library/adapters/moneyflow.py`
- 股票映射: `all_ashare_stocks.csv`
