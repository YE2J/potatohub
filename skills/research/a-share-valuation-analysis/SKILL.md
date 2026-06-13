---
name: a-share-valuation-analysis
title: A股估值分析系统 (daily_stock_analysis)
description: 基于 daily_stock_analysis (42k⭐) + DeepSeek AI，对A股自选股进行每日估值分析、技术面和舆情分析，生成决策仪表盘报告并通过 Hermes 自动推送。
tags: [a-share, 估值分析, DCF, 基本面, deepseek, 量化投资, valuation-channel]
---

# A股每日估值分析系统

## 架构

```
daily_stock_analysis (42k⭐ GitHub)
  ├─ AKShare / 腾讯财经 → 实时行情 + 财务数据 (免费)
  ├─ DeepSeek AI         → 基本面 + 技术面 + 舆情分析
  ├─ 决策仪表盘报告        → Markdown 完整报告
  └─ Hermes cronjob       → 定时运行 + 推送
```

## 已部署路径

- **项目目录**: `/Users/yellow/daily_stock_analysis`
- **Python venv**: `.venv` (Python 3.9)
- **配置文件**: `.env`
- **报告输出**: `reports/report_YYYYMMDD.md`
- **运行脚本**: `run_and_report.sh`
- **Hermes cronjob**: `A股每日估值分析` (job_id: `146427eba3a4`)
- **Cron 调度**: 每天 16:00 北京时间 (`0 16 * * *`)
- **推送渠道**: 通过 Hermes 自动送达当前聊天

## 修改自选股

修改 `.env` 文件中的 `STOCK_LIST` 变量：

```bash
cd /Users/yellow/daily_stock_analysis && source .venv/bin/activate
python main.py --stocks 600519,000858,002594 --no-notify
```

修改后更新 Hermes cronjob：用 `cronjob action=update job_id=146427eba3a4` 更新 prompt 中的股票列表。

## 手动运行

```bash
bash run_and_report.sh
```

## 注意事项

### Python 3.9 兼容性
已在以下文件中添加 `from __future__ import annotations`：
- `src/market_analyzer.py`
- `src/agent/factory.py`
- `src/core/market_review.py`

### API Key
DeepSeek API key 保存在 `.env` 中。编辑 `LLM_DEEPSEEK_API_KEY`。

## 数据源

| 数据源 | 状态 | 内容 | 备注 |
|--------|------|------|------|
| ✅ **腾讯 qt.gtimg.cn** (实时) | ✅ 可用 | 实时行情、PE-TTM、成交量 | 直接 HTTP GET, 无需认证 |
| ✅ **腾讯 web.ifzq.gtimg.cn** (K线) | ✅ 可用 | 前复权日/周/月K线 | 分页上限 ~640条/次 |
| ✅ **同花顺 akshare stock_financial_abstract_ths** | ✅ 可用 | 季度EPS、营收、ROE等 | ~0.15s/股, 无需API Key |
| ❌ 东方财富 (push2.eastmoney.com) | ❌ 网络阻塞 | — | 连接被重置 |
| ❌ 雪球 (xueqiu.com) | ❌ 需登录 | — | 返回 400 |

### 腾讯 K线 API 用法

```
# 日K线 (前复权), 每段约640条, 需分页
GET http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,{start_date},{end_date},{limit},qfq

# 周K线 (更推荐用于通道分析, 连续无缺口)
GET http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},week,{start_date},{end_date},{limit},qfq

# 月K线 (超长周期)
GET http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},month,{start_date},{end_date},{limit},qfq
```

返回格式: `[日期, 开盘, 收盘, 最高, 最低, 成交量]`

### 腾讯实时行情

```
GET https://qt.gtimg.cn/q={market}{code}
```

位置 `[39]` = PE-TTM (动态市盈率); 字段以 `~` 分隔。

### 腾讯 K线分页策略

日K线单次最多~640条。若要覆盖5年+数据需要分段请求并拼接。周线单次即可覆盖 2016-2026 (533条)。

### 同花顺 EPS 数据

```python
import akshare as ak
df = ak.stock_financial_abstract_ths(symbol='000001', indicator='按报告期')
# → 返回 DataFrame: ['报告期','基本每股收益','每股净资产','营业总收入',...]
```

EPS 为**累积值**: Q1即Q1累积, H1=Q1+Q2累积... 计算TTM需转为单季度值:
```
Q1_standalone = Q1_cum
Q2_standalone = H1_cum - Q1_cum
Q3_standalone = 9M_cum - H1_cum
Q4_standalone = FY_cum - 9M_cum
TTM_EPS = sum of latest 4 standalone quarters
```

### 股票代码市场识别

| 前缀 | 市场 | 示例 |
|------|------|------|
| 6xx, 9xx | `sh` (上海) | 600519 → sh600519 |
| 0xx, 3xx, 2xx | `sz` (深圳) | 000001 → sz000001, 300750 → sz300750 |

## PE-TTM 估值通道 (PE Band)

已有独立实现工具，见 `valuation-channel` skill (`autonomous-ai-agents/valuation-channel`)。

该工具复刻同花顺 PE Band，支持：
- **5条轨道通道图** + 交互式悬停查看
- **多模型估值评估** (DCF / PB-ROE / 格雷厄姆 / PEG / DDM)
- **批量扫描底部股票**
- 数据源：腾讯 K线 + 同花顺 EPS (已验证可用)

```bash
# 单只股票估值评估
cd ~/.hermes/skills/autonomous-ai-agents/valuation-channel/scripts
source ~/.hermes/venv_stock/bin/activate
python valuation_channel.py 600519 --evaluate
```

## 费用
DeepSeek API 约 ¥0.5/百万token，一次4只股票分析约 ¥0.01-0.03。

## 输出内容
报告包含：分析总览、舆情情绪、当日行情、均线排列、乖离率、支撑/压力位、操作点位、止损位、仓位建议、检查清单、关联板块。
