---
name: minerva-backtest-robustness
description: Use when 用户要对量化策略回测/参数格点搜索结果做稳健性评级与0-100打分。五门(DSR/PBO/SPA/MinTRL/regime)→Seal封印。
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [backtest, robustness, dsr, pbo, spa, mintrl, overfitting, multiple-testing, minerva, seal]
metadata:
  hermes:
    tags: [backtest, robustness, dsr, pbo, spa, mintrl, overfitting, multiple-testing, minerva, seal]
    category: a-share
    related_skills: [a-share-strategy-research-flow, a-share-factor-ic-evaluation, quant-alpha-factory, a-share-backtesting, nonparametric-var]
---

# MinervaScore — 策略回测稳健性评级（Luck or Edge?）

选后验证层：把 DSR（Deflated Sharpe Ratio）、PBO（Probability of Backtest Overfitting）、SPA（Superior Predictive Ability）、MinTRL（Minimum Track Record Length）+ 自研 regime 稳定性诊断，合成 0–100 评分与二元 **Robustness Seal（稳健性封印）**。**度量的是回测结果的统计支持强度，不是未来盈利概率**——论文自己在真实市场预注册检验中得到 null 结果。

## 论文依据
"Equity Strategy Backtesting: Luck or Edge? The MinervaScore as a Statistical Robustness Grade"，Santoni/Jouanne/Scullin（Minerva, Minerva1.com），arXiv:2608.23808v2 [q-fin.ST]，2026-08-26。本地全文：`~/paper_library/q-fin/2608.23808/paper.md`（正文从约第 50 行起）。

## When to Use
- 用户在等分回测 / 参数格点搜索 / 推进分析得到"最优策略"后，想判断该回测结果是真 edge 还是搜索运气，再决定是否投入
- 用户要体检历史策略档案，比较不同策略的统计支撑强度并排序
- 注意 ⚠️：本评分**只做选后认证与排序**，绝不能喂回搜索循环当优化目标（论文 §9.1：validator 被搜索盯上就不再可信，Goodhart 风险）

## 核心思想（三阶段）
1. **五门判定**：每个候选与五个准入阈值比较 → Seal（AND 关系）
2. **带符号边际**：每门取"观测值 − 阈值"的距离，在**能让该门保持信息量的尺度**上标准化（DSR 用 pre-Φ 统计量 u；有界量 PBO/SPA/ρ 用 logit；MinTRL 用 tanh）
3. **相关调整加权聚合** → raw score r ∈ [0,1] → 0–100 两段显示（80 以上仅授予 Seal 通过者）

## 1) 五维评分卡与 Seal
```
Seal = [ DSR ≥ 0.95 ∧ PBO ≤ 0.50 ∧ SPA ≤ 0.10 ∧ T ≥ MinTRL ∧ ρ ≥ 0.60 ]
```
（论文 Eq.2；τ_DSR=0.95, τ_PBO=0.50, τ_SPA=0.10, τ_ρ=0.60。SPA 取 0.10 比学界 0.05 宽松，论文明说更严的 operator 可改 0.05 不影响结构）

| 门 | 控制什么失败模式 | 通过条件 | 输入 |
|---|---|---|---|
| DSR | **选择运气**：考虑了试过 N 个候选后的选后膨胀 + 非正态收益 | DSR ≥ 0.95 ⟺ u ≥ Φ⁻¹(0.95)=1.645 | 冠军的年化 SR̂、试验数 N、收益偏度/峰度 |
| PBO | **选择不稳定**：IS 冠军在 OOS 常掉到同族中位以下 | PBO ≤ 0.50 | candidate×fold 表现矩阵（CSCV） |
| SPA | **基准运气**：考虑依赖性与重复比较后仍优于基准 | p ≤ 0.10 | 冠军 vs 基准的损失差序列（block bootstrap） |
| MinTRL | **证据长度**：现有 track record 是否够支撑观测 SR | T ≥ MinTRL（α=0.05） | 每 bar SR、偏度、峰度、历史长度 |
| Regime ρ | **regime 依赖**：证据是否集中于单一市场状态 | ρ ≥ 0.60 | 各验证窗口的 SR |

**DSR 门要点**（论文 §3/§5/§6.6）：
- DSR=Φ(u)，u=(SR̂−SR₀)/sê。通货基准 = **Lo null sampling variance Var(SR̂)=1/years**（年化单位，等价每 bar 1/T）——这是论文在合成实验中验证后采纳的修正（AUROC 0.9855→0.9894；DSR 门对纯噪声假阳性保持为 0，真信号检出率 1%→41%）。旧实现用固定 Var=1（相当于假设 1 年历史，长历史会被系统性过度打折，DSR 边际随 T 漂到 −7.5）⚠️
- 试验数 N 用**有效独立试验数**：对搜索的参数向量做特征值去相关估计，不是原始格点个数（近似，论文 §9.6 承认）
- 修正后门槛量级参考（N=100 试验）：5 年历史需年化 SR≈1.9，10 年≈1.3（旧固定常数 ≈3）
- **必须持久化 pre-Φ 统计量 u**。60–95% 的生产 DSR 恰为 0.0（u≲−8 时 Φ 浮点下溢）；从 DSR=Φ(u) 反推 u 会把所有强过拟合策略压到 Φ⁻¹(ε)≈−4.75，饱和回归。**u 缺失 → 不出分（fail-closed）**，不许用近似顶替（论文 §4.2）
- 序列相关不在 DSR 门内修正：用 i.i.d. Mertens 方差调整（含偏度峰度）；HAC/Newey-West Sharpe 只作审计字段不进门（论文 §9.6 限制 7）⚠️ 分钟级高频 A股 序列相关强，留意

**MinTRL 公式**（论文 Eq.1，Bailey & López de Prado 2012；SR 为**每 bar** 值，γ₃=偏度，γ₄=原始峰度，α=0.05）：
```
MinTRL = 1 + ( 1 − γ₃·SR + ((γ₄−1)/4)·SR² ) · ( Φ⁻¹(1−α) / SR )²
```
- MinTRL 只看单策略性质，与试验数 N 无关；勿与 MinBTL（≈2lnN/E[max]²，含多重检验）混淆
- 门条件 T ≥ MinTRL，T = track record 长度（bars）

**Regime 门公式**（论文 Eq.3，自研、最 ad hoc 的一门）：
```
ρ = 0.5·p₊ + 0.3·clip[0,1](1 − s_SR/σ_ref) + 0.2·logistic(SR_min)
σ_ref = 2（固定参考尺度）;  logistic(x) = 1/(1+e⁻ˣ);  结果 clip 到 [0,1]
```
p₊=SR>0 的窗口占比；s_SR=窗口间 SR 标准差；SR_min=窗口最小 SR。0.5/0.3/0.2 为**启发式子权重**，论文承认是框架最主观部件，且对 80–100 区间影响不成比例（名义权重 0.10，理论完美点贡献 39.2%）⚠️

**Evidence floor（证据地板，不是第 6 门）**：交易数太少 / 独立候选太少 / 验证窗口太少 → 单独 flag "证据不足"；不进连续分、不得展示为"统计认证"，但区别于"证据够却失败"。表 6 中全指数共享参数的 universe-mode 候选 2 年只交易 9–15 次 → 全部按"证据不足"报告而非失败。

## 2) 符号化边际（两尺度，论文 §4.2）
| 门 | 边际 | 阈值（同尺度） | 冻结 σ（论文表 3） |
|---|---|---|---|
| DSR | z_DSR = (u − 1.645) / σ_DSR | Φ⁻¹(0.95)=1.645 | σ_DSR = 1.128（pooled IQR/1.349） |
| PBO | z_PBO = (logit(0.50) − logit(g)) / σ_PBO | logit(0.50)=0 | σ_PBO = 10.028 |
| SPA | z_SPA = (logit(0.10) − logit(g)) / σ_SPA | logit(0.10)=−2.197 | σ_SPA = 6.013 |
| Regime | z_ρ = (logit(ρ) − logit(0.60)) / σ_ρ | logit(0.60)=0.405 | σ_ρ = 1.161 |
| MinTRL | z_T = tanh( (T − MinTRL) / σ_T )，σ_T = max(0.2·MinTRL, 50) | — | 无 σ_k（σ_T 内建） |

- logit 前把 p clamp 到 [ε, 1−ε]，**ε=10⁻⁶**，边界值有限（论文 Eq.5）
- **方向约定**：五门全部 z ≥ 0 ⟺ Seal 通过（Φ 与 logit 严格单调 → 只改带内排序，绝不动 Seal 判定）
- 语义：z=1 = 超过阈值一个总体 spread。**descriptive 而非推断**——z、S 都不是 null 下 N(0,1) 变量，无显著性解释（论文 §4.2/§3 反复强调）
- σ 估计是 **clamp-inclusive by design**：σ_PBO=10.028 是含退化点估计的。生产 14.4% 行 PBO=0（CSCV 组合数塌缩），ε-clamp 后 logit 边际 +13.8；大 σ 把它压到 ~+1.4σ 影响。若只在无 clamp 核心上估（σ≈1.1），退化点贡献 +12σ → 10% 行 raw≥0.98 饱和（论文 §5）⚠️⚠️ 实现时必须在**完整总体含边界值**上估 σ
- σ 是 population-relative：同一 ledger 按行 pool 得 1.128，按 run 加权得 0.63（DSR）。论文保留 pooled 行加权以维持跨版本可比。绝对分只在**同一校准 vintage** 内可比（§9.5：重新校准只改变带内排序与百分位显示，**不改变 Seal 判定**——Seal 只依赖阈值 τ，与 σ 无关）

## 3) 加权聚合 → raw score → 0–100（论文 §4.3–4.6）
```
S  = wᵀz / √(wᵀ·Σ_eff·w),     w = (0.35, 0.25, 0.20, 0.10, 0.10)   # DSR,PBO,SPA,MinTRL,Regime
r  = Φ(S − c),                 c = 0.5（operator default 保守偏移）
Display = ⌊D⌋：
  Seal 通过：D = min( 80 + 20·(r − r₀)/(r⋆ − r₀), 100 )          # [80,100] 区间线性映射
  Seal 失败：D = min( 80·F̂(r), 80 − δ ),  δ = 0.1                # F̂=冻结参考总体经验CDF
```
- Σ_eff：冻结的边际相关矩阵（winsorized-1% Pearson，论文表 4；全掩码分母 √(wᵀΣw)=**0.753**）。分母是固定归一化常数（≈单位尺度、方差稳定），**不是**合并相关检验的推断修正
- r₀ = Φ(−0.5) ≈ **0.3085** = 全边际为零（S=0）的 admissible 最低 raw；r⋆ ≈ **0.9997** = 每门到物理极限的完美策略
- F̂：355,214 条 uncertified 生产行，存成 81 个 1.25% 间隔的分位 knots，线性插值；**cap 必须存在**否则 F̂ 最高 knot 处失败者会得 80
- **构造级保证：Display ≥ 80 ⟺ Seal passed**（Eq.10，359,062 行零违例；失败者最高 79，sealed 82–100 中位 91）。分数带由二元 Seal 决定，连续量只排带内序——79→80 的小跳变是设计而非 bug
- 失败带解读：Display/0.8 ≈ 该策略 raw 分在参考总体中的百分位
- 缺失某门 → 权重在剩余 active 门上**重归一化**（Σ_eff 相应取子块 ⚠️ 论文未细说子块归一化公式，按 w 子块重归一 + 对应 Σ 子块实现）
- 存储 raw r + verdict，display 服务时重算 → 换 vintage 不用重写历史（论文 §4.6）
- 有效权重 ≠ 名义权重：DSR 名义 0.35 但总体平均绝对贡献 76.9%（pre-Φ 坐标能表达大跨度失败）；regime 名义 0.10 却在理论完美点贡献 39.2%（论文表 8）——别按名义权重解读贡献

## 实现步骤（用户自己的回测系统）
**前置纪律**：搜索必须已结束、冠军已定；本评分只用选后信息。输入清单：
1. 冠军策略的每 bar（日/周/月）**OOS 净收益**序列 → 每 bar SR、年化 SR̂、偏度 γ₃、原始峰度 γ₄、历史长度 T（bars/年数）
2. 试验数 N（格点搜索的格点数 / GA 评估数；有效 N 需参数向量去相关 ⚠️）
3. 参数格点 × 推进窗口的**表现矩阵 M**（每个参数在每个 walk-forward 窗口的绩效）→ PBO（CSCV）与 regime 窗口序列的输入
4. 基准同期序列（A股：沪深300/中证500）→ SPA
5. 参考总体 F̂（可选，仅做显示时需要）：用户自己的历史回测档案

步骤：
1. 算五门原值（DSR u、PBO、SPA p、T vs MinTRL、ρ）→ 判定 Seal 五项
2. 任一输入缺失 → 该门 fail-closed；证据不足 → 打 Evidence-floor flag
3. 算五条边际 z（冻结常数或自校常数，公式见上表）
4. S = wᵀz/√(wᵀΣ_eff w)；r = Φ(S−0.5)
5. （可选）显示分：用自己参考总体的 F̂
6. 输出：Seal 布尔 / display 分 / raw r / 五门原值+边际 / evidence floor / 缺失清单

```python
import numpy as np
from scipy import stats

EPS = 1e-6
def logit(p): p = np.clip(p, EPS, 1-EPS); return np.log(p/(1-p))

# 论文冻结常数（Minerva 生产人口，359,062 行）⚠️ 用于自己总体前建议重估并锁 vintage
SIGMA_K = np.array([1.128, 10.028, 6.013, 1.161])          # DSR,PBO,SPA,Regime（MinTRL 用 tanh 内建尺度）
PHI_INV_TAU = np.array([stats.norm.ppf(0.95), logit(0.50), logit(0.10), logit(0.60)])
# 论文表4: winsorized-1% Pearson 相关（DSR,PBO,SPA,MinTRL,Regime 顺序）
SIG_EFF = np.array([
 [1.00,0.23,0.32,0.71,0.25],[0.23,1.00,0.65,0.48,0.51],
 [0.32,0.65,1.00,0.57,0.60],[0.71,0.48,0.57,1.00,0.55],
 [0.25,0.51,0.60,0.55,1.00]])
W = np.array([0.35,0.25,0.20,0.10,0.10])

def mintrl(sr_per_bar, skew, kurt_raw, alpha=0.05):
    """论文 Eq.1；sr_per_bar=每bar Sharpe, kurt_raw=原始峰度γ4"""
    z = stats.norm.ppf(1-alpha)
    return 1 + (1 - skew*sr_per_bar + (kurt_raw-1)/4*sr_per_bar**2) * (z/sr_per_bar)**2

def z_margins(u_dsr, pbo, spa_p, rho, T_bars, mt):
    """mt=minTRL 预计算值；返回 5 维 z（DSR,PBO,SPA,MinTRL,Regime）"""
    return np.array([
        (u_dsr - PHI_INV_TAU[0]) / SIGMA_K[0],
        (PHI_INV_TAU[1] - logit(pbo)) / SIGMA_K[1],
        (PHI_INV_TAU[2] - logit(spa_p)) / SIGMA_K[2],
        np.tanh((T_bars - mt) / max(0.2*mt, 50)),
        (logit(rho) - PHI_INV_TAU[3]) / SIGMA_K[3]])

def raw_score(z, active=None, c=0.5):
    active = np.ones(5, bool) if active is None else np.asarray(active, bool)
    w = W[active]; w = w / w.sum()                       # 缺门时重归一 ⚠️
    S = w @ z[active] / np.sqrt(w @ SIG_EFF[np.ix_(active,active)] @ w)
    return stats.norm.cdf(S - c), S                      # (raw r, 聚合 S)

def seal(u_dsr, pbo, spa_p, T_bars, rho, mt):
    return bool(u_dsr >= stats.norm.ppf(0.95) and pbo <= 0.50
                and spa_p <= 0.10 and T_bars >= mt and rho >= 0.60)
```

## A股数据源映射（输入 → 来源）
| 输入 | 来源 | 备注 |
|---|---|---|
| 每 bar 收益/SR/偏度/峰度 | 用户回测引擎输出（SQLite stock_data.db 或回测日志），**净收益（含成本）** | 停牌/涨跌停模拟已在用户引擎处理 |
| 试验数 N | 格点搜索的配置数 / GA 评估数 | 有效 N 需参数去相关（⚠️ 近似，可先用格点总数并标注） |
| candidate×fold 矩阵 M | 用户 walk-forward / CPCV 格点搜索的 per-配置 × per-窗口绩效 | 只有单一 OOS 段则 **PBO 标"未计算"**，勿填默认值 |
| 基准序列 | tushare `index_daily`（000300.SH 沪深300 / 000905.SH 中证500）或东财 | SPA 的损失差序列 |
| 窗口 SR（regime） | 推进分析各灰框窗口的 SR | 窗口太少 → evidence floor |
| 参考总体 F̂ | 用户自己的历史格点搜索档案 | 显示层可选 |

## 验证方法（论文 §6/§8 复制为验收）
1. **合成真信号分离度（重，可选）**：按论文 §6.1 搭 ground-truth 环境——n=2000 个策略，每个是 n_trials~LogUniform(20,5000) 次候选的搜索冠军，S=10 个 CPCV fold，T=1260 根日 bar（5 年）；一半搜索含 1 个真信号候选（真实年化 SR~U(0.5,2.5)），另一半纯噪声；对冠军跑完整评分。验收（论文表 5，headline）：AUROC vs 真标签 ≈0.989，DSR-alone 0.988（近并列），GT-Score 代理 0.986，gates-passed 仅 0.960；ECE≈0.174（非校准概率）。用户自校 σ 后绝对 AUROC 会漂移，但应保持"高于 gates-passed 一大截、与 DSR-alone 同量级"
2. **行为方向检查（轻，推荐）**（论文 §6.4，量级供参照）：
   - 搜索规模每 ×10 → DSR 边际降 ≈0.7σ；纯噪声总体 median raw ≤0.011，任何搜索规模/历史长度下**纯噪声零 Seal**
   - 历史变长（修正 null 下）：噪声总体 DSR 边际基本恒定（−3.7→−4.2 跨 20×T），真信号从 −3.9 升到 +2.1（T=5040）；真信号 Seal 率 1y≈0% → 5y≈17% → 20y≈73%
3. **随机基线交叉（与 a-share-strategy-research-flow 步骤 5 复用）**：用用户现成的 permutation 随机基线总体跑同管线——对照其 raw 分位是否压底、是否零 Seal
4. **工程审计（论文 §8，轻量必做）**：(a) verdict-consistency：全档案 Display≥80 ⟺ Seal，零违例；(b) 不饱和：raw≥0.99 占比应极小（论文生产 0.002%）；(c) ±20% 权重扰动 Spearman≥0.997、offset 排序精确不变（论文表 7，可在自己数据上复算）

## Pitfalls
1. **统计支持 ≠ 盈利概率**：r=Φ(S−c) 看似概率，实为排序量（ECE 0.174，论文 §6.5 明示不要读成"有 edge 的概率"）。论文自己的预注册真实市场检验是 **null**：352 个策略 pooled Spearman ρs=0.013（95% CI [−0.094,0.121]，单侧 permutation p=0.40，AUROC 0.496）；该群体 median OOS SR=−0.15、仅 45% 为正。所以：**分数高 ≠ 未来赚钱**；Seal 是统计认证标准，论文明确**不建立"分 ≥ X 就实盘"的决策规则**；低 Seal 率可能只因群体缺 edge 或历史太短（2 年 5-min 历史即使真 edge 也常不够格，别强求）
2. **单位分析错误**：universe-mode（一整套参数共享全指数）的 per-ticker 行继承父搜索的验证值，预测器几乎无变异（IQR≈0.001）→ 任何分数都无法显示预测力（论文 §7.1 前版研究的设计缺陷）。评分必须挂在"每次独立搜索的冠军"上，一行=一次搜索
3. **把评分喂回搜索循环 / 自适应查询**：分数只在"未被用于选择该策略"时才有效；用户迭代提交变体看分再选下一个变体 = 分析师层的 selection bias，门看不到你试过又扔掉的变体（论文 §9.2）→ 需要 query 预算 + 锁死的最终 OOS 窗口
4. **σ/Σ_eff 校准污染**：σ 必须在**完整总体（含 clamp 边界点质量）**上估，clamp-free 子集会把 σ_PBO 从 10.028 拉到 ~1.1 致 10% 行饱和；pooled vs run-weighted 差 1.128 vs 0.63。σ/Σ/F̂ 是 population-relative——换总体必须重估并锁 vintage，绝对分跨 vintage 不可比（Seal 判定本身与 σ 无关、可移植）
5. **DSR 实现细节**：u 缺失必须 fail-closed 而非从 DSR 反推（饱和回归）；通货方差用 Lo null 1/years 而非固定 1.0；**族内方差估计已证伪**（AUROC 0.96→0.50，论文 §6.6 否决）——不要自作主张"改进"成按家族估方差；任何"提高通过率"的改动都必须先在 ground-truth 环境证明分离度改善
6. **权重≠贡献、regime 门最弱**：DSR 有效贡献 76.9%（名义 0.35）、regime 完美点贡献 39.2%（名义 0.10）；regime 公式的 0.5/0.3/0.2、σ_ref=2 都是启发式。±20% 权重扰动排序几乎不变（Spearman≥0.997）——调权救不了差分数，别花时间
7. **自相关不在 DSR 内修正**：Mertens i.i.d. 调整只含偏度峰度；HAC 仅审计。高频（分钟级）回测注意序列相关对 DSR/SPA block bootstrap 结果的影响

## 与现有系统衔接
- **a-share-strategy-research-flow**：其白框/灰框 walk-forward 每参数每窗口绩效 = 本文 PBO/regime 的 candidate×fold 输入；其步骤 5 随机基线 permutation 总体 = 分离度验证的"纯噪声半边"
- **quant-alpha-factory / multi-factor-stock-picking**：Top10 输出与格点搜索冠军在上实盘模拟前过本评分做评级闸门
- **a-share-factor-ic-evaluation**：IC/分层回测结论 + 本评分统计支持强度 → 投资决策前双确认
- **a-share-paper-trading**：评分后入模拟盘，滚动积累 forward 结果——论文 future work 明确这是验证分数预测力的正途（真实市场至今 null）

## 来源与校准数字核对（均摘自 paper.md）
- 校准：359,062 行生产 trial-ledger（536 次优化 run，含持久化 pre-Φ u）；Seal 通过 3,848 行 = 1.07%，集中于 6 个长历史日线 run；PBO=0 退化行 14.4%；DSR=0 记录 60–95%（视策略族）
- 表 1/表 5：headline（T=1260）AUROC：Minerva 0.989 / DSR 0.988 / GT 0.986 / gates 0.960；worst-case regret：Minerva 0.021、GT 0.071、gates 0.138、DSR 0.009（最小）
- 表 3：冻结 σ_DSR=1.128（pooled IQR/1.349）、σ_PBO=10.028、σ_SPA=6.013、σ_ρ=1.161；√(wᵀΣw)=0.753（表 4 全掩码）；r₀≈0.3085、r⋆≈0.9997；c=0.5、δ=0.1、ε=10⁻⁶、σ_ref=2
- 生产分布：failing median raw 8.9×10⁻³、raw≥0.99 占 0.002%、仅 18 条 Seal-fail 行 raw≥0.90；sealed raw 范围 0.391–0.9998 vs failing p99=0.64；display：sealed 82–100（median 91），failing 最高 79
