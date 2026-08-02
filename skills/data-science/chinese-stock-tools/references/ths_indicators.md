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

**原版公式**（通达信语法，用户2026-07提供）：

```
IF(ISNULL(LV_D_SUPER_HLD_RATIO[-1]) != 0) {
    b1 := BIGBUYCOUNT1[-1] + WAITBUYCOUNT1[-1];   // 特大单买笔数+挂单(昨日)
    s1 := BIGSELLCOUNT1[-1] + WAITSELLCOUNT1[-1];
    b2 := BIGBUYCOUNT2[-1] + WAITBUYCOUNT2[-1];   // 大单买笔数+挂单(昨日)
    s2 := BIGSELLCOUNT2[-1] + WAITSELLCOUNT2[-1];
    DDX := ((b1 - s1) + (b2 - s2) * 0.7) / TV_D_PUBLIC_SHARES * 100;
    x1 := LV_D_SUPER_HLD_RATIO * 100;   // 前日真实持仓值
    ret := x1 + DDX;
    // 三段衰减
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

**关键依赖**：
- `LV_D_SUPER_HLD_RATIO` — 同花顺L2独有字段，每日真实主力持仓率
- `BIGBUYCOUNT1/BIGSELLCOUNT1` — **订单笔数**（不是金额/不是成交量）
- `TV_D_PUBLIC_SHARES` — 流通股本（股）
- 均用前一日 `[-1]` 数据

**Python翻译注意事项**：
- `BIGBUYCOUNT1` 等笔数无法从公开数据获取，用金额 `BIGBUYMONEY1` 近似
- `TV_D_PUBLIC_SHARES` 需要流通股本数据，可从 `股本结构.float_a_shares` 表（如存在）获取，或估算
- `[-1]` 偏移意味着用**昨日**的资金流数据调整**今日**的持仓
- 三段衰减的阈值（95/90/85/5/10/15）是固定参数

**无LV2数据时的替代方案**：
- 用 `elg_buy_amt + lg_buy_amt*0.7` 代替 `(b1+b2)`，`amount` 代替 `TV_D_PUBLIC_SHARES`
- 用递推代替 `LV_D_SUPER_HLD_RATIO`：`holding[t] = holding[t-1] + DDX_shifted[t] * SCALE`
- SCALE 参数个股相关（可差10倍），无法统一适用于所有股票
- 当前代码位置：`strategy_library/indicators/_zhuli_holdings.py`

**已验证局限**：
- 精确值依赖LV2专有数据，外部无法完美复刻
- 趋势方向可信，绝对数值不可信
- 东方锆业偏差+34pp，天华新能偏差+9pp（SCALE=0.5下）

## 6. 综合信号生成

各指标独立打分后汇总，生成 signal_buy/signal_sell/signal_neutral。
默认阈值：score >= 2.0 买入，score <= -2.0 卖出。
