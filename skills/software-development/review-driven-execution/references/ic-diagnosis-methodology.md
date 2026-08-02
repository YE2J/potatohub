# IC诊断方法论 — 买入信号IC为负的根本原因分析

## 适用场景

当系统的买入信号IC（信息系数）为负值时，用此方法系统性诊断"哪个环节错了"。

## 5轴诊断框架

### 轴1：信号因素分解

将当前组合信号拆解为原子条件，对每个分条件分别计算IC：

```
买入 = A(GS信号) AND B(主力线上穿零轴) AND C(主力持仓>20%) AND D(暗盘资金流入)
                  ↓ 拆分为:
A单独IC  → 如果IC为正→GS本身有效，是被其他条件带偏
B单独IC  → 如果IC为正→上穿零轴有效，问题在持仓/暗盘
C单独IC  → 持仓条件可能太松或太紧
D单独IC  → 暗盘资金在A股可能是反向指标
A+B      → 不带持仓和暗盘的原始策略
A+B+C    → 逐次加入条件看IC变化
A+B+C+D  → 当前策略（期望IC已知为负）
(A OR B)+C+D → G点替代组合
```

**关键检查**: 脚本中的信号定义必须与 `config.py V4_PARAMS` 和 `backtest_v4.py` 完全一致。常见遗漏：
- 暗盘资金需要"连续2日流入"（front + shift(1)），不是单日
- GS条件 = `gs_g_point > 0 OR gs_bull_market > 0`，不是AND

### 轴2：窗口测试

对每个信号，分别计算不同预测窗口的IC：

| 窗口 | 含义 | 用途 |
|------|------|------|
| fwd_1d | 明天1个交易日 | 超短线预测力 |
| fwd_3d | 未来3个交易日 | 短线 |
| fwd_5d | 未来1周 | 策略持仓上限 |
| fwd_10d | 未来2周 | 中期 |

**解读**: 如果fwd_1d的IC为正但fwd_5d为负，说明信号有1日有效但持仓5天就反转——要改的是持有期，不是信号。

**实现**: 通过 `groupby("stock_code")["close"].transform(lambda s: s.shift(-n) / s - 1)` 计算。

### 轴3：涨跌停排除

买入信号在涨停日实际无法成交。如果IC评估包含涨停样本，会把"买不到"的交易日算成"买了亏损"：

```
样本A: 全量（当前IC）
样本B: 排除当日涨停的股票
样本C: 排除涨停+跌停的股票
```

**数据源**: `limit_up_pool` 表的 `thscode` 列（可能带交易所后缀如 `000506.SZ`，用正则 `\d{6}` 提取6位代码）。

### 轴4：分市场状态

IC在不同市场环境下可能完全不同：

```
按年份:  2023年IC vs 2024年IC vs 2025年IC vs 2026年IC
按沪深300趋势: 上涨月(>3%) vs 震荡月(-3%~3%) vs 下跌月(<-3%)
```

**解读**: 如果IC在牛市中为正、震荡市中为负，说明策略不是无效，而是有市场状态偏好——要做市场状态识别而非改参数。

### 轴5：分股票池

对比全市场 vs 自选股的IC差异，确认问题是选股逻辑的问题还是信号本身的问题。

## 数据源对照表

| 数据 | 表名 | 关键字段 | 格式说明 |
|------|------|---------|---------|
| 因子 | daily_factors | stock_code, trade_date, gs_g_point, cross_zero, zhuli_holding, dark_pool_inflow_signal | trade_date=YYYY-MM-DD |
| 日线 | daily_kline | stock_code, date, close | date=混合(YYYY-MM-DD+YYYYMMDD)，stock_code有InnerCode和SecuCode两种 |
| 涨停 | limit_up_pool | trade_date, thscode | thscode可能带.SZ/.SH后缀 |
| 沪深300 | index_daily | trade_date, ts_code, close, pct_chg | ts_code可能是000300.SH或000300 |
| 代码映射 | all_ashare_stocks.csv | InnerCode, SecuCode | InnerCode=6位无后缀 |

## 脚本结构模板

新建IC诊断脚本的标准结构：

1. 导入 + sys.path设置（项目根加入路径）
2. PATH常量（PROJECT_ROOT, DEFAULT_DB, REPORT_DIR, CSV_MAP_PATH等）
3. 信号定义（SIGNAL_DEFS + CONDITIONS原子条件 + 组合模式）
4. 数据加载（load_factor_data: factors表 + kline表 + merge + 前向收益率）
5. IC计算（_cross_sectional_ic + compute_signal_ic + compute_all_signal_ics）
6. 诊断函数（每个诊断一个函数，返回DataFrame）
7. HTML报告生成（generate_html_report）
8. 主流程（run_diagnosis + CLI argparse + if __name__）

## 真实案例 (2026-07-07)

ic_diagnosis.py 执行结果：
- 所有信号的fwd_1d IC均为负值
- D条件(暗盘资金流入)最差：IC=-0.0261
- C条件(主力持仓>20%)接近中性：IC=-0.0042
- 涨跌停排除无改善（信号问题不是由"涨停不可买"导致）
- ICIR绝对值均<0.5（信号不稳定）
- 结论：不是单个条件拖累，是所有信号在T+1时间尺度上都表现出反预测力
