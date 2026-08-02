# Coze Scheme D — 同步架构（2026-06-26）

## 背景

初版方案 C 使用 `coze agent file download` 从 Coze 项目空间下载，但 Coze CLI v0.3.2 不支持该命令。

## Scheme D：Coze 直接写入

```
00:15  Coze 日历任务触发
   ↓
Coze 使用 write_file 工具
   ↓
写入 ~/quant_shared/daily_sync/coze_sync_{YYYY-MM-DD}.md
   ↓
01:30  Hermes 日报自动读取（hermes_daily_report.py Section 2）
   ↓
10:00  晨报汇总（daily_morning_report.sh v2.0）
```

## 关键决策

| 项目 | 值 |
|:---|:---|
| 传输方式 | Coze 直接 write_file（不经过文件空间） |
| 目标路径 | `~/quant_shared/daily_sync/` |
| Hermes 读取 | `~/quant_shared/daily_sync/`（通过 symlink → real） |
| 废弃脚本 | `download_coze_sync.sh`（标注 DEPRECATED，保留仅供参考） |
| 废弃 cron | crontab 中的 01:00 download 条目（已删除） |

## Hermes 不做的事

- ❌ 不使用 coze CLI 下载
- ❌ 不调用 Coze API
- ❌ 不维护下载脚本
- ✅ 只等待文件出现（01:30 读取，如果不存在则降级显示）

## 文件格式

`coze_sync_{YYYY-MM-DD}.md` — Coze 任务同步文件，包含：
- Coze 执行的任务列表和结果
- 需要 Hermes 关注的事项
- 与 Hermes 相关的系统状态变更
- 需要主人配合的事项
- 明日计划
