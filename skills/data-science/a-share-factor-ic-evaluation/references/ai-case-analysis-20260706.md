# AI产业链大牛股跨案例因子分析 — 2026-07-06 Session

## 20只案例股票

光模块/光芯片(6): 300308中际旭创, 300502新易盛, 300394天孚通信, 002281光迅科技, 603083剑桥科技, 000988华工科技
PCB(4): 002916深南电路, 002463沪电股份, 002938鹏鼎控股, 600183生益科技
光纤通信(2): 600487亨通光电, 600522中天科技
封测(2): 002156通富微电, 000021深科技
AI设备(2): 002008大族激光, 002384东山精密
其他(4): 601138工业富联(AI服务器), 603986兆易创新(存储芯片), 301526国际复材(复合材料), 300433蓝思科技(AI硬件)

## 核心发现

### 买入信号（KDJ_J<0 最优）
- KDJ_J<0: 买入准确率95%, 卖出准确率100%, 综合得分195, 提前10.5天
- RSI(14)买入均值26.86（超卖区）
- 布林带位置均值-0.16（下轨以下）
- 距20日高点平均跌幅-22.6%
- 距60日高点平均跌幅-28.4%

### 卖出信号（全部高确定性）
- RSI(14)卖出均值67.55, RSI(6)均值71.30
- KDJ_K均值78.21, KDJ_J均值72~117（严重超买）
- 布林带位置均值0.78~1.17（上轨附近或以上）
- MA60乖离率均值25%~157%

### IC评估（时间序列IC，N=20小样本）
- 60日涨幅%: IC=-0.061（反转效应显著）
- 5日均量: IC=+0.054（量能驱动）
- 布林带宽: IC=+0.044（高波动预示方向）
- 56%因子IC为正

## 输出文件
- 综合报告: `strategy_library/evaluation/ai_case_report.html`
- 买入信号: `strategy_library/evaluation/ai_case_analysis/buy_signals.csv`
- 卖出信号: `strategy_library/evaluation/ai_case_analysis/sell_signals.csv`
- 因子统计: `strategy_library/evaluation/ai_case_analysis/signal_statistics.csv`
- IC评估: `strategy_library/evaluation/ai_case_analysis/factor_ic.csv`
- 提前性分析: `strategy_library/evaluation/ai_case_analysis/lead_analysis.csv`
- RSI演化: `strategy_library/evaluation/ai_case_analysis/rsi_evolution.csv`
- 组合评估: `strategy_library/evaluation/ai_case_analysis/combination_scores.csv`
- 因子计算脚本: `strategy_library/evaluation/ai_case_factors.py`

## 审核发现的问题
1. **P0 RSI NaN bug**: `loss.replace(0, np.nan)` → 连续涨时NaN, 应改为`np.where(loss==0, np.inf, gain/loss)`
2. **P0 资金流数据缺失**: `moneyflow_daily.main_net_amt` 只有5行数据, 资金流因子全无效
3. **P1 HTML报告结论错误**: "提前约4天" → 应改为"约10.5天"
4. **P1 HTML IC卡片未填充**: 需JS动态填充
5. **P2 ICIR计算方法**: 小样本用时间序列IC, ICIR不能按标准|ICIR|>2解读
