# Web 工具（Firecrawl）诊断与修复全流程

2026-08-04 会话实录：用户问「之前会话里 Web 工具未配置是什么情况」，完整走了一遍 诊断→方案→设备码登录 流程。本机当时状态：web_search/web_extract 报错、Firecrawl 无 key、Nous Portal 未登录，用户选择方案①（Nous Portal 登录）后改期再弄。

## 症状

```text
Error searching web: Web tools are not configured. Set FIRECRAWL_API_KEY for cloud
Firecrawl or set FIRECRAWL_API_URL for a self-hosted Firecrawl instance. Log in to
Nous Portal to use managed Firecrawl web tools: run `hermes model`.
```

## 诊断命令（按序执行）

```bash
hermes status | grep -iE 'Firecrawl|Nous Portal'
# → Firecrawl ✗ (not set)  /  Nous Portal ✗ not logged in (run: hermes portal)

env | grep -iE 'firecrawl'                # 空 = 无 key
grep -A4 '^web:' ~/.hermes/config.yaml    # web.backend: firecrawl 已设但缺后端凭证
```

判断逻辑：`web.backend: firecrawl` 只是选了后端类型；真正缺的是 后端凭证三选一（key / url / Portal 登录）。config.yaml 里 `web.use_gateway: true` 与报错无关。

## 修复三选一

1. **Nous Portal 登录（推荐，免费额度托管）**：`hermes portal login`（`hermes portal` 无子命令即 login）
2. **云 Firecrawl key**：`~/.hermes/.env` 加 `FIRECRAWL_API_KEY=xxx`（firecrawl.dev 付费）
3. **自托管**：`~/.hermes/.env` 加 `FIRECRAWL_API_URL=http://localhost:3002`（需自己部署 Firecrawl 实例）

## `hermes portal login` 执行实录（设备码 OAuth）

```bash
# ❌ 前台 + pty 60s → exit 124（进程在等用户授权，不会自己结束）
hermes portal login   # Command timed out after 60s

# ✅ 正确姿势：background + pty，然后 poll 拿授权链接
terminal(background=true, pty=true, command="hermes portal login")
process(action='poll')  # 输出:
#   To continue:
#     1. Open: https://portal.nousresearch.com/manage-subscription?user_code=XN8Z-AQV3
#     2. If prompted, enter code: XN8Z-AQV3
#   Waiting for approval (polling every 1s)...
```

关键点：
- 输出附注 `(Opened browser for verification)` —— Hermes 尝试本机弹浏览器，但**用户不在电脑前也能完成**：设备码流程让用户拿手机/任意设备浏览器打开 URL + 输入验证码即可，本机只是后台轮询
- 验证码几分钟过期；用户改期 → `process(action='kill')` 停掉等待进程，下次重新发起生成新 code
- login 是 one-shot onboarding：帮助文本提示会「pick a model, set Nous as your provider」。登录成功后核对 `hermes config get model.provider`（本机原 deepseek），被改则 `hermes config set model.provider deepseek` 恢复
- 只想加凭据、不想动模型配置：`hermes auth add nous --type oauth`（`hermes portal --help` 中注明与 login 等价于该命令）

## 未配置期间的 curl 降级模式

web 工具不可用时不阻塞任务，用 terminal + curl 打公开 API：

```bash
# GitHub 仓库元数据 + 文件树 + README（评估开源项目够用）
curl -sL --max-time 15 -o /tmp/repo.json "https://api.github.com/repos/<owner>/<repo>"
curl -sL --max-time 15 -o /tmp/tree.json "https://api.github.com/repos/<owner>/<repo>/git/trees/<branch>?recursive=1"
curl -sL --max-time 15 -o /tmp/readme.md "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md"
# 之后 python3 -c "import json; ..." 解析
```

经验：评估 GitHub 开源项目时这套比 web_extract 还稳（无正文噪音、无反爬）。行情类抓取（东财/同花顺接口）不受影响——那些本就走 terminal + requests。
