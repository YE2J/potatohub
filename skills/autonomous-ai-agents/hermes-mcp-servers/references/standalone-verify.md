# 不重启会话直连 MCP 服务器验证工具与凭据

`hermes mcp list` 只证明服务器注册成功，不代表凭据有效。此脚本用 Hermes venv python 直连 stdio MCP 服务器，真实调用工具验证。

## 关键点

- **系统 python3（/usr/bin/python3）无 `mcp` 模块** → 必须用 Hermes venv：`~/.hermes/hermes-agent/venv/bin/python`
- stdio 服务器子进程**不继承 shell 环境变量** → 凭据必须在脚本里显式传入 `env`（与 config.yaml 的 `env:` 段一致）
- 用 `grep -v "^\["` 过滤 MCP 服务器的日志行（服务器 logger 输出到 stderr）

## 模板脚本

```python
import asyncio, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(
        command="zlibrary-mcp",   # 或 npx / uvx 命令
        env={**os.environ,
             "ZLIBRARY_EMAIL": "xxx",
             "ZLIBRARY_PASSWORD": "yyy",
             "ZLIBRARY_MIRROR": "https://z-lib.li"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"TOOLS: {len(tools.tools)}")
            # 真实调用一个工具验证凭据
            result = await session.call_tool("search_books", {"query": "python", "limit": 3})
            for item in result.content:
                txt = item.text if hasattr(item, 'text') else str(item)
                print("SEARCH_RESULT:", txt[:1500])
            # 可选：读取限额类工具进一步验证账号状态
            limits = await session.call_tool("get_download_limits", {})
            for item in limits.content:
                txt = item.text if hasattr(item, 'text') else str(item)
                print("LIMITS:", txt[:500])

asyncio.run(main())
```

运行：

```bash
~/.hermes/hermes-agent/venv/bin/python /tmp/mcp_verify.py 2>&1 | grep -v "^\[" | head -60
```

## 判读

| 输出 | 含义 |
|:-----|:-----|
| `TOOLS: N` + 真实数据（书名/ID） | ✅ 凭据有效，工具可用 |
| `Python virtual environment not found / run uv sync` | ⛔ UV-based 包未初始化，见 SKILL.md「UV-based npm MCP 包需要 uv sync」 |
| `Missing environment variable(s)` | ⛔ 凭据没传进子进程（检查 env 是否显式传入） |
| 连接超时 / ECONNREFUSED | ⛔ 服务器命令路径不对或服务起不来 |
