# kanban_await.py — 自动推送工具

## 位置

`~/my_quant_system/scripts/kanban_await.py`

## 用途

创建 Kanban 卡后，自动轮询等待完成并推送结果到终端。替代手动 `kanban list` + `kanban show`。

## 依赖

- `hermes CLI` 在 PATH 中
- 使用 `hermes kanban show --json`（结构化API），不依赖文本格式，防止版本升级后正则断掉

## 用法

```bash
# 等待单张卡
python kanban_await.py t_xxx

# 等待多张卡（worker评审卡同时等）
python kanban_await.py t_glm t_kimi t_auditor

# 自定义超时（默认600s）和间隔（默认15s）
python kanban_await.py t_xxx --timeout 300 --interval 10
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|:-----|:----:|:------:|:-----|
| `card_ids` | positional | — | 一个或多个卡片ID |
| `--timeout` | int | 600 | 总超时秒数 |
| `--interval` | int | 15 | 轮询间隔秒数 |

**⚠️ 不支持 --extra-ticks 或 --background**（这两个参数已被多个版本确认不存在）

### 推荐运行方式（terminal background）

```python
# 在 terminal() 中以 background=true 启动
result = terminal(
    "cd ~/my_quant_system && python3 scripts/kanban_await.py t1 t2 t3 --timeout 600",
    background=True,
    notify_on_complete=True
)
# 进程退出后 process(action='log') 读取 stdout
```

### 超时兜底

kanban_await.py 超时后 exit code 1，不会自动重试。超时后执行：

```bash
hermes kanban show t_xxx     # 检查各卡实际状态
hermes kanban list            # 查看所有卡的状态总览
```

部分卡可能在超时边缘已完成但没被读取，手动 `kanban show` 即可补救。

## JSON 解析格式

`hermes kanban show --json` 返回结构：

```json
{
  "task": {"id": "t_xxx", "title": "标题", "status": "done"},
  "latest_summary": "摘要文本",
  "events": [...]
}
```

脚本扁平化为：`status ← task.status`, `title ← task.title`, `summary ← latest_summary`

## 失败模式

| 场景 | 脚本行为 | 退出码 |
|------|----------|:------:|
| 全部完成 | 打印所有摘要 | 0 |
| 部分失败 | 打印 done 的摘要，标记 failed | 0 |
| 全部超时 | 打印各卡最终状态 | 1 |
| hermes CLI 不可用 | 持续重试直到超时 | 1 |
