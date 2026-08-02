---
name: a-stock-valuation
description: A股智能估值引擎；根据股票所属行业自动选择最合适的估值模型（银行→PB、科技→DCF+PEG、消费→PE+PEG等），基于Tushare获取财务数据，输出自有估值区间和关键假设
dependency:
  python:
    - tushare>=2.0.0
    - pandas>=2.3.0
    - numpy>=2.0.0
---

# A股智能估值引擎

## 任务目标

本技能为A股上市公司提供行业自适应的估值分析：
- 自动识别股票所属行业
- 按行业特征选择最合适的估值模型
- 计算自有估值区间
- 输出关键假设和估值结论

## 核心能力

1. **行业识别**：通过 data_fetcher 多来源（问财/东方财富/Tushare stock_basic）获取股票所属行业分类
2. **模型选择**：根据行业特征自动匹配估值模型（银行→PB、科技→DCF+PEG等）
3. **财务数据获取**：通过 Tushare 获取资产负债表、利润表、现金流量表
4. **估值计算**：执行选定模型的估值计算
5. **结果输出**：生成结构化估值报告

## 操作步骤

### 标准流程

1. 识别行业 → 调用 `scripts/industry_mapper.py --stock-code <代码>`
2. 获取财务数据 → 调用 `scripts/get_financials.py <代码>`
3. 执行估值计算 → 调用 `scripts/calculate_valuation.py <代码> --model auto`
4. 生成估值报告 → 输出结构化结果

### 行业→估值模型映射（申万一级行业）

| 申万行业 | 首选模型 | 辅助模型 | 关键参数 |
|----------|---------|---------|---------|
| 银行 | PB | DDM | 不良率、拨备覆盖率、ROE |
| 食品饮料 | PE | PEG | 品牌溢价、渠道库存、提价能力 |
| 医药生物 | DCF | PE | 管线进度、获批概率、专利悬崖 |
| 电力设备 | EV/EBITDA | PE | 订单增速、产能利用率、招标价格 |
| 电子 | PE | PEG | 研发占比、新品周期、客户集中度 |
| 计算机 | PE | PS | 云化比例、ARR增速、客户留存率 |
| 其他/通用制造业 | PE | EV/EBITDA + PEG | 订单增速、毛利率趋势、行业景气 |

> 此映射基于 2026-06-17 用户指定规则，优先以申万一级行业匹配上述 7 类，
> 不在表中的行业走「其他/通用制造业」兜底。

## 使用示例

```bash
# 在Hermes对话中
估值分析 贵州茅台 600519

# 或直接调用脚本
python scripts/industry_mapper.py --stock-code 600519
python scripts/calculate_valuation.py 600519 --model auto
```

## 数据获取

数据源优先级（按降级链排列）：

```
① Tushare `income` / `balancesheet` / `cashflow` — ✅ 首选，5000积分全量可用
② Tushare `fina_indicator` — 财务指标（ROE/毛利率/净利率），一次性取全
③ Tushare `daily_basic` — 日估值指标（PE/PB/PS/市值/换手率）
④ 腾讯行情 API（qt.gtimg.cn）— 行情/PE/PB/市值，无频率限制
⑤ 本地 JSON 缓存（Hermes 预拉）— 离线可用，秒级
⑥ 问财 OpenAPI — 备用（当日更新，无反爬）
```

> **2026-07-02**：数据源已全面切换至 Tushare。`data_fetcher.py` 内建实时降级链：
> ① 问财缓存 → ② 腾讯 API → ③ Tushare → ④ 兜底默认值。

### 问财 OHLCV 批量拉取

详见 `references/web-app-pitfalls.md` 和 iwencai-skillhub 的 `references/iwencai-ohlcv.md`。

> **2026-07-02 更新**：数据源已全面切换到 Tushare（`income`/`balancesheet`/`cashflow`/`fina_indicator`/`daily_basic`/`stock_basic`），
> `data_fetcher.py` 内建实时降级链。不再依赖 Hermes 预拉 JSON 缓存作为主要财务数据源。

### 当前数据链路（data_fetcher.py）

```
行情数据（价格/PE/PB/市值/名称）:
  ① 问财 JSON 缓存
  ② 腾讯 qt.gtimg.cn API（稳定、无反爬、无频率限制）
  ③ 东方财富 JSON 缓存（残存）
  ④ Tushare daily（降级兜底）

财务数据（营收/净利/ROE/负债率）:
  ① Hermes 生成的财务三表 JSON
  ② Tushare fina_indicator + income + balancesheet（✅ 新首选）
  ③ 兜底默认值

行业分类:
  ① 问财 JSON（含 sw_l1，优先且直接）
  ② 东方财富 industry JSON（申万二级，需 SW_LEVEL2_TO_LEVEL1 映射）
  ③ Tushare stock_basic（industry 字段，稳定兜底）
  ④ 返回"未知"
```

### 腾讯 API 格式参考

`https://qt.gtimg.cn/q=sh600519` 返回 `~` 分隔字段：
- 字段 1: 名称, 3: 现价, 32: 涨跌幅%, 38: 换手率%, 39: PE(TTM), 44: 流通市值(亿), 45: 总市值(亿), 46: PB

### Tushare 财务数据注意事项

- 财务数据单位是**元**（与 akshare 不同，akshare 带"万/亿"后缀），无需 `_parse_cn_amount()` 转换
- `fina_indicator` 中 ROE/毛利率/净利率是**百分比值**（15.2 表示 15.2%），需除以 100
- 优先取年报（end_date 以 1231 结尾），季报数据不完整不适合估值
- `daily_basic` 接口**1次/小时**限频（非分钟级），调用前注意确认额度
- `stock_basic` 行业字段包含申万一级行业名称，可直接用于模型匹配

### Tushare 常见调用陷阱

| 陷阱 | 表现 | 修复 |
|------|------|------|
| **限频429** | 连续API调用过快被Tushare拒绝 | 每次调用间加 `time.sleep(1.1)`，5000积分限频500次/分钟 |
| **北交所后缀** | 8xxxxx/4xxxxx 被映射成 .SZ 返回空数据 | `_ts_code()` 中先判断前2位：`startswith(('8','4'))` → .BJ |
| **period不筛选年报** | annual分支不过滤end_date=1231，拿到混合报告期 | 加 `df[df['end_date'].astype(str).str.endswith('1231')]` |
| **fina_indicator上限** | 单次最多100条，多年数据被截断 | 按年分多次请求，或加注释标注限制 |
| **派生ROE覆盖官方ROE** | 自己算的ROE覆盖了Tushare返回的 fina_indicator.roe | 优先用官方值，仅当为None时才用派生值 |
| **行业一级vs二级混淆** | Tushare返回申万一级名（食品饮料），而降级链可能返回二级名（白酒Ⅱ） | 映射字典中为每个一级行业加上自映射 |

### 已知坑点

- **东财 push2 不可用**（2026-06-11 验证）：部分网络环境阻断，不要依赖 push2 数据源
- 问财 OpenAPI 返回的字段名是**中文 key**（如 `最新市盈率ttm`、`总市值[20260616]`），不是英文，取值时注意 key 匹配
- 问财 API 响应数据在 **`datas`** 键下（复数），不是 `data`。股票代码带 `.SZ`/`.SH` 后缀需剥离
- 同花顺行业字段 `所属同花顺行业` 是三级数组 `["一级","二级","三级"]`
- 腾讯 API 返回 GBK 编码，ETF 名称会乱码，不适合写入 SQLite
- K 线接口（`push2his`）最稳定，`web_extract` 几乎总能拿到
- 报价接口（`push2`）不稳定，特定股票可能被"拉黑"（持续 502），直接降级到搜狐
- 行业接口（`push2` fields=f127,f128,f129）**不可用**，改用申万分类多源验证
- 搜狐备用：`https://q.stock.sohu.com/cn/{CODE}/index.shtml`，一次拿到 PE/市值/EV/ROE 等全套
- **Tushare 限频**：`stock_basic` 1次/分钟，`daily_basic` **1次/小时**（非分钟！）—— 调用前务必确认额度
- `data_fetcher.py` 保留了 `_parse_cn_amount()` 和 `_parse_pct()` 函数，用于处理**历史 JSON 缓存**中可能包含的中文后缀字段；新数据来自 Tushare（纯数字元单位）无需这些转换
- 原始数据统一缓存到 `data/` 目录
- **不要反复重试同一工具/同一参数**：502 意味着该股票路由到了故障后端，换数据源比换工具更有效
- **行业分类不走 push2 的 f127/f128/f129**：该接口已确认不可靠，直接用申万分类体系

> **Tushare 财务数据搭建细节见** `references/tushare-financial-fetching.md`（限频退避、年报过滤、北交所后缀、ROE优先级等已验证模式）

## 批量估值

### 批量脚本

`~/my_quant_system/scripts/batch_valuation.py`（Coze 编写，Hermes 部署）：
- 支持全量：`python batch_valuation.py`
- 支持单只/多只：`python batch_valuation.py 600519,000988`
- 仅处理 `group_id='default'` 的股票
- 逐只调用 `calculate_valuation.py --model auto --json --output /tmp/_val_*.json`
- 结果写入 `valuation_results` 表（带时间戳和 `primary_model` 字段）

### 调度

Hermes Cron 管理，非系统 crontab/launchd：
- `hermes cronjob list` 查看所有定时任务
- 每周日 0:00 全量估值（cron job `5f20a2f80e20`）
- 手动触发：在 Hermes 说「估值 600519」或用 `terminal` 跑 `batch_valuation.py`

### 注意事项

- batch 脚本在 `valuation_results` 表写入了 `primary_model` 列（2026-06-17 新增）
- 估值结果偏保守：PE 模型默认 15x 地板 PE，无增长率数据时价值偏低
- 存量 watchlist 中 88 只缺名称（仅代码），首次跑估值时腾讯 API 会自动补充名称
- **Web 服务参考**：`references/web-app-ops.md`（FastAPI 启动/重启/500 修复/旧进程占端口）

### Web 服务快速参考

量化系统 Web 仪表盘：`http://127.0.0.1:8001`

```bash
# 启动（务必 PYTHONDONTWRITEBYTECODE=1 + reload=False）
cd ~/my_quant_system && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -c "
import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=8001, reload=False)"

# 重启：先杀旧进程再清缓存再启动（旧进程占端口是新进程静默失败的头号原因）
kill -9 $(lsof -ti:8001) && sleep 1
find ~/my_quant_system -name __pycache__ -exec rm -rf {} +
lsof -i:8001 2>/dev/null || echo "端口干净"
```

> **分组切换**：侧边栏始终传全量 `groups`，内容区用 `display_groups`。切换走 `location.href` 触发服务端重渲染，**禁止 `loadStocks()` 在 DOMContentLoaded 中覆盖服务端数据**（会导致所有股票显示「暂无行情」）。
>
> **排障参考**：`references/web-app-pitfalls.md`（JS 覆盖/SQLite 未同步/ETF 乱码/端口占用/行情补齐 SOP）。
