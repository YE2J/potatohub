# 自定义 Provider API Key 配置陷阱

## 问题现象

在默认 profile 中设置了：
```yaml
model:
  provider: zai
  default: glm-5.2
  base_url: https://api.z.ai/api/paas/v4
```
但调用时提示：
```
Provider 'zai' is set in config.yaml but no API key was found.
Set the ZAI_API_KEY environment variable, or switch to a different provider.
```

## 根因 — 内置 provider vs 自定义 provider

Hermes 有两种 provider 类型，API Key 的解析路径完全不同：

### 1. 内置 provider（如 `zai`、`openai`、`deepseek`）

使用 Hermes 预留的 provider 名。**只读环境变量，完全不看 `providers.<name>` 节。**

| provider 名 | 环境变量 |
|-------------|---------|
| `zai` | `ZAI_API_KEY`（推荐）或 `GLM_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `openai` | `OPENAI_API_KEY` |

**特例：主 session 通过 Nous 订阅网关走的是托管 key**（透明的），但 delegation 子 agent 依然走环境变量。

### 2. 自定义 provider 名（如 `z.ai`、`kimi-coding-cn`）

使用 `providers.<name>` 节中的 inline 配置：

```yaml
model:
  provider: z.ai            # 自定义名，不是内置的 zai
providers:
  z.ai:
    api_key: '你的key'      # 内联 key
    base_url: 'https://api.z.ai/api/paas/v4/'
```

⚠️ **重要陷阱**：`zai`（内置）和 `z.ai`（自定义）是两个不同的 provider 名！如果你在 config 里把 `model.provider` 设为 `zai`，然后又在 `providers.z.ai` 下配 key——**不会生效**，因为内置 `zai` 根本不读 providers 节。

### 常见混淆场景

```
config.yaml 写了:         model.provider: zai
也写了:                   providers.z.ai: { api_key: 'xxx' }
结果:                     ❌ 报 "no API key found"
原因:                     内置 `zai` 只读 ZAI_API_KEY 环境变量
                         providers.z.ai 是给自定义 provider `z.ai` 用的
```

## 修复方法

### 方案 A：设环境变量（内置 provider 唯一选择）

在 `~/.hermes/.env` 添加：

```bash
ZAI_API_KEY='你的key'
GLM_API_KEY='你的key'      # 两个都设，双重保障
```

```bash
# 或追加
echo "ZAI_API_KEY='your-key'" >> ~/.hermes/.env
echo "GLM_API_KEY='your-key'" >> ~/.hermes/.env
```

### 方案 B：改用自定义 provider 名（走 inline 配置）

修改 config.yaml：

```bash
hermes config set model.provider 'z.ai'
hermes config set providers.z.ai.api_key '你的key'
hermes config set providers.z.ai.base_url 'https://api.z.ai/api/paas/v4/'
```

生成的结构：
```yaml
model:
  provider: z.ai              # ← 不再是内置 zai
providers:
  z.ai:
    api_key: 'id.secret'       # dot-separated key，可以 safe 用 write_file
    base_url: 'https://api.z.ai/api/paas/v4/'
```

**注意**：`z.ai` 是自定义名，可以随便取。但 `z.ai` 这个命名的好处是能从 config 内容猜出实际供应商（Z.AI）。

## 各自定义 provider 对照

| config.yaml 中的 provider 名 | 对应环境变量 | 备注 |
|----------------------------|------------|------|
| `zai` 或 `z.ai` | `ZAI_API_KEY` | z.ai / 智谱 GLM |
| `kimi-coding-cn` | `KIMI_CN_API_KEY` | Kimi / Moonshot |
| `kimi-coding` | `KIMI_API_KEY` | Kimi / Moonshot（境外） |

注意：`provider` 名称必须精确匹配。`zai` 和 `z.ai` 是两个不同的 provider 名，分别需要各自的 `providers.zai` 或 `providers.z.ai` 配置。

## Kimi/Moonshot Key 诊断

### 问题特征

worker-kimi profile 配置了 inline key 但调用时 fallback 到 deepseek，或直接报 HTTP 401。

### 诊断步骤

```bash
# 1. 用 .env 中的 key 列出现有模型（确认 key 有效 + 模型名正确）
source ~/.hermes/.env 2>/dev/null
curl -s https://api.moonshot.cn/v1/models -H "Authorization: Bearer $KIMI_CN_API_KEY" \
  | python3 -c "import sys,json; [print(d['id']) for d in json.load(sys.stdin)['data']]"

# 2. 对比 profile config 中的 key 是否与 .env 一致
grep -A2 "kimi" ~/.hermes/profiles/worker-kimi/config.yaml | grep api_key

# 3. 直接用 .env key 测试模型调用
curl -s -w "\nHTTP %{http_code}" https://api.moonshot.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KIMI_CN_API_KEY" \
  -d '{"model":"kimi-k2.6","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'
```

### 修复方案

方案 A（推荐）：删掉 profile config 中的 inline key，改用内置 provider 名
```bash
# 在 profile 的 config.yaml 中
hermes config set --profile worker-kimi-mid model.provider 'kimi-cn'
# 并从 providers 节中删掉 kimi-coding-cn 的 api_key 和 base_url
```

Kimi 内置 provider 名：
- `kimi-cn` → 读 `KIMI_CN_API_KEY`（国内）
- `moonshot` → 读 `KIMI_API_KEY`（境外）

方案 B（保留 inline key）：手动更新过期 key
```bash
hermes config set --profile worker-kimi-mid providers.kimi-coding-cn.api_key '新key'
```

## 验证

```bash
curl -s -w "\n%{http_code}" https://api.z.ai/api/paas/v4/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"glm-5","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' \
  | tail -1
# 期望输出：200
```
