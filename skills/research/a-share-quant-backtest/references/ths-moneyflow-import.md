# THS 资金流向数据导入

## 数据来源

购买的 quant-data 目录核心数据之一。

| 数据 | 路径 | 覆盖 |
|------|------|------|
| 个股资金流向 | `~/Documents/quant-data/moneyflow/` | 5,663 只, 2007~2026 |
| 板块资金流向 | `~/Documents/quant-data/板块资金流向_同花顺/` | 板块级 |
| 行业资金流向 | `~/Documents/quant-data/行业资金流向_同花顺/` | 行业级 |

## 个股资金流向 CSV 结构

每个 CSV 文件名 = `{stock_code}.csv`（6位数字，无后缀）

| 字段 | 类型 | 说明 |
|------|------|------|
| trading_date | TEXT YYYYMMDD | 交易日期 |
| close / high / low / open | REAL | OHLC价 |
| pre_close | REAL | 前收盘 |
| vol | REAL | 成交量（手） |
| amount | REAL | 成交额（万元） |
| pct_change | REAL | 涨跌幅% |
| sm_buy_vol / sm_sell_vol | REAL | 小单买卖量(手) |
| md_buy_vol / md_sell_vol | REAL | 中单买卖量(手) |
| lg_buy_vol / lg_sell_vol | REAL | 大单买卖量(手) |
| elg_buy_vol / elg_sell_vol | REAL | 特大单买卖量(手) |
| sm_buy_amt / sm_sell_amt | REAL | 小单买卖额(万元) |
| md_buy_amt / md_sell_amt | REAL | 中单买卖额(万元) |
| lg_buy_amt / lg_sell_amt | REAL | 大单买卖额(万元) |
| elg_buy_amt / elg_sell_amt | REAL | 特大单买卖额(万元) |
| net_mf_amt | REAL | 净流入总额(万元) |
| net_mf_vol | REAL | 净流入总量(手) |
| main_net_amt | REAL | 主力净额(万元) |

## moneyflow_daily 表

```sql
CREATE TABLE moneyflow_daily (
    stock_code TEXT,
    date TEXT,
    buy_sm_vol REAL, sell_sm_vol REAL,
    buy_md_vol REAL, sell_md_vol REAL,
    buy_lg_vol REAL, sell_lg_vol REAL,
    buy_elg_vol REAL, sell_elg_vol REAL,
    buy_sm_amt REAL, sell_sm_amt REAL,
    buy_md_amt REAL, sell_md_amt REAL,
    buy_lg_amt REAL, sell_lg_amt REAL,
    buy_elg_amt REAL, sell_elg_amt REAL,
    main_net_amt REAL,
    net_mf_amt REAL,
    net_mf_vol REAL,
    data_source TEXT DEFAULT 'ths',
    PRIMARY KEY (stock_code, date)
);
```

## 导入模式

全量一次性导入（不可增量追加）。单文件约 2700 行，5,663 文件合计 ~14M 行，1.9GB CSV。

```python
# 导入脚本核心逻辑
for f in glob('moneyflow/*.csv'):
    stock_code = os.path.basename(f)[:-4]
    rows = parse_csv(f)  # 按旬分块读取
    batch = [(stock_code, row['date'], ...) for row in rows]
    conn.executemany("INSERT OR REPLACE INTO moneyflow_daily ...", batch)
```

性能：~76K 行/秒，总耗时 ~3 分钟（5,663 文件）。

## 常见操作

```sql
-- 查自选股最新资金流向
SELECT stock_code, date, main_net_amt, buy_elg_amt, sell_elg_amt
FROM moneyflow_daily
WHERE stock_code IN (SELECT stock_code FROM watchlist)
  AND date = (SELECT MAX(date) FROM moneyflow_daily WHERE stock_code = '000988');

-- 每日主力净流入 TOP5（148只自选）
SELECT w.stock_code, w.stock_name, m.main_net_amt
FROM watchlist w
JOIN moneyflow_daily m ON w.stock_code = m.stock_code AND m.date = '2026-06-26'
ORDER BY m.main_net_amt DESC LIMIT 5;

-- 数据源分布
SELECT data_source, COUNT(*) FROM moneyflow_daily GROUP BY data_source;
```

## 注意事项

- 净流入列（net_mf_amt, main_net_amt）CSV 中自带，每行都有值
- 不需要从买卖推算净额
- `data_source='ths'` 标识 THS 来源；`data_source='eastmoney'` 为旧数据（31 行残留）
- 领域咨询费确认每日增量后，再设计增量更新方案
