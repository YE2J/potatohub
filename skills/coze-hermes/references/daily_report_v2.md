# 日报协作 v2 完整参考

> 创建于: 2026-06-18
> 关联: `coze-hermes` Skill 的"每日日报协作 (v2)"章节

## v2 增量改动（vs v1）

v1 只实现了基础的文件交换（写报告 → 读报告 → 写反馈）。v2 加了 3 个核心防御机制 + 3 个质量优化。

### 必须改的 3 个核心点

1. **信号文件机制** — 解决 race condition (00:00 vs 00:10 太短)
2. **Frontmatter 状态标记** — 解决失败兜底
3. **老报告归档** — 解决目录膨胀

### 建议加的 3 个小优化

4. 章节结构 schema 自检
5. feedback_log.md 集中维护
6. 时间戳统一 ISO 8601

## 信号文件流程

```
Coze 00:00:00
  ├─ 生成 YYYY-MM-DD_coze.md
  ├─ touch _ready_coze_YYYY-MM-DD
  └─ 清理 >90天报告

Hermes 00:00:10
  ├─ 轮询 _ready_coze_YYYY-MM-DD
  │   ├─ 每 10s 检查一次（2026-06-19 从 30s 调优）
  │   ├─ 30s 超时 → 降级（从 5min 调优，原值导致 cron 120s 超时）
  │   └─ 找到 → 立刻继续
  ├─ 解析 Coze 报告 frontmatter
  ├─ 章节完整性检查
  ├─ 生成 YYYY-MM-DD_hermes.md
  └─ 清理 >90天报告（后台 &，不阻塞）
```

## Frontmatter 格式

```yaml
---
status: ok|partial|missing
generated_at: 2026-06-20T00:01:23+08:00
agent: coze|hermes
---
```

- `status: ok` — 正常生成
- `status: partial` — Hermes 读到 Coze missing，降级生成
- `status: missing` — 完全失败

## 章节自检正则

Coze 和 Hermes 的章节命名因报告者角色视角不同而变化。自检用宽松正则：

| 场景 | Coze 会写 | Hermes 会写 | 正则 |
|------|----------|-------------|------|
| 昨日干了啥 | "1. 昨日 Hermes 干了啥（自动回执）" | "1. 昨日对方干了啥" | `(昨日\|干了啥\|干了)` |
| 反馈 | "2. Hermes 对 Coze 报告的反馈" | "2. 对方对昨日报告的反馈" | `对.*报告.*反馈` |
| 自动任务 | "3. 今日自动任务（etl_runs）" | "3. 日报系统状态" | `自动任务` |
| 估值明细 | "4. 今日估值明细" | "4. v2 合作日报配置" | `估值明细` |
| 统计 | "5. 最近 7 天任务统计" | "5. 最近工作摘要" | `统计` |
| 待决策 | "6. 待主人决策" | "6. 待主人决策" | `主人决策` |
| 配合 | "7. 需要 Hermes 配合的事项" | "7. 需要对方配合的事项" | `需要.*配合` |
| 待办 | "8. 待办 / 遗留" | "8. 待办 / 遗留" | `待办\|遗留` |

## 文件清单

### Hermes 端 (本 session 创建)

| 文件 | 路径 | 功能 |
|------|------|------|
| Shell | `~/my_quant_system/scripts/hermes_daily_report.sh` | 信号轮询 + 清理 |
| Python | `~/my_quant_system/scripts/hermes_daily_report.py` | frontmatter 解析 + 日报生成 |
| Python | `~/my_quant_system/scripts/hermes_append_feedback.py` | 反馈 + feedback_log |
| Wrapper | `~/.hermes/scripts/hermes_daily_report.sh` | Cron 入口 |

### Coze 端 (Hermes 宿主 Mac 上运行)

| 文件 | 路径 | 功能 |
|------|------|------|
| Shell | `~/my_quant_system/scripts/coze_daily_report.sh` | 调用 Python + touch 信号 |
| Python | `~/my_quant_system/scripts/generate_daily_report.py` | Coze 工作报告生成（v2.1 + SIGTERM handler + frontmatter） |
| Python | `~/my_quant_system/scripts/append_feedback.py` | 写反馈 + feedback_log |

### Cron Jobs

| Job ID | 名称 | 调度 | 角色 |
|--------|------|------|------|
| `00b779e99fdf` | Hermes 日报生成 (v2) | `10 0 * * *` | Hermes |
| (待注册) | coze_daily_report | `0 0 * * *` | Coze |

## macOS shell 坑点

- `date -Iseconds` 在 macOS 不存在，用 `date '+%Y-%m-%dT%H:%M:%S%z'` 或函数包装
- `date -v-1d +%F` 获取昨天日期 (macOS)，Linux 用 `date -d 'yesterday'`
- `find -mtime +90` 按修改时间，在 macOS 上单位是天 (24h 倍数)

## 验证清单

- [ ] `archive/` 目录存在
- [ ] `feedback_log` 表在 `stock_data.db` 中存在
- [ ] `feedback_log.md` 从 DB 自动导出正常
- [ ] `hermes_daily_report.sh` 可执行
- [ ] `hermes_daily_report.py` 对正常 Coze 报告产出 `status: ok` + 无告警
- [ ] `hermes_daily_report.py` 对 missing 场景产出 `status: partial` + 🚨 告警
- [ ] `hermes_append_feedback.py` v2.1 写入 SQLite + 导出 feedback_log.md
- [ ] Cron job `00b779e99fdf` 已注册，调度 00:10
- [ ] 清理命令 `find ... -mtime +90` 不碰信号文件和 feedback_log

---

## v2.1 增量 (2026-06-18)

### feedback_log 切 SQLite

v2 原来用 markdown 文件追加，需要 flock 防并发。v2.1 改用 `stock_data.db` 的 `feedback_log` 表：

```sql
CREATE TABLE feedback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_time TEXT NOT NULL,      -- ISO 8601
    from_role TEXT NOT NULL,     -- coze / hermes
    to_role TEXT NOT NULL,
    feedback_type TEXT NOT NULL, -- read/confirm/question/coordinate
    message TEXT,
    target_date TEXT NOT NULL    -- 对方报告日期
);
```

- **WAL 模式已开**，SQLite 自动串行化写入，无需 locks
- `feedback_log.md` 改从 DB 导出（只读副本）
- 旧 feedback_log.md 首次运行自动迁移到 DB（跳过表头行）
- Coze 的 `append_feedback.py` 同样改 INSERT 即可，无需 flock

### 重试策略

| 决策 | 值 | 理由 |
|------|---|------|
| 策略 | 单查询内部 retry 1 次 (方案 B) | DB 锁/网络抖覆盖 80%+ 失败场景 |
| 间隔 | 5 秒 | 覆盖 DB 锁释放 + akshare rate limit |
| 次数上限 | 1 次 | 2 次边际收益 <5%，不值得 |

```python
def query_with_retry(query_func, *args, max_retries=1, retry_delay=5):
    for attempt in range(max_retries + 1):
        try:
            return query_func(*args), None
        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
    return [], e
```

### 清理 pattern 收紧

```bash
# v2 用 [0-9]*-*.md (宽松)
# v2.1 收紧为 20[0-9][0-9]-*-*.md (只匹配 YYYY-MM-DD 格式)
find ~/quant_shared/daily_reports/ -maxdepth 1 \
    -name "20[0-9][0-9]-*-*.md" -mtime +90 \
    -exec mv {} ~/quant_shared/daily_reports/archive/ \;
```
