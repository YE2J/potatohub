# 已安装地问财技能完整清单

此文件作为 `iwencai-skillhub` 的参考清单，记录所有已安装技能及安装时间。

## 安装状态（共12个）

| # | 技能名称 | 安装日期 | 大小 | 类型 | 目录 |
|---|---------|---------|------|------|------|
| 1 | 估值模型方法论 | 2026-06-16 | 9KB | 社区 | valuation-model |
| 2 | 基本面因子筛选 | 2026-06-16 | 4.4KB | 社区 | fundamental-filter |
| 3 | 市场情绪分析 | 2026-06-16 | 8.3KB | 社区 | sentiment-analysis |
| 4 | 财务报表深度解读 | 2026-06-16 | 8.6KB | 社区 | financial-statement |
| 5 | 因子研究框架 | 2026-06-16 | 3.4KB | 社区 | factor-research |
| 6 | 盈利预期修正分析 | 2026-06-16 | 4.8KB | 社区 | earnings-revision |
| 7 | 盈利预测与一致预期分析 | 2026-06-16 | 4.1KB | 社区 | earnings-forecast |
| 8 | 量化因子选股 | 2026-06-16 | 9.1KB | 社区 | quant-factor |
| 9 | 现金流折现估值模型 | 2026-06-16 | 49KB | 社区 | dcf-model (含 scripts/ + TROUBLESHOOTING.md) |
| 10 | hithink-management-query | 2026-06-16 | 12KB | 官方 | flat (含 scripts/cli.py) |
| 11 | 分钟级数据分析 | 2026-06-16 | 4.2KB | 社区 | minute-analysis |
| 12 | 基本面因子筛选 | 2026-06-16 | 4.4KB | 社区 | fundamental-filter |

## Hermes 原生翻译版

以下问财技能已翻译为 Hermes 原生 Skill 格式（`~/.hermes/skills/research/`）：

| 翻译版名称 | 基于 | 功能 |
|-----------|------|------|
| a-share-valuation | 估值模型方法论 | DCF/DDM/SOTP + PE-Band/PB-ROE/EV-EBITDA + 10陷阱 |
| a-share-research | 研报搜索 + 机构研究 | Tushare MCP 研报 + 问财API机构数据 |

## 官方技能 API

官方技能（如 hithink-management-query）需要额外配置：
- `IWENCAI_BASE_URL=https://openapi.iwencai.com`
- `IWENCAI_API_KEY=sk-...`
- 调用方式：POST `/v1/query2data` + 特定 Headers（X-Claw-Skill-Id 等）
- API Key 获取：SkillHub 页面 → 登录 → 点击 Skill → 查看详情
