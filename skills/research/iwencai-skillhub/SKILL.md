---
name: iwencai-skillhub
description: "安装、使用同花顺问财 Skill Hub 的技能生态系统。涵盖 CLI 安装、PYTHONPATH 冲突修复、技能发现与安装、以及将问财技能翻译为 Hermes 原生格式的流程。"
version: 1.0.0
tags: [iwencai, skillhub, a-share, valuation, financial-data, openclaw]
---

# 问财 Skill Hub 集成

## 触发条件

当用户提到：问财、iwencai、同花顺skill、iwencai-skillhub-cli、安装问财技能、问财估值、问财研报 等。

## 概述

同花顺问财 Skill Hub（https://www.iwencai.com/skillhub）是「全球最大的金融投资AI技能库」，包含：
- **24 个官方技能**：同花顺出品，底层对接同花顺数据平台
- **67+ 个社区技能**：@ClawHub 贡献，量化/分析/策略类

技能为 **OpenClaw 格式**，但逻辑可直接翻译到 Hermes。CLI 工具用于下载和管理技能。

## CLI 安装

```bash
# 下载并运行安装脚本
cd /tmp && curl -fsSL https://www.iwencai.com/skillhub/static/0.0.4/download_and_install.sh | bash
```

⚠️ **安装脚本可能找不到内部脚本**：如果报告 `aime-install.sh not found`，那是因为脚本名已改为 `iwencai-install.sh`。此时需手动操作：

```bash
mkdir -p /tmp/iwencai_cli && cd /tmp/iwencai_cli
curl -fsSL https://www.iwencai.com/skillhub/static/0.0.4/iwencai-skillhub-cli.zip -o cli.zip
unzip -o cli.zip
cd iwencai-skillhub-cli && bash iwencai-install.sh
```

安装到：`~/.iwencai-skillhub/` + wrapper `~/.local/bin/iwencai-skillhub-cli`

## PYTHONPATH 冲突修复（关键）

Hermes 设置了 `PYTHONPATH=/Users/yellow/.hermes/hermes-agent`，导致 Python 的 `import cli` 找到了 Hermes 的 `cli.py` 而非问财的 `cli/` 目录，报错 `ModuleNotFoundError: No module named 'yaml'`。

**需要两步修复**：

### 1. 修改 wrapper 脚本 `~/.local/bin/iwencai-skillhub-cli`

在 `exec python3` 前添加：
```bash
unset PYTHONPATH
```

### 2. 修改 CLI 脚本 `~/.iwencai-skillhub/aime_skillhub_cli.py`

在 `sys.path.insert(0, ...)` 前添加：
```python
# Override CWD to avoid shadowing by other cli.py files
os.chdir(str(Path(__file__).resolve().parent))
```

修复后验证：
```bash
export PATH="$HOME/.local/bin:$PATH" && iwencai-skillhub-cli --help
```

## 技能安装

```bash
export PATH="$HOME/.local/bin:$PATH"

# 安装单个技能（slug 为中文名时直接用中文）
iwencai-skillhub-cli --dir "$HOME/.iwencai-skillhub/skills" install "技能名称"

# 例如
iwencai-skillhub-cli --dir "$HOME/.iwencai-skillhub/skills" install "估值模型方法论"
```

安装产物：`~/.iwencai-skillhub/skills/<技能名>/<英文目录>/SKILL.md`

## 技能 Slug 发现

问财社区技能的 **slug 就是中文名称本身**（URL-encoded），下载 URL 模板：
`http://ms.10jqka.com.cn/gateway/market/api/v1/skills/square/download?name={slug}`

**多候选探测法**（不确定slug时批量试）：
```bash
for slug in "中文名" "english-name" "简写"; do
  code=$(curl -fsSL -o /dev/null -w "%{http_code}" \
    "http://ms.10jqka.com.cn/gateway/market/api/v1/skills/square/download?name=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$slug'))")" 2>&1)
  size=$(curl -fsSL -o /dev/null -w "%{size_download}" \
    "http://ms.10jqka.com.cn/gateway/market/api/v1/skills/square/download?name=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$slug'))")" 2>&1)
  echo "$slug → HTTP $code, $size bytes"
done
```

**判定标准**：HTTP 200 + response size > 1000 bytes = 有效技能（<100 bytes 返回的是 `{"status_code":-1,...}` 错误JSON）。

## 官方技能 vs 社区技能

| 类型 | 来源 | 下载方式 | Slug |
|------|------|---------|------|
| 社区技能 | ClawHub square | `iwencai-skillhub-cli install` | 中文名 |
| 官方技能 | 同花顺出品 | 通过问财 **OpenAPI**（非ClawHub），需 `IWENCAI_API_KEY` | slug 如 `hithink-management-query` |

⚠️ **官方技能不在 ClawHub square 中**：尝试下载 `研报搜索`、`机构研究与评级查询` 等官方技能时，API 返回 `"广场中未找到该Skill"`。官方技能需通过问财 OpenAPI 直接调用或从 SkillHub 页面获取 API Key。

### 官方技能 API Key 配置

1. 浏览器打开 https://www.iwencai.com/skillhub → 登录 → 点击具体 Skill → 查看详情获取 API Key
2. 配置环境变量（shell + Hermes 两个位置都要设）：

```bash
# ~/.zshrc
export IWENCAI_BASE_URL=https://openapi.iwencai.com
export IWENCAI_API_KEY="sk-proj-..."

# ~/.hermes/.env
IWENCAI_BASE_URL=https://openapi.iwencai.com
IWENCAI_API_KEY="sk-proj-..."
```

3. 官方技能通过 `POST https://openapi.iwencai.com/v1/query2data` 调用，需携带特定 Headers：

| Header | 值 |
|--------|---|
| `Authorization` | `Bearer <IWENCAI_API_KEY>` |
| `Content-Type` | `application/json` |
| `X-Claw-Skill-Id` | 技能标识（如 `hithink-finance-query`） |
| `X-Claw-Skill-Version` | 版本（如 `1.0.0`） |
| `X-Claw-Trace-Id` | 每次请求新生成的64字符hex（`secrets.token_hex(32)`） |

**请求体**：`{"query": "查询语句", "page": "1", "limit": "10", "is_cache": "1", "expand_index": "true"}`

## 技能内容结构

安装的技能是 OpenClaw 格式的 Markdown，包含：
## 已安装的技能

| # | 技能 | 大小 | 内容概要 |
|---|------|------|---------|
| 1 | 估值模型方法论 | 9KB | DCF/DDM/SOTP + PE-Band/PB-ROE/EV-EBITDA |
| 2 | 基本面因子筛选 | 4.4KB | PE/PB/ROE价值/成长筛选，A/港/美股 |
| 3 | 市场情绪分析 | 8.3KB | 恐贪指数/PCR/融资融券/北向资金/舆情 |
| 4 | 财务报表深度解读 | 8.6KB | 三表勾稽+盈利质量+12红旗+杜邦分析 |
| 5 | 因子研究框架 | 3.4KB | IC/IR分析+分层回测+因子组合(等权/IC加权/正交化) |
| 6 | 盈利预期修正分析 | 4.8KB | SUE/PEAD/管理层指引/盈利质量，美股/港股 |
| 7 | 盈利预测与一致预期分析 | 4.1KB | Top-Down/Bottom-Up预测+SUE+A股PEAD日历 |
| 8 | 量化因子选股 | 9.1KB | 6因子(价值/动量/质量/低波/规模/成长)+择时+拥挤度(含references) |
| 9 | 现金流折现估值模型 | 49KB | 投行级DCF+Excel生成+三场景+敏感性+验证脚本(requirements.txt+scripts) |
| 10 | 分钟级数据分析 | 4.2KB | OKX/Tushare/yfinance分钟K线+VWAP/TWAP |

### Hithink 官方技能（IWENCAI OpenAPI）

| # | 技能 | 大小 | 领域 |
|---|------|------|------|
| 11 | hithink-market-query | 10.3KB | 行情数据：实时价格/涨跌幅/技术指标/资金流向 |
| 12 | hithink-finance-query | 10.4KB | 财务数据：营收/净利润/ROE/负债率/现金流/PE/PB |
| 13 | hithink-management-query | 10.4KB | 股东股本：股本结构/前十大股东/实控人/高管/质押(含scripts/cli.py) |
| 14 | hithink-insresearch-query | 10.4KB | 机构研究：研报评级/业绩预测/券商金股/ESG/信用评级 |
| 15 | report-search | 75KB | 研报搜索：投研机构研报全文+智能拆解+质量评估(含9个Python脚本+references) |

## 与你现有系统的关系

| 问财技能 | 对应 Hermes 系统 | 关联 |
|----------|-----------------|------|
| 估值模型方法论 → | `a-share-valuation` (Hermes原生翻译版) | 估值框架 |
| 现金流折现估值模型 → | `a-share-valuation` | 执行层：DCF Excel模型 |
| 财务报表深度解读 → | `a-share-valuation` | 补充：盈利质量+造假检测 |
| 量化因子选股 → | `a-share-quant-backtest` | 因子筛选+择时+拥挤度 |
| 因子研究框架 → | `a-share-quant-backtest` | 因子验证：IC/IR/分层回测 |
| 基本面因子筛选 → | `a-share-quant-backtest` | PE/PB/ROE价值筛选 |
| 盈利预测与一致预期分析 → | `a-share-research` + `a-share-quant-backtest` | SUE/PEAD信号生成 |
| 盈利预期修正分析 → | `a-share-research` | 分析师修正动量 |
| 市场情绪分析 → | `a-share-quant-backtest` | 情绪过滤层 |
| 分钟级数据分析 → | `a-share-quant-backtest` | Tushare数据通道 |
| hithink-management-query → | `a-share-research` | 股本/股东/高管查询 |

## 已安装的技能

- `估值模型方法论` — `~/.iwencai-skillhub/skills/估值模型方法论/valuation-model/SKILL.md` (9KB)
  - DCF/DDM/SOTP 绝对估值 + PE-Band/PB-ROE/EV-EBITDA 相对估值 + 10项估值陷阱检测

## 参考文件

- `references/skillhub-catalog.md` — 完整技能目录（官方24个 + 社区67个），含与 Hermes 系统的匹配建议
- `references/installed-skills.md` — 已安装技能完整清单（15个），含安装日期、类型、对应 Hermes 原生翻译版
- `references/hithink-openapi.md` — Hithink OpenAPI 调用规范：端点/认证/请求头/响应解析
