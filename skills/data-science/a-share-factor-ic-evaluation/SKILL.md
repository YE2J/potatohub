---
name: a-share-factor-ic-evaluation
description: A股因子IC评估全流程——从数据库读取、IC/ICIR/分层回测/衰减分析计算、HTML报告生成，到用同花顺App数据校准算法参数
---

# A股因子IC评估工作流

## 适用场景

- 已有 daily_factors（因子表）+ daily_kline（日线）数据，想评估各因子的预测力
- 想测试衍生信号（组合信号、阈值调整）的 IC 表现
- 需要对比系统计算结果与同花顺App的差异，校准算法参数
- 不想引入 Qlib/RD-Agent 等重型框架，纯 pandas/numpy 自实现

## Pipeline 架构

```
daily_factors           daily_kline
    │                       │
    ▼                       │
  load_data() ◄─────────────┘  (JOIN on stock_code + trade_date)
    │
    ├── compute_ic()           → (IC, ICIR)
    ├── compute_all_ic()      → DataFrame[factor, ic, icir]
    ├── compute_quantile_returns() → 分层回测累计收益
    ├── compute_decay()       → 滚动IC衰减曲线
    ├── compute_factor_correlation() → 相关性矩阵
    └── generate_html_report() → 离线HTML（Chart.js内嵌）
```

## 关键坑点与修复

### 1. kline 表日期格式混用
- daily_kline.date 同时存在 `YYYYMMDD`（SecuCode）和 `YYYY-MM-DD`（InnerCode）
- SQL 字符串比较 `>=` 对不同格式排序错乱（`-` ASCII 45 < 数字 48）
- **修复**: 去掉 SQL 中的日期 where，全量加载后在 pandas 中统一 `pd.to_datetime(..., format='mixed')` 过滤

### 2. kline stock_code 编码双体系
- YYYY-MM-DD 的行用 InnerCode（如 `398589`）
- YYYYMMDD 的行用 6位 SecuCode（如 `000988`）
- daily_factors 只用 6位 SecuCode
- **修复**: 加载 `all_ashare_stocks.csv` 的 InnerCode↔SecuCode 映射，在导入时转换

### 3. compute_ic 的统计方法

#### 大样本（N≥100只股票）——标准截面IC
- 不要用全样本混合相关（pooled correlation）——会被时间序列趋势污染
- **标准做法**: 按日算截面 Spearman IC → 取均值作为全样本IC → mean/std 得 ICIR
- 最少需要 2 个有效日截面（实际至少20天才有统计意义）
- 日截面最少 10 只股票有非空数据

#### 小样本（N<50只股票）——时间序列IC
当股票池很小（如N=20时，日截面IC噪声极大），改用**时间序列IC**：
- 每只股票独立计算`corr(因子值, 未来N日收益)`的全历史Spearman相关系数
- 跨股票聚合：`mean(各股时序IC)`作为因子总IC
- ICIR = `mean(各股时序IC) / std(各股时序IC)`——这里衡量的是**跨股票一致性**而非时间稳定性
- **注意**：这样算出的ICIR **不能**与标准ICIR（|ICIR|>2为显著）对比；它回答的是"这个因子在不同股票间行为是否一致"而非"预测力是否随时间稳定"
- 信号名称要明确标注计算方法（如"时间序列IC"而非"IC"）避免误导

**小样本IC评估局限**：
- 重叠收益窗口（`pct_change(forward_days)`相邻行共享收益数据）导致p值偏乐观
- 建议使用`forward_days=1`避免重叠，或使用HAC标准误修正
- 信号提前性分析（因子触发日距实际买卖日天数）在小样本下可能比IC值更有实际价值

### 4. 分层回测的 groupby 陷阱
- pandas `groupby.apply` 在部分版本会丢失非分组列（如 trade_date）
- **修复**: 改用显式 `for dt, grp in result.groupby('trade_date'):` 循环

### 5. json.dumps 处理 NaN
- Chart.js 数据中的 NaN 会使 json.dumps 报错
- **修复**: 序列化前用 `_safe_json()` 将 NaN 替换为 None

### 6. RSI 连续上涨时返回 NaN
- `_rsi()` 函数中 `loss.replace(0, np.nan)` 会导致连续上涨（loss=0）时RSI=NaN
- 修正：用 `np.where(loss == 0, np.inf, gain / loss)`，此时RSI应为100
- 验证：连续6天阳线 → RSI(6)=100.0 ✅，旧代码→NaN ❌

### 7. 数据完整性验证模式
在数据填充前/后，始终做三字段检查：
```python
cur.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM daily_kline WHERE stock_code=?", (code,))
min_dt, max_dt, cnt = cur.fetchone()
```
- 每个股票应覆盖从买入日（最早2025-01-02）到卖出日（最晚2026-07-03）
- 不应出现断档（COUNT少于预期天数时可疑）
- 用前复权close验证复权正确性：`pre_close * adj_factor ≈ close（复权版本）`

### 8. Tushare历史数据回填流程
当 `daily_kline` 缺少早期数据时：
1. 从Tushare MCP配置提取token（位于 `~/.hermes/mcp.json` 或 `~/.hermes/config.yaml` 的 `tushareMcp.url` 参数中）
2. 用 `ts.pro_api().daily(ts_code, start_date, end_date)` 批量获取
3. 用 `INSERT OR IGNORE` 写入DB，避免重复
4. 每次请求间 `time.sleep(0.35)` 避免限流
5. 写入后重新检查 MIN(date)/MAX(date)/COUNT(*)

## 同花顺数据校准方法

### 校准流程
1. 在同花顺App翻到特定日期，截取指标值（主力雷达、主力持仓、暗盘资金）
2. 从数据库查询同一日期的数据做对比
3. 如果偏差超过预期，调整算法参数

### 主力持仓校准方法论

#### 同花顺真实公式结构（2026-07 验证）

用户提供的同花顺源码（通达信语法）：

```
// 核心：LV_D_SUPER_HLD_RATIO 是L2独有字段，未知则无锚点
IF(ISNULL(LV_D_SUPER_HLD_RATIO[-1]) != 0) {
    b1 := BIGBUYCOUNT1[-1] + WAITBUYCOUNT1[-1];  // 注：用昨日[-1]数据
    s1 := BIGSELLCOUNT1[-1] + WAITSELLCOUNT1[-1];
    b2 := BIGBUYCOUNT2[-1] + WAITBUYCOUNT2[-1];
    s2 := BIGSELLCOUNT2[-1] + WAITSELLCOUNT2[-1];
    DDX := ((b1 - s1) + (b2 - s2) * 0.7) / TV_D_PUBLIC_SHARES * 100;
    x1 := LV_D_SUPER_HLD_RATIO * 100;   // ★ 真实持仓锚点
    ret := x1 + DDX;                     // = 前日真实值 + 昨日DDX调整
    // 三段衰减（极端水位减弱DDX影响）
    IF(DDX > 0) {
        IF(x1 > 95) ret := x1 + DDX * 0.1;
        ELSE IF(x1 > 90) ret := x1 + DDX * 0.5;
        ELSE IF(x1 > 85) ret := x1 + DDX * 0.8;
    }
    IF(DDX < 0) {
        IF(x1 < 5) ret := x1 + DDX * 0.1;
        ELSE IF(x1 < 10) ret := x1 + DDX * 0.5;
        ELSE IF(x1 < 15) ret := x1 + DDX * 0.8;
    }
    ret := clamp(ret, 2.08, 97.18);
}
```

#### 我们实现 vs 真实公式的关键差异

| 项 | 真实公式 | 我们的实现 | 影响 |
|:---|:---------|:-----------|:-----|
| **锚点** | `LV_D_SUPER_HLD_RATIO`（L2独有，每日真实值） | `INIT_HOLD`（凭空猜的15%） | 🔴 根本差异：无锚点则递推必然漂移 |
| **时间偏移** | `[-1]` 用**前一日**数据 | 用**当日**数据 | 影响DDX时序对齐 |
| **DDX分子** | `COUNT` **订单笔数**（如BIGBUYCOUNT1） | `MONEY` **金额**（elg_buy_amt） | 量纲不同，计数值≠资金额 |
| **DDX分母** | `TV_D_PUBLIC_SHARES` **流通股本(股)** | `amount` **成交额(元)** | 需估算流通股本 |
| **数据源** | 同花顺L2行情 | Tushare/东方财富资金流 | 采集口径不同 |

**核心结论：没有 LV_D_SUPER_HLD_RATIO，不可能精确复现同花顺主力持仓。** 纯DDX递推在个股间偏差可达10-30pp（见校准数据）。

#### 无LV2数据的替代方案（趋势方向版）

```
DDX_day = ((elg_buy_amt - elg_sell_amt) + (lg_buy_amt - lg_sell_amt) * 0.7) / amount * 100
DDX_shifted[t] = DDX[t-1]  // [-1]偏移：用昨日DDX调整今日holding
holding[t] = clip(holding[t-1] + DDX_shifted[t] * SCALE, 2.08, 97.18)
```
可选三段衰减：同真实公式，极端水位减弱DDX影响。

参数：INIT_HOLD（默认15.0）、SCALE（默认0.5）、三段衰减（默认启用）

#### ⚠️ SCALE 参数个股相关（已验证）

| 股票 | 代码 | 同花顺 | 系统(SCALE=0.5) | 说明 |
|:----|:----:|:------:|:--------------:|------|
| 蜀道装备 | 002173 | 11~15% | ~13% ✅ | 拟合过SCALE |
| 天华新能 | 300390 | 10.70% | 19.87% ❌ | 需要SCALE<<0.5 |
| 东方锆业 | 002167 | 19.52% | 53.81% ❌ | 需要SCALE≈0.05 |

SCALE在不同个股间可差10倍。建议统一参数作为趋势方向指标，不做绝对数值依赖。

#### 最小二乘法参数拟合
```
对所有候选SCALE/INIT组合做网格搜索
→ 计算各组合下递推序列 holding[t]  
→ RMSE = sqrt(mean((holding[i] - y[i])²))
→ 选RMSE最小的组合
```
**至少需要同一股票 5-6 个交易日的同花顺真实值做拟合**，覆盖持仓上升/下降场景。

#### 校准数据需求
- 最少：同一股票 5-6 个交易日（覆盖涨跌方向）
- 最佳：10+ 个离散交易日，跨度 2-4 周
- 获取：同花顺App截图 + DB查询系统值对比
- 注意：节假日休市会导致数据断档，拟合时需跳过
- 工具：用 `scripts/verify_zhuli.py`（在系统内）快速对比同花顺 vs 系统值

### 暗盘资金校准（已验证）
- 偏差较小（~250万），主要因数据源不同（Tushare vs 同花顺L2）
- 可接受，不影响信号判断

### 主力雷达校准（已验证）
- 同花顺App值 vs 系统值：完全一致 ✅
- 说明 calc_zhuli_radar 的算法复刻准确

## 衍生信号测试

可以在 `DERIVED_FACTORS` 列表中添加组合信号，自动参与IC计算：

```python
DERIVED_FACTORS = [
    # (列名, 显示名, 计算函数)
    ("zhuli_above_zero", "主力线>0(买入)",  lambda df: df["radar_zhuli"] > 0),
    ("combo_dd10_or_below", "峰回落10%或<0", lambda df: _peak_drawdown(df["radar_zhuli"], 5, 0.10) | (df["radar_zhuli"] < 0)),
]
```

## 增量验证流水线（ic_runner.py）

除了全量跑IC评估，还支持**增量验证**——自动判断最新交易日是否需要计算新因子，计算后跑IC评估。

### IC报告解读模板

当IC报告生成后，按以下结构解读：

**判断标准：**
- IC > 0.05: 有预测力
- ICIR > 0.5: 预测稳定（可入策略）
- 分层回测5组单调递增/递减：因子质量高
- 新因子IC > 原有因子：值得替换或补充

**新因子 vs 原有因子交叉验证模板：**

新因子（如涨停因子）必须与原有因子（GS/主力雷达）做IC对比：

| 因子 | IC | ICIR | 评价 |
|------|:--:|:----:|------|
| zt_first_time_bin（新） | +0.104 | 0.739 | 最强短期预测 |
| gs_bull_market（原有） | +0.072 | 0.322 | 中强度但更弱 |
| dark_pool_1d（原有） | +0.032 | 0.194 | 弱但正相关 |

**分层回测验证单调性：** 因子值从低到高5组，收益必须单调递增（正因子）或递减（负因子）。否则即使IC高也可能是过拟合。同时检查Group 5（最高组）是否显著跑赢Group 1（最低组）。

**决策：** 当新因子IC ≈ 原有因子IC × 1.5 以上时，应优先将新因子接入策略。当新因子ICIR > 0.5 时，可作为独立信号使用。

### 文件位置

```
financial_api/
├── factors.py            # 5大类因子计算（涨停/龙虎榜/热度/异动/板块）
├── ic_runner.py          # ✨ 增量验证 runner（连接 factors.py + ic_analyzer.py）
└── ...

strategy_library/evaluation/
├── ic_analyzer.py        # IC/ICIR/分层回测/衰减/报告
├── reports/              # ✨ HTML 报告输出目录
│   └── ic_incremental_*.html
└── vendor/
    └── chart.umd.min.js  # Chart.js v4.4.0 离线版
```

### 增量验证工作流

`ic_runner.py` 自动执行以下步骤：

```
① 检查数据库状态
   └─ daily_factors 最新日期、各源表(limit_up_pool/dragon_tiger_daily/hot_stock_daily)最新日期
② 判断是否需要计算新因子
   └─ daily_factors 中有该日期行，但 zt_first_time_bin 全为 NULL/0 → 需要计算
③ 调用 factors.run_all(date) 计算5大类因子并写入
   └─ 涨停104只 / 龙虎榜 / 热度30只 / 异动 / 板块5193只
④ 确定 IC 评估日期范围
   └─ 需与 daily_kline 有交集（fwd_1d 需要 T+1 收盘价）
   └─ 默认取最近20个交易日
⑤ 运行 IC 评估（fwd_1d + fwd_5d 各一次）
   └─ 输出 HTML 报告到 reports/ 目录
```

### CLI 用法

```bash
cd ~/my_quant_system

# 完整流程：计算最新交易日因子 + 跑 IC 评估
~/my_quant_system/.pyenv/versions/3.11.11/bin/python financial_api/ic_runner.py

# 指定日期计算因子 + 跑 IC
python3 financial_api/ic_runner.py --date 2026-07-03

# 跳过因子计算，只跑 IC 评估
python3 financial_api/ic_runner.py --skip-factors --start 2026-06-01 --end 2026-06-26

# 跳过 IC 评估，只计算因子
python3 financial_api/ic_runner.py --skip-ic --date 2026-07-03
```

### 关键坑点

| 坑 | 说明 | 处理 |
|:---|:-----|:-----|
| **kline 日期滞后** | `daily_kline` 最新日期可能晚于因子源表（limit_up_pool 到 07-03 但 kline 只到 06-26） | IC评估自动取 `min(factors_max, kline_max - 1d)` |
| **龙虎榜/异动数据稀疏** | 并非每天都有数据，lh_* 和 yd_* 因子可能全为 NULL | IC评估时这些因子 IC=NaN，属于正常现象 |
| **日期格式不统一** | daily_kline 用 `YYYYMMDD`，daily_factors 用 `YYYY-MM-DD` | pandas `format='mixed'` 自动识别 |
| **new factor 列存在但为 NULL** | 旧日期的 daily_factors 有新因子列（ALTER TABLE 加的），但值都是 NULL | runner 检查 `zt_first_time_bin != 0` 判断是否已计算 |

### Python API

```python
from financial_api.ic_runner import run_pipeline

# 全自动增量验证
run_pipeline()

# 指定日期，跳过IC
run_pipeline(target_date="2026-07-03", skip_ic=True)

# 仅IC评估（因子已算好）
run_pipeline(
    skip_factors=True,
    ic_start="2026-06-01",
    ic_end="2026-06-26",
)
```

## 文件结构（ic_analyzer.py）

```
strategy_library/evaluation/
├── __init__.py           # 模块导出
├── ic_analyzer.py        # 主模块（~670行）
└── vendor/
    └── chart.umd.min.js  # Chart.js v4.4.0 离线版
```

## CLI 用法

```bash
cd ~/my_quant_system
python3 -m strategy_library.evaluation.ic_analyzer \
  --start 2024-06-01 --end 2024-06-30 \
  --watchlist              # 仅自选股
  --stocks 000988 300748   # 指定股票
  --forward 1              # fwd_1d / fwd_5d / fwd_10d
```

## 风险提示

- IC 衡量的是历史预测能力，不保证未来
- 数据不足 20 个交易日时结果统计意义低
- 二值信号（0/1）的 IC 绝对值通常比连续因子低

## 参考案例

实际应用示例见 `references/ai-case-analysis-20260706.md`（20只AI大牛股的跨案例因子分析），包含：
- 完整买卖点信号统计
- 小样本IC评估方法
- 3-Agent审核发现的问题清单（P0/P1/P2分类）
- 全部输出文件路径
