# 跨案例因子分析工作流（Cross-Case Factor Analysis）

## 适用场景

已有 20-30 个 A 股大牛股案例（已知买入/卖出日期），想从案例中提取共性因子信号。

## 文件结构

```
my_quant_system/strategy_library/evaluation/
├── ai_case_factors.py           # 因子计算：MA/RSI/KDJ/MACD/布林带/资金流
│                                #   定义 CASE_STOCKS, BUY_DATES, SELL_DATES
├── cross_case_analysis.py       # 主综合评估脚本
├── ai_case_report.html          # 输出：暗色主题HTML报告（Chart.js可视化）
└── ai_case_analysis/            # 输出：7个CSV分析数据
    ├── buy_signals.csv
    ├── sell_signals.csv
    ├── signal_statistics.csv
    ├── factor_ic.csv
    ├── lead_analysis.csv
    ├── rsi_evolution.csv
    └── combination_scores.csv
```

## 运行命令

```bash
cd ~/my_quant_system
~/my_quant_system/.pyenv/versions/3.11.11/bin/python \
  strategy_library/evaluation/cross_case_analysis.py
```

## 五大分析模块

### 1. 买卖点信号统计 (`compute_signal_statistics`)
- 对每个因子，计算在买入日和卖出日的跨案例：均值、中位数、标准差、一致性（方向一致性%）
- 一致性 = max(正信号占比, 负信号占比) × 100%
- 100% 一致性意味着所有案例在该日的因子值方向完全一致

### 2. 时间序列 IC 评估 (`compute_cross_case_ic`)
- 对每只股票独立计算：因子值 vs 未来 N 日收益率的 Spearman 相关系数
- 跨案例聚合：取均值 ± 标准差
- ICIR = 均值 / 标准差（衡量预测稳定性）
- p 值使用正态近似 `math.erfc(|t|/sqrt(2))` 计算（无需 scipy）
- **与截面IC的区别**：截面IC需要日截面 N>500 只股票才有统计意义；时间序列IC适合 N<50 的小样本池

### 3. 信号提前性分析 (`analyze_lead_times`)
- 对每个预定义的信号规则（如 RSI<30、KDJ_K<20、布林带<0.05），检查买入/卖出日前 60 天窗口是否触发
- 统计：平均/中位数提前天数、触发率、当天触发率
- 预定义的信号规则在 `LEAD_CONFIGS` 列表中

### 4. RSI 演化轨迹 (`analyze_lead_evolution`)
- 对买入日前 30 天到买入当天，跟踪 RSI(14) 的均值和中位数变化
- 可用于判断「超卖信号是在买入日前几天出现的」
- 同样可推广到其他因子

### 5. 最优因子组合 (`evaluate_all_combinations`)
- 对 12 组预定义的因子组合（AND逻辑）做评估
- 买入准确率 = 组合条件在买入日前触发的案例比例
- 卖出准确率 = 组合条件在卖出日前触发的案例比例
- 综合得分 = 买入准确率 + 卖出准确率

## 2026-07-06 AI 产业链 20 牛股实战结果

### Top 买入信号提前性
| 信号 | 平均提前(天) | 触发率 |
|------|:-----------:|:------:|
| MACD金叉 | 24.2 | 75% |
| KDJ_J<0 | 10.5 | 95% |
| RSI(6)<20 | 4.0 | 95% |
| KDJ_K<20 | 3.6 | 90% |
| RSI(14)<30 | 1.2 | 85% |
| 布林带<0.05 | 1.7 | 85% |

### Top 因子组合
| 组合 | 买入准确率 | 卖出准确率 | 综合得分 |
|------|:--------:|:--------:|:-------:|
| KDJ_J<0 | 95% | 100% | 195 |
| KDJ_K<20 | 90% | 100% | 190 |
| RSI<30 超卖 | 85% | 100% | 185 |
| 布林带<0.05 | 85% | 100% | 185 |
| 距20日高点<-15% | 85% | 100% | 185 |

### Top 时间序列 IC（绝对值）
| 因子 | Spearman IC | ICIR | 方向 |
|------|:---------:|:----:|:----:|
| 60日涨幅% | -0.061 | -0.64 | 反转(负) |
| 5日均量 | +0.054 | +0.66 | 正 |
| 布林带宽% | +0.044 | +0.54 | 正 |

### 关键发现
1. AI 大牛股的买入信号高度一致：买入时 RSI ≈ 27、KDJ_K ≈ 26、距20日高点 ≈ -23%
2. 反转效应显著：60日涨幅与未来5日收益负相关（IC = -0.061），涨多了要跌
3. KDJ_J<0 是最优单因子策略：95% 买入准确率，提前 10.5 天触发
4. 56% 的因子 IC 为正，技术面因子在 AI 大牛股上有一定的收益预测能力

## Pitfalls

### 1. 时间序列 IC 的样本量问题
- 每只股票大约 200-300 个交易日数据点，剔除 NA 后约 100-200 个有效点
- IC 稳定性不如全市场截面IC（因为 N 小），建议以 ICIR > 0.5 为可信标准
- t 检验使用正态近似（大样本假设），df 较小时 p 值可能偏小

### 2. 提前性分析的窗口选择
- 默认 60 天回看窗口适合中长线投资
- 对短线交易，建议缩到 20 天
- MACD 金叉提前 24 天可能是「30分钟/60分钟级别的金叉提前于日线级别」

### 3. 无 scipy 依赖的注意事项
- `cross_case_analysis.py` 使用 `math.erfc()` 做正态近似 p 值计算
- 如果有 scipy，建议改用 `scipy.stats.ttest_1samp()` 做 t 检验（更精确）
- 安装：`pip install scipy`

### 4. 买入/卖出日期的对齐
- `ai_case_factors.py` 中的 `BUY_DATES`/`SELL_DATES` 必须与 `daily_kline` 表中的交易日期对齐
- 如果设置的非交易日会导致无匹配行，影响统计数据
- 建议使用最近交易日（允许 ±1 天浮动）
