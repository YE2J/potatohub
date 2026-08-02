# MOA Provider 命名速查

## 凭证池 → 真实 provider 名

为每个有 API key 的 provider，Hermes 注册的 provider 名可能与直觉不同。

```bash
# 查真实 provider 名
cat ~/.hermes/state-snapshots/latest/auth.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
pool = d.get('credential_pool', {})
for p, creds in sorted(pool.items()):
    labels = [c.get('label','?') for c in creds]
    print(f'{p}: {labels}')
"
```

## 常见映射表

| 你想用的模型 | MOA 配 provider | MOA 配 model | 环境变量 | 模型查询 API |
|:------------|:----------------|:-------------|:---------|:------------|
| DeepSeek V4 Flash | `deepseek` | `deepseek-v4-flash` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1/models` |
| Z.AI GLM 5.1 | **`zai`** (非 `z.ai`) | `glm-5.1` | `ZAI_API_KEY` / `GLM_API_KEY` | `https://api.z.ai/api/paas/v4/models` |
| Kimi K2.6 | **`kimi-coding-cn`** (非 `moonshot`) | `kimi-k2.6` | `KIMI_CN_API_KEY` | `https://api.moonshot.cn/v1/models` |
| MiniMax M2.7 | `minimax` | `minimax-m2.7` | `MINIMAX_API_KEY` | `https://api.minimax.io/anthropic`（兼容 API） |
| Xiaomi MiMo V2.5 | `xiaomi` | `mimo-v2.5` | `XIAOMI_API_KEY` | `https://api.xiaomimimo.com/v1/models` |

## 常见错误

| 错误写法 | 正确写法 |
|:---------|:---------|
| `provider: z.ai` | `provider: zai`（去点号） |
| `provider: moonshot` | `provider: kimi-coding-cn` |
| `model: glm-5.1` 被缓存认为不存在 | 缓存可能不完整，直接查 API 确认 |
