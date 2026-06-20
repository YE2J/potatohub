---
name: coze-hermes
description: Coze (扣子) 桌面端与本地 Hermes Agent 的集成方案：bash 执行验证、沙箱边界、分工架构、文件读写权限测试
dependency: {}
---

# Coze + Hermes 本地集成

## 任务目标

用 Coze（线上大脑）做调度/分析/通知，用 Hermes（本机）做执行/数据库/脚本运行。两者通过 Coze 桌面端 Electron 桥接本地 bash 执行来通信。

> **2026-06-20 重新评估**：三 Agent 并行评审后，Coze 从「对等协作者」降级为「数据补充源 + 兜底守护」。恒生聚源 5 类独有数据保留，独立日报和频繁心跳砍掉。详阅 `references/architecture-reevaluation-20260620.md`。**最终数据源综合推荐（保留/砍掉/成本/L2决策）见** `references/final-data-source-recommendation-20260620.md`。

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

```
Coze（云端大脑）:
  ├─ 恒生聚源机构数据（Coze 独占）
  ├─ Calendar 定时调度
  ├─ 按需触发：用户说"估值 600519"→ 执行本地 bash
  └─ 汇总分析 + 异常提醒

Hermes（本地执行引擎）:
  ├─ batch_valuation.py — 读 SQLite → 逐只估值 → 写结果
  ├─ 单只/多只即席估值
  ├─ SQLite 数据存储（~/my_quant_system/stock_data.db）
  └─ 估值脚本：industry_mapper.py, get_financials.py, calculate_valuation.py
```

## SQLite 数据库

路径：`/Users/yellow/my_quant_system/stock_data.db`

关键表：
- `watchlist` — 自选股（stock_code, stock_name, group_id, group_name, added_at）
- `valuation_results` — 估值结果（stock_code, stock_name, run_date, pe_ttm, consensus_fair/low/high, rating, stars, report_text 等）

估值脚本在：`~/.hermes/skills/a-stock-valuation/scripts/`

### Coze ↔ Hermes 每日日报协作 (v2)

### Hermes ↔ Coze 双向守护 (Mutual Watchdog) — v2

当用户不在电脑旁时，通过 **launchd KeepAlive（系统级进程守护）+ Coze 10min 兜底检查 + 主人口令触发** 三层保障 Hermes 可用性。

**架构分层：**
- **治本层：** launchd KeepAlive — 进程死掉自动拉起，无需任何脚本
- **诊断层：** Hermes cron 每 30s 写心跳 + HTTP 自检
- **兜底层：** Coze 每 10min 深度检查（curl /health + 心跳新鲜度）
- **救火层：** 主人说"救Hermes" → Coze 跑救火脚本（方案A kickstart || 方案B nohup）

**救命脚本覆盖的故障：** .env 丢失 / Python AMFI 拦截 / gateway 假死 / kickstart 失败

详细勘查记录、v1→v2 演进和评审记录见 `references/mutual_watchdog.md`。

### 概述
Coze (00:00:00) 和 Hermes (00:00:10) 每天自动生成日报到共享目录 `~/quant_shared/daily_reports/`。Coze 写完报告后 touch 信号文件，Hermes 轮询信号文件后生成自己的报告。双方互读对方报告并写独立反馈文件。

### 共享目录结构
```
~/quant_shared/daily_reports/
├── _ready_coze_YYYY-MM-DD          ← Coze 信号文件
├── YYYY-MM-DD_coze.md              ← Coze 日报
├── YYYY-MM-DD_hermes.md            ← Hermes 日报
├── YYYY-MM-DD_coze_feedback_hermes.md  ← Hermes 对 Coze 的反馈
├── YYYY-MM-DD_hermes_feedback_coze.md  ← Coze 对 Hermes 的反馈
├── feedback_log.md                 ← 反馈汇总表
└── archive/                        ← >90天归档
```

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
- `~/my_quant_system/scripts/hermes_daily_report.sh` — 信号轮询 + 清理
- `~/my_quant_system/scripts/hermes_daily_report.py` — frontmatter 解析 + 日报生成 + 章节自检
- `~/my_quant_system/scripts/hermes_append_feedback.py` — 写反馈 + SQLite feedback_log (v2.1)
- `~/.hermes/scripts/hermes_daily_report.sh` — Cron wrapper

### Coze 端脚本（Hermes 宿主 Mac 上运行）
- `~/my_quant_system/scripts/coze_daily_report.sh` — 调用 generate_daily_report.py + touch 信号文件
- `~/my_quant_system/scripts/generate_daily_report.py` — Coze 工作报告生成器（v2.1 + SIGTERM handler）
  - 常见 bug 模式见 `references/generate_daily_report_bugs.md`

### Cron Job
- Job ID: `00b779e99fdf`，调度 `10 0 * * *` (00:10 CST)，`no_agent: true`

### feedback_log — SQLite (v2.1)

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

### generate_daily_report.py 常见 5 大 Bug + 跨脚本标签 Bug\n\n该脚本在 `build_report()` 执行期间本身正在 `etl_run` 上下文中，会产生自引用问题。4 个核心 bug + 1 个跨脚本标签 bug 模式及验收 checklist 见 `references/generate_daily_report_bugs.md`。

---

## 注意事项

- Coze 桌面端需要保持运行才能执行本地命令
- Coze bash 执行权限由桌面端控制，云端 Agent 无感
- 文件写入优先用 stdout 输出，避免依赖沙箱外文件系统
- 首次集成时，先跑验证脚本确认 bash 通路正常
