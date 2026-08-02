# 资金流数据适配方案（2026-06-29 更新）

> ⚠️ **数据源已切换**：从东方财富/问财降级方案 → **同花顺 THS 全量数据**。
> 现在 moneyflow_daily 表有 5,663 只股票的完整四档量+额，不再需要降级估算。
> 详见 `references/ths-moneyflow-import.md`。

## 背景

2026-06-29 购入同花顺 THS 全量资金流向数据（quant-data/），一次性导入 moneyflow_daily 表
14,232,762 行，覆盖所有四档（小/中/大/特大单）买卖量（手）+ 额（万元），2007~今。
之前基于东方财富 push2his（仅净额，~830 行，100 只）和问财 API的降级方案已停用。

## 当前架构

```
THS 资金流向数据（data_source='ths'）
  5,663 只 A 股, 14M 行, 2007~2026
  四档买卖量+额，逐行净流入
        │
        ▼
  MoneyflowAdapter
  strategy_library/adapters/moneyflow.py
  
  get_moneyflow(code, start, end) → DataFrame
  列: elg/lg/md/sm 各档 buy_vol/sell_vol/buy_amt/sell_amt
      main_net_amt, net_mf_amt, net_mf_vol
        │
        ├──→ calc_dark_pool()   — 暗盘资金（完整模式）
        └──→ calc_zhuli_holdings() — 主力持仓（完整模式）
```

## moneyflow_daily THS 字段

详情见 `references/ths-moneyflow-import.md`。

## MoneyflowAdapter 列名映射

| Adapter 输出 | THS moneyflow_daily 列 | 说明 |
|-------------|----------------------|------|
| `BIGBUYMONEY1` | `buy_elg_amt` | 特大单买入金额(万元) |
| `BIGSELLMONEY1` | `sell_elg_amt` | 特大单卖出金额(万元) |
| `BIGBUYMONEY2` | `buy_lg_amt` | 大单买入金额(万元) |
| `BIGSELLMONEY2` | `sell_lg_amt` | 大单卖出金额(万元) |
| `BIGBUYVOL1` | `buy_elg_vol` | 特大单买入量(手) |
| `BIGSELLVOL1` | `sell_elg_vol` | 特大单卖出量(手) |
| `MONEY` | — | 用 daily_kline.amount 替代 |
| `MAIN_NET_AMT` | `main_net_amt` | 主力净额(万元) |
| `NET_MF_AMT` | `net_mf_amt` | 总净流入(万元) |
| `DATA_SOURCE` | `'ths'` | 数据来源标识 |

## 注意事项

- THS 数据自带 net_mf_amt（净流入总额），不需要从买卖差值推算
- 两个指标（暗盘资金、主力持仓）现在都运行在完整模式，信号精度显著高于降级估算
- 每日增量更新方式待与数据商确认后纳入系统
