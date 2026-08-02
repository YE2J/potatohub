# 因子 IC 评估方法论（纯 pandas 自实现）

基于 2026-07-02 实际开发经验，为 `~/my_quant_system/` 添加因子评估模块。

## 目标

在不引入 Qlib/alphalens 的前提下，对 daily_factors 表中的 15 个因子做系统性评估：
- IC（截面信息系数）
- ICIR（IC 稳定性）
- 分层回测（五分位组收益）
- 因子衰减（滚动 IC）
- 因子相关性矩阵

## 架构

```
strategy_library/evaluation/
├── __init__.py          # 模块导出（公开 8 个函数）
├── ic_analyzer.py       # IC 评估主逻辑（628 行，纯 pandas/numpy）
└── vendor/
    └── chart.umd.min.js # Chart.js v4.4.0 离线版（200KB）
```

## 关键设计决策

### 1. IC 必须是日截面均值，不是混合相关

```python
# ❌ 错误：跨时间+截面混合相关，时间趋势污染
ic = df[[factor_col, forward_col]].corr(method="spearman").iloc[0, 1]

# ✅ 正确：每日算截面IC，然后取均值
daily_ic = df.groupby("trade_date").apply(
    lambda g: _cross_sectional_ic(g, factor_col, forward_col, "spearman")
)
mean_ic = daily_ic.mean()
icir = mean_ic / daily_ic.std()
```

`_cross_sectional_ic()` 做单日 Spearman 相关，需要求当日股票数 ≥ 10 才计算（否则返回 NaN）。

### 2. 未来收益率用 close shift

```python
df["fwd_1d"] = df.groupby("stock_code")["close"].transform(
    lambda s: s.shift(-1) / s - 1
)
```

注意：
- `shift(-N)` 在最后 N 天返回 NaN，这是预期的
- close 是前复权价（daily_kline 表已经是 Coze 前复权）
- 加载 kline 时必须多取 `forward_max + 10` 天数据，确保未来收益率有足够数据

### 3. SQL 参数化（防注入）

```python
# ❌ 错误：字符串拼接
wheres.append(f"f.trade_date >= '{start_date}'")

# ✅ 正确：参数化查询
params.append(start_date)
wheres.append("f.trade_date >= ?")
df = pd.read_sql_query(sql, conn, params=params)
```

### 4. JSON 序列化前替换 NaN

```python
# ❌ 错误：json.dumps 遇到 float('nan') 会崩溃
vals = [round(v * 100, 2) for v in pivoted[c].tolist()]  # 如果v是nan会报错

# ✅ 正确
vals = [None if (isinstance(v, float) and math.isnan(v)) else round(v * 100, 2)
        for v in pivoted[c].tolist()]
```

### 5. 离线 Chart.js（避免 CDN 依赖）

不引用 CDN，而是下载 chart.umd.min.js 到 vendor/ 目录，HTML 中内嵌 `<script>` 标签嵌入全部 JS 代码。

## 分层回测

每天按因子值 pd.qcut 分 5 组：

```python
g["group"] = pd.qcut(g[factor_col], n_groups, labels=False, duplicates="drop")
```

- `duplicates='drop'` 处理因子值完全相同的边界情况（此时分组数 < 5）
- 回退：当天股票数 < n_groups 时返回空 DataFrame
- 多空收益 = Group4 - Group0（最高组 - 最低组）

## 注意事项

### 二值信号的 IC 解读
- 0/1 信号的 IC 绝对值通常比连续因子低（0.01~0.03），属正常
- `radar_maisell` 实际值是 {0, 30} 不是 {0, 1}，标记 `is_binary=False`

### 过拟合风险
因子 IC 评估不会导致过拟合（只是描述过去），但过拟合发生在：
- 根据 IC 结果去调参数
- 在训练期和验证期没有分开的情况下反复优化
- **建议 walk-forward 验证**：每季度一轮，不跨期调参

### 数据需求
- daily_factors 表（15 个因子列 + stock_code/trade_date）
- daily_kline 表（close 列用于 forward return）
- Python 3.11.11 + pandas + numpy + math（标准库即可）

## 使用方法

```bash
cd ~/my_quant_system
~/.pyenv/versions/3.11.11/bin/python3 \
  -m strategy_library.evaluation.ic_analyzer \
  --start 2025-01-01 \
  --watchlist
```

参数：
- `--start` / `--end` 时间范围（默认今天）
- `--forward 1|5|10` 未来收益天数
- `--stocks 000988 301338` 指定股票
- `--watchlist` 仅自选股（148 只）

输出：`reports/factor_eval_YYYYMMDD_HHMMSS.html`（含 IC 表 + 分层曲线 + 衰减 + 相关性矩阵）

## 2026-07-02 踩坑记录

### 1. kline 混合日期格式导致 merge 全空

**症状**：`load_data()` 返回的 `close` 列全部为 NaN，IC 无法计算。

**原因**：daily_kline 表日期格式不统一——大部分行用 `YYYYMMDD`（无横线，如 `'20260624'`），小部分用 `YYYY-MM-DD`（有横线，如 `'2026-06-29'`）。当 SQL WHERE 子句做 `date >= '2026-06-23' AND date <= '2026-07-05'` 时，ASCII 里 `'-'` (45) < `'0'` (48)，所以 `'2026-07-05'` 在字符串排序中比 `'20260624'` 更小——`'20260624' <= '2026-07-05'` 为 False，数据被 SQL 过滤器排除。

**修复**：不在 SQL 中做日期过滤。而是按股票代码全量加载后，在 pandas 中用 `pd.to_datetime()` 统一转换再用 datetime 比较过滤。

```python
# ❌ 错误：SQL 字符串比较，混合格式排序错乱
sql = "SELECT ... FROM daily_kline WHERE date >= ? AND date <= ?"

# ✅ 正确：全量加载 → pandas 统一格式 → datetime 过滤
sql = "SELECT stock_code, date AS trade_date, close FROM daily_kline"
df = pd.read_sql_query(sql, conn)
df["trade_date"] = pd.to_datetime(df["trade_date"], format="mixed")
if start_date:
    df = df[df["trade_date"] >= pd.to_datetime(start_date)]
if end_date:
    df = df[df["trade_date"] <= pd.to_datetime(end_date)]
```

**代价**：全量加载 watchlist 148 股的 kline（约 19K 行）不影响性能。全市场 ~5200 股（~2.6M 行）的加载耗时约 3-5 秒。

### 2. 日IC数量阈值过高

**症状**：数据只有 2 个有效的日截面（最后一个交易日没有未来收益率），但 `compute_ic` 要求 `len(daily_ic) >= 5`，导致 IC 全部为 NaN。

**修复**：阈值从 5 降到 2。对于初期只有少量交易日覆盖的情况特别重要。

```python
# ❌ 错误：最少 5 天才有 IC
if len(daily_ic) < 5: return np.nan, np.nan

# ✅ 正确：最少 2 天，但增加 ICIR 的警告提示
if len(daily_ic) < 2: return np.nan, np.nan
```

**注意**：只有 2-3 个交易日的 IC 结果**统计意义有限**。应在报告中标注 `⚠️ 仅 N 个有效日截面`。

### 3. groupby.apply 丢失分组列

**症状**：`compute_quantile_returns()` 中 `result.groupby("trade_date").apply(...)` 后 `result` 丢失 `trade_date` 列，后续 `groupby(["trade_date", "group"])` 报 `KeyError: 'trade_date'`。

**原因**：pandas 3.0 的 `groupby.apply` 在 `include_groups=True`（默认）时返回结果的行为与旧版不一致，可能丢失分组列。

**修复**：用显式 for 循环替代 `groupby.apply`：

```python
# ❌ 错误：apply 后可能丢失列
def _quantile_assign(g):
    g["group"] = pd.qcut(g[factor_col], n_groups, labels=False, duplicates="drop")
    return g
result = result.groupby("trade_date", group_keys=False).apply(_quantile_assign)

# ✅ 正确：显式循环
all_groups = []
for dt, grp in result.groupby("trade_date"):
    if len(grp) < n_groups:
        continue
    g = grp.copy()
    try:
        g["group"] = pd.qcut(g[factor_col], n_groups, labels=False, duplicates="drop")
    except ValueError:
        continue
    all_groups.append(g)
result = pd.concat(all_groups)
```

### 4. 有限交易日下的 IC 解读

当 `daily_factors` 表只有 2-3 个有效交易日（加上未来收益率后只剩 1-2 个日截面），IC 值可能高估或低估。2026-07-02 实测：主力强度 IC=0.225（2 天），这个值远高于常规期望值（~0.02~0.05），**大概率是数据过少导致的统计噪声**。

**正确做法**：
- 优先确保 `daily_factors` 表有至少 20-30 个交易日再做 IC 分析
- 对少量数据的 IC 结果标注 `⚠️ 仅 N 天数据，仅供参考`
- 不做基于少量数据的权重调整

### 5. InnerCode→SecuCode 映射（关键 JOIN 修复）

**问题**：`ic_analyzer._load_kline()` 从 `daily_kline` 表加载数据后做 `merge` 时，stock_code 编码不匹配：
- `daily_kline` 中 YYYY-MM-DD 格式日期行使用 **InnerCode**（如 `'398589'`）
- `daily_kline` 中 YYYYMMDD 格式日期行使用 6位 **SecuCode**（如 `'000988'`）
- `daily_factors` 统一使用 6位 SecuCode
- 没有映射时，JOIN 到 InnerCode 的 5000 只股票只剩 16 只（0.3%）

**修复**：在 `_load_kline()` 中，加载完数据后加入映射步骤：

```python
inner_to_secu, _ = _load_stock_map()  # 从 all_ashare_stocks.csv 读取
if inner_to_secu:
    is_inner = df["stock_code"].isin(inner_to_secu.keys())
    df.loc[is_inner, "stock_code"] = df.loc[is_inner, "stock_code"].map(inner_to_secu)
```

`_load_stock_map()` 用 `csv.DictReader` 读取 `all_ashare_stocks.csv` 的 InnerCode/SecuCode 两列，构建双向映射字典。

**验证方法**：在修复前后分别查 merge 后的 close NaN 比例：
```python
# 修复前：close NaN=15147/15618 (97%)
# 修复后：close NaN=0（全市场~5000只股票 × 20天 → 100739行全部有close）
```

**注意**：该映射在 `factors.py` 的 `batch_load_data()` 中已经存在（通过 `_load_stock_map` 在入参处转换），但在 `ic_analyzer.py` 中缺失。**任何从 daily_kline 读取数据的模块都必须做这个映射**。

### 6. 衍生信号快速测试法

无需修改 `daily_factors` 表即可测试新信号概念：

```python
# 在 ic_analyzer.py 的 run_evaluation() 中计算衍生信号
DERIVED_FACTORS = [
    ("zhuli_above_zero",  "主力线>0",       lambda df: df["radar_zhuli"] > 0),
    ("zhuli_below_zero",  "主力线<0",       lambda df: df["radar_zhuli"] < 0),
    ("zhuli_peak_dd15_5d","峰回落15%(5日)", lambda df: _peak_drawdown(df["radar_zhuli"], 5, 0.15)),
]

def _peak_drawdown(series, window=5, threshold=0.30):
    """从滚动高点回落幅度检测"""
    rolling_high = series.rolling(window=window, min_periods=1).max()
    drawdown = (rolling_high - series) / rolling_high.abs().clip(lower=1)
    return drawdown >= threshold

# 在 run_evaluation 中：
for col, name, fn in DERIVED_FACTORS:
    df[col] = fn(df).astype(float)

# compute_all_ic 同时计算原始因子和衍生信号的 IC
```

**适用场景**：
- 测试新买卖信号（如"主力线从高点回落 N%"）
- 对比不同阈值（如 15% vs 20% vs 30%）
- 对比不同窗口（5日 vs 10日）
- 快速验证"如果我把 X 改成 Y，IC 会怎么变化"

**不做**：将衍生信号写入 daily_factors（会污染数据层的版本管理），保留在评估模块中即可。

### 7. 峰回落卖出信号实测对比（2024-06 全市场 20天）

| 信号 | 阈值 | IC | 排名 |
|------|------|:---:|:----:|
| 主力线<0 | — | +0.029 | 1 |
| 5日峰回落15% | 15% | **+0.024** | 2 |
| 5日峰回落20% | 20% | +0.024 | 2 |
| 10日峰回落30% | 30% | +0.023 | 4 |
| 5日峰回落30% | 30% | +0.022 | 5 |
| 日跌幅>0 | — | +0.015 | 6 |

**结论**：
- **越灵敏的回落阈值 IC 越高**（15% > 20% > 30%）
- 5日和10日窗口差别不大
- 所有回落信号都优于"单纯日跌幅"
- 峰值回撤信号适合做**卖出**（正IC，触发后下跌）
- 主力线>0 作为买入信号在2024年 IC 为负（-0.04），不建议依赖

## 三层评审模板

每次新加评估逻辑或修改核心算法时，开 3 个 Agent 并行审查：

1. **Agent 1: 代码质量和架构**
   - 函数拆分是否合理？参数命名是否清晰？
   - 有没有重复计算（如 compute_ic 和 compute_decay 的 IC 逻辑）
   - HTML 报告占比是否过高（>20% 考虑拆分）

2. **Agent 2: 逻辑正确性和 Bug**
   - IC 计算方法是否标准（日截面均值 vs 混合相关）
   - 有无前视偏差（未来数据泄露）
   - SQL 注入、NaN 序列化、边界条件
   - 因子数据映射是否正确

3. **Agent 3: 可维护性和集成**
   - 与现有系统的集成方式（独立运行 vs 嵌入 backtest）
   - 依赖管理（CDN 离线化、版本锁定）
   - 错误处理是否充分
   - `__init__.py` 是否导出
