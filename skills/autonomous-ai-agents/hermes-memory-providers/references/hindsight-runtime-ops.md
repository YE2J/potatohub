# Hindsight 运行时运维：状态验证 / 容量预算 / 注入机制（2026-08-18 实测）

回答「运行正常吗」「有多少条记忆」「容量多大」「预算够不够」这类运行时问题的标准路径。全部命令本机实测通过（macOS, Hermes 桌面端, local_embedded 模式）。

## 状态验证清单（问「运行正常吗」时）

1. **配置**：`grep -A6 "memory:" ~/.hermes/config.yaml` → `provider: hindsight`
2. **进程**：
   - daemon：`ps aux | grep hindsight-api` → `hindsight-api --daemon --idle-timeout 0 --port 9177`（随 Hermes serve 拉起，无 launchd）
   - 数据库：`ps aux | grep postgres` → `postgres -D ~/.pg0/instances/hindsight-embed-hermes/data -p 5432`
3. **健康**：`curl -s http://localhost:9177/health` → `{"status":"healthy","database":"connected"}`
4. **功能实测**：直接调 `hindsight_recall` 发**真实查询**（如「用户的项目用什么数据库」），命中相关事实即读取链路通。不要用元描述查询（0 facts 不可检索）。

## psql 直连（查记忆条数/明细）

密码不在记忆里，在实例文件里（终端显示 `***` 是掩码，文件里有真值）：

```bash
cd /tmp && python3 -c "
import json, subprocess, os
inst = json.load(open('/Users/yellow/.pg0/instances/hindsight-embed-hermes/instance.json'))
env = dict(os.environ, PGPASSWORD=inst['password'])
sql = '''SELECT count(*) FROM memory_units;'''
r = subprocess.run(['/Users/yellow/.pg0/installation/18.1.0/bin/psql','-h','127.0.0.1','-p',str(inst['port']),'-U',inst['username'],'-d',inst['database'],'-c',sql], capture_output=True, text=True, env=env)
print(r.stdout if r.returncode==0 else r.stderr)
"
```

- 连接参数全在 `~/.pg0/instances/hindsight-embed-hermes/instance.json`（username=hindsight / database=hindsight / port=5432）
- **关键表**：`memory_units`(有效记忆) / `invalidated_memory_units`(已失效/被合并) / `entities` / `memory_links` / `documents` / `chunks`
- 统计模板：`SELECT count(*) FROM memory_units` + 同理查 invalidated/entities 等
- 表大小：`pg_total_relation_size`；整实例 `du -sh ~/.pg0/instances/hindsight-embed-hermes/`

## 容量与预算（实测反直觉结论）

- **存储无硬上限**：`max_observations_per_scope=-1`，本地 postgres 容量=磁盘。实例 ~67MB（含引擎），记忆数据 <1MB（36 条 → memory_units 表 840KB）
- **`budget` 参数不限制注入量**（关键实测）：同一查询分别传 `budget=mid` 与 `budget=high`，返回完全一致（47 条 / ~9.7k 估算 token）。服务端 budget(300/1000) 只作用于 **source_facts 证据深度**（RecallResponse `source_facts_truncated` 字段），不是结果列表
- **真正的量控制** = `recall_max_tokens=4096`（插件默认，config key `recall_max_tokens`），且库小时不触发
- 现状：库小 → 命中即全注入，实际注入远超 300 tokens（每轮 [memory-context] 20+ 条）。「mid=300 不够」担忧不成立；未来库涨到几百上千条时风险是**注入过多**（token 成本），靠 max_tokens 或 consolidate 控量
- bank 配置查看：`GET http://localhost:9177/v1/default/banks/hermes/config`（recall_budget_fixed_* / recall_max_tokens 等）
- 端点枚举：`GET /openapi.json` 列出全部 API 路径；recall 端点为 `POST /v1/default/banks/{bank_id}/memories/recall`（body: query/budget/max_tokens）

## 注入机制（源码确认，agent/memory_manager.py + plugins/memory/hindsight/__init__.py）

| 层 | 机制 |
|---|---|
| 原生 MEMORY.md/USER.md（builtin provider） | 每轮 system prompt **全量硬注入**，无检索；受 memory_char_limit=4000 / user_char_limit=3000 限制 |
| hindsight | `memory_manager.prefetch_all(用户消息)` → 每 provider 独立后台线程召回 → 结果包成 `[System note: ... recalled memory context]` 块注入 |
| recall_sync（默认 False） | 后台预取注入的是**上一轮**查询的结果（queue_prefetch 上轮结束时跑，prefetch 本轮读缓冲）；`recall_sync=true` 则每轮同步召回当前消息（相关性更高，代价+延迟） |
| flush_min_turns=6 | 每 6 轮对话自动 retain 到 hindsight（auto_capture） |
| nudge_interval=10 | 每 10 轮提醒 agent review 原生 memory |
| 失败隔离 | provider prefetch 超时/异常仅打日志跳过，不阻塞对话；[memory-context] 偶缺是设计非故障 |

## 当前部署状态（2026-08-18）

- 单 daemon：hindsight-api 9177（随 Hermes serve 拉起，**无 launchd 常驻**）
- 单 postgres：**5432**（hindsight-embed-hermes）——注意旧文档记 5433，那是双 daemon 时期 hermes profile 的端口；孤儿 daemon 清理后新实例占 5432
- bank=hermes：36 有效 + 10 失效 + 27 实体 + 258 链接 + 5 文档

## 故障实录：huggingface.co 不可达 → daemon 启动超时（2026-09-04 修复）

**症状**：retain/recall 420s 超时；日志反复 `'timed out' thrown while requesting HEAD https://huggingface.co/.../modules.json`（Retry 5/5）；最终 `Daemon failed to start (timeout)`。daemon 进程活着（ps 可见）但 9177 无监听、CPU 0.0%（卡网络等待）。

**根因**：huggingface.co 网络不可达（`curl -sI -m 10 -o /dev/null -w "%{http_code}" https://huggingface.co` → HTTP 000 exit=28）。模型缓存虽完整（~/.cache/huggingface/hub/models--*/snapshots/*/），但 daemon 每次启动时 huggingface_hub 仍做远程版本 HEAD 检查，超时重试耗尽启动窗口。

**修复（一劳永逸，本地路径方案）**：`~/.hindsight/profiles/hermes.env` 加两行，把模型标识从 repo id 改为本地 snapshot 绝对路径：
```
HINDSIGHT_API_EMBEDDINGS_LOCAL_MODEL=/Users/<user>/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5/snapshots/<commit_hash>
HINDSIGHT_API_RERANKER_LOCAL_MODEL=/Users/<user>/.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L-6-v2/snapshots/<commit_hash>
```
原理：daemon_embed_manager spawn 时 `load_profile_config(profile)` 读 hermes.env → **只 propagate `HINDSIGHT_` 前缀键**进 daemon env → SentenceTransformer(本地目录) 不触发 huggingface_hub → 秒级启动。

**关键机制（排查必读）**：
- daemon env = `os.environ.copy()`（hermes serve 环境）+ HINDSIGHT_* 白名单 propagate → **非 HINDSIGHT_ 变量（如 HF_HUB_OFFLINE）写 hermes.env 无效**，只能靠父进程环境（GUI app 需 launchctl setenv + 重启）
- `hindsight-api --daemon` wrapper 会 daemonize（wrapper 退出、真身父=launchd）；手动起 daemon 后 Hermes 插件检测健康会复用（_clear_port 不杀 hindsight 进程）
- 插件 spawn 的 daemon 父=hermes serve；Hermes 重启会重新 spawn（hermes.env 本地路径 → 秒启动，无复发）
- ps 排查注意：`ps aux | grep hindsight-api` 匹配不到 `python -m hindsight_api.main`（连字符 vs 下划线），用 `grep -E "hindsight_api.main|hindsight-api"`
- 验证命令：`curl -s http://localhost:9177/health` → healthy；`ps eww <pid> | grep HINDSIGHT_API_EMBEDDINGS_LOCAL_MODEL` 确认 env；日志无 HF timed out 即干净
- 离线快速加载验证：`HF_HUB_OFFLINE=1 python -c "from sentence_transformers import SentenceTransformer; m=SentenceTransformer('<snapshot_path>'); m.encode(['x'])"`
