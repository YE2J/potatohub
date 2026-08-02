---
name: a-share-case-methodology
description: A股买入/卖出案例收集与因子挖掘方法论。从交易案例中提取可量化的买入/卖出/持有信号因子，支持3Agent评审流程和批量扫描。
---

# A股案例收集与因子挖掘方法论

## 用途
收集A股买入/卖出交易案例，从案例中提取共性的因子驱动信号，为量化策略提供依据。

## 核心流程

### Phase 1：案例收集（目标20-30个）
1. 确定收集方向（如AI产业链、消费、医药等）
2. 扫描候选股：
   - 使用 Tushare MCP (`mcp_tushareMcp_daily`) 查日线
   - 也可查本地 SQLite `stock_data.db` 的 `daily_kline` 表（注意：数据可能不完整）
3. 排除规则：
   - ❌ 北交所（8xxxxx/4xxxxx）
   - ❌ 科创板（688xxx）
4. 质量标准：
   - 买入点在相对低位
   - 涨幅 ≥4x 优先
   - 买入/卖出日期允许 ±3 个交易日浮动
   - 买入/卖出价格使用 **开盘价**
5. 案例保存位置：`~/my_quant_system/案例/ai_cases.md`

### Phase 2：数据提取
- 对每个案例提取买入前60个交易日的价量数据
- 提取资金流（`moneyflow_daily` 表）
- 提取板块热度（`industry_moneyflow_ths` / `sector_moneyflow_ths`）

### Phase 3：因子分析

#### 3a. 全A股截面IC验证（已有因子普适性）
- 使用 `ic_analyzer.py` 做全A股截面 Spearman IC 评估
- 需要 500+ 只股票才有统计意义（截面IC按日算 → 取均值）
- 输出：IC / ICIR / 分层回测 / 衰减曲线 / 相关性矩阵
- 详见 `data-science/a-share-factor-ic-evaluation` skill

#### 3b. 跨案例时间序列IC评估（案例池专用）
当只有 20-30 个高质量案例，而非全市场数千只股票时，**不要用截面IC**（截面样本太少，IC 不稳定）。改用**时间序列IC**：

1. 对每个案例独立计算因子与未来N日收益的 Spearman/ Pearson 相关系数
2. 跨案例聚合：取均值作为该因子在案例池的预测能力
3. 补充指标：ICIR（均值/标准差）、正相关率、p值（正态近似检验显著性）
4. 核心文件：`strategy_library/evaluation/cross_case_analysis.py`

**关键区别**：截面IC看的是「同一时刻不同股票间因子值 vs 收益的排序相关性」，时间序列IC看的是「同一股票不同时间点因子值 vs 未来收益的相关性」。

**ICIR标识**：时间序列IC的ICIR = mean(各股时序IC) / std(各股时序IC)，衡量的是「该因子在不同股票间表现的一致性」，而非标准日截面IC的「预测力时间稳定性」。不能与文献中|ICIR|>2的标准对比。

**重叠收益窗口注意事项**：用 `pct_change(N)` 再全量日数据计算未来收益时，相邻行共享N-1天的相同收益数据（高度自相关），有效样本量被高估，计算的p值偏小。

#### 3c. 信号提前性分析
对于已知买卖点，评估各信号规则提前几天触发：

- 对每个信号规则，检查买入日前 N 天（默认 60 天窗口）是否满足条件
- 统计：平均/中位数提前天数、触发率、当天触发率
- **提前天数越长的信号价值越高**（给操盘留出反应窗口）
- 详见 `cross_case_analysis.py` 的 `analyze_lead_times()` 函数

#### 3d. 最优因子组合评估
对多个信号规则的 AND 组合测试：

- 买入准确率 = 信号在买入日前触发的比例
- 卖出准确率 = 信号在卖出日前触发的比例
- 综合得分 = 买入准确率 + 卖出准确率
- 预定义了 12 组组合做评估

### Phase 4：信号框架构建
- 买入信号因子筛选、持有信号因子筛选、卖出信号因子筛选
- 根据 Phase 3b/c/d 的结果，选择：
  - 优先采用买入一致性高 + 提前天数长的因子
  - 优先采用 IC 绝对值高 + ICIR > 0.5 的因子
  - 组合策略选择综合得分最高的

### Phase 5：回测验证
- 接入 `backtest_v4.py` 回测引擎
- 详见 `references/kdj-backtest-methodology.md`：KDJ_J<0 单因子回测设计、绩效分析、改进方向

## 工作流规范（强制）
每做一步，必须：
1. 派3个Agent并行评审方案
2. 汇总评审意见，修复问题
3. 再执行
4. 执行后审查→修复→终验

## 案例格式
| 案例号 | 股票代码 名称 | 赛道 | 买入日 | 买入开盘价 | 卖出日 | 卖出开盘价 | 涨幅 |

## 数据源优先级
1. 本地 SQLite `stock_data.db`（最快，但数据可能不完整）
2. Tushare MCP `mcp_tushareMcp_daily`（完整，但有调用次数限制）
3. 同花顺 Financial-API（同花顺特色数据如涨停池、龙虎榜）

## 跨案例分析参考
详见 `references/cross-case-analysis-workflow.md`：完整工作流说明、每个分析模块的细节、2026-07 实战结果、Pitfalls。

## 回测验证参考
详见 `references/kdj-backtest-methodology.md`：KDJ_J<0 单因子回测设计、绩效分析、改进方向（含趋势过滤/止损优化/市场环境筛选）。

## 板块分布指导
- 避免单一板块过度集中
- 建议覆盖：光模块、AI服务器、PCB、存储芯片、光纤通信、半导体设备、散热/液冷、交换机

## Pitfalls
- 本地 `daily_kline` 表可能只有2025-12-15之后的数据，无法覆盖早期低位，需用Tushare API补全。
- 多位Agent评审内容可能被截断（因context过长），完整报告保存在 `~/.hermes/cache/delegation/` 下。
- 3个Agent意见不一致时，以多数为准，有争议的候选股保留到下一轮再评估。

### 因子计算Pitfalls
- **RSI NaN bug**：`loss.replace(0, np.nan)` 在连续上涨（loss=0）时会导致 RSI=NaN。应改用 `np.where(loss==0, np.inf, gain/loss)` 再转为 Series，此时RSI=100。
- **KDJ递推**：使用 `ewm(alpha=1/3, adjust=False)` 等价于传统递推公式，前8行为NaN（RSV需要9期），第9行正确初始化。
- **MACD EMA初值**：使用 `ewm(span=N, adjust=False)`，初始值为close[0]，无NaN问题。
- **布林带**：`bb_range.clip(lower=0.001)` 防止除零，但极端缩量时boll_pos可能不准确。

### 数据ETL Pitfalls
- **日期格式**：`daily_kline` 表中 date 可能混合 YYYYMMDD（20251215）和 YYYY-MM-DD（2025-12-15）两种格式。读取时必须用 `pd.to_datetime(col, format='mixed')` 统一。
- **资金流数据**：`moneyflow_daily` 表的 `main_net_amt` 等字段可能只有少量数据，导致资金流因子全部NaN。使用前先用 `df['col'].notna().sum() / len(df)` 检查覆盖率。
- **turnover字段**：`daily_kline` 表的 `turnover` 可能100%为NULL，换手率因子不可用。

### 3-Agent 审核常见发现
- **ICIR方法混淆**：当股票池只有20-30只时，不能做标准日截面IC（样本太少）。替代方案是时间序列IC（每只股票独立计算因子vs未来收益的相关系数，再跨案例聚合）。此时报告的ICIR = mean(各股时序IC) / std(各股时序IC)，不能与文献中|ICIR|>2的截面IC标准对比。
- **重叠收益窗口**：用 `pct_change(N)` 再全量日数据计算未来收益时，相邻行共享N-1天的相同收益数据（高度自相关），有效样本量被高估，p值偏小。
- **卖出准确率系统性地接近100%**：可能源于卖出规则过于宽松或卖出窗口太大，应缩短卖出检测窗口。
