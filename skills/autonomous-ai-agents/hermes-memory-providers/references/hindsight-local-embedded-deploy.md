# Hindsight local_embedded 部署配方（2026-08-17 实测通过，Mac mini M4 / 16GB）

将 Hermes 记忆从云端 supermemory 切换到本地 Hindsight，全程实测验证。数据全本地、仅 retain 时走 DeepSeek 少量 token。

## 部署前预检（都通过才动手）

| 项 | 检查 | 本次实测 |
|:---|:-----|:---------|
| 硬件 | Mac Apple Silicon，16GB 内存，磁盘空闲 >10GB | M4/16GB/107GB ✅ |
| 端口 | `lsof -iTCP:8888 -sTCP:LISTEN` 空闲 | ✅（注：8888 是 config.json 哨兵值；embedded daemon 端口动态分配） |
| 依赖 | `uv` 可用、Hermes venv = `~/.hermes/hermes-agent/venv/bin/python` | ✅ |
| LLM | `curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $KEY"` 确认模型名真实存在 | `deepseek-v4-flash`/`deepseek-v4-pro` ✅ |
| 干净 | 无 `~/.hindsight`、无 hindsight 包 | ✅ |

## 安装（5 步）

```bash
# 1. .env 预设（HF 直连加速 + daemon 常驻）
#    ⚠️ 不要写 HF_ENDPOINT=https://hf-mirror.com —— 实测连不上/308 回原站
echo "HF_HUB_ENABLE_HF_TRANSFER=1" >> ~/.hermes/.env
echo "HINDSIGHT_IDLE_TIMEOUT=0" >> ~/.hermes/.env

# 2. 装完整包（不是 hindsight-client！local_embedded 需要本地推理，约 1-2GB）
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python hindsight-all
#   慢则加 -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 写 config.json（手写可靠；CLI 向导是 curses 交互，桌面无 TTY 会卡）
#    详见下方模板
# 4. .env 加 LLM key（复用 DeepSeek）
echo "HINDSIGHT_LLM_API_KEY=$DEEPSEEK_KEY" >> ~/.hermes/.env
echo "HINDSIGHT_API_URL=http://localhost:8888" >> ~/.hermes/.env

# 5. 切 provider —— ⚠️ config.yaml 受保护，patch/write_file 会被拒
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-hindsight-$(date +%Y%m%d)
hermes config set memory.provider hindsight
```

## config.json 模板（~/.hermes/hindsight/config.json）

```json
{
  "mode": "local_embedded",
  "llm_provider": "openai_compatible",
  "llm_base_url": "https://api.deepseek.com/v1",
  "llm_model": "deepseek-v4-flash",
  "api_url": "http://localhost:8888",
  "bank_id": "hermes",
  "recall_budget": "mid",
  "timeout": 120,
  "idle_timeout": 0
}
```

键名全 snake_case（源码 `_load_config` 读取）。`llm_provider=openai_compatible` 会被插件转成 daemon 的 `openai` wire format。模型名必须实测存在，否则推理 404。

## 首次启动与验证

- daemon 首次启动自动：初始化 pg0（`~/.pg0/instances/hindsight-embed-<profile>/`，实际 hermes）→ 从 HF 下载 BGE embedder(~130MB)+MiniLM reranker(~90MB) → 起服务
- **embedded daemon 端口由 profile env 钉死**（`~/.hindsight/profiles/hermes.env` 的 `HINDSIGHT_API_PORT=9177`；旧 default profile 曾用 8984；8888 仅 config.json 哨兵值，非实际监听）
- 冒烟测试直接调 SDK（比插件层更早暴露问题）：
  ```python
  from hindsight import HindsightEmbedded
  c = HindsightEmbedded(llm_provider="openai", llm_api_key=KEY,
                        llm_model="deepseek-v4-flash", llm_base_url="https://api.deepseek.com/v1")
  c.retain(bank_id="hermes", content="测试...")
  c.recall(bank_id="hermes", query="...")
  ```
- 日志：`~/.hindsight/profiles/<profile>.log`（profile 默认 hermes → `hermes.log`；daemon 失败先看这里，如模型下载/LLM 配置错误）
- `hermes memory status` → `Provider: hindsight · installed ✓ · available ✓`

## 实测踩坑

1. **hf-mirror.com 不可用**：daemon 首次启动报 `OSError: We couldn't connect to 'https://hf-mirror.com'`。删掉 HF_ENDPOINT，改 `HF_HUB_ENABLE_HF_TRANSFER=1`（需 `pip install hf_transfer`）直连，一次通过。
2. **不要直接 exec 插件 __init__.py 验证**（`importlib.util.spec_from_file_location`）→ dataclass 命名空间 AttributeError。正确路径：`hermes memory status` 看插件可用 + SDK 冒烟测试；插件工具（hindsight_store/search）在**新会话**才注册。
3. **UI 配置面板不显示 local_embedded**：config_schema.py 只有 cloud/local_external；local_embedded 只存在于 CLI 向导和手写 config.json。
4. retain 一次约消耗 DeepSeek 3k tokens（事实抽取），recall 纯本地 0 成本——告知用户成本构成。

## 回滚

```bash
hermes config set memory.provider supermemory
pkill -f "hindsight-api --daemon" 2>/dev/null
uv pip uninstall --python ~/.hermes/hermes-agent/venv/bin/python hindsight-all -y
rm -rf ~/.hermes/hindsight ~/.hindsight
```

## 多 profile 隔离与孤儿 daemon（2026-08-17 实测）

- 每个 profile 独立 pg 实例（`~/.pg0/instances/hindsight-embed-<profile>/`）、独立日志/env（`~/.hindsight/profiles/<profile>.log|.env`），**数据互不互通**
- 曾出现孤儿 daemon：旧 default profile（8984/pg5432）无 launchd/plist（PPID=1），与 hermes profile（9177/pg5433）并存且数据隔离 → 收敛为单一 hermes profile
- 清理方法：kill 孤儿 API 进程 → `pg_ctl -D <data_dir> stop` → 归档数据目录与 profiles/*.env 至 backups（勿直接删，可回滚）
- config.json `api_url=8888` 是插件 `_DEFAULT_LOCAL_URL` 哨兵默认值，**非故障，勿改**

## 数据位置（备份要覆盖）

- 数据库：`~/.pg0/instances/hindsight-embed-<profile>/`（实际使用 hermes → `hindsight-embed-hermes/`，pg5433）
- 配置/日志：`~/.hindsight/`（profiles/*.log, profiles/*.env）
- Hermes 配置：`~/.hermes/hindsight/config.json`
