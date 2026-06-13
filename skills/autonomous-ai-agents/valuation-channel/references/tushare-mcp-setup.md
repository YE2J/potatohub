# Tushare MCP + Python SDK 配置参考

## 背景

用户已有 Tushare token（6570d7...e8e），配置了双通道访问：

| 方式 | 用途 | 配置命令 |
|------|------|----------|
| MCP 服务器 | 对话中让 Hermes 直接调 Tushare 数据 | `hermes mcp add tushareMcp --url "https://api.tushare.pro/mcp/?token=..."` |
| Python SDK | 脚本/分析中编程调取 | `pip install tushare` + `.env` 写入 token |

## MCP 服务器配置

### 添加命令

```bash
hermes mcp add tushareMcp --url "https://api.tushare.pro/mcp/?token=6570d7ea1f9ab8dece97e18afb1e3e814c681b4b9bc6d3841ddd7e8e"
```

### 交互式输入（两个提示）

该命令会触发两个交互式提示，需通过 pty 后台进程处理：

1. **"Does this server require authentication? [Y/n]:"** → 回答 `n`
   - Tushare token 已在 URL 中，无需额外认证
2. **"Enable all 258 tools? [Y/n/select]:"** → 回答 `Y`
   - 启用全部工具

### 处理交互提示的流程

```bash
# 启动后台 pty 进程
hermes mcp add tushareMcp --url "..."&
# 回答认证问题
# -> 输入 n
# 等待工具发现完成
# -> 输入 Y
```

### 验证

```bash
hermes mcp list
```

预期输出：
```
Name             Transport                      Tools        Status
──────────────── ────────────────────────────── ──────────── ──────────
tushareMcp       https://api.tushare.pro/m...   all          ✓ enabled
```

### 生效

MCP 工具需要重启会话才可用（`/reset` 或新开会话）。工具名前缀 `mcp_tushareMcp_`，例如 `mcp_tushareMcp_daily`。

## Python SDK 配置

### 安装

```bash
pip install tushare
```

### 配置 token

在 `~/.hermes/.env` 中添加：

```
TUSHARE_TOKEN=6570d7ea1f9ab8dece97e18afb1e3e814c681b4b9bc6d3841ddd7e8e
```

### 使用示例

```python
import tushare as ts
ts.set_token('6570d7ea1f9ab8dece97e18afb1e3e814c681b4b9bc6d3841ddd7e8e')
pro = ts.pro_api()

# 日线行情
df = pro.daily(ts_code='000988.SZ', start_date='20260601', end_date='20260613')

# 利润表
df = pro.income(ts_code='000988.SZ', start_date='20260101', end_date='20260613')

# 每日指标（PE/PB等）
df = pro.daily_basic(ts_code='000988.SZ', start_date='20260601', end_date='20260613')

# 个股资金流向
df = pro.moneyflow(ts_code='000988.SZ', start_date='20260601', end_date='20260613')
```

## 常用 MCP 工具速查

| MCP 工具名 | 对应 Tushare API | 用途 |
|-----------|-----------------|------|
| `mcp_tushareMcp_daily` | `pro.daily()` | 日线行情 |
| `mcp_tushareMcp_daily_basic` | `pro.daily_basic()` | 每日指标(PE/PB/换手率) |
| `mcp_tushareMcp_income` | `pro.income()` | 利润表 |
| `mcp_tushareMcp_balancesheet` | `pro.balancesheet()` | 资产负债表 |
| `mcp_tushareMcp_cashflow` | `pro.cashflow()` | 现金流量表 |
| `mcp_tushareMcp_fina_indicator` | `pro.fina_indicator()` | 财务指标(ROE等) |
| `mcp_tushareMcp_moneyflow` | `pro.moneyflow()` | 个股资金流向 |
| `mcp_tushareMcp_stk_mins` | `pro.stk_mins()` | 历史分钟线 |
| `mcp_tushareMcp_limit_list` | `pro.limit_list()` | 涨跌停统计 |
| `mcp_tushareMcp_ths_hot` | `pro.ths_hot()` | 同花顺热榜 |
| `mcp_tushareMcp_stk_factor_pro` | `pro.stk_factor_pro()` | 技术面因子 |
