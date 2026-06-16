# 6大同花顺指标 Python 翻译参考

本文档记录了 Session 2026-06-13 翻译的 6 个同花顺指标代码。
完整代码参见 `/Users/yellow/Documents/量化回测/indicators.py`

## 指标清单

| # | 名称 | 依赖LV2 | 函数名 |
|---|------|---------|-------|
| 1 | 主力雷达 | 否 | calc_zhuli_radar() |
| 2 | AI机构活跃度 | 否 | calc_ai_activity() |
| 3 | GS信号（主图+副图） | 否 | calc_gs_signal() |
| 4 | 暗盘资金 | 是（可替代） | calc_dark_pool() |
| 5 | 主力持仓 | 是（可替代） | calc_zhuli_holdings() |
| 6 | 综合信号 | — | generate_combined_signal() |

## 1. 主力雷达

**原版公式**：
- RSI1 = SMA(MAX(C-LC,0),6,1)/SMA(ABS(C-LC),6,1)*100
- AR = SUM(H-O, 26)/SUM(O-L, 26)*100
- 卖点雷达 = CROSS(85, RSI1)*30
- 买点雷达 = (Varb<20 AND Varc<25 AND Vard>50 AND AR<70 AND VOL递减3日)*30
- 主力线 = EMA((C-MA(C,7))/MA(C,7)*480, 2)*5
- 散户线 = EMA((C-MA(C,11))/MA(C,11)*480, 7)*5
- 买入信号 = CROSS(主力,散户) AND 主力<-10 AND 散户>REF(散户,1)
         OR CROSS(主力,散户) AND 散户<-35
- 底部信号 = CROSS(RSI1,20) AND 散户<-20 AND 买点雷达

**注意**：名称带"主力"和"散户"但实际上只是均线偏离度的EMA，不涉及真实资金流。

## 2. AI机构活跃度

**原版公式**：
- X_2 = SMA(MAX(C-LC,0),2,1)/SMA(ABS(C-LC),2,1)*100 (2日RSI)
- X_5 = (min(C,O)-L)/L*100
- X_18 = MAX(7个维度) * 1.2
- 生命线=1.56, 强势线=3, 大牛线=6
- 爆发信号 = 近10日内首次满足暴涨条件

**注意**：名称含"AI"和"机构"但实际不涉及AI算法或机构数据，只是价格动量的多维度综合评分。

## 3. GS信号

**原版公式**：
- BB = (MA3+MA7+MA13+MA27)/4
- a0 = (H+L+2O+6C)/10
- 迭代10次: a(n+1)=IF(CROSS(an,BB) AND tk, BB*0.98, IF(CROSS(BB,an) AND tp, BB*1.02, an))
- kk0 = CROSS(a, BB) (买入G点)
- pp0 = CROSS(BB, a) (卖出S点)
- tcy = 多头强势, tzk = 多头普通
- tkc = 空头弱势, tzd = 空头普通
- 决策线 = EMA(JCx, 39), 牛/熊线 = EMA(JCx, 99)

**GS信号使用建议**：
- G点提示 = kk0 → "趋势启动，逢低建仓"
- S点提示 = pp0 → "趋势结束，逢高减仓"
- G区间 = tcy → "趋势健康，继续持股"
- S区间 = tkc → "趋势走弱，持币观望"

## 4. 暗盘资金

**原版公式**：
- 调整幅度 = min(6项K线形态值之和, 0.8)
- 资金分级：特大单/大单/中单/小单（买入和卖出）
- 调账：中单部分金额"暗盘"到特大单，小单暗盘到大单
- 暗盘资金 = IF(调整幅度>0, (中单买入+小单买入)*调整幅度, (中单卖出+小单卖出)*调整幅度)

**LV2替代**：原版需要 BIGBUYMONEY1/2/3 等LV2函数。Python中可用 akshare 的 `stock_individual_fund_flow` 获取资金流数据近似替代。

## 5. 主力持仓

**原版公式**：
- 核心 = LV_D_SUPER_HLD_RATIO（同花顺LV2独有数据）
- DDX = ((特大净买+大单净买*0.7)/流通股本)*100
- 持仓 = X1 + DDX，极端值时DDX影响缩减（>95%或<5%时*0.1）
- 钳位到 [2.08, 97.18]

**LV2替代**：`LV_D_SUPER_HLD_RATIO` 无法从外部获取。建议用 DDX 累积 + 大单净占比近似估算。

## 6. 综合信号生成

各指标独立打分后汇总，生成 signal_buy/signal_sell/signal_neutral。
默认阈值：score >= 2.0 买入，score <= -2.0 卖出。
