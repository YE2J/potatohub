---
name: a-share-research
description: "A股机构研报收集：通过Tushare MCP获取券商研报、评级、业绩预测，通过同花顺问财API获取机构研究数据。覆盖个股研报、行业研报、券商金股、评级变化追踪。"
version: 1.0.0
tags: [a-share, research-report, 研报, 券商, 评级, broker, tushare]
---

# A股机构研报收集与分析

## 触发条件

当用户提到：研报、券商研报、机构研报、评级、目标价、券商金股、业绩预测、研究报告、research report、分析师 等。

## 两大数据源

| 数据源 | 接口 | 覆盖范围 | 数据特点 |
|--------|------|---------|---------|
| **Tushare MCP** | `research_report` | 2017年起全市场个股+行业研报 | 标题+摘要+URL，结构化评级 |
| **Tushare MCP** | `report_rc` | 2010年起券商盈利预测 | EPS/PE/ROE预测+目标价+评级 |
| **同花顺问财** | web_extract | 最新研报（实时性更好） | 最新摘要、评级变化、热门研报 |

---

## 一、Tushare 研报查询

### 1.1 个股研报搜索 (`research_report`)

**参数**：
- `ts_code`: 股票代码（如 `000988.SZ`）
- `start_date` / `end_date`: 日期范围 (YYYYMMDD)
- `report_type`: `个股研报` 或 `行业研报`
- `inst_csname`: 券商名称（可选，如"中信证券"）

**默认返回字段**：`trade_date, abstr, title, report_type, author, name, ts_code, inst_csname, ind_name, url`

```python
# 示例：获取华工科技近3个月研报
mcp_tushareMcp_research_report(
    ts_code="000988.SZ",
    start_date="20260301",
    end_date="20260616",
    report_type="个股研报"
)
```

### 1.2 盈利预测数据 (`report_rc`)

**参数**：
- `ts_code`: 股票代码
- `start_date` / `end_date`: 报告日期范围

**默认返回字段**：`ts_code, name, report_date, report_title, report_type, classify, org_name, author_name, quarter, op_rt, op_pr, tp, np, eps, pe, rd, roe, ev_ebitda, rating, max_price, min_price`

关键字段说明：
- `rating`: 评级（买入/增持/中性/减持/卖出）
- `tp`: 目标价（元）
- `eps`: 预测EPS
- `pe`: 预测PE
- `max_price` / `min_price`: 目标价区间

---

## 二、同花顺问财 研报搜索

当 Tushare 数据不够新时，通过问财网站补充：

**搜索 URL 模式**：
```
https://www.iwencai.com/unifiedwap/result?w={股票代码}+研报&querytype=stock
```

**提取方法**：
1. `web_extract` 获取问财搜索结果
2. 或 `browser_navigate` + `browser_snapshot` 获取详细内容
3. 提取评级、目标价、券商名称、报告摘要

---

## 三、常用查询场景

### 场景1：某股最新研报汇总

```
1. 调用 research_report (Tushare) → 获取近3个月研报列表
2. 调用 report_rc (Tushare) → 获取最新盈利预测
3. 按券商/日期排序，提取评级变化
4. 汇总：总研报数、买入/增持/中性比例、一致目标价
```

### 场景2：评级变化追踪

```
1. 获取历史上对该股的所有研报
2. 按券商分组，追踪评级变化时间线
3. 标记：上调（中性→买入）、下调（买入→中性）、首次覆盖
4. 输出评级变化图表/列表
```

### 场景3：券商金股

```
1. 调用 broker_recommend (Tushare) → 按月获取券商金股
2. 参数：month="202606"
3. 统计：最热门的推荐股票、最活跃的券商
```

### 场景4：行业研报

```
1. 调用 research_report，report_type="行业研报"
2. 按 ind_name 筛选
3. 获取行业评级、核心观点
```

---

## 四、输出格式

### 个股研报汇总

```markdown
## 研报汇总：[股票名称/代码]

### 近3个月研报概览
- 总研报数：12篇
- 买入/增持/中性：8/3/1
- 一致目标价：¥35.20（当前价 ¥25.00，上行空间 +40.8%）

### 最新研报（Top 5）
| 日期 | 券商 | 评级 | 目标价 | 核心观点 |
|------|------|------|--------|---------|
| 2026-06-10 | 中信证券 | 买入 | ¥38.00 | Q2业绩超预期... |
| 2026-06-05 | 华泰证券 | 增持 | ¥34.00 | 行业景气度回升... |
| ... | ... | ... | ... | ... |

### 评级变化
- 📈 中信证券：中性 → 买入（2026-05-15）
- 📉 国泰君安：买入 → 增持（2026-04-20）

### 一致预期
| 指标 | 2026E | 2027E | YoY |
|------|-------|-------|-----|
| EPS | ¥1.45 | ¥1.78 | +22.8% |
| PE | 17.2x | 14.0x | — |
| ROE | 15.2% | 16.8% | +1.6pp |
```

---

## 五、如何选择数据源

| 需求 | 推荐源 | 原因 |
|------|--------|------|
| 历史研报（2017年前） | Tushare `research_report` | 覆盖全、结构化 |
| 盈利预测/目标价 | Tushare `report_rc` | 量化数据直接可用 |
| 最新研报（本周） | 问财 web_extract | 实时性更好 |
| 券商金股 | Tushare `broker_recommend` | 月度汇总 |
| 行业研报 | Tushare `research_report` (行业) | 按行业筛选 |

---

## 六、注意事项

1. **Tushare `research_report` 每天更新两次**（盘中+盘后），最新研报可能有半天延迟
2. **评级术语不统一**：不同券商用"买入/推荐/强推"，统一映射为：买入/增持/中性/减持/卖出
3. **目标价≠预测价**：券商目标价通常比当前价高20-30%，是乐观预期，需打折参考
4. **看多偏见**：A股研报中买入+增持占比通常>80%，独立判断更重要
5. **首次覆盖研报价值更高**：首次覆盖往往包含深度行业+公司分析

## 七、相关资源

- `iwencai-skillhub` Skill — 已安装 `hithink-management-query`（股本/股东/高管查询，需 IWENCAI_API_KEY）
- `a-share-quant-backtest` Skill — 回测系统的策略指标和数据管线
- `a-share-valuation` Skill — 估值框架，与研报评级交叉验证
