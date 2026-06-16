# 同花顺6大指标Python翻译指南

## 1. 主力雷达

### 原版公式

```
LC:=REF(CLOSE,1);
RSI1:=SMA(MAX(CLOSE-LC,0),6,1)/SMA(ABS(CLOSE-LC),6,1)*100;
AR:=SUM(HIGH-OPEN,26)/SUM(OPEN-LOW,26)*100;
卖点雷达:CROSS(85,RSI1)*30;
DRAWTEXT(CROSS(85,RSI1),80,'顶');

Varb:=SMA(MAX(CLOSE-LC,0),7,1)/SMA(ABS(CLOSE-LC),7,1)*100;
Varc:=SMA(MAX(CLOSE-LC,0),13,1)/SMA(ABS(CLOSE-LC),13,1)*100;
Vard:=BARSCOUNT(CLOSE);
买点雷达:(Varb<20 AND Varc<25 AND Vard>50 AND AR<70
          AND VOL<VOL[1] AND VOL[1]<VOL[2] AND VOL[2]<VOL[3])*30;

主力:EMA((CLOSE-MA(CLOSE,7))/MA(CLOSE,7)*480,2)*5;
散户:EMA((CLOSE-MA(CLOSE,11))/MA(CLOSE,11)*480,7)*5;

DRAWTEXT(CROSS(主力,散户) AND 主力<-10,-60,'升');
DRAWICON(CROSS(主力,散户) AND 主力<-10 AND 散户>REF(散户,1)
         OR CROSS(主力,散户) AND 散户<-35 ,-15,222);
DRAWTEXT(CROSS(RSI1,20)AND 散户<-20 AND 买点雷达 ,-60,'底');
```

### Python key points

- `RSI1=SMA(X,6,1)` → `TDX_SMA(X,6,1)`，不是 `ta.RSI()`！Wilder RSI 和通达信SMA(6,1) 是一样的。
- `AR` 需要 `SUM(HIGH-OPEN,26)` 和 `SUM(OPEN-LOW,26)`，注意分母可能为0。
- `VOL<VOL[1] AND VOL[1]<VOL[2] AND VOL[2]<VOL[3]` → 连续3日缩量，不是简单比较。
- DRAWICON条件: `(CROSS AND A<-10 AND B>REF(B,1)) OR (CROSS AND B<-35)`

## 2. AI机构活跃度

### 关键翻译要点

- SMA(2,1) = `(X*1 + PREV*(2-1))/2`，循环递推
- X_4 = `IF(C<=O, C, O)` = min(C,O)
- X_5 = (X_4 - LOW) / LOW * 100
- X_18 = MAX(MAX(MAX(MAX(MAX(MAX(X_15,X_16),X_14),X_13),X_12),X_11),X_17) * 1.2
- **AND优先级高于OR** (`x_23 = (X_19>=25) | (X_20>=23) | ((X_22>=23) & count1>=2 & count2>=4)`)
- COUNT(X_23>0, 10) == 1: 过去10日内X_23刚好触发1次
- **名字含"AI"和"机构"但实际没有AI也没有机构数据** — 只是多维度价格动量评分

## 3. GS信号（主图+副图）

### 核心逻辑

```
BB0 = (MA3 + MA7 + MA13 + MA27) / 4
bb1 = EMA5
bb  = IF(bb0==NULL, bb1, bb0)              # 基准均线

a0  = (H+L+2*O+6*C) / 10                    # 加权价格

迭代10次:
  C1 = CROSS(a_iter, bb) AND tk
  C2 = CROSS(bb, a_iter) AND tp
  a_iter = IF(C1, bb*0.98, IF(C2, bb*1.02, a_iter))
```

- `tk`(空头条件): 阴线/冲高回落/偏空形态
- `tp`(多头条件): 阳线/探底回升/偏多形态
- 迭代使a收敛到BB附近，类似自适应滤波器
- kk0 = a上穿BB(G点买入), pp0 = BB下穿a(S点卖出)
- 决策线: EMA(JCx,39), 牛线/熊线: EMA(JCx,99)比较
- ax1/ax2: 支撑阻力计算 (rb1 = 4*1.01-1540/2457)

### 迭代必须严格10次，不能多不能少

## 4. 暗盘资金

### 调整幅度计算

```
调整幅度1 = 高低开 + 实体涨跌幅 + 冲高 + 回落 + 杀跌 + V反
调整幅度  = IF(调整幅度1>=1, 0.8, 调整幅度1)
```

这6项根据日内OHLC计算波动形态。

### 核心暗盘计算

```
暗盘资金 = IF(调整幅度>0,
             (中单买入初+小单买入初)*调整幅度,     # 流入
             (中单卖出初+小单卖出初)*调整幅度)      # 流出(负数)
```

### 依赖LV2

原版使用 `BIGBUYMONEY1/2/3` + `WAITBUYMONEY1/2/3` 等LV2函数。外部复现需要:
1. akshare `stock_individual_fund_flow()` — 日频资金流(有网络问题)
2. tushare pro `moneyflow` — 需付费积分
3. 完全无LV2时的回退 — 按成交额固定比例估算

## 5. 主力持仓

### 原版逻辑

依赖 `LV_D_SUPER_HLD_RATIO`（同花顺独有LV2合成指标，外部不可得）。

外部复现: 用逐日DDX累积+主力净流入占比近似。
- DDX = (超大单净额 + 0.7*大单净额) / 成交额
- 持仓 = 初始50% + 累积DDX增量
- 极端值衰减: >95%或<5%时DDX影响系数从0.8降到0.1

## 综合信号生成

策略引擎（见 `references/rule_engine_strategy.md`）使用10分制双向打分:
- 买入分: GS趋势+3, G点+3, 暗盘流入+2, 主力雷达+2, 活跃度+2, 主力增仓+1
- 卖出分: 类似反向
- strong(≥7) / medium(≥5) / weak(≥3) 三级
