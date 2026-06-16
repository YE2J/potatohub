---
name: valuation-channel
description: "A股PE-TTM估值通道图生成器。输入股票代码，生成5条轨道的市盈率通道图（复刻同花顺PE Band），支持交互式悬停查看、批量扫描底部股票、多模型综合估值评估、四通道(PE/PB/PS/PCF)网格图。数据源：腾讯财经K线 + 同花顺EPS。"
version: 2.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [a-share, stock, valuation, pe-band, finance, quant, dcf, pb, ps]
    related_skills: []
---

# A股 PE-TTM 估值通道 (Valuation Channel)

同花顺风格市盈率估值通道图 + **多模型估值评估引擎** + **四维度通道网格图**。

## 功能概览

| 功能 | 类 | CLI参数 |
|------|-----|---------|
| 📈 PE通道图（5条轨道+交互悬停） | `ValuationChannelGenerator` | `python val_channel.py 600519` |
| 📋 批量扫描通道底部 | `BatchScanner` | `--batch 000001,600519` |
| 🧠 **多模型估值评估** | `ValuationAssessor` | `--evaluate / -e` |
| 🗺️ **4合1多维度通道 (PE/PB/PS/PCF)** | `MultiChannelValuation` | `--all-channels / -a` |

## 多维度估值通道 (MultiChannelValuation)

同花顺App风格的2×2四通道网格图，同时展示**市盈率(PE-TTM)、市净率(PB-MRQ)、市销率(PS-TTM)、市现率(PCF-TTM)**四个估值维度。

### 各通道公式

| 通道 | 指标 | 公式 | 数据来源 |
|------|------|------|----------|
| PE-TTM | 市盈率 | 收盘价 ÷ TTM每股收益 | akshare 同花顺EPS |
| PB-MRQ | 市净率 | 收盘价 ÷ 每股净资产（最新季度） | akshare 同花顺 |
| PS-TTM | 市销率 | 收盘价 ÷ TTM每股销售额(营收÷总股本) | akshare营收 + 腾讯市值 |
| PCF-TTM | 市现率 | 收盘价 ÷ TTM每股经营现金流 | akshare 同花顺 |

### CLI

```bash
# 生成4合1图
python valuation_channel.py 000999 --all-channels -o /tmp/all.png

# Python API
from valuation_channel import MultiChannelValuation
mcv = MultiChannelValuation()
fig = mcv.generate_all('000999', days=365)
fig.savefig('/tmp/all.png', dpi=150)
```

### 输出格式

同花顺App一致的2×2网格，每个子图包含：
- 5条估值轨道线（低估→偏低→中位→偏高→高估）
- 实际收盘价曲线（深色粗线）
- 低于低估轨道的红色填充区域
- 左下角统计：Min / Median / 当前值

## 多模型估值引擎 (ValuationAssessor)

整合 **5种估值模型 + PE通道 + 安全边际评分**，一键输出投资评级。

### 模型明细

| 模型 | 适用 | 输入数据 |
|------|------|----------|
| **DCF 现金流折现** | 现金流稳定的消费/制造企业 | 每股经营现金流、营收增长率 |
| **PB-ROE 框架** | 金融、保险、周期股 | 每股净资产、ROE |
| **格雷厄姆公式** | 价值股通用 | EPS-TTM、增长率 |
| **PEG 比率** | 成长股（创业板/科创板） | PE、EPS增长率 |
| **DDM 股息折现** | 高分红成熟企业 | EPS、BVPS、ROE |

### 评级规则

| 星级 | 条件 | 建议 |
|------|------|------|
| ⭐⭐⭐⭐⭐ | 安全边际>20% + 通道底部 + PEG合理 | 强烈推荐 |
| ⭐⭐⭐⭐ | 安全边际>5% + 通道低位 | 推荐 |
| ⭐⭐⭐ | 估值合理区间内 | 中性/持有 |
| ⭐⭐ | 安全边际不足 | 谨慎 |
| ⭐ | 高估 | 回避 |

## 安装依赖

```bash
pip install akshare matplotlib mplcursors pandas numpy requests
```

> macOS 自带中文字体；Linux 需安装 fonts-wqy-zenhei

## 使用方法

### CLI

```bash
# PE通道图（默认）
python valuation_channel.py 600519 --days 365

# 4合1多维度估值通道 (PE/PB/PS/PCF)
python valuation_channel.py 000999 --all-channels -o /tmp/all.png

# 多模型估值评估
python valuation_channel.py 002415 --evaluate

# 批量扫描通道底部
python valuation_channel.py --batch 000001,600519,300750,600887 --top 5

# 保存图表
python valuation_channel.py 600519 -o /tmp/moutai.png

# 导出数据
python valuation_channel.py 000001 --export-csv /tmp/pingan.csv
```

### Python API

```python
from valuation_channel import (
    ValuationChannelGenerator,
    ValuationAssessor,
    BatchScanner,
    MultiChannelValuation,
)

# PE通道图
vcg = ValuationChannelGenerator()
fig = vcg.generate('600519', days=365)
vcg.save_image('/tmp/band.png')
df = vcg.export_data()

# 4合1通道
mcv = MultiChannelValuation()
fig4 = mcv.generate_all('000999', days=365)

# 估值评估
va = ValuationAssessor()
print(va.evaluate('002415'))

# 批量扫描
scanner = BatchScanner()
df = scanner.scan(['000001', '600519', '002415'])
```

## 数据源

| 数据 | 来源 | 状态 | 方式 |
|------|------|------|------|
| 日K线（不复权） | 腾讯财经 ifzq.gtimg.cn | ✅ | 脚本直接HTTP |
| 季度EPS/ROE/营收/经营现金流 | 同花顺 akshare stock_financial_abstract_ths | ✅ | 脚本akshare |
| 实时PE/市值/价格 | 腾讯 qt.gtimg.cn | ✅ | 脚本直接HTTP |
| 总股本 | 腾讯市值÷价格 | ✅ | 脚本计算 |
| **全量行情+财务数据** | **Tushare MCP (258工具)** | ✅ | Hermes MCP `mcp_tushareMcp_*` |
| **Python编程访问** | **Tushare Python SDK** | ✅ | `import tushare; pro = ts.pro_api()` |

> 东方财富 push2、雪球 API 在部分网络环境下被阻断，腾讯 + 同花顺 + Tushare 三条链路已验证可替代。

### Tushare 数据源

用户已配置 Tushare MCP 服务器和 Python SDK：
- **MCP 工具**：`hermes mcp add tushareMcp --url "https://api.tushare.pro/mcp/?token=..."` — 添加时交互式回答 `n`（无需额外认证）+ `Y`（启用全部258工具）
- **Python SDK**：已安装 `pip install tushare`，token 已写入 `~/.hermes/.env` 作为 `TUSHARE_TOKEN`
- 在对话中可直接让 Hermes 调用 `mcp_tushareMcp_daily`、`mcp_tushareMcp_income` 等工具获取数据
- 查看参考文件 `references/tushare-mcp-setup.md` 了解详细配置和使用示例

## 参考脚本

`scripts/` 目录下包含辅助脚本：

| 脚本 | 说明 |
|------|------|
| `valuation_channel.py` | 主模块：通道生成 + 批量扫描 + 估值评估 + 4合1网格图 |
| `shu_zhai_strategy.py` | 薯仔交易系统Python版 — 移植自同花顺公式，含GS信号、主力雷达、仓位管理(最多3只/每只≤1/3) |

## 通道算法

1. 获取日K线（不复权）+ 季度累积财务数据
2. 累积值 → 单季值 → 滚动TTM
3. 每日比率 = 收盘价 ÷ TTM指标（PE=价格÷EPS，PB=价格÷BVPS等）
4. **Step** = 0.5 × (Median − Min)（过滤负值）
5. 5条轨道：Min → Min+Step → Median → Min+3Step → Min+4Step
6. 各轨道理论股价 = 固定比率 × 当日TTM指标

## 输出规范

当用户询问多只股票或多个维度时（如"帮我看茅台和五粮液"），**每次聚焦一个主题**，不要在一段回复里混合多个分析结果。正确的做法是：

1. 先问用户想看哪只/哪个维度先
2. 逐一呈现，每只/每个维度用明确的标题分隔
3. 等用户看完一个再问是否需要看下一个

## 边缘处理

| 情况 | 处理 |
|------|------|
| 亏损股（负EPS） | 过滤负值，不参与通道统计 |
| 新股（<20个有效数据点） | 数据不足，抛异常 |
| 分红除权 | 使用不复权 `day` 数据 |
| 营收/增长率含"亿"单位 | 自动解析去除单位 |
| ROE含"%"字符串 | 自动解析为浮点数 |
| EPS季度累积值 | 自动转为单季值再算TTM |
| 营收含"亿"（如"316.03亿"） | 先 strip("亿"), 再 float(), 单位为亿元 |

## 常见坑点

### 1. 腾讯API域名变更
`web.ifzq.gtimg.cn` 子域名已全面下线（返回 501/WAF 错误），新域名为 `ifzq.gtimg.cn`（无 `web.` 前缀）。所有引用该 API 的地方均需将 `http://web.ifzq.gtimg.cn` 改为 `https://ifzq.gtimg.cn`。

涉及文件: `scripts/valuation_channel.py` 中的 `get_kline()` 方法。

### 2. matplotlib 在 async Web 服务中挂起
在 FastAPI/uvicorn 等 async web 进程中直接导入 `valuation_channel` 并调用 `generate()` / `evaluate()` 会导致 matplotlib 静默挂起（无异常、无输出、整个进程卡死）。

**原因**：matplotlib 的 `use('Agg')` backend 与 uvicorn 的事件循环存在交互冲突，具体表现为：
- `from valuation_channel import X, Y, Z` 一次性导入多个类时可能触发
- `DataFetcher.get_kline()` 内部的分页循环在某些环境下也会僵死

**解决方案**：将估值计算隔离到独立子进程中运行，不要直接在 Web 服务进程中调用。

```python
import subprocess, json
result = subprocess.run(
    [sys.executable, 'run_valuation_subprocess.py', json.dumps(codes)],
    capture_output=True, text=True, timeout=300
)
# 从 stdout 中解析 ---RESULT_JSON--- 标记之间的 JSON
```

参考 `references/subprocess-isolation.md` 获取完整实现。

### 3. 腾讯API K线数据含分红字典字段
`get_kline()` 返回的某些行在第 6 个字段后包含一个字典（分红除权信息）。处理方式：
```python
all_rows = [r[:6] for r in all_rows]  # 只取前6个字段，丢弃分红信息
```

### 4. 腾讯API市场前缀规则
A股代码的市场前缀规则不止 `6→sh/其余→sz`：

| 股票代码开头 | 市场前缀 | 示例 |
|-------------|---------|------|
| 6xxxxx | sh | 600519, 688519 |
| 5xxxxx | sh | 501018(LOF), 513350(ETF) |
| 8xxxxx | sh | 830xxx, 87xxxx(北交所) |
| 9xxxxx | sh | 900xxx(B股) |
| 0/1/2/3xxxxx | sz | 000001, 300308 |

实现示例：
```python
market_prefix = "sh" if stock_code.startswith(("6", "5", "8", "9")) else "sz"
```

### 5. ValuationAssessor.evaluate() 极慢
`ValuationAssessor.evaluate()` 因内部多次调用 akshare + matplotlib 多模型计算，**单只股票耗时 ~460 秒**。不适合批量或在线场景。

**快速替代方案**：直接从本地 SQLite 数据库读取已缓存的日线数据，只做 PE 通道计算 + 画图，单只耗时 ~1 秒。参考 `references/simplified-valuation.md` 获取实现。
