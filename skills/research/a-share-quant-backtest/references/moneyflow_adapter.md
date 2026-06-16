# 资金流数据适配方案

## 背景

暗盘资金（`calc_dark_pool`）和主力持仓（`calc_zhuli_holdings`）两个同花顺指标需要 LV2 级别的资金流数据。由于免费数据源（Tushare 低积分、东方财富 API 被墙）无法获取真实 moneyflow，系统采用**降级估算 → 数据库留位 → 未来升级**的三段式架构。

## 架构

```
数据源（未来）                   当前降级方案
┌──────────────────┐      ┌─────────────────────┐
│ Tushare moneyflow │      │ K线数据估算          │
│ (需 ≥2000积分)    │      │ pct_chg × vol × close│
│ 东方财富资金流API  │      │ → 按比例分配买卖     │
└────────┬─────────┘      └──────────┬──────────┘
         │                           │
         ▼                           ▼
  ┌──────────────────────────────────────────┐
  │  MoneyflowAdapter                        │
  │  strategy_library/adapters/moneyflow.py  │
  │                                          │
  │  get_moneyflow(code) → DataFrame         │
  │  列: BIGBUYMONEY1, BIGSELLMONEY1, ...    │
  │       MONEY, BIGBUYCOUNT1, ...           │
  └──────────────────┬───────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
  calc_dark_pool()        calc_zhuli_holdings()
  (_dark_pool.py)         (_zhuli_holdings.py)
```

## 数据库表

```sql
CREATE TABLE moneyflow_daily (
    stock_code TEXT,
    date TEXT,
    main_net_amt REAL,    -- 主力净流入
    lg_buy_amt REAL,      -- 大单买入
    lg_sell_amt REAL,     -- 大单卖出
    elg_buy_amt REAL,     -- 超大单买入
    elg_sell_amt REAL,    -- 超大单卖出
    md_buy_amt REAL, md_sell_amt REAL,
    sm_buy_amt REAL, sm_sell_amt REAL,
    net_mf_amt REAL,      -- 总净流入
    data_source TEXT,     -- 来源: 'tushare' / 'eastmoney' / 'estimated'
    PRIMARY KEY (stock_code, date)
);
```

## 升级路径

获得 Tushare ≥2000 积分后：

1. 在 Hermes Tushare MCP 配置中更新 API key
2. 运行数据拉取脚本填充 `moneyflow_daily` 表
3. `MoneyflowAdapter._from_db()` 自动读取真实数据
4. 两个指标自动切换到完整模式（无需修改指标代码）

## 列名映射

MoneyflowAdapter 输出列 → 同花顺公式变量：

| Adapter 输出 | 同花顺公式变量 | 说明 |
|-------------|---------------|------|
| `BIGBUYMONEY1` | BIGBUYMONEY1 | 特大单买入金额 |
| `WAITBUYMONEY1` | WAITBUYMONEY1 | 特大单挂单买入（≈BIG*0.3） |
| `BIGBUYMONEY2` | BIGBUYMONEY2 | 大单买入金额 |
| `BIGSELLMONEY1` | BIGSELLMONEY1 | 特大单卖出金额 |
| `MONEY` | MONEY | 总成交额 |
| `BIGBUYCOUNT1` | BIGBUYCOUNT1 | 特大单买入笔数（当前不可得=0） |
| `TV_D_PUBLIC_SHARES` | TV_D_PUBLIC_SHARES | 流通股本（当前不可得=0） |

## 注意事项

- 降级模式仅提供信号参考，**不应用于实际交易决策**
- 两个指标在 bridge.py 管线中已自动串联（dark_pool 先 merge，holdings 检测到已有列则跳过 merge）
- 持有指标（zhuli_holdings）merge 逻辑：`if 'BIGBUYMONEY1' not in result.columns: merge; else: 跳过`
