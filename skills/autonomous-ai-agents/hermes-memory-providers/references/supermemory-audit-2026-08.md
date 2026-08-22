# Supermemory 审计实录（2026-08-16）

用户启用 supermemory 一周后问「使用效果如何」。以下是完整审计路径与根因定位，未来复评可直接复用。

## 环境事实

- provider: `config.yaml memory.provider: supermemory`，`flush_min_turns: 6`
- 云端 API: `https://api.supermemory.ai`（**非本地容器**——macOS 无 docker，勿再查 docker logs）
- API key: `~/.hermes/.env` 的 `SUPERMEMORY_API_KEY`
- SDK 位置: `~/.hermes/hermes-agent/venv/bin/python`（系统 python3 没有 supermemory 包）

## 审计命令序列（按序执行）

```bash
# 1. 配置确认
grep -A 15 -i "memory" ~/.hermes/config.yaml

# 2. 工具层实测（暴露工具）
supermemory_search(query="晨报 微信推送 cron")   # 返回 content 全空，相似度 62-63 → 可疑
supermemory_search(query="透明PNG 全黑 误判")    # 返回完整正文，98/97/92 分 → 检索质量其实不错

# 3. SDK 直查云端存储结构（关键步骤）
~/.hermes/hermes-agent/venv/bin/python - <<'EOF'
from supermemory import Supermemory
import os
c = Supermemory(api_key=os.environ['SUPERMEMORY_API_KEY'],
                default_headers={'x-sm-source': 'hermes'})
docs = c.documents.list(container_tags=['hermes'], limit=200)
for m in docs.memories:
    print(m.id, m.custom_id, m.metadata, (m.summary or '')[:100])
EOF
# 结果：仅 6 条；4 条 full_session（只有 summary 无正文）+ 2 条 explicit_memory

# 4. search_mode 差异验证
for mode in hybrid semantic fulltext:
    c.search.memories(q='晨报 微信推送 cron', container_tag='hermes', limit=5, search_mode=mode)
# hybrid → 5 条 memory 字段全空（len=0）
# semantic/fulltext → 400 BadRequestError（中文查询不支持）
EOF
```

## 根因定位（三层）

1. **存储层**：auto_capture 每 6 轮把整会话 POST `/v4/conversations`，云端生成 `full_session` 文档 = 只有 `summary` + `metadata`，无正文
2. **搜索层**：`search_mode=hybrid` 会命中这些只有摘要的条目
3. **插件映射层**：`plugins/memory/supermemory/__init__.py` 的 `_tool_search` 读 `item.memory`（`entry["content"] = item.get("memory","")`），而摘要条目的 memory 字段为空 → 工具返回 `{"content": ""}`

显式 store 的条目（`supermemory_store`）在搜索时 memory 字段有完整正文 → 检索质量其实很好（透明PNG 98 分命中）。

## 结论与修复选项

| 问题 | 严重度 | 修复 |
|:-----|:-------|:-----|
| hybrid 搜索返回大量空正文条目 | 高 | 插件层 fallback：memory 为空时回退 `summary` |
| auto_capture 产出无正文摘要 | 中 | 关 auto_capture（`~/.hermes/supermemory.json` 或 env），只用手动 store |
| 中文 semantic/fulltext 400 | 低 | 保持 hybrid（服务端限制，无解） |
| 与本地 MEMORY 重复 ~60-70% | 中 | 评估注入价值；本地仍是主记忆 |

## 插件代码要点（v2026-08）

- `_tool_search`（约 960 行）: `{"id": item.id, "content": item.get("memory","")}` + similarity
- `search_memories`（约 337 行）: kwargs = q/container_tag/limit/search_mode，结果取 `item.memory`
- `ingest_conversation`（约 398 行）: POST `/v4/conversations`，`containerTags` 数组
- `documents.add` 需 `content=` 关键字（SDK 坑）；`documents.list` 用 `container_tags=` 列表；`memories.forget(container_tag=, id=)` 位置参数
