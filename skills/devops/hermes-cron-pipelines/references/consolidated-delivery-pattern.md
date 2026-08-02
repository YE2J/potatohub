# Consolidated Cron Delivery Pattern — 每日晨报

## 问题

多个 cron 同时 `deliver: origin` 推送到微信时触发 iLink 30s cooldown 限流。散列调度（方案B）只能缓解不能根治，且用户被多轮消息轰炸。

## 方案

**1 条晨报 = N 个 cron 的聚合结果。**

### 架构

```
cron A (00:00, deliver: local)  ─┐
cron B (00:10, deliver: local)  ─┤
cron C (03:00, deliver: local)  ─┤
cron D (08:30, deliver: local)  ─┤
...                              ─┤
                                  ├──→ ~/.hermes/cron/output/<id>/YYYY-MM-DD_HHMMSS.md
                                  │
                                  ▼
          ~/.hermes/scripts/daily_morning_report.sh
                    ↓ no_agent=true, deliver=origin
          每天 10:00 一条微信推送
```

### 脚本要点

**路径**: `~/.hermes/scripts/daily_morning_report.sh`

**核心逻辑**:
1. 遍历各 cron 的 output 目录，取最新一份 `.md` 文件
2. 用 `grep` / `sed` 抽取关键摘要行（不读全文）
3. 输出结构化文本，作为 cron 的交付内容

**macOS 兼容注意事项**:
- 不用 `grep -oP`（macOS 原版 grep 不支持 Perl 正则）
- 不用 `set -euo pipefail`（`grep` 无匹配返回 1 会中断脚本）
- 用 `|| true` 兜底 grep 的退出码
- 用 `echo` 和 `set -u` 替代 `set -euo pipefail`
- 路径用 `~` 展开，不用绝对路径

### 注册 cron job

```bash
hermes cron action=create \
  name="每日晨报推送" \
  schedule="0 10 * * *" \
  script="daily_morning_report.sh" \
  no_agent=true \
  deliver=origin
```

### 各 cron 的 output 目录映射

| 数据源 | job_id (前12位) | 提取字段 |
|--------|----------------|---------|
| 自选股行情 | `fda7975b8524` | ✅ 写入总结行 |
| 资金流 | `209c43908019` | 更新条数、日期范围、数据源 |
| DB 备份 | `df2e4b24d5f8` | 备份完成行 |
| 估值状态 | `8260f871c2c8` | 失败任务数 |
| CSRC 案例 | `2e89791a416c` | 总案例数 |
| 热门板块 | `29f36877421b` | 是否昨日更新 |
| Coze/Hermes 日报 | `quant_shared/` | 日报文件是否存在 |

### Cron job 生命周期

- **Active jobs** are listed in `~/.hermes/cron/jobs.json`
- **Historical output** persists in `~/.hermes/cron/output/<job_id>/` even after a job is removed from jobs.json
- The scheduler only runs jobs from `jobs.json`; output directories are never auto-cleaned
- When checking "did this cron run", check BOTH `jobs.json` (active) AND `cron/output/` (history)
