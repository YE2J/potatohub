---
name: coze-hermes
description: Coze (扣子) 桌面端与本地 Hermes Agent 的集成方案：bash 执行验证、沙箱边界、分工架构、文件读写权限测试
dependency: {}
---

# Coze + Hermes 本地集成

## 任务目标

用 Coze（线上大脑）做调度/分析/通知，用 Hermes（本机）做执行/数据库/脚本运行。两者通过 Coze 桌面端 Electron 桥接本地 bash 执行来通信。

> **2026-06-20 重新评估**：三 Agent 并行评审后，Coze 从「对等协作者」降级为「数据补充源 + 兜底守护」。恒生聚源 5 类独有数据保留，独立日报和频繁心跳砍掉。详阅 `references/architecture-reevaluation-20260620.md`。**最终数据源综合推荐见** `references/final-data-source-recommendation-20260620.md`。
>
> **2026-06-26 路径统一 & 调度重构**：共享目录从 `~/.hermes/health_shared/` 迁移到 `~/quant_shared/`（symlink → `~/quant_shared_real/`）。cron 调度从 Hermes cron 迁移到系统 crontab。详见下方更新章节。

## Coze 桌面端 — 关键事实

| 项目 | 值 |
|------|-----|
| App 路径 | `/Applications/扣子.app` |
| 运行时架构 | Electron (Chromium) |
| 用户数据目录 | `~/Library/Application Support/Coze/` |
| CFBundleExecutable | `Coze`（pgrep 必须用 "Coze" 而非 "扣子"） |
| 进程名 | `Coze Helper (Renderer)`, `Coze Helper (GPU)`, etc. |
| 本地执行方式 | Coze 云端 Agent 通过桌面端 Electron IPC 执行本地 bash 命令 |

### Coze 能力约束（2026-06-19 实测）

| 约束 | 值 | 影响 |
|------|-----|------|
| 定时任务最小间隔 | **10 分钟** | ❌ 不能做 30s/60s 心跳 |
| bash 写文件 | ✅ 无沙箱拦截（`~/.hermes/health_shared/` 可读写） | 共享目录方案可行 |
| bash 执行可靠性 | ✅ 稳定（桌面端在线即可） | 救命脚本可依赖 |
| Coze 云端 Agent | 永不依赖 Mac mini | Coze 不需要被 Hermes 救 |
| Coze.app 桌面端 | 仅 UI，主人有多渠道（移动 APP/网页） | 桌面端挂了不影响 Agent 可用性 |

### Coze 云端 vs Coze 桌面端

**Coze 云端 Agent** = 运行在 Coze 基础设施上的 AI，主人通过任何客户端都能对话。**不需要被 Hermes 救。**

**Coze 桌面端 (Coze.app)** = Mac mini 上的 Electron UI 客户端。挂了对 Agent 服务无影响——主人有移动 APP、网页版等替代渠道。

## 验证 Coze 能否执行本地命令

### 标准验证流程

1. 在 Hermes 端创建测试脚本，写入可检查的痕迹文件：
   ```bash
   echo "coze_test_$(date)" > /tmp/coze_test_result.txt
   ```

2. 在 Coze 对话中让扣子执行：
   ```
   请在本机执行 bash /path/to/test.sh
   ```

3. 从 Hermes 端检查产物文件是否生成。

### 已知坑点：沙箱文件写入

Coze 的 bash 执行**可能是沙箱化的**——脚本 stdout 会显示在 Coze 聊天窗口，但写入用户目录的文件可能不会出现在真实文件系统中。验证时：
- **优先用 `/tmp/` 路径**写测试文件
- 如果 `/tmp/` 也不行，让 Coze 用 stdout 直接输出结果在聊天里

## Coze ↔ Hermes 分工模式

> **2026-06-25 重新确认**：经过三方 Agent 并行评审，数据管线最终方案：**Coze 统一提供所有行情数据（不复权 + 前复权），Hermes 纯消费。** 详阅 `references/data-pipeline-division-20260625.md`。

```
Coze（云端数据源 + 调度）:
  ├─ 恒生聚源 MCP → 不复权原始行情（dz_dailyquote）
  ├─ 腾讯 fqkline API → 前复权日K线（daily_kline）
  ├─ Calendar 定时调度
  ├─ 按需触发：用户说"估值 600519"→ 执行本地 bash
  └─ 汇总分析 + 异常提醒

Hermes（本地消费引擎）:
  ├─ 数据导入：Coze 推送 CSV → 本地 SQLite
  ├─ 策略运行 / 回测 / 日报生成
  ├─ 告警推送（deliver:origin → 微信）
  ├─ SQLite 数据存储（~/my_quant_system/stock_data.db）
  └─ 估值脚本：industry_mapper.py, get_financials.py, calculate_valuation.py
```

### 数据管线决定（2026-06-25）

| 决定 | 说明 |
|------|------|
| **不复权行情** | Coze 恒生聚源 → `dz_dailyquote` 表 |
| **前复权行情** | Coze 腾讯 fqkline → `daily_kline` 表（直接返回前复权，无需本地计算） |
| **Tushare adj_factor** | ❌ 放弃。积分=0 无法调用，且腾讯直接给前复权无需此环节 |
| **Hermes 角色** | 纯消费者，不负责任何数据拉取或复权计算 |

### QFQ 增量导入管线（2026-06-27 新建）

Coze 日历任务每日凌晨拉取全量前复权 → 上传项目空间 `/data/qfq/` → Hermes cron 05:30 自动下载导入。

数据文件：`/data/qfq/qfq_incremental_{YYYYMMDD}.csv.gz`
信号文件：`/data/qfq/signal_{YYYYMMDD}.json`（格式: `{"status":"ok|partial|failed","trade_date":"...","row_count":N}`）

Hermes 侧：`~/.hermes/scripts/qfq_import.sh`（no_agent, deliver=local, 周一到周五 05:30），从 Coze 项目空间下载信号+数据文件，解析 JSON status，INSERT OR REPLACE 导入 daily_kline 表，验证行数后写入日志 `~/.logs/qfq_import.log`。

完整架构详见 `references/qfq-auto-import.md`。

## SQLite 数据库

路径：`/Users/yellow/my_quant_system/stock_data.db`

关键表：
- `watchlist` — 自选股（stock_code, stock_name, group_id, group_name, added_at）
- `daily_kline` — 前复权日K线（stock_code=InnerCode, date, OHLCV）
- `moneyflow_daily` — 资金流向（大/中/小/超大单买卖额，来源: 东方财富 push2his）
- `valuation_results` — 估值结果（stock_code, stock_name, run_date, pe_ttm, consensus_fair/low/high, rating, stars, report_text 等）

> 💡 资金流向推荐改用问财 OpenAPI `hithink-market-query`，可获取完整的特大/大/中/小单**成交量（股）**+ 成交额（元），详见 iwencai-skillhub → `references/iwencai-moneyflow-fields.md`。

估值脚本在：`~/.hermes/skills/a-stock-valuation/scripts/`

### Coze ↔ Hermes 共享目录（2026-06-26 更新）

**核心变更**：共享目录从 `~/.hermes/health_shared/` 迁移到 `~/quant_shared/`（symlink → `~/quant_shared_real/`）。

#### 两层级共享目录

| 层级 | 路径 | 用途 | 谁读写 |
|:---:|:---|:---|:---:|
| **日报层** | `~/quant_shared/daily_reports/` | 日报文件、信号文件 | Hermes+Coze 均可用 |
| **同步层** | `~/quant_shared/daily_sync/` | Coze 任务同步文件 | Coze 上传，Hermes 下载 |
| **心跳层** | `~/.hermes/health_shared/` | 心跳、自检、临时工单 | Hermes 写入，Coze 读取 |

#### 日报目录结构
```
~/quant_shared/daily_reports/
├── _ready_coze_YYYY-MM-DD           ← Coze 信号文件
├── YYYY-MM-DD_coze.md               ← Coze 日报
├── YYYY-MM-DD_hermes.md             ← Hermes 日报
├── YYYY-MM-DD_hermes_feedback_coze.md ← Hermes 反馈
├── YYYY-MM-DD_coze_feedback_hermes.md ← Coze 反馈
└── archive/                         ← >90天归档
```

### Coze 同步方案（Scheme D）

Coze 日历任务 00:15 触发 → 用 `write_file` 工具直接写同步文件到 `~/quant_shared/daily_sync/coze_sync_{YYYY-MM-DD}.md`。

**不需要 Hermes 侧下载脚本**。`download_coze_sync.sh` 已废弃（标注 DEPRECATED，保留仅供参考），对应的系统 crontab 条目已删除。

`hermes_daily_report.py` 已内置读取 coze_sync 文件的逻辑（Section 2 "Coze 日任务同步"），文件不存在时优雅降级。

#### ⚠️ 路径一致性规则

**所有脚本必须使用 `~/quant_shared/`（symlink 路径），不得硬编码 `~/quant_shared_real/`。**
- `coze_daily_report.sh`, `hermes_daily_report.sh/.py`, `download_coze_sync.sh`, `daily_morning_report.sh` 全部统一使用 symlink 路径
- 未来如果 real 目录变更，只需修改 symlink 一处，无需改所有脚本

#### 路径更新检查

修改 `COZE_SYNC_DIR` 等路径变量后，用以下命令确认无 real 残余：
```bash
grep -rn "quant_shared_real" ~/my_quant_system/scripts/ ~/.hermes/scripts/ --include="*.sh" --include="*.py" || echo "✅ 零残余"
```

当用户不在电脑旁时，通过 **launchd KeepAlive（系统级进程守护）+ Coze 10min 兜底检查 + 主人口令触发** 三层保障 Hermes 可用性。

**架构分层：**
- **治本层：** launchd KeepAlive — 进程死掉自动拉起，无需任何脚本
- **诊断层：** Hermes cron 每 30s 写心跳 + HTTP 自检
- **兜底层：** Coze 每 10min 深度检查（curl /health + 心跳新鲜度）
- **救火层：** 主人说"救Hermes" → Coze 跑救火脚本（方案A kickstart || 方案B nohup）

**救命脚本覆盖的故障：** .env 丢失 / Python AMFI 拦截 / gateway 假死 / kickstart 失败

详细勘查记录、v1→v2 演进和评审记录见 `references/mutual_watchdog.md`。
Session 历史工单报告生成模式（用户问「这几天做了什么」时的完整流程）见 `references/session-audit-report-pattern.md`。

### 共享目录结构

```
| **心跳层** | `~/.hermes/health_shared/` | 心跳、自检、临时工单 |

**同步方案（Scheme D）**：Coze 日历任务 00:15 直接用 `write_file` 写入同步文件到 `~/quant_shared/daily_sync/coze_sync_{date}.md`。Hermes 日报（01:30）自动读取。不需要 Hermes 侧下载脚本。

### 旧共享目录清理

`~/.hermes/health_shared/` 曾用于日报交换，2026-06-26 已迁移到 `~/quant_shared/`。当前仅保留心跳文件和归档目录，不再用于日报。

### 核心机制

| 机制 | 说明 |
|------|------|
| 信号文件 | `_ready_coze_YYYY-MM-DD` — Coze 写完报告后创建 |
| 轮询超时 | Hermes 每 **10s** 轮询，**30s** 超时 → 降级读昨日（2026-06-19 调优：原 30s/90s 导致 cron 120s 超时） |
| Frontmatter | 每份日报开头 YAML 块: `status: ok\|partial\|missing`, `generated_at`, `agent: coze\|hermes` |
| 章节自检 | 8 个必要章节，任一缺失报警 |
| 清理策略 | `find -mtime +90 → archive/`，**后台运行**（`&`），不阻塞主流程 |
| 时间格式 | ISO 8601 (`YYYY-MM-DDTHH:MM:SS+08:00`) |

### Hermes 端脚本
- `~/my_quant_system/scripts/hermes_daily_report.sh` — v2.2，信号轮询 + 清理。支持 `REPORT_DATE` 环境变量指定日期。改用 `/usr/bin/python3`。（注意：output 目录必须为 ~/.hermes/health_shared/）
- `~/my_quant_system/scripts/hermes_daily_report.py` — frontmatter 解析 + 日报生成 + 章节自检
- `~/my_quant_system/scripts/hermes_append_feedback.py` — 写反馈 + SQLite feedback_log (v2.1)
- `~/.hermes/scripts/daily_morning_report.sh` — v3.0，每日 07:00 统一晨报。聚焦 A股日线+资金流+日报对齐+备份。`no_agent: true` + `deliver: origin`。

### Coze 端脚本（Hermes 宿主 Mac 上运行）
- `~/my_quant_system/scripts/coze_daily_report.sh` — v2.2，调用 generate_daily_report.py + touch 信号文件。改用 `/usr/bin/python3`，不再依赖 `.venv`。支持 `REPORT_DATE` 环境变量补跑历史日期。
- `~/my_quant_system/scripts/generate_daily_report.py` — v2.2，Coze 工作报告生成器（含 SIGTERM handler）。修复日期参数：`sys.argv[1]` 支持指定日期补跑历史报告。
  - 常见 bug 模式见 `references/generate_daily_report_bugs.md`

## 数据管线 crontab（2026-06-27 最终版）

```
00:00  venv_guard.sh
00:05  coze_daily_report.sh
01:30  hermes_daily_report.sh
04:00  daily_moneyflow_iwencai.sh backfill    ← 资金流向回补
05:30  qfq_import.sh (Mon-Fri)                ← 前复权增量
18:30  daily_moneyflow_iwencai.sh incremental ← 资金流向增量
```

### 资金流向数据源（2026-06-29 更新）

- **主力**：同花顺 THS 全量数据（data_source='ths'），5,663 只，14M 行，2007~今
- ~~问财 hithink-market-query（已停用，被 THS 数据替代）~~
- ~~东方财富 push2his（保留32行历史，不做主数据源）~~
- 存储：moneyflow_daily 表（四档买卖量+额，手+万元）
- 每日增量待续购数据商确认后更新

#### 系统 crontab（3 条，2026-06-30 最新）

```cron
0  0 * * *  venv_guard.sh              # 健康检查
5  0 * * *  coze_daily_report.sh       # Coze 日报
30 1 * * *  hermes_daily_report.sh     # Hermes 日报（读取 coze_sync）
```

> `coze_incremental_update.py` 和 `download_coze_sync.sh` 的 cron 已删除（2026-06-26）。数据导入由 qfq_import.sh（系统 crontab 05:30 Mon-Fri）和 daily_moneyflow_iwencai.sh（系统 crontab 18:30 Mon-Fri）负责。

#### Hermes cron（仅保留 2 个，2026-06-30）
| job | 调度 | deliver | 说明 |
|:---|:---:|:---:|:---|
| 每日晨报推送 | `0 7 * * *` | `origin` | **唯一允许推微信的 cron** |
| Wiki 增量整理 | `30 3 * * *` | `local` | 数据整理，不推送 |

#### 每日 07:00 统一晨报 v3.0

**设计目标**: 将所有 cron 结果整合为**一条消息**推微信，避免 iLink 限流。聚焦实质数据，去掉旧内容和冗余。

**数据源**（v3.0）:
- A股全量日线日志 `~/.logs/qfq_import.log`（05:30 Mon-Fri 产出）
- 资金流日志 `~/.logs/moneyflow_cron.log`（18:30 Mon-Fri 产出）
- Coze/Hermes 日报 `~/quant_shared/daily_reports/`
- Coze 同步文件 `~/quant_shared/daily_sync/coze_sync_{date}.md`

**内容结构**:
1. 📊 A股全量日线 — 导入状态、只数、成功/失败
2. 💰 资金流 — hits/inserted、Key 状态
3. 🤖 日报对齐 — 两报是否存在、信号是否对齐、没干成的事
4. 🔄 Coze 任务同步 — 前 8 行摘要
5. 备份到 `~/quant_shared/daily_reports/archive/morning/`（30天自动清理）

**实现**: `~/.hermes/scripts/daily_morning_report.sh` v3.0 — `no_agent: true` + `deliver: origin`

#### 推送限流规则（核心约束）
- **新增 cron 默认 `deliver: local`**（只存不推送）
- **仅每日晨报**（`daily_morning_report.sh`, 07:00）可 `deliver: origin` 推微信
- 新接入通讯平台同样先评估该平台的推送频率限制
- 违反此规则的 cron 会在微信端触发 iLink 30s cooldown 限流
- venv 健康检查、DB 备份状态、CSRC 案例、热门板块、估值日报 (定时任务已不存在)
- "最近工作摘要"、"待主人决策" 等伪更新章节

### 共享目录结构

```sql
-- 在 stock_data.db 中，WAL 模式，并发安全
CREATE TABLE feedback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_time TEXT NOT NULL,      -- ISO 8601
    from_role TEXT NOT NULL,     -- coze / hermes
    to_role TEXT NOT NULL,
    feedback_type TEXT NOT NULL, -- read/confirm/question/coordinate
    message TEXT,
    target_date TEXT NOT NULL
);
```

- `feedback_log.md` 是从 DB 自动导出的可读副本，不是主存储
- Coze 和 Hermes 都 INSERT 同一张表，SQLite WAL 自动排队，无需 flock
- 旧 feedback_log.md 内容首次运行时自动迁移到 DB

### 查询失败重试策略 (v2.1)

| 决策 | 值 | 理由 |
|------|---|------|
| 策略 | 单查询内部 retry 1 次 | DB 锁/网络抖是 80%+ 失败原因 |
| 间隔 | 5 秒 | 覆盖 DB 锁释放 + akshare rate limit |
| 次数 | 1 次 | 2 次边际收益 <5%，不值 |

### 章节正则自检的坑
Coze 和 Hermes 的章节命名因报告者角色视角不同而变化（如 Coze 写 "Hermes 对 Coze 报告的反馈"，Hermes 写 "对方对昨日报告的反馈"），正则必须宽松适配，用 `对.*报告.*反馈` 而非 `对方对.*报告的反馈`。

详细参考：`references/daily_report_v2.md`

### Cron 超时排查流程（2026-06-19 建立）

当日报 cron 失败时，按以下流程排查：

1. **查 cron job 状态**：`hermes cron list` → 看 last_status + last_run_at
2. **查输出文件**：`~/.hermes/cron/output/<job_id>/` → 看错误信息
3. **判断瓶颈**：
   - `Script timed out after 120s` → 脚本总耗时超过 cron 限制
   - 检查脚本的 sleep/poll 时间是否合理（不应超过 30s）
4. **协同诊断**：写诊断文档到共享目录（如 `hermes_timeout_diagnosis.md`），双方各自修复自己侧
5. **修复后反馈**：写 `YYYY-MM-DD_hermes_feedback_coze.md` 到共享目录

**常见瓶颈**：
- 轮询 sleep 过长 + 大 interval → 多轮叠加超限
- Python 脚本里的网络调用超时（akshare API）
- `find -exec mv` 同步阻塞（改为 `&` 后台）

### Python venv 兼容性：macOS 26.2

**问题**：Homebrew Python 3.11.15_3 在 macOS 26.2 上有 dyld 兼容性问题（`libexpat` 符号缺失），pip/ensurepip 全部报错。

**症状**：
```
ImportError: Symbol not found: _XML_SetAllocTrackerActivationThreshold
Expected in: /usr/lib/libexpat.1.dylib
```

**修复**：改用系统 Python（`/usr/bin/python3`，目前 3.9.6），对量化栈完全兼容（pandas 2.3.3 + akshare 1.18.64）。

**注意**：系统 Python 3.9.6 的 pip 初始版本较旧（21.x），需先 `pip install --upgrade pip`。

### SIGTERM handler：防 cron 超时残留 running 状态

当 cron 超时发送 SIGTERM 杀 Python 进程时，`etl_runs` 表里会残留 `status='running'` 的记录。

**修复**：在 Python 脚本里加 signal handler：

```python
import signal
_CURRENT_RUN_ID = None

def _handle_sigterm(signum, frame):
    if _CURRENT_RUN_ID is not None:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute(
            "UPDATE etl_runs SET status='failed', finished_at=datetime('now'), "
            "error_message='killed by SIGTERM (cron timeout)' "
            "WHERE run_id=? AND status='running'",
            (_CURRENT_RUN_ID,)
        )
        conn.commit()
    sys.exit(1)

signal.signal(signal.SIGTERM, _handle_sigterm)
```

在 `main()` 里设置 `_CURRENT_RUN_ID = run.id`。

详细排查步骤见 `references/troubleshooting.md`。

### Coze CLI 文件下载

`coze agent file download` 命令在 CLI v0.3.2 中**可用**（已验证 2026-06-26）。子命令：`list`, `write`, `read`, `edit`, `upload`, `download`。

#### 下载脚本（已废弃）

```bash
# 下载方式切换：
# 1. 如果文件已存在（Coze 桌面端直接写入）→ 跳过
# 2. 如果 coze CLI 支持下载 → 用 CLI
# 3. 如果 Coze 报告已就绪 → 跳过并提示（报告内容可替代）
# 4. 否则 → 静默跳过，不报错
```

**实现**：脚本必须幂等（文件已存在则跳过），不能因 CLI 不支持而导致 cron 失败。Coze 同步文件优先由 Coze 桌面端直接写入共享目录。

#### `hermes_daily_report.py` 章节计数模式

章节数量变化时必须使用 **动态计数**，不得硬编码：
```python
# ✅ 正确
f"> 缺失 ({len(missing_chapters)}/{len(REQUIRED_SECTIONS)}): "

# ❌ 错误（session 2026-06-26 发现 2 处此类硬编码残留）
f"> 缺失 ({len(missing_chapters)}/8): "
```

**检查命令**：
```bash
grep -n '/8' ~/my_quant_system/scripts/hermes_daily_report.py || echo "✅ 零残余"
```

---

## 注意事项

- Coze 桌面端需要保持运行才能执行本地命令
- Coze bash 执行权限由桌面端控制，云端 Agent 无感
- 文件写入优先用 stdout 输出，避免依赖沙箱外文件系统
- 首次集成时，先跑验证脚本确认 bash 通路正常

## Pitfalls

### 日期格式混用（YYYYMMDD vs YYYY-MM-DD）

Coze 推送 `daily_kline` 数据时可能混用 `YYYYMMDD`（如 `20260623`）和 `YYYY-MM-DD`（如 `2026-06-24`）两种日期格式。影响：
- `ORDER BY date DESC` 时，`YYYY-MM-DD` 格式排在 `YYYYMMDD` 之前（`-` ASCII 45 < 数字 ASCII 48）
- `WHERE date >= '20260623'` 查不到 `2026-06-24` 格式的数据，反之亦然

**必须同时查两种格式**：
```sql
SELECT date, COUNT(*) FROM daily_kline
WHERE date LIKE '2026-06-2%' OR date LIKE '2026062%'
GROUP BY date ORDER BY date DESC;
```

**发现混用后**：向 Coze 报告，要求统一为 `YYYY-MM-DD`（ISO 8601）。

### 共享目录不要混用两层
`~/.hermes/health_shared/` 用于心跳/自检/临时工单（Hermes 写入，Coze 读取）。
`~/quant_shared/`（→ `~/quant_shared_real/`）用于日报/同步文件（双方读写）。
不要把日报文件写到 health_shared/，也不要把心跳写到 quant_shared/。

### 路径必须统一用 symlink
所有脚本必须用 `~/quant_shared/`，不得硬编码 `~/quant_shared_real/`。
验证：`grep -rn "quant_shared_real" scripts/ --include="*.sh" --include="*.py" || echo "✅"`

### coze CLI 已支持 file download
CLI v0.3.2 确认可用 `coze agent file download`。之前标注为"不存在"是错误的（2026-06-26 修正）。

### 章节计数不得硬编码
`hermes_daily_report.py` 的章节数变化时必须用 `len(REQUIRED_SECTIONS)` 替代硬编码数字。

### Session 历史工单报告 vs 日报
日报（daily report）是定时自动生成的，由 cron 触发。而用户询问「这几天做了什么」时，应该用 `session_search` 浏览+搜索历史会话，然后现场生成一次性工单报告，不要尝试复用日报生成脚本（日报和工单报告的 scope/格式完全不同）。
