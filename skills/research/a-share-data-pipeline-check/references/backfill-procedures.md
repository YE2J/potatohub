# 数据管线手动回补指南 (Backfill After Mass Failure)

使用场景: 某晚管线批量失败（外置盘 TCC 拒绝、迁移完成太晚、token 临时错误等）后，
补回缺失交易日数据。所有脚本支持手动回补，且幂等（INSERT OR REPLACE），可安全重跑。

## 回补命令矩阵

| 数据 | 脚本位置 | 回补命令 |
|------|---------|---------|
| daily_kline 前复权日线 | `~/.hermes/scripts/qfq_tushare_daily.sh` | `bash qfq_tushare_daily.sh 20260731` |
| moneyflow_daily 资金流 | `~/.hermes/scripts/daily_moneyflow_tushare_dc.sh` | `bash daily_moneyflow_tushare_dc.sh 20260731` |
| index_daily 指数 | `~/.hermes/scripts/daily_index_tushare.sh` | `bash daily_index_tushare.sh`（增量模式自动补缺口） |
| sector_moneyflow_ths | `~/my_quant_system/scripts/daily_sector_moneyflow.py` | `~/.hermes/venv_cron/bin/python3 scripts/daily_sector_moneyflow.py --date 20260731` |
| sector_moneyflow_dc | `~/my_quant_system/scripts/daily_sector_moneyflow_dc.py` | `... --date 20260731` |
| margin_balance 两融 | `~/.hermes/scripts/daily_margin_balance.sh` | `bash daily_margin_balance.sh`（从最近缺口自动拉取） |
| L1 大盘温度 | `~/my_quant_system/engines/market_temperature.py` | `venv_cron/bin/python3 engines/market_temperature.py --date 2026-07-31` |
| L2 板块轮动 | `~/my_quant_system/engines/sector_rotation.py` | `... --date 2026-07-31` |
| L3 决策融合 | `~/my_quant_system/engines/decision_fusion.py` | `... --date 2026-07-31` |

参数格式:
- kline / moneyflow / sector: `YYYYMMDD`（8位）
- 引擎: `--date` 接受 `YYYY-MM-DD` 或 `YYYYMMDD`（示例用 `YYYY-MM-DD`）
- index: 无参数增量；`--backfill` 为全量回补（重，一般用增量即可）

## 关键规则（易错点）

1. **回补数据后必须手动重跑 L1→L2→L3 引擎**，且逐日 `--date` 跑。
   数据表补齐不会自动触发引擎重算，否则晨报仍显示"昨日无温度数据"。
2. **margin 数据 T+1 发布**：回补最近交易日可能"写入 0 条"——这是正常现象，
   不是脚本失败。缺口由下一个工作日 18:35 cron 自动补（margin cron 仅工作日 `35 18 * * 1-5` 运行；
   注意周五数据周六早回补=0 条，要等周一 cron）。
3. **kline 部分写入可重跑补全**：脚本 `STOCK_MIN_COUNT = 4800`，`has_data_for_date()` 只跳过
   >=4800 行的日期。部分写入（如 2744 行）会正常重跑，补全至 ~5197。
4. **并行回补**：kline（105 批）和 moneyflow 各耗时约 2~4 分钟，用
   `terminal(background=true, notify_on_complete=true)`；不同脚本可并行，同一脚本多日期串行。
5. **回补前先 source token**：`source ~/.hermes/.env.tushare; export TUSHARE_TOKEN`。
6. **验证方式**：回补后查 `SELECT date, COUNT(*) ... GROUP BY date`，对照期望值：
   kline~5197 / moneyflow~5900-6000 / index=5行 / sector THS=386+90 / sector DC=504+496。

## 迁移后遗留文件清理

DB 从外置盘 symlink 迁到内置盘实体文件后，以下旧文件可安全删除
（先 `lsof <file>` 确认无进程占用）:

```bash
cd ~/my_quant_system
rm -f stock_data.db.real              # 旧实体快照，可达 3.8G+
rm -f stock_data_new.db-shm stock_data_new.db-wal   # 迁移中间产物
rm -f stock_data.symlink_to_external.bak            # 旧 symlink 备份
rm -f stock_data.bak.db-shm stock_data.bak.db-wal   # 历史备份
```

清理后 `ls -la ~/my_quant_system/ | grep stock_data` 应只剩 `stock_data.db` 及其 `-shm/-wal`。
外置盘 `/Volumes/500gb/data/stock_data.db` 保留为备份（best-effort 月推 db_backups/）。

## 2026-08-01 实战案例

背景: 7-31 晚 18:00~22:00 全部 15+ 管线失败（`unable to open database file`，
外置盘 TCC 会话锁拒绝），DB 迁移 23:07 才完成 → 8-1 晨报显示"数据延迟 3 个交易日"、
"昨日无温度数据"、多个采集任务 ❌。
**根因方向: 不是迁移导致失败，而是迁移完成太晚——管线仍打到 symlink → 外置盘。**

回补步骤（全部成功）:
1. 并行后台启动: kline 20260730+20260731 / moneyflow 20260730+20260731 / index+margin
2. sector THS+DC: `for d in 20260729 20260730 20260731; do ... --date $d; done`
3. 引擎: L1/L2/L3 各 `--date 2026-07-30` 和 `--date 2026-07-31`
4. 清理遗留文件（stock_data.db.real 3.8G 等）
5. 验证: integrity_check=ok; kline 7-30/7-31 各 5197; mf 5964/5933;
   idx 到 07-31(5行); sector THS 386/DC 504; temp 7-30=17.1冰点 / 7-31=37.7低温

结果: margin 7-31 待 T+1（下一工作日 18:35 cron 补），其余全部到位。

## 独立杂项发现

- 7-30 21:22 手动跑 kline 曾报 `您的token不对`——当前 token 已验证有效，
  属当时临时问题，无需处理（不要据此固化"token 坏了"的结论）。
