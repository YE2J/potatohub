---
name: a-stock-valuation
description: A股智能估值引擎；根据股票所属行业自动选择最合适的估值模型（银行→PB、科技→DCF+PEG、消费→PE+PEG等），基于akshare获取财务数据，输出自有估值区间和关键假设
dependency:
  python:
    - akshare>=1.18.13
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

1. **行业识别**：通过akshare获取股票所属申万行业分类
2. **模型选择**：根据行业特征自动匹配估值模型（银行→PB、科技→DCF+PEG等）
3. **财务数据获取**：获取资产负债表、利润表、现金流量表
4. **估值计算**：执行选定模型的估值计算
5. **结果输出**：生成结构化估值报告

## 操作步骤

### 标准流程

1. 识别行业 → 调用 `scripts/industry_mapper.py --stock-code <代码>`
2. 获取财务数据 → 调用 `scripts/get_financials.py <代码>`
3. 执行估值计算 → 调用 `scripts/calculate_valuation.py <代码> --model auto`
4. 生成估值报告 → 输出结构化结果

### 行业→估值模型映射

| 行业 | 首选模型 | 辅助模型 | 关键参数 |
|------|---------|---------|---------|
| 银行 | PB | 股息率+RORE | 不良率、拨备覆盖率 |
| 保险 | PB | 内含价值倍数 | 新业务价值 |
| 科技/互联网 | DCF | PEG+PS | 研发占比、用户增速 |
| 消费/食品饮料 | PE | PEG+EV/EBITDA | 品牌溢价、同店增速 |
| 周期/资源 | PB | 周期调整PE | 商品价格、产能利用率 |
| 医药/生物科技 | DCF | 峰值销售额折现 | 管线进度、获批概率 |
| 房地产 | NAV | PB | 土储货值、去化率 |
| 公用事业 | DDM | PB | 利用率、电价/水价 |
| 制造业 | PE | EV/EBITDA | 订单增速、毛利率 |
| 新能源 | PEG | DCF | 装机量、渗透率 |

## 使用示例

```bash
# 在Hermes对话中
估值分析 贵州茅台 600519

# 或直接调用脚本
python scripts/industry_mapper.py --stock-code 600519
python scripts/calculate_valuation.py 600519 --model auto
```

## 注意事项

- 估值结果仅供参考，不构成投资建议
- akshare接口依赖网络爬虫，可能不稳定
- 模型参数（WACC、永续增长率等）可在 `references/industry_model_config.json` 中调整
- 估值区间基于保守假设，实际市场定价可能偏离
