# 实测样例：~/my_quant_system AGENTS.md（2026-08-05 生成，58 行）

给 A股三层决策量化系统生成 AGENTS.md 的完整过程，作为复刻参考。

## 扫描清单（实际执行）

- 根目录 `ls -1`（40+ 文件：engines/ scripts/ docs/ app/ factor_engine/ data/ 等）
- requirements.txt（akshare / pandas / pyarrow / backtrader / quantstats / sqlalchemy / fastapi / uvicorn）
- docs/THREE_LAYER_ARCHITECTURE_PLAN.md（三层架构设计文档头部）
- engines/market_temperature.py / sector_rotation.py / decision_fusion.py 的 docstring（**命令唯一来源**）
- config.py 头部（DB_PATH / PARQUET_DIR / 回测参数常量）
- scripts/db_utils.py、scripts/valuation_utils.py 存在性确认
- sqlite_master 查真实表名（25+ 关键表：market_temperature / sector_rotation / leader_stocks / margin_balance / daily_kline / industry_moneyflow_dc 等）
- 自选股清单.txt 头部（104 只）
- `.git` 不存在 → 非 git 仓库，概述中注明

## 提炼出的约定（写进文件）

- 三层架构表：L1 温度（35%趋势+35%资金+30%情绪）→ L2 板块 → L3 融合，各层对应输出表
- 精确命令照 docstring：`python engines/market_temperature.py --date 2026-07-09`、`--backfill --start ... --end ...` 等
- 数据源：DC（东方财富）主源、THS 交叉验证
- 公共模块：config.py / scripts/db_utils.py / scripts/valuation_utils.py

## 坑点节素材（历史教训 + 观察）

1. 日期格式双轨：引擎 CLI 参数 `--date YYYY-MM-DD` vs config.py `START_DATE/END_DATE YYYYMMDD`
2. 单位换算：DC 资金流元/亿元（真实量级）vs THS 万元，跨源对比先统一
3. API 限频 ≥1.5s（防封）
4. cron 时序：18:00~18:50 采集 → 19:00~20:30 L1~L3 引擎 → 07:05 晨报（微信，字符上限约 3800）

## 产出

58 行 / 6 节，写入 `~/my_quant_system/AGENTS.md`。后续架构变更需同步更新该文件（用本 skill 的合并纪律）。
