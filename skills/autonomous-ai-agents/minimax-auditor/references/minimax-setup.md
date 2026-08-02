# MiniMax M3 配置与调优备忘

## Provider 配置

MiniMax 的 Hermes provider 配置在插件 `~/.hermes/hermes-agent/plugins/model-providers/minimax/__init__.py`：

| 项目 | 值 |
|------|-----|
| Provider 名 | `minimax` (全球) / `minimax-cn` (中国) |
| API 模式 | `anthropic_messages`（Anthropic 兼容） |
| 全局端点 | `https://api.minimax.io/anthropic` |
| 中国端点 | `https://api.minimaxi.com/anthropic` |
| 认证方式 | **X-Api-Key** 请求头（大小写敏感！） |
| 环境变量 | `MINIMAX_API_KEY` / `MINIMAX_CN_API_KEY` |
| OAuth | `minimax-oauth` 可用（不需要 API Key） |

## API 认证细节

**⚠️ 关键：MiniMax 用 `X-Api-Key` 请求头，不是 `Authorization: Bearer`**

```bash
# 正确方式
curl -H "X-Api-Key: $MINIMAX_API_KEY" \
     -H "anthropic-version: 2023-06-01" \
     https://api.minimax.io/anthropic/v1/messages

# 错误方式（返回 401）
curl -H "Authorization: Bearer $MINIMAX_API_KEY" ...
curl -H "x-api-key: $MINIMAX_API_KEY" ...  # 注意大小写
```

## API Key 存放位置

Key 存在 `~/.hermes/.env`，**不自动导出到 shell 环境**。需要在 shell 中手动 source：

```bash
source ~/.hermes/.env
```

## MiniMax-M3 推理特性

Hermes 的 MiniMax provider 支持 `reasoning_split` — 在 OpenAI 兼容端点下，自动请求拆分格式的 thinking（详见 `__init__.py` 中的 `build_api_kwargs_extras`）。

## 常见错误码

| HTTP | 错误码 | 含义 | 处理 |
|------|--------|------|------|
| 401 | 1004 | 认证失败 | 检查 key 格式和请求头 |
| 429 | 2056 | Token Plan 额度用完 | 充值或升级计划 |
| 200 | 1004 | login fail | key 格式不匹配端点 |
| 200 | 2049 | invalid api key | 老版端点不支持新版 key |

## 注意事项

- 充值后可能需要等待几分钟才生效
- 充值 Token Plan 和 Credits 是两套资源体系
- 国内端点 `minimaxi.com` 需要单独的 `MINIMAX_CN_API_KEY`
