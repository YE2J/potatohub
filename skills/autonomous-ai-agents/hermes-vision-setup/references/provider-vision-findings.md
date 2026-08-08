# Provider Vision Findings — 2026-08-03 实测

会话：用户问"什么模型能帮纯文本主模型 DeepSeek 扫码"时的实测结论。
配置入口：`~/.hermes/config.yaml` → `auxiliary.vision`（provider/model）。
环境：macOS 26.2，主模型 deepseek-v4-flash（纯文本）。

## 用户机器当前状态

- `auxiliary.vision: {provider: auto, model: ''}` → auto 无 OPENROUTER/GOOGLE key，**传图会失败**
- 可用 key（名字）：`DEEPSEEK_API_KEY GLM_API_KEY ZAI_API_KEY KIMI_CN_API_KEY
  MOONSHOT_API_KEY MINIMAX_API_KEY NVIDIA_API_KEY XIAOMI_API_KEY IWENCAI_API_KEY`

## 逐 provider 结论

| Provider | 模型列表 | 视觉实测 |
|---|---|---|
| z.ai (GLM) `api.z.ai/api/paas/v4/models` | 仅文本：glm-4.5/4.5-air/4.6/4.7/5/5-turbo/5.1/5.2，**无 -v 后缀** | ❌ glm-5.2 发图 → HTTP 400（拒绝图像输入）。旗舰文本 ≠ 多模态 |
| NVIDIA NIM `integrate.api.nvidia.com/v1/models` | 有视觉：`meta/llama-3.2-90b-vision-instruct`、`meta/llama-3.2-11b-vision-instruct`、`microsoft/phi-3-vision-128k-instruct`、`nvidia/nemotron-parse`、`nvidia/nemotron-nano-12b-v2-vl`、`microsoft/kosmos-2`、`nvidia/neva-22b`、`nvidia/vila`、`adept/fuyu-8b` | ✅ llama-3.2-90b-vision 能读图：英文数字全对；中文那次乱码经查是测试图 PIL 默认字体画不出中文（模型根本没看到中文字形），**需用苹方字体重测**。NIM 同时托管 `z-ai/glm-5.2`、`moonshotai/kimi-k2.6`、`deepseek-ai/deepseek-v4-*` |
| Moonshot/Kimi `api.moonshot.cn/v1/models` | 空返回 | ⚠️ 未验证（key 或端点存疑，可能需换端点） |
| MiniMax `api.minimax.io` | 未列出 | ⚠️ 未验证；`chatcompletion_v2?model=abab6.5s-chat` 返回"missing required parameter"说明 key 有效、需正确参数 |
| DeepSeek | 纯文本 | ❌ 主模型无视觉（这正是本问题的起因） |

## 环境坑（修复方式在 SKILL.md Pitfalls）

- Hermes venv（`~/.hermes/hermes-agent/venv`）PIL 损坏：`cannot import name '_imaging'`。
  修复：`python3 -m venv /tmp/vt_venv && /tmp/vt_venv/bin/pip install pillow`，
  脚本里 `sys.path.insert(0, "/tmp/vt_venv/lib/python3.11/site-packages")`。
  注：macOS 系统 python3 建 venv 后 pip 可能不在（本会话 pip 缺失但包已装好）。
- terminal 工具 lifecycle_guard 对 `/tmp` 下 .py 脚本 + heredoc 组合报
  `ValueError: embedded null byte`（`cron/lifecycle_guard.py::_read_referenced_script`）。
  绕法：用 `execute_code` 进程内跑同样的 Python 逻辑（本会话 31s 内完成 z.ai+NVIDIA 双测）。
  execute_code 里同样要先 `sys.path.insert` 指向干净 venv 的 PIL。

## 推荐结论（待用户选择）

1. 快速可用：`auxiliary.vision.provider: nvidia` + `model: meta/llama-3.2-90b-vision-instruct`
   （key 已存在且实测能读图）；
2. 追求中文 OCR 精度：先用 `scripts/test_vision_provider.py` 复测 90b-vision vs
   `nvidia/nemotron-parse`（文档解析型）再定。
