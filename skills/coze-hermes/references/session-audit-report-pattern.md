# Session 审计工单报告生成模式

当用户问「这几天 Hermes 做了什么」时，需要从 session 历史重建完整工作图像。以下是已验证的流程：

## 流程

1. **浏览最近会话**
   ```python
   # session_search() 无参数 → 返回最近会话列表
   # 关注: title, source, started_at, message_count
   ```

2. **读取关键会话**
   ```python
   # 对每个相关会话:
   session_search(session_id="...")  # 获取全貌
   # 大会话(>30条)会自动截断，显示首20+尾10条
   session_search(session_id="...", around_message_id=N)  # 滚动中间
   ```

3. **识别 Cron 任务**
   - session_id 以 `cron_` 开头的 = 定时任务
   - 查看其 prompt（第一条 user message）了解任务定义
   - 查看 final response 了解执行结果

4. **跨会话关联**
   - 同一主题可能分散在多个会话中（微信端→TUI延续）
   - 按来源（weixin/tui/cron）和时间排序，重建完整时间线

5. **生成结构化 Markdown 报告**
   - YAML frontmatter（status, generated_at, agent, period）
   - 工作总览表格
   - 每个任务独立二级标题
   - 待办/提醒事项（🔴🟡🟢优先级）
   - 共享文件索引

## 输出规范

- 保存到 `~/.hermes/health_shared/`（Coze 桌面端可读）
- 也同步到 `~/quant_shared/daily_sync/`（Coze 项目空间）
- 文件名: `YYYY-MM-DD_hermes_work_report_MMDD-MMDD.md`
- 报告的时间段必须明确（frontmatter 的 period 字段）
- 每个任务注明来源平台和日期
