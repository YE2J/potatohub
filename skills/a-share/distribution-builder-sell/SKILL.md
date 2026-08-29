---
name: distribution-builder-sell
description: Use when 用户要做A股卖出/止盈时点决策。用 Azéma-Yor barrier 从目标分布反推卖出触发。
author: Hermes Agent
license: MIT
version: 1.0.0
metadata:
  hermes:
    tags: [a-share, sell-signal, optimal-stopping, distribution-builder, azema-yor]
    related_skills: [a-share-buy-sell-case-analysis, tuige-shortline-trading, a-stock-valuation, a-share-strategy-research-flow]
---

# Distribution Builder 卖出决策

## When to Use
- 用户问"什么时候卖出这只股票/这个指数持仓？"
- 用户想设定止盈目标分布而非固定百分比止盈
- 用户有持仓，想知道当前价格、波动率下的最优卖出触发条件
- 需要量化"目标收益 vs 等待时间 vs 风险"权衡

## 论文依据
Carr & Sturm (2026), "When to Sell an Asset? – A Distribution Builder Approach", arXiv:2608.18783。
核心：不指定效用函数，而是让投资者指定**目标卖出分布 F**，通过 Skorokhod embedding（Azéma-Yor barrier）构造停止时间 τ，使 X_τ ~ F。

## 核心算法（GBM 情形）

### 参数
- x: 当前价格（X0）
- μ: 年化漂移（用历史日收益均值 × 252）
- r: 折现率（无风险利率）
- σ: 年化波动率（历史日收益 std × √252）
- F: 目标分布（论文支持 Log-normal / Pareto / Weibull / Gamma）

### 关键常数
```
A = 1 - 2(μ - r) / σ²
```

### 三个 regime（定理 3.2）
| 条件 | A | 含义 |
|------|---|------|
| μ-r ≥ σ²/2 | A ≤ 0 | 超可达：任何分布都可达，无卖出约束 |
| 0 < μ-r < σ²/2 | 0 < A < 1 | **有趣区**：可赚风险溢价（目标均值 m > x） |
| μ ≤ r | A ≥ 1 | 均值下降区：仅 m ≤ x 可达，应尽快卖 |

### 可达性条件（定理 3.1）
```
∫(z/x)^A F(dz) ≤ 1    （等号 = 最优分布）
```

### Log-normal 目标 LN(b, a²)
- 可达性: `b ≤ log(x) - A·a²/2`
- **Barrier 闭式解**:
```
Ψ(z) = [ Φ((b-log z)/a + aA) / Φ((b-log z)/a) ]^(1/A) · exp(b + a²·A/2)
```
- 停止时间: `τ = inf{t : M_t ≥ Ψ(X_t)}`，其中 M_t = 运行最大值
- 预期卖出时间: `E[τ] = 2(log x - b) / (σ² - 2(μ-r))`

### 参数族闭式解（论文 3.4 节）
| 分布 | 可达条件 | Barrier |
|------|---------|---------|
| Log-normal LN(b,a²) | b ≤ log x - Aa²/2 | 上式闭式解 |
| Pareto(x0,p) | (p/(p-A))(x0/x)^A ≤ 1 | 论文 Eq. (10) 附近 |
| Weibull(k,λ) | 需数值求解积分 | 数值 barrier |

## 实现步骤
1. 从数据库读历史日收益（`daily_kline` 或 `index_daily`），估计 μ, σ
2. 用户指定目标分布参数（或自动扫描 m 目标溢价）
3. 检查 regime 和可达性；不可达则提示降低目标或调整参数
4. 预计算 barrier 网格（查表插值，2000 点足够）
5. 蒙特卡洛模拟 GBM 路径 + barrier 停止，统计卖出分布
6. 验证：KS 检验 卖出分布 vs 目标分布；比较实际均值/溢价/等待时间

## 参考实现
PoC 脚本：`~/.hermes/scripts/poc1_distribution_builder.py`（真实数据）
`~/.hermes/scripts/poc1b_theory_check.py`（理论正确性验证）

```python
# barrier 闭式解（Log-normal 目标）
from scipy import stats
def barrier(z, b, a, A):
    num = stats.norm.cdf((b - np.log(z))/a + a*A)
    den = stats.norm.cdf((b - np.log(z))/a)
    return (num/den)**(1/A) * np.exp(b + a**2*A/2)
# 停止: 模拟路径中 M_t ≥ Ψ(X_t) 时卖出
```

## 验证结果（2026-08-23 实测）
- 有趣区 A=0.18 / 0.50：卖出分布 vs 目标 LN，KS≈0.034，分位数吻合（10/50/90 误差 <8%）
- 卖出均值 > 目标均值（super-attainable 理论成立）
- 风险-收益权衡：目标溢价 5%→30%，实际卖出均值递增、等待时间递增（Markowitz 式有效前沿）
- A≈0.85 组偏差大：因理论 E[τ]=38 年 >> 模拟窗 15 年（horizon 截断），非算法错误
- 超可达区（A<0）：沪深300 20年数据，实际溢价 96% vs 目标 128%（可超可达）

## Pitfalls
1. **regime 判断先行**：A≤0（超可达区）时 barrier 公式的 (·)^(1/A) 数值不稳定，目标均值会爆炸（如 b_max 算出千万级），必须先检查 regime
2. **b_max 不是目标**：b 取 b_max - 0.05 左右留裕量，严格可达
3. **horizon 截断**：理论 E[τ] 远超模拟年限时，分布尾部失真（KS 会差）；模拟年限至少 1.5×E[τ]
4. **查表插值**：barrier 是单调函数，用 bisect 查表（3000 点）比逐点算快 100×
5. **数据长度**：个股库内仅 ~165 天时 μ,σ 估计不稳；优先用指数（沪深300 有 20 年）或 Tushare 拉全历史
6. **折现率 r**：论文中 r 是卖家的时间偏好，不等同无风险利率；调 r 可改变 regime

## 与现有系统衔接
- 输入：自选股/持仓的日线（`daily_kline`），输出：目标溢价对应的 barrier 表 + 当前价相对 barrier 的位置
- 可嵌入 L3 决策融合作为卖出触发补充（当前系统只有买入/持有逻辑）
- 与 `a-share-buy-sell-case-analysis` 的区别：后者是案例分析框架，本 skill 是数值化卖出时点