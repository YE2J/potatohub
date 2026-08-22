# 恒生聚源一致预期数据管线（经扣子平台）

> 状态: 2026-08-17 首采成功。数据源=恒生聚源A股数据库（StarRocks），通过扣子（Coze）平台 SQL 查询聚合，绕开 Tushare 积分门槛获取券商一致预期/评级/盈利预测数据。

## 数据源能力（摸底结论）

| 表 | 内容 | 关键字段 |
|:---|:----|:--------|
| c_rr_researchreport | 研报元数据（标题/日期/结论摘要/行业分类） | OrgName, IndustrySW, Conclusion |
| c_ex_stock + c_ex_targetprice | 个股评级 + 机构目标价 | 买入/增持/中性/减持/卖出, 目标价 |
| c_ex_proforstat + c_ex_datastockderivative | **一致预期**（盈利预测汇总） | EPS均值/中位/最大/最小/标准差, 预测机构家数, 净利润预测均值/增长率, ROE预测, PE/PB/PEG预测 |

- 收录范围：2005年至今，日更新（EndDate 截止日期 + WritingDate 最新报告撰写日期）
- 券商覆盖：80-120家量级（中信/中金/华泰/国君/申万宏源/海通/广发...）
- 覆盖个股：约3000-4000只（有机构覆盖的A股）
- 申万行业：c_rr_researchreport.IndustrySW 关联 CT_IndustryType（Standard=38，申万一级31个）
- 合规红线：研报结论不能直接引用原文，只能保留原义总结 → **我们只取统计数字，不碰原文**

## 提问模板（可一键复制给扣子）

硬性要求前缀：
```
所有数字必须用SQL实跑，禁止估算、禁止编造；查不到标注"查不到"；
输出表格带数据截止日期、字段单位、行业代码+名称；不需要研报原文引用。
```

- A组：31行业一致预期快照（预测净利润/增速YOY/ROE/PE/PB/机构家数/覆盖股数）+ 覆盖度
- B组：近1月上调/下调家数 + 近3月增速变化 + 机构家数变化（**拐点信号核心**）
- C组：行业评级分布 + 近1月评级上调个股 + 近3月首次覆盖个股
- D组：低估+拐点共振（PE分位<40% 且 净上调>0）+ 未来12个月增速Top15 + 龙头个股
- E组：SQL 模板固化可行性 + 推荐表结构（每日增量 UPSERT）

## 三层真实性验证（入库前必做，防LLM编造）

| 层 | 方法 | 通过标准 |
|:--|:----|:--------|
| 1. 现价比对 | 返回的龙头股"现价" vs 本地 daily_kline 同日收盘价 | 抽查12只全中（精确到分） |
| 2. PE/PB 自洽 | Tushare daily_basic 个股 PE/PB vs 数据库行业加权 | 权重股吻合、加权逻辑自洽 |
| 3. 机构覆盖 | Tushare report_rc 年内去重机构数 vs 数据库"预测机构数" | 前者≥后者（年内全量 ≥ 当前快照） |

> 现价是**最硬核锚点**——LLM 编不出12只股票精确到分的真实收盘价。每次扣子返回新数据都抽5只现价复核。

## 已发现的口径坑

1. **t层增速缺失**：2026预测年度(t层) NPYOY/IncomeGR 有值率0%，增速须用 t+1层(2027) NPYOY 按预测净利润加权，且表结构要显式区分 forecast_year
2. **PE分位仅2年**：恒生聚源估值历史只覆盖~2年 → 5年分位不可得，降级2年分位；P1 必须用 sw_daily+index_dailybasic 自建5年+分位
3. **C3 首次覆盖数字异常**："新增首次覆盖 6586 只"远超 A股总数(~5600) → 是**评级事件数**非个股数（同一股票被多家券商首次覆盖重复计数），需 COUNT(DISTINCT InnerCode) 重跑
4. **B3 机构覆盖收缩**：中报季特征（机构调整覆盖），对比须用**交集口径**（两时点都有的同一批股票），否则虚减
5. **卖方评级无卖空**：全市场减持/卖出占比=0% 是惯例，不是数据问题
6. **低基数失真**：亏损行业（房地产预测净利-224亿）的增速/ROE 失真（增速98%、ROE 56.86%），须剔除

## 入库模式

- 表：industry_consensus_daily / industry_updown_daily / industry_revision_3m / industry_rating_dist / industry_rating_flow（见 l2b-bottom-engine-design.md）
- 增量：每日定时触发，以最新 MAX(EndDate) 为 end_date，主键 UPSERT（end_date, forecast_year, industry_code），历史自动保留，单日秒级
- 断供 fallback：Tushare `report_rc` 可查原始研报记录（积分够），但需自行聚合；扣子断供时本地聚合替代 + 最近快照标 stale
- 数据质量防线：① 入库校验（行业数=31/PE范围/增速<500%）② 每日抽5只龙头现价复核 ③ 周度 Tushare 交叉

## 落地文件

- 回填脚本：`~/my_quant_system/scripts/backfill_l2b_coze_20260817.py`
- 映射脚本：`~/my_quant_system/scripts/build_sector_mapping.py`
- 建表：`~/my_quant_system/migrations/005_create_l2b_bottom_tables.sql`
