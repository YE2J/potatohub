# generate_daily_report.py 常见 Bug 模式

> 创建于: 2026-06-19 | 来源: 5-bug 修复工单
> 关联: `coze-hermes` Skill

## 这 5 个 bug 的特征（一次修完，下次不再犯）

---

### Bug 1: 报告中出现当前 run 的 running 状态

**症状**：etl_runs 表格里出现 `run_id=N | status='running' | total=0 | ok=0 | fail=0 | sec=None`

**根因**：`etl_run` context manager 在 `build_report()` 调用之前已 INSERT 了新记录（status='running'），而 `query_today_etl_runs()` 查询当日所有记录时把它也查出来了。

**修复**：所有 etl_runs 查询函数加 `exclude_run_id` 参数：

```python
def query_today_etl_runs(date_str, exclude_run_id=None):
    if exclude_run_id is not None:
        cur.execute("... WHERE DATE(started_at) = ? AND run_id != ?", 
                    (date_str, exclude_run_id))
    else:
        cur.execute("... WHERE DATE(started_at) = ?", (date_str,))

def query_etl_runs_stats(days=7, exclude_run_id=None):
    # 同上模式
```

**调用侧**：
```python
def build_report(current_run_id=None, triggered_by="unknown"):
    etl_runs, _ = query_with_retry(query_today_etl_runs, TODAY_STR, current_run_id)
    stats, _ = query_with_retry(query_etl_runs_stats, 7, current_run_id)
```

**适用范围**：任何在 `etl_run` 上下文内查询 `etl_runs` 的脚本。

---

### Bug 2: 7 天统计 success 数少 1

**症状**：`coze_daily_report | 2 | 1 | 0 | 0.0`（total=2, success=1）

**根因**：和 Bug 1 同源。统计查询包含了当前 run（status='running'），`SUM(CASE WHEN status='success'...)` 只计了已完成的那条。

**修复**：同 Bug 1，`query_etl_runs_stats(days, exclude_run_id)`。

---

### Bug 3: 章节硬编码占位文字

**症状**：3 个章节写 `"（由 Coze 在执行任务时动态写入。今天没有就写\"无\"）"` / `"（动态维护）"` 等开发期占位文字。

**修复**：改为有意义的统一占位：
```
**今日无新增待决策项，详见历史日报**
**今日无新增待配合事项，详见历史日报**
**今日无新增遗留项，详见历史日报**
```

---

### Bug 4: 未使用的变量 + 日期读错

**症状**：`YESTERDAY_COZE` 变量定义但从未使用；曾被怀疑读错日期。

**实际**：日期逻辑正确（`YESTERDAY = TODAY - timedelta(days=1)`），`build_report()` 读的是 `YESTERDAY_HERMES`（`2026-06-18_hermes.md`）和 `HERMES_FEEDBACK_ON_YESTERDAY_COZE`（`2026-06-18_coze_feedback_hermes.md`），均引用正确。

**修复**：删除未使用的 `YESTERDAY_COZE` 变量定义。

---

### Bug 5: frontmatter agent 字段写死

**症状**：无论谁跑脚本，frontmatter 都写 `agent: coze`。

**修复**：动态判定：
```python
def build_frontmatter(status, agent="coze"):
    return (
        "---\n"
        f"status: {status}\n"
        f"generated_at: {now}\n"
        f"agent: {agent}\n"
        "---\n"
    )

def build_report(current_run_id=None, triggered_by="unknown"):
    agent_name = triggered_by.lower() if triggered_by else "unknown"
    out.append(build_frontmatter(status, agent=agent_name))

def main():
    report, status = build_report(current_run_id=run.id, triggered_by="Hermes")
```

---

## 跨脚本 Bug：标签与实际文件不匹配（hermes_daily_report.py）\n\n### Bug: \"昨日对方干了啥\" 标签写死计算日期，与 --coze-file 实际文件不一致\n\n**症状**：报告\"## 📋 1. 昨日对方干了啥\"章节的 `> 来源:` 标签显示 `2026-06-17_coze.md`，但实际读的文件可能是 6/18 或 6/19。\n\n**根因**：`build_report()` 第 141 行标签写死 `{YESTERDAY_STR}_coze.md`，不随 `--coze-file` 参数变化。YESTERDAY_STR 是 Python 计算的昨天，但 shell 可能传了不同日期的文件。\n\n**修复（2 处）**：\n\n1. **标签用实际文件名**：\n```python\ndef build_report(coze_status, coze_content, coze_fm, missing_chapters, coze_source_name=None):\n    # 标签改用实际来源\n    add(f\"> 来源: `{coze_source_name or f'{YESTERDAY_STR}_coze.md'}`\")\n```\n\n2. **main() 传实际文件名**：\n```python\nreport = build_report(coze_status, coze_content, coze_fm, missing_chapters,\n                      coze_source_name=coze_path.name if coze_content else None)\n```\n\n3. **过期 fallback 防护（main() 中）**：\n```python\nif args.coze_file:\n    coze_path = Path(args.coze_file)\n    file_date_str = coze_path.name[:10]\n    try:\n        file_date = datetime.date.fromisoformat(file_date_str)\n        if file_date < YESTERDAY:\n            print(f\"⚠️ 拒绝过期 fallback: {coze_path.name} (早于 {YESTERDAY_STR})\")\n            coze_path = Path(REPORT_DIR) / f\"{TODAY_STR}_coze.md\"  # 重置，走 missing\n    except ValueError:\n        pass  # 无法解析日期，保留原路径\n```\n\n**适用范围**：任何通过 CLI 参数传入文件路径、又在报告中引用该文件的脚本。标签必须与实际来源一致。\n\n---\n\n## 次要修复

### avg_sec 显示 None

**症状**：`db_backup` 的 `duration_sec` 为 NULL 时，`AVG(duration_sec)` 返回 NULL，表格显示 `None`。

**修复**：`ROUND(AVG(COALESCE(duration_sec, 0)), 1)`。

---

## 验收 checklist

每次改完 `generate_daily_report.py` 后跑：

```bash
cd ~/my_quant_system && bash scripts/coze_daily_report.sh
```

检查生成报告：
```bash
grep -E "agent:|读自|run_id=[0-9]+\|running|无\"|\"无\"|详见历史日报" \
  ~/quant_shared/daily_reports/$(date +%F)_coze.md
```

期望输出：
- `agent: hermes`（非 coze）
- `读自 2026-06-XX_hermes.md`（昨日，非前日）
- 不出现 `running` 状态
- 不出现 `"无"` 硬编码
- 出现 `详见历史日报`
