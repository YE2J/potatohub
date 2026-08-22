# Hindsight 部署后验证与故障排查（2026-08-17 实测）

验证「hindsight 能否正常使用」的标准流程与排障路径。全部命令本机实测通过（macOS, Hermes 桌面端）。

## 验证流程（全链路）

1. **健康检查**
   ```bash
   curl -s http://localhost:<port>/health   # {"status":"healthy","database":"connected"}
   ```

2. **retain 必须用「有事实」的文本**（含实体/时间/关系，如「用户于X日部署了Y系统，用Z模型」）：
   - 有事实文本 → 日志 `Extract facts: 2 facts, 1 chunks` ✓
   - 元描述/流水账文本（「这是一条用于验证…的测试数据」）→ `Extract facts: 0 facts` → chunk 被 skip → **document 入库但 memory_unit_count=0，永远检索不到**

3. **写后立即 recall 会查空**（时序竞态，非故障）：retain 完成 ~2s 后 recall 返回 0（日志 semantic=0, bm25=0, graph=0），约 1 分钟后才可检索（embedding 索引/consolidation 就绪）。验证时 retain 后等 1-2 分钟再 recall。

4. **recall 正常判据**：返回条目带 `scores.final/reranker/semantic`（实测 semantic 0.78-0.89, reranker 0.99）。

5. **reflect 综合验证**：能跨 memories 推理输出总结。

6. **测试数据清理**（删干净，勿留测试污染库）：
   ```bash
   curl -X DELETE "http://localhost:<port>/v1/default/banks/<bank>/documents/<doc_id>"   # 200
   ```

## 关键诊断路径（插件 recall 空但怀疑有数据时）

绕过插件层逐级确认，先定位是「没数据」还是「插件/时序问题」：

1. **查数据是否真入库**：
   - `GET /v1/default/banks/<bank>/documents` → `items[].memory_unit_count`
   - `GET /v1/default/banks/<bank>/memories/list` → units 明细（fact_type/entities/chunk_id/consolidated_at/state）
2. **直接调 REST recall 对比**（绕过插件）：
   ```bash
   curl -X POST "http://localhost:<port>/v1/default/banks/<bank>/memories/recall" \
     -H "Content-Type: application/json" -d '{"query":"..."}'
   ```
   REST 层命中而插件层空 → 插件调用时序/参数问题，**不是 daemon 故障**。
3. **看 daemon 日志**：`~/.hindsight/profiles/<profile>.log`。RETAIN_BATCH START / Extract facts 数量 / RECALL 检索明细 / consolidation 状态全在里面。日志文件名对应 profile：hermes.log=hermes profile，default.log=default profile。

## 双 daemon 架构（2026-08-17 实测）

| daemon | 端口 | 父进程 | postgres 实例 | profile |
|---|---|---|---|---|
| launchd 常驻 | 8984 | launchd (PID 1) | 5432 (hindsight-embed-default) | default |
| Hermes serve 拉起 | 9177 | hermes_cli.main serve | 5433 (hindsight-embed-hermes) | hermes |

- **当前 Hermes 会话实际走 9177**（hermes profile），数据在 pg5433。8984 查不到 9177 写入的数据（反之亦然）——排查「数据丢失」前先确认查的是哪个 daemon。
- profile 环境文件：`~/.hindsight/profiles/{default,hermes}.env`（`HINDSIGHT_API_PORT` 决定 daemon 端口）；日志同名 .log。
- `~/.hermes/hindsight/config.json` 的 `api_url` 可能是**死配置**（实测指向 8888，无监听）——local_embedded 模式下插件自动发现/spawn daemon，api_url 残留不影响功能但误导排查。
- 配置锚点：`memory.provider=hindsight`、`mode=local_embedded`、LLM=DeepSeek（openai_compatible + deepseek-v4-flash）。
- 首次 retain 提取 facts 耗时 ~25s（DeepSeek LLM 调用），属正常。

## 已知行为

- 0 facts 文档：memory_unit_count=0，不可检索（chunk 被 skip）。
- consolidation 自动执行（写入后 ~2s 内），无需手动干预。
- 本地模型：BAAI/bge-small-en-v1.5 (384维, CPU, MPS 默认禁用) + cross-encoder/ms-marco-MiniLM-L-6-v2。
