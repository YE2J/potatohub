# 系统一（已删除 — 仅作历史参考）

> 系统一 `~/Documents/量化回测/` 已于 2026-06-16 彻底删除。
> 所有核心逻辑已迁入系统二 `~/my_quant_system/`（见 `unified_system_files.md`）。
> 以下内容仅为历史记录，帮助理解各模块的迁移来源。

## 系统一：`~/Documents/量化回测/`（已删除）

### 核心源码
```
config.py          — 99只自选股 + BacktestConfig dataclass（起始资金100万、万3佣金、千1印花税）
data_fetcher.py    — 腾讯ifzq日K线API（qfq前复权）+ akshare回退，含parquet缓存逻辑
indicators.py      — ~29KB，3个有效指标：calc_zhuli_radar(), calc_ai_activity(), calc_gs_signal()
strategies.py      — ~20KB，v3规则引擎：五层决策(打分制)，暗盘/持仓已标记False
backtest.py        — v3单票回测引擎
backtest_v4.py     — 526行，v4多票组合引擎（GS+主力雷达+组合管理+冷静期）
main.py            — 204行，CLI入口 `python main.py --codes ...` / `--assess-db`
analyze_losers.py  — 亏损诊断脚本
```

### 数据/结果
```
cache/002552_qfq.csv              — 仅1个缓存文件（pyarrow未安装导致parquet静默失败）
results/summary.txt               — 早期回测汇总
results/summary_v2.txt            — v2规则引擎汇总
results/v4_multi_result.csv       — v4多票组合结果
results/000988_result.csv         — 华工科技单票结果
results/000999_result.csv         — 华润三九
results/301338_result.csv         — 凯格精机
results/301526_result.csv         — 国际复材
```

### 虚拟环境
```
.venv/  — Python 3.9, akshare 1.18.64
```

### 已知问题
- pyarrow 未安装 → parquet 缓存静默失败，每次运行重新拉数据
- 腾讯API单次最多800条（~2.5年）
- 无定时更新机制

---

## 系统二：`~/my_quant_system/`

### 核心源码
```
config.py                    — 全局配置（demo单股STOCK_CODE="000001"）
data_manager.py              — 459行，StockDataManager：akshare+腾讯API，SQLite+Parquet双存储
strategy.py                  — backtrader策略类 MyStrategy
main.py                      — CLI入口
fast_download.py             — 快速下载脚本
valuation_channel.py         — PE-TTM估值通道生成器（复刻同花顺PE Band）
valuation_integration.py     — 估值集成模块
run_valuation_subprocess.py  — 估值子进程运行器
requirements.txt
```

### Web应用 (FastAPI)
```
app/__init__.py
app/main.py                  — 1035行，包含：仪表盘/自选股管理/策略管理/回测/估值/历史
app/static/style.css
app/templates/base.html
app/templates/index.html         — 仪表盘
app/templates/watchlist.html     — 自选股管理
app/templates/backtest.html      — 回测执行
app/templates/strategies.html    — 策略列表
app/templates/strategy_editor.html — 策略编辑器
app/templates/history.html       — 历史查询
app/templates/valuation.html     — 估值通道
app/templates/valuation_detail.html — 估值详情
```

### 数据库
```
stock_data.db        — SQLite 53MB，14张表：
  daily_kline        — 307只股票, 44,470条日线
  minute_kline       — 243,435条1分钟线
  minute5_kline      — 58,176条5分钟线
  backtest_results   — 3条回测结果
  trade_log          — 0条
  valuation_results  — 6条估值结果
  股本结构, 股东户数, 净资产收益率, A股营业总收入,
  REITs基金财务数据, 可转债补充
stock_data.db-shm    — WAL共享内存
stock_data.db-wal    — WAL日志
```

### 数据缓存
```
data/parquet/        — 106个.parquet文件（860KB），按股票代码命名
web_data/watchlist.json  — 自选股配置（cron job 从这里读取）
web_data/strategies/
  index.json              — 策略索引
  双均线金叉死叉.py       — 示例策略
自选股清单.txt            — 104只自选股（含ETF）
```

### 报告
```
reports/backtest_report_000001.html
reports/backtest_report_000988.html
reports/valuation/000988.png
reports/valuation/002409.png
reports/valuation/301338.png
```

### 定时任务
```
cron job_id: fda7975b8524
  名称: 自选股日线数据自动更新
  调度: 每天 00:00
  模式: no_agent=True
  脚本: ~/.hermes/scripts/daily_update_v2.sh（shell wrapper，强制用 venv Python）
  workdir: ~/my_quant_system/
  逻辑: 读取 watchlist.json → 检查DB最新日期 → 腾讯API增量拉取 → INSERT OR IGNORE → 更新Parquet
  静默: stdout为空时不推送
```

### 虚拟环境
```
.venv/  — Python 3.9, fastapi + uvicorn + backtrader + quantstats + jinja2 + matplotlib
```

---

## 迁移记录 (2026-06-16)

| 源文件 | 目标文件 | 修改 |
|--------|----------|------|
| `indicators.py` | `indicators_tdx.py` | 无修改（纯复制） |
| `strategies.py` | `strategies_v3.py` | 无修改（纯复制） |
| `backtest_v4.py` | `backtest_v4.py` | 导入路径适配（STOCKS→STOCKS_V4, indicators→indicators_tdx, data_fetcher→data_manager） |
| `analyze_losers.py` | `analyze_losers.py` | 导入路径适配（indicators→indicators_tdx） |
| `config.py` (系统一) | `config.py` (系统二) | STOCKS_V4 dict + V4_PARAMS 追加到系统二 config |
| — | `bridge.py` | 新建：适配层（DB→DataFrame→回测→DB保存） |
| — | `data_manager.py` | 新增 `load_to_dataframe()` 方法 |
