# Kanban 等待时间基准（15s dispatch interval）

> 实测数据，2026-07-09 ~ 2026-07-12，gateway dispatch_interval_seconds=15
> gateway 重启方式：从外部终端 `hermes gateway restart`

## 各 Worker 实测耗时

| Worker | 模型 | 平均耗时 | 最短 | 最长 | 评审轮次 | 备注 |
|--------|------|:--------:|:----:|:----:|:--------:|------|
| `worker-glm` | GLM-5.2 (z.ai) | ~4min | 3min | 5min | 7 | 通常最快，稳定 |
| `worker-kimi` | Kimi K2.6 (moonshot) | ~7min | 3min | 10min | 8 (1次crash) | 最不稳定，有时超长 |
| `worker-auditor` | MiniMax M2.7 | ~6min | 4min | 9min | 6 | 评审最详细（有SQL EXPLAIN） |
| `worker-xiaomi` | MiMo v2.5 | ~4min | 3min | 5min | 3 | 2026-07-12启用，稳定且快 |
| `orchestrator` | DeepSeek V4 Flash | ~35s | 27s | 50s | 6 | 汇总极快 |

## 典型总周期

| 场景 | 总耗时 |
|:----:|:------:|
| 3 worker 全部成功 + orchestrator | **5~10分钟** |
| 4 worker 全部成功 + orchestrator（含xiaomi） | **6~11分钟** |
| Kimi crash 1次 + 自动重试 | +3~8分钟 |
| Kimi crash 2次（重试耗尽） | 需切换其他worker代审 |
| 全部顺利完成（最快） | **~4分钟** |

## 关键发现

1. **15s dispatch 比 60s 快很多** — 每次检查只需等15s
2. **Kimi 最慢且最不稳定** — 实测 ~2/9 的 Kanban worker 运行会崩溃。设 failure_limit: 2 允许一次重试
3. **MiniMax 最慢但质量最高** — 每次评审产出详细的 SQL EXPLAIN 和性能基准数据
4. **Xiaomi (MiMo v2.5) 稳定且快** — 约和GLM同等速度，2026-07-12首次实测通过
5. **Orchestrator 极快** — 通常 30~60s 完成汇总
6. **backlog 不阻塞** — 旧卡即使未归档，新卡派发不受影响
7. **多轮评审会累积** — kanban list 显示所有历史卡，用 archive 清理

## 通信节奏建议（不依赖自动推送时）

| 时间点 | 动作 |
|:------|------|
| T+0 | 创建3~4张worker卡，告知用户预计5-10分钟 |
| T+90s | 首次检查kanban list，报进度 |
| T+4min | GLM和xiaomi预计完成，检查并汇报 |
| T+6min | MiniMax预计完成，检查并汇报 |
| T+7min | Kimi预计完成，检查并汇报 |
| T+7min30s | 创建orchestrator汇总卡 |
| T+8min | 汇总完成，给用户最终结果 |
