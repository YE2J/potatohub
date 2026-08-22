# P0 多因子补数数据审计（2026-08-20）

多因子选股系统 Phase 0 数据审计实测结论。背景：用户提出"因子工厂"方案（T日数据→T+1选股→验证→因子库），MOA评审后确认5决策点，P0 数据审计发现以下事实。

## 数据现状总览（stock_data.db 实测）

| 数据 | 表 | 覆盖 | 状态 |
|------|-----|------|------|
| 日线(前复权) | daily_kline | 2019-12-31~今，~5,200只/日 | ✅ 完整，日期已全为 YYYY-MM-DD（旧8位格式已无） |
| 指数 | index_daily | 五大指数至今 | ✅ |
| 个股资金流 | moneyflow_daily | THS 2007~2026-07-03停更；tushare_dc 06-29~今 | ⚠️ 双源 |
| 板块资金流 | sector_moneyflow_dc/ths | 至今，滞后行情~2天 | ⚠️ 时序偏移 |
| 两融 | margin_balance | T+1 发布 | ✅ |
| 涨停/龙虎榜/热榜 | limit_up_pool等 | 至今 | ✅ |
| 技术因子库 | daily_factors | 2024-05~今，33因子 | ✅ |
| 股票名(ST过滤) | stock_name_map | 11,732只，680 ST | ✅ |
| 营收(仅revenue) | A股营业总收入 | 1990~2026-03-31，5,184只 | ⚠️ 只有营收无净利 |
| 股本 | 股本结构 | 仅1,999只，total_shares全0 | ❌ 不可用 |
| 换手率 | daily_kline.turnover | 仅2026-07-09起有值 | ⚠️ 历史缺失 |

## 8因子 × 数据源可用性矩阵

| 因子 | 判定 | 计算字段 | 说明 |
|------|------|---------|------|
| Rev_20 反转 | ✅ | close 20日收益取负 | daily_kline |
| Mom_60_20 动量 | ✅ | close 60日收益跳过20日 | daily_kline |
| VOL_20 波动率 | ✅ | close 20日std | daily_kline |
| Turn_20 换手率 | ⚠️ | turnover_rate 20日均 | daily_basic（回填后）；daily_kline.turnover 仅2026-07-09起 |
| NF_5D 资金流 | ⚠️ 降级 | 5日net_mf_amt/5日成交额 | tushare_dc 只有总净流入，无主力分档 |
| EP_TTM | ⏳ | 1/pe_ttm | daily_basic（回填后） |
| BP | ⏳ | 1/pb | daily_basic（回填后） |
| ROE_TTM | ❌ 暂缓 | 净利润TTM/净资产 | 需财务三表逐股拉，P2增强项 |

## 数据可得性日历（T日收盘后）

| 数据 | 可得时间 | 前视风险 |
|------|---------|---------|
| 日线/资金流DC/指数 | T日18:00-18:30 | 无 |
| 板块资金流 | T日18:45 | 无 |
| 两融 | T+1 | T+1才可得 |
| 市值/PE/PB/换手 | T日盘后 | 无（盘后快照） |
| 财务公告 | 公告日 | **必须用ann_date** |
| 涨停/龙虎榜/热榜 | T日22:00 | 无 |

## 实测坑

1. **THS资金流停更于2026-07-03**：ths 2007~07-03全量分档（含main_net_amt）；ths_snapshot 06-29~06-30；tushare_dc 06-29~今 **net_mf_amt有值但 lg_net_amt/main_net_amt 全0**（仅总净流入可用）。
2. **财务三表接口限制**：income/balancesheet/fina_indicator 必须 ts_code 逐股拉（报"必填参数, ts_code"），全市场~5,000次调用≈2-3小时。daily_basic 按 trade_date 批量一次5,541行，是补数最优解。
3. **股本结构表不可用**：total_shares 全0、仅1,999只；市值必须用 daily_basic.total_mv/circ_mv。
4. **daily_kline.turnover 历史缺失**：仅2026-07-09起有值；历史回测用 daily_basic.turnover_rate。
5. **Tushare token 无 export**：`~/.hermes/.env.tushare` 的变量没有 export 关键字，Python 子进程读不到，必须直接解析文件（见 SKILL.md 陷阱节）。
6. **板块资金流滞后2天**：sector_moneyflow 比行情慢2天，L2门控时序需容忍。

## 补数执行记录

| 步骤 | 内容 | 结果 |
|------|------|------|
| 1 | disclosure_date 回填 27报告期(2019Q4~2026Q2) | ✅ 133,664行/5,799只 |
| 2 | daily_basic 回填 2020-01-01~今(1608交易日) | 后台运行，断点续传 |
| 3 | 财务三表 | 暂缓（P2增强项） |

脚本：`~/my_quant_system/scripts/p0_backfill_basics.py`（`--only daily_basic|disclosure_date` 分步）
审计脚本：`scripts/p0_data_audit.py` / `p0_data_audit2.py` / `p0_data_audit3.py`（三轮：表清单→字段有效性→缺口细节）
报告存档：`~/my_quant_system/docs/P0_data_audit_report.md`
