# Tushare THS 板块资金流数据格式说明

## 数据来源

| API | 表 | 说明 |
|-----|----|------|
| `moneyflow_cnt_ths` | `sector_moneyflow_ths` | 概念板块资金流向 |
| `moneyflow_ind_ths` | `industry_moneyflow_ths` | 行业板块资金流向 |

## 单位说明

**`net_amount` 存储单位是 万元（万人民币），不是元。**

- 转换为 亿：`net_amount / 1e4`
- 转换为 元：`net_amount * 1e4`

验证：semiconductor 板块单日最大净流入约396元（数据库值），对应 396万元 = 0.04亿，符合板块级别资金量级。
如果错误地除 1e8（当作元来算），所有值会显示为 0.0亿。

## 列映射（daily_sector_moneyflow.py 中定义）

### sector_moneyflow_ths
| Tushare 字段 | 数据表列 | 说明 |
|:------------|:---------|:-----|
| trade_date | trade_date | 交易日 YYYYMMDD |
| ts_code | sector_code | 板块代码 (885xxx.TI) |
| name | sector_name | 板块名称 |
| lead_stock | lead_stock | 领涨股名称 |
| close_price | latest_price | 最新价 |
| pct_change | sector_pct_change | 板块涨跌幅% |
| industry_index | sector_index | 行业指数值 |
| company_num | company_count | 成分股数量 |
| pct_change_stock | lead_stock_pct_change | 领涨股涨跌幅% |
| net_buy_amount | inflow_amount | 主动买入(万元) |
| net_sell_amount | outflow_amount | 主动卖出(万元) |
| net_amount | net_amount | 净流入(万元) |

### industry_moneyflow_ths
对应列名略有不同：`ts_code→industry_code`, `industry→industry_name`, `close→close_index` 等。

## 日期格式

数据表中 `trade_date` 统一为 `YYYYMMDD` 格式（文本）。
早期可能有 `YYYY-MM-DD` 混合数据，已被一次性清理。

## 数据时效

- 每日盘后约 17:00~18:00 更新（Tushare 采集时间）
- cron 注册在 `45 18 * * 1-5`

## 已知坑

1. **单位混淆**: 最容易犯的错误是以为 `net_amount` 单位是元，除以 1e8 转亿。实际是万元，应除 1e4。
2. **lambda 闭包参数名**: `_call_with_retry` 或 `fetch_and_save` 通过 keyword 传参时，
   `lambda td: pro.func(trade_date=td)` + `pro_func(trade_date=val)` → TypeError。
   必须 `lambda trade_date: pro.func(trade_date=trade_date)` 或传位置参数 `pro_func(val)`。
3. **同一 try 块两个 API**: 概念+行业在同一个 try 块时，行业失败会吞没概念的异常。
   应拆成独立 try/except。
