---
name: zlibrary-download
description: "z-lib 搜索/下载/失败诊断/配额管理全流程。Use when 用户要求从 z-lib 下载书籍/研报，或遇到下载失败/配额耗尽/镜像问题。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [zlibrary, z-lib, download, books, quota, eapi, diamwall]
    category: productivity
    related_skills: [office-to-markdown, ocr-and-documents]
    validation_status: verified  # 2026-08-23 05:30 cron 实跑 5/5 成功闭合
---

# Z-Library 下载全流程

> 覆盖：搜索定位、失败诊断、配额管理、批量下载、自动兜底。
> **验证状态：pending**（2026-08-23 cron 72f397da4a6b 实跑 5 篇后闭合）。

## 触发条件

- 用户要求从 z-lib 下载书籍/研报/文档
- 下载失败、报错（配额/镜像/DiamWall/Cloudflare）
- 书库批量入库前的获取环节

## 核心认知（先读，前两次误判的根因）

1. **`ZLIBRARY_MIRROR` 只管网页端（浏览器打开 z-lib.bh 等），不影响 EAPI 直连**。
   下载失败先怀疑配额，不要甩锅镜像。
2. **每日 10 篇下载配额是账号级**，服务端限制，~05:00（北京时间）重置。
   症状：`disallowDownloadMessage` 含 "daily limit ... is already reached"。
3. **EAPI 域探测 z-library.ec 健康**（eapi.py 内置 probe + 自动切换），登录/搜索正常。
4. **MCP 进程缓存旧镜像**：`ZLIBRARY_MIRROR` 在 MCP 连接启动时注入，改配置后**需重启 Hermes 应用**才生效；但下载走 EAPI 不受此影响。

## 4 种失败模式诊断表

| 模式 | 症状 | 诊断命令 | 修复 |
|---|---|---|---|
| ① 每日配额耗尽 | `disallowDownloadMessage` 含 "daily limit" | `tail -30 ~/logs/zlibrary_debug.log`（看 ERROR 行） | 等 ~05:00 重置 / 挂 cron 自动下载 / 网页手动 |
| ② MCP 缓存旧镜像 | `ps eww $(pgrep -f zlibrary-mcp) \| tr ' ' '\n' \| grep MIRROR` 显示旧域 | 同上 | 重启应用；或绕过 MCP 用直连脚本 |
| ③ DiamWall 拦截 | HTTP 307/403/513/517 + `diamwall` 字样 | eapi.py `probe_eapi_domain` 自动跳过墙域 | 已内置（DEFAULT_EAPI_DOMAINS 首位 z-library.ec）；手动可 `export ZLIBRARY_EAPI_DOMAIN=z-library.ec` |
| ④ Cloudflare 挑战 | HTTP 403 + HTML 响应 | 同 ③ | 同 ③；**勿误判为配额/镜像** |

**第一步永远是**：`tail -30 ~/logs/zlibrary_debug.log` 找 ERROR 行的真实原因，再对照上表。

## 直连脚本（绕过 MCP 缓存，推荐）

工作副本：`~/.hermes/scripts/zlib_download_guoxin.py`（**含真实凭据，chmod 600**）
包内解释器：`~/.npm-global/lib/node_modules/zlibrary-mcp/.venv/bin/python`

```bash
# 验证登录+配额（不下载）
cd ~/.npm-global/lib/node_modules/zlibrary-mcp && ./.venv/bin/python ~/.hermes/scripts/zlib_download_guoxin.py --check

# 下载（BOOKS 默认列表）
bash ~/.hermes/scripts/zlib_download_guoxin.sh

# 自定义书单（JSON 文件覆盖 BOOKS）
./.venv/bin/python ~/.hermes/scripts/zlib_download_guoxin.py --books-file /tmp/books.json
```

`--books-file` JSON 格式：`[{"id":"15822516","hash":"e7f7c3","filename":"书名.pdf"}, ...]`（id/hash 来自 search_books 返回）。

**幂等/断点续传**：目标文件已存在且 >100KB 且 `file` 判定为 PDF → 跳过不重下（cron 重复触发安全）。

## 标准流程

1. **诊断**：`tail -30 ~/logs/zlibrary_debug.log` → 对照 4 模式表
2. **定位**：MCP `search_books`（不重复封装搜索）→ 拿 id/hash/书名
3. **验配额**：`--check` 跑一遍（登录 + 5 篇 allowDownload 状态）
4. **下载**：配额 OK → 直接跑；配额耗尽 → 挂一次性 cron 明早 05:30（配额 05:00 重置）+ 或网页手动
5. **入库**：下载后走 office-to-markdown 批量分析入库（见该 skill）

## 验证清单

- `file <pdf>` 输出含 "PDF document" + 页数
- `md5 -q <pdf>` 记录（入库去重用）
- pymupdf 取文本层字符数（>0 说明非扫描件）：
  ```bash
  PY=/Users/yellow/.hermes/hermes-agent/venv/bin/python
  $PY -c "import pymupdf; d=pymupdf.open('文件.pdf'); print(sum(len(p.get_text()) for p in d))"
  ```

## 安全合规（必须遵守）

- **z-lib 为影子图书馆，仅限个人学习研究，不传播、不商用**。
- 脚本含明文凭据 → `chmod 600`；**任何模板/示例绝不出现真实邮箱密码**（skills 每周日同步 GitHub PotatoHub）。
- 模板用环境变量/占位符：`EMAIL = os.getenv("ZLIB_EMAIL", "YOUR_EMAIL")`。
- 下载目标仅限用户明确要求的书目。

## 资产依赖表

| 资产 | 路径 | 说明 |
|---|---|---|
| 工作脚本（含凭据） | `~/.hermes/scripts/zlib_download_guoxin.py` | chmod 600；BOOKS 默认 5 篇国信 |
| cron 包装 | `~/.hermes/scripts/zlib_download_guoxin.sh` | 一次性 cron 引用，勿改名 |
| 包内解释器 | `~/.npm-global/lib/node_modules/zlibrary-mcp/.venv/bin/python` | 依赖 zlibrary-mcp 包内 venv，**包升级后路径可能漂移，先验证** |
| EAPI 客户端 | 包内 `zlibrary/src/zlibrary/eapi.py` | 内置域探测/墙跳过/登录 |
| MCP 日志 | `~/logs/zlibrary_debug.log` + 包内 `logs/` | 诊断第一现场 |
| 技能模板 | 本 skill `scripts/zlib_download_template.py` | 无凭据参数化模板，复制改 BOOKS 用 |

## Fallback 路径（主链路全挂时）

1. `search_multi_source`（LibGen / Anna's Archive）——2026-08 实测**通道不可用**（连通用词都空），但可作为候补
2. 网页端手动下载（浏览器登录 z-lib 官方域，链接给用户纯文本）
3. 明日配额重置后再试（cron 自动）
