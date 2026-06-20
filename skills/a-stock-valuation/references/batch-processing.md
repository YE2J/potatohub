# 批量估值架构（Hermes + 扣子 Coze）

## 架构分工

```
扣子（云端大脑）                    Hermes（本地执行引擎）
  │                                    │
  ├─ 恒生聚源机构数据更新              ├─ 数据预拉取（web_extract → JSON cache）
  ├─ Calendar 定时调度                 ├─ batch_valuation.py 执行
  ├─ 汇总分析 / 异常提醒               ├─ calculate_valuation.py 估值计算
  └─ 按需触发（"估值 600519"）        └─ SQLite 读写（valuation_results）
```

**关键**：扣子桌面端通过 Electron 桥接在 Mac 本地执行 bash，但运行在沙箱中。

## 扣子桌面端权限要求

| 权限 | 用途 | 设置路径 |
|------|------|---------|
| Full Disk Access | 读写 `~/my_quant_system/stock_data.db` | 系统设置 → 隐私与安全性 → 完全磁盘访问权限 → 添加 `/Applications/扣子.app` |

### Python 路径限制

扣子沙箱无法使用 pyenv Python（libpython 被拦截），必须使用：
- `~/my_quant_system/.venv/bin/python3`（优先，venv 中已装 akshare/pandas）
- 或 `/usr/bin/python3`（系统自带，缺 akshare）

## 数据获取（已内置实时降级，预拉取可选）

> **2026-06-17 更新**：`data_fetcher.py` 已内置三层降级：JSON 缓存 → 腾讯 API → akshare。**无需预先拉取数据即可直接估值**。

缓存目录（可选）：`~/.hermes/skills/a-stock-valuation/data/`

如有本地 JSON 缓存则优先读取（秒级），缓存缺失时自动走腾讯行情 API（价格/PE/PB/市值）+ akshare 同花顺财务摘要（营收/净利/ROE）。

> **东财 push2 已废弃**（2026-06-11 验证不可用），不要依赖。腾讯 API 格式参考 `references/tencent-api.md`，akshare 注意事项参考 `references/akshare-quirks.md`。

## batch_valuation.py

位置：`~/my_quant_system/scripts/batch_valuation.py`（由扣子编写并部署）

### 用法

```bash
# 全量估值（default 组所有股票）
cd ~/my_quant_system && python3 scripts/batch_valuation.py

# 单只
cd ~/my_quant_system && python3 scripts/batch_valuation.py 600519

# 多只
cd ~/my_quant_system && python3 scripts/batch_valuation.py 600519,000001,000988
```

### 工作流

1. 读 `watchlist` 表（`WHERE group_id='default'`）
2. 逐只调用 `calculate_valuation.py --model auto --json --output /tmp/_val_{code}.json`
3. 解析 JSON → 提取 primary_model 结果 → INSERT INTO `valuation_results`
4. 输出概览（最近 10 分钟入库的结果，按 safety_margin 排序）

### 写入字段映射

| valuation_results 列 | 来源 |
|----------------------|------|
| stock_code, stock_name | watchlist |
| current_price | `data.current_price` |
| pe_ttm | `financials_summary.pe_ttm` |
| roe | `financials_summary.roe` |
| growth_rate | `financials_summary.cagr_3y` |
| consensus_fair | 首选模型的 `value_mid` |
| consensus_low | 首选模型的 `value_low` |
| consensus_high | 首选模型的 `value_high` |
| safety_margin | `(value_mid/price - 1) * 100` |
| rating | 基于 safety_margin 的阈值判断 |
| stars | ★ 评级（1-5 星） |
| report_text | 结构化摘要文本 |
| primary_model | 使用的估值模型名（PE/PB/DCF 等） |

## Cron 定时任务

在 Hermes 侧配置（非扣子）：

```
0 0 * * 0  cd ~/my_quant_system && .venv/bin/python3 scripts/batch_valuation.py >> logs/batch_valuation.log 2>&1
```

## 已知问题

### 1. ~~预拉取数据缺失~~（已解决：2026-06-17）

`data_fetcher.py` 已内置腾讯行情 API + akshare 同花顺财务实时降级，无需预拉取。详见 `references/tencent-api.md` 和 `references/akshare-quirks.md`。

### 2. watchlist 含非股票代码 → 批量估值产生垃圾数据

症状：`valuation_results` 出现 `1B0001`、`1A0002` 等指数代码，price=0.0

原因：watchlist 可能混入 1A/1B 开头的指数代码和 ETF。

解决：批量估值前过滤 `stock_code NOT GLOB '1[A-C]*'`；定期清理 watchlist。

### 3. 概览打印 None 崩溃

症状：`TypeError: unsupported format string passed to NoneType.__format__`

原因：估值失败时 `consensus_fair` 为 None。

解决：概览打印处加 `or 0` 保护（v3.1 已修复）。

## P3 Phase 1 改进（2026-06-17）

- **etl_runs 表**：全量任务状态追踪（run_id, job_name, status, duration_sec, fail_count）
- **batch_valuation.py v3.1**：文件锁（`fcntl.flock`）防并发、新字段写入（model_version, data_as_of, run_id, data_source）
- **valuation_results 新字段**：`model_version`, `data_as_of`, `run_id`, `data_source`
- **Cron 任务**：每日 03:00 DB 备份 + 每日 08:30 估值日报推微信
- **评级分布已知**：当前 110 只全量估值中 88 只"显著高估"，需周日人工判断是市场真实状况还是模型参数偏保守
