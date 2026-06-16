# 东方财富资金流API + web_extract 数据管线

## URL 模式

```
https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
  ?lmt=50          ← 返回行数（≤50可获原始JSON，>50会被web_extract摘要化）
  &klt=1           ← K线类型：1=日线
  &secid=0.000988  ← 市场.代码：0=深市, 1=沪市
  &fields1=f1,f2,f3,f7
  &fields2=f51,f52,f53,f54,f55,f56,f61,f62
  &fmt=json        ← ⚠️ 加此参数后web_extract返回原始JSON（否则返回摘要markdown）
```

## 字段映射

| f51 | f52 | f53 | f54 | f55 | f56 | f61 | f62 |
|-----|-----|-----|-----|-----|-----|-----|-----|
| 日期 | 主力净流入 | 超大单净流入 | 大单净流入 | 中单净流入 | 小单净流入 | 主力占比% | 收盘价 |

> 主力净流入 = 超大单 + 大单（f52 = f53 + f54，验证一致性）

## 网络限制

⚠️ **本地终端无法直接访问**（curl 返回 `Empty reply from server`，Python SSL 连接被重置）。
数据必须通过 Hermes `web_extract` 工具获取（Hermes 基础设施有独立网络路径）。

## web_extract 原始 JSON 阈值

- `lmt ≤ 50`：返回 ```json ``` 块（原始数据，可直接解析）
- `lmt > 50`：返回 markdown 摘要（无原始数据，不适合程序化处理）

## moneyflow_daily 表结构

```sql
CREATE TABLE moneyflow_daily (
    stock_code TEXT,
    date TEXT,
    main_net_amt REAL,       -- f52 主力净流入
    lg_buy_amt REAL,         -- 大单买入（max(f54,0)）
    lg_sell_amt REAL,        -- 大单卖出（abs(min(f54,0))）
    md_buy_amt REAL,         -- 中单买入（max(f55,0)）
    md_sell_amt REAL,        -- 中单卖出（abs(min(f55,0))）
    sm_buy_amt REAL,         -- 小单买入（max(f56,0)）
    sm_sell_amt REAL,        -- 小单卖出（abs(min(f56,0))）
    elg_buy_amt REAL,        -- 超大单买入（max(f53,0)）
    elg_sell_amt REAL,       -- 超大单卖出（abs(min(f53,0))）
    net_mf_amt REAL,         -- 总净流入 = f52+f53+f54（应为约0，校验用）
    data_source TEXT,         -- 'eastmoney'
    PRIMARY KEY (stock_code, date)
);
```

## Cron Job

- **Job ID**: `209c43908019`
- **名称**: 每日资金流更新
- **调度**: `30 18 * * *`（每天18:30收盘后）
- **覆盖**: STOCKS_V4 全部 99 只自选股
- **策略**: lmt=3 只拉最新 3 个交易日增量
