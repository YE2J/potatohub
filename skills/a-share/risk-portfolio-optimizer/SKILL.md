---
name: risk-portfolio-optimizer
description: Use when 用户要做组合优化/风险度量/资产配置。用 EVaR/CVaR 风险度量构建组合，替代单纯均值-方差。
author: Hermes Agent
license: MIT
version: 1.0.0
metadata:
  hermes:
    tags: [portfolio-optimization, evar, cvar, var, risk-management, asset-allocation]
    related_skills: [a-share-strategy-research-flow, multi-factor-stock-picking, nonparametric-var, distribution-builder-sell]
---

# EVaR/CVaR 组合优化

## When to Use
- 用户要做多标的组合优化/权重分配（替代等权或均值-方差）
- 用户需要 VaR/CVaR/EVaR 风险度量（日/周/月级别）
- 用户想"最小化尾部风险"而非仅最小化方差
- 需要组合的风险预算、风险贡献分解

## 论文依据
Nedeltchev & Zaevski (2026), "Entropic Value-at-Risk portfolio optimization for tempered stable Lévy processes", arXiv:2608.18022。
核心：EVaR（信息论风险度量，Ahmadi-Javid 2012）比 CVaR 更紧、计算更快（10x）、无需尾部分布假设。

## 核心定义

### EVaR（对损失 L，置信度 1-η）
```
EVaR_{1-η}(L) = inf_{u>0} (1/u) · ln( M_L(u) / η )
```
其中 M_L(u) = E[e^{uL}] 是损失的矩生成函数（MGF）。

### 对收益 X（论文 Eq.4）
```
EVaR_{1-η}(X) = inf_{u>0} (1/u) · ln( M_X(-u) / η )
```

### 风险度量层级（理论性质，PoC 验证 ✓）
```
EVaR ≥ CVaR ≥ VaR
```

### 特殊情形（论文 Table 附近）
- 正态：EVaR = -μ + σ√(-2 ln η)
- 组合（权重 w）：EVaR_{1-η}(w'X_t) 用投影 MGF

## 实证简化实现（PoC 验证可用，无需 Lévy 参数估计）

```python
import numpy as np
from scipy import optimize

def evar_empirical(w, R, eta=0.05):
    """实证 EVaR: 用历史收益样本 MGF"""
    rp = R @ w  # 组合日收益
    def f(u):
        if u <= 0: return np.inf
        m = np.mean(np.exp(-u * rp))
        if m <= 0: return np.inf
        return (np.log(m) - np.log(eta)) / u
    u_max = 1.0 / max(1e-8, -np.min(rp) + 1e-8) * 0.5
    u_grid = np.linspace(1e-4, max(u_max, 1.0), 400)
    vals = np.array([f(u) for u in u_grid])
    u0 = u_grid[np.argmin(vals)]
    res = optimize.minimize_scalar(f, bounds=(1e-4, max(u_max, 1.0)*2),
                                   method='bounded', options={'xatol': 1e-10})
    return res.fun, res.x

def cvar_empirical(w, R, eta=0.05):
    rp = R @ w
    return -np.mean(rp[rp <= np.quantile(rp, eta)])

def var_empirical(w, R, eta=0.05):
    rp = R @ w
    return -np.quantile(rp, eta)
```

### 组合优化目标（论文 5 节）
- 最小 EVaR：`min_w EVaR(w'R)` s.t. Σw=1, w≥0
- EVaR 比率：`max_w (w'μ) / EVaR(w'R)`（类似 Sharpe 但用尾部风险）
- 收益约束：`max_w w'μ` s.t. EVaR(w'R) ≤ 阈值

## 实现步骤
1. 从数据库读多标的日收益（对齐共同交易日）
2. 计算组合收益序列 R@w
3. 用 `evar_empirical` 算 EVaR（对任意权重向量）
4. 组合优化（scipy.optimize.minimize Nelder-Mead 或 SLSQP，随机重启 50-100 次避免局部最优）
5. 输出：最优权重、EVaR/CVaR/VaR 对比、η 敏感性

## 验证结果（2026-08-23 实测，4 只 A 股 165 日）
- EVaR ≥ CVaR ≥ VaR 成立 ✓
- 等权 EVaR=8.23%/日 → 优化后 3.56%/日（-57%），年化收益 -0.82% → +18.6%
- η 敏感性：η=1%→5.43%, η=5%→3.56%, η=10%→2.75%（置信度越高 EVaR 越大，正确）
- 优化收敛：权重集中到正收益标的（000001 77.6% + 300750 22.4%）

## 增补模块 A1 — 广义二次风险测度 R_P(w)=½wᵀQw+cᵀw+k：全闭式解（论文 2608.24449）

出处：Gasparavičius & Grigutis (2026), "Generalizing Markowitz Portfolio Optimization by a Quadratic Risk Measure", arXiv:2608.24449。
核心结论：把协方差 Σ 换成**任意对称正定（SPD）矩阵 Q**、方差换成**带线性项 cᵀw 与常数 k 的二次风险测度**
R_P(w) := ½wᵀQw + cᵀw + k，Markowitz 全套结果（GMV/有效前沿/切线/最大效用）**仍全部有显式闭式解**。
本模块所有公式已用 numpy 复算，与论文 Table 1 数值完全一致（见下文"可复算演示"）。

### 定义与前提（论文 Eq.1–3）
```
R_P(w) = ½ wᵀ Q w + cᵀ w + k ,   w∈𝒫={Σwᵢ=1}, Q=Qᵀ≻0, c∈ℝⁿ, k∈ℝ
非负性条件（保证任何组合 R_P≥0）:   k ≥ ½ cᵀQ⁻¹c
```
- 完成平方：R_P(w) = ½(w+Q⁻¹c)ᵀQ(w+Q⁻¹c) − ½cᵀQ⁻¹c + k ≥ 0 ⟺ k ≥ ½cᵀQ⁻¹c。
- 经典退化：c=0, k=0, Q=2Σ 即普通方差（注意论文的 ½ 因子：R_P=½wᵀQw 时 Q=2Σ 才是方差）。
- c 的含义（A股直译）：**线性调整项**——单边交易成本线性化、偏离基准/目标组合 w_T 的惩罚
  （wᵀΣw + λ(w−w_T)ᵀ(w−w_T) 展开后即含 −2λw_Tᵀw 类线性项）、因子暴露拉格朗日项等。
- k 的含义：归一化常数，取 k = ½cᵀQ⁻¹c + ε（ε≥0 可调）即满足非负性。
- 与 EVaR/CVaR 主线关系：本模块是**均值-二次风险闭式族**，与尾部分布的 EVaR 互补——
  需要"一步解析、无迭代"时用它；需要尾部分布刻画时仍走本 skill 的 EVaR 流程；两者可交叉验证权重。

### 一表速查：闭式解（列向量记号，Q⁻¹ 存在）
| 组合 | 闭式公式 | 出处 |
|---|---|---|
| GMV 最小风险 | w* = [(1+1ᵀQ⁻¹c)/(1ᵀQ⁻¹1)]·Q⁻¹1 − Q⁻¹c | Prop.1 |
| 指定收益 μ₀ 最小风险 | w* = (Q⁻¹μ, Q⁻¹1)·M⁻¹·(μ₀+μᵀQ⁻¹c, 1+1ᵀQ⁻¹c)ᵀ − Q⁻¹c，M=[[μᵀQ⁻¹μ, μᵀQ⁻¹1],[·,1ᵀQ⁻¹1]] | Prop.3 |
| 最大 Sharpe（超额 μ̃=μ−r_f·1） | w* = Q⁻¹[ (A(E−2k)−(C+1)²)/(AD−B(C+1))·μ̃ + (D(C+1)−B(E−2k))/(AD−B(C+1))·1 − c ]，A=1ᵀQ⁻¹1, B=1ᵀQ⁻¹μ̃, C=cᵀQ⁻¹1, D=cᵀQ⁻¹μ̃, E=cᵀQ⁻¹c | Prop.2 |
| 切线组合（含 rf 前沿切点） | w* = Q⁻¹[ (1+1ᵀQ⁻¹c̃)/(1ᵀQ⁻¹μ̃)·μ̃ − c̃ ]，c̃=c−c_f·1（c_f 为无风险资产线性项） | Prop.6 |
| 最大效用（无 rf） | w* = Q⁻¹[ (1+1ᵀQ⁻¹c−1ᵀQ⁻¹μ)/(1ᵀQ⁻¹1)·1 + μ − c ] | Prop.8 |
| 最大效用（含 rf） | w* = Q⁻¹(μ̃−c̃)，w_f = 1−1ᵀw | Prop.9 |

有效前沿（Prop.4/Cor.1，无 rf）：R_P(μ) = a/(2d)·μ² + (ae−b(1+f))/d·μ + [ae²−2be(1+f)+c(1+f)²]/(2d) − g/2 + k，
μ ≥ μ_Rmin = −e + b(1+f)/a；其中 a=1ᵀQ⁻¹1, b=1ᵀQ⁻¹μ, c=μᵀQ⁻¹μ, d=ac−b², e=μᵀQ⁻¹c, f=1ᵀQ⁻¹c, g=cᵀQ⁻¹c。
含 rf 前沿（Prop.5，Capital Market **Curve** 而非 Line）：μ = r_f + √((2R_P + c̃ᵀQ⁻¹c̃ − 2k̃)(μ̃ᵀQ⁻¹μ̃)) − μ̃ᵀQ⁻¹c̃。

**几何新现象（务必记住）**：c≠0 时 R_P 不是正齐次 → **切线组合 ≠ 最大 Sharpe 组合**（经典 Markowitz 中两者重合）。
选"贴 rf 无风险前沿的切点"还是"最大化 Sharpe"，是两个不同组合，别混用。

### Python 实现 + 论文 §4 Example 1 数值演示（✓已实测复算）
论文例（μ, Q, c, r_f=1, c_f=0）：k 取 ½cᵀQ⁻¹c + 1 = 7.10（½cᵀQ⁻¹c = 6.10）。以下输出与论文 Table 1 全一致：
```python
import numpy as np
mu = np.array([2.,5.,9.,14.])
Q  = np.array([[6.,2.,-1.,0.],[2.,5.,1.,1.],[-1.,1.,4.,1.],[0.,1.,1.,3.]])
c  = np.array([3.,-4.,2.,-1.]); rf=1.0; cf=0.0
k  = 0.5*c@np.linalg.inv(Q)@c + 1.0            # = 7.10，满足 k ≥ ½cᵀQ⁻¹c
Qi = np.linalg.inv(Q); one = np.ones(4)
def R(w): return 0.5*w@Q@w + c@w + k

w_gmv  = (1+one@Qi@c)/(one@Qi@one)*(Qi@one) - Qi@c                       # Prop.1 GMV
mu_t   = mu - rf*one;  c_t = c - cf*one                                  # 含 rf 参数折叠
w_utilF= Qi@(mu_t - c_t); wf = 1 - w_utilF.sum()                         # Prop.9 最大效用(含rf)
A_=one@Qi@one; B_=one@Qi@mu_t; C_=c@Qi@one; D_=c@Qi@mu_t; E_=c@Qi@c      # Prop.2 最大Sharpe
den = A_*D_ - B_*(C_+1)
w_sr  = Qi@( (A_*(E_-2*k)-(C_+1)**2)/den*mu_t + (D_*(C_+1)-B_*(E_-2*k))/den*one - c )
w_tan = Qi@( (1+one@Qi@c_t)/(one@Qi@mu_t)*mu_t - c_t )                   # Prop.6 切线组合
w_util= Qi@( ((1+one@Qi@c-one@Qi@mu)/(one@Qi@one))*one + mu - c )        # Prop.8 最大效用(无rf)
# 有效前沿系数（Prop.4）：R_P(μ) = c2 μ² + c1 μ + c0，μ ≥ 12.16
a_=one@Qi@one; b_=one@Qi@mu; cc=mu@Qi@mu; e_=mu@Qi@c; f_=one@Qi@c; g_=c@Qi@c; d_=cc*a_-b_**2
c2, c1 = a_/(2*d_), (a_*e_-b_*(1+f_))/d_
c0 = (a_*e_**2 - 2*b_*e_*(1+f_) + cc*(1+f_)**2)/(2*d_) - g_/2 + k
```
复算核对表（论文 Table 1，✓一致）：
| 组合 | 权重 w | 期望收益 μ | 风险 R_P |
|---|---|---|---|
| 最小风险 GMV | (−0.72, 1.54, −0.67, 0.85) | 12.16 | 3.06 |
| 最大 Sharpe | (−1.26, 1.17, −0.97, 2.05) | 23.38 | 6.14 |
| 切线组合 | (−1.03, 1.32, −0.84, 1.55) | 18.63 | 4.09 |
| 最大效用(无 rf) | (−1.70, 0.87, −1.21, 3.04) | 32.59 | 13.28 |
| 最大效用(含 rf) | (−0.67, 1.00, 0.00, 4.33; w_f=−3.67) | 60.67 | 31.77 |
前沿（无 rf）：R_P = 0.02μ² − 0.60μ + 6.68（μ≥12.16），等价 μ = √(40.85(R_P−3.06)) + 12.16；
含 rf 前沿（Curve）：μ = √(61.53·(2R_P−2.00)) − 0.87（R_P ≥ 1.00 = k̃ − ½c̃ᵀQ⁻¹c̃）。✓ 上表 5 组合均落在各自前沿上（复算逐点核对误差 < 0.02）。

### A股落地映射（用闭式解替代迭代凸优化）
- **Q**：收缩协方差 (1−ρ)Σ̂+ρI（论文 Eq. 里 Q=2(Σ+λI) 即此形）、因子模型协方差 BΣ_F Bᵀ+diag(σ²_残)、行业块状相关矩阵；
  任意 SPD 都行——EVaR/CVaR 流程里的 scipy 迭代可被替换为一步 `np.linalg.solve`。
- **c**：交易成本线性化（cᵢ ≈ 单位换手的单边冲击/佣金成本）、偏离目标权重的惩罚
  （wᵀΣw + λ‖w−w_T‖² → 展开出 c=−2λw_T 类的线性项）、对基准行业/风格暴露的拉格朗日项。
- **k**：取 ½cᵀQ⁻¹c + ε，ε 小正数，保证 R_P≥0 与 Sharpe 分母可开方（还需 cᵀQ⁻¹c < 2k，Prop.2 前提）。
- 使用顺序建议：选股 Top10 → 读收益矩阵 → 造 Q（收缩/因子）+ c（成本/约束）→ 闭式一步出 w。
- **闭式解的适用边界（新增 Pitfall 条目）**：
  1. 闭式解在**允许卖空、仅预算约束 Σw=1** 下成立；A股多头通常要求 w≥0（可能还有个股/行业上限）→
     约束非平凡时闭式失效，退回数值优化（此时广义二次目标仍凸，scipy SLSQP 可解，QP 起步点可用闭式解）。
  2. 公式含 Q⁻¹：n 大时勿显式求逆，用 `np.linalg.solve(Q, v)` 分批解。
  3. 切线组合 ≠ 最大 Sharpe（c≠0）：报告中写明用的是哪一个，二者收益/风险差别显著（例中 μ 18.63 vs 23.38）。
  4. R_P 是"方差类"风险（对称惩罚涨跌），不刻画尾部；尾部诉求仍回 EVaR 主线。
```

---

## Pitfalls
1. **MGF 数值稳定**：exp(-u·rp) 溢出时用 log-sum-exp 技巧；u 上限取 1/(−min(rp)+ε)
2. **η 语义**：η=0.05 是 95% 置信度（5% 尾部）；η 越小 EVaR 越大
3. **局部最优**：组合优化用随机重启（Dirichlet 初始 60 次），Nelder-Mead 后归一化权重再算目标
4. **论文完整版**：MNTS/ICA 参数化方法需估计 Lévy 参数（α,θ,β,γ,μ,ρ），PoC 用实证 MGF 已足够；若需严格参数化参照论文 Algorithm 1（分段 Brent）
5. **数据对齐**：不同标的历史长度不同，须取共同交易日交集；库内个股仅 ~165 天，长历史用指数或 Tushare
6. **组合收益单位**：EVaR 输出为日损失比例，年化 ×√252（波动尺度）

## 增补模块 A2 — 停牌/次新股票池的协方差处理（pairwise-complete + 谱修复，论文 2608.30446）

出处：Bongiorno & Villassero (2026), "End-to-End Neural Shrinkage of Indefinite Pairwise Correlation Matrices
for Small-Cap-Inclusive Portfolios", arXiv:2608.30446。
动机（论文摘要+§1）：股票池含次新股、长期停牌、断续交易时，若强制所有股票取共同回看窗口会丢弃大量信息
（论文美股 1500 只池中 17.15% 的"股票×调仓日"观测有效历史 <1200 日，8.45% <600 日，3.48% <252 日）。
A股停牌更频繁（重组/重大事项/*ST 长期停牌），本模块给出**不等长收益面板**的协方差处理基线。

### 第 1 步 — 构造收益面板与有效性掩码
- 对齐：tushare `trade_cal` 取交易日历；`daily` 取前复权收益；`suspend_d`（停复牌表）标记停牌日。
- 面板 R ∈ ℝ^{T×n}、掩码 M∈{0,1}^{T×n}（M_ti=1 表示第 i 股第 t 日有有效收益）。
- 停牌/无交易日 M=0；**涨跌停一字板**按需求可一并置 0（价格无效）或保留（论文未涉，标注为本模块取舍 ⚠️）。
- 重叠矩阵（论文 Eq.1）：T_ij = Σ_t M_ti·M_tj —— 每对股票共同交易日数，对角线 T_ii = 各自有效天数。

### 第 2 步 — 边际标准化的 pairwise-complete 估计（论文 Eq.2–5）
- 每个资产用**各自全部有效历史**估边际矩：μ̂_i = ΣM_ti R_ti / T_ii，σ̂_i² = ΣM_ti(R_ti−μ̂_i)² / T_ii。
- 标准化 Z_ti = M_ti·(R_ti−μ̂_i)/σ̂_i；逐对用重叠样本估交叉矩：
  C∩,ij = (1/T_ij)·Σ_t Z_ti Z_tj（无重叠的配对置 0），C∩,ii = 1。
- 协方差：Σ∩ = D̂·C∩·D̂，D̂ = diag(σ̂_1,…,σ̂_n)。
- 与"每对单独中心化"的经典 pairwise 法不同：边际矩只估一次、全局复用，保留更多可预测信息（论文 §2 论证）。
- 注意：**边际缩放救不了不定性**——D̂ 非奇异 ⇒ Σ∩ 与 C∩ 合同 ⇒ 惯性相同（Sylvester 惯性律），负特征值个数不变。

### 第 3 步 — 负特征值诊断（进 Markowitz 前必查）
```python
w_cap, V_cap = np.linalg.eigh(Ccap)          # Ccap 为第 2 步输出，对称
neg = w_cap[w_cap < -1e-6]
print(len(neg), w_cap.min())                  # 负特征值个数与最小特征值
# 判据：min eig < 0 → 矩阵不定 → GMV 会给某些组合算出“负方差”，必须先修复
```
- 高浓度比 q = n/ΔT（股票数/有效窗长）大时，正的谱同样被噪声污染，需要收缩；论文指出现有 RMT 收缩理论
  只适用于"单一共同面板"估计（PSD 且每项同样本量），**pairwise-complete 矩阵两项都不满足**，故无现成 RMT 规则。

### 第 4 步 — 修复基线（先落：特征值裁剪，⚠️ 诚实标注）
⚠️ 论文**没有**"特征值裁剪"基线；论文的经典修复对照是 Higham 最近相关矩阵投影（结果表 14.74% 年化 5 日波动，
下称 Anderson 法）与因子填充/岭回归等。裁剪是本模块给 A股部署的**第一个朴素基线**（先跑通、作门槛，再升级）。
```python
def clip_psd(C, delta=1e-6):
    """特征值裁剪：负特征值抬到 delta，再归一化对角=1（相关系数矩阵语义）"""
    w, V = np.linalg.eigh(C)
    wc = np.clip(w, delta, None)
    Cc = (V * wc) @ V.T
    d  = np.sqrt(np.diag(Cc)); Cc = Cc / np.outer(d, d)   # 重标度回单位对角
    return (Cc + Cc.T) / 2
```
- 修复后验：`np.linalg.eigvalsh(C_fix).min() > 0`；协方差 Σ̂ = D̂·C_fix·D̂ 须正定，再进 GMV
  w = Σ̂⁻¹1/(1ᵀΣ̂⁻¹1)（论文 Eq.7，或带 w≥0 的 long-only 凸优化）。
- 裁剪的已知失真（诚实标注）：负特征值对应的方向被压平，相关结构被扭曲，负特征值越大失真越大；
  若负特征值占比/幅度大，应直接上第 5 步投影法而非依赖裁剪结果。

### 第 5 步 — 升级路径（按需）
1. **最近 PSD 投影（Higham/Anderson 法）**：交替投影到 PSD 锥+单位对角（论文基线，效果优于朴素裁剪）；
2. 因子模型/岭回归填充（论文 Factor 基线效果最好，14.08%）；MLE（完整行子面板，16.25%）、QIS（完整行子面板 RMT 收缩，15.54%）；
3. （远期，先不上）神经 RIEnet：把"符号谱 + 因子对齐有效样本长 τ_k=Σ_ij Q_ik²T_ijQ_jk²"喂给双向 GRU，
   softplus 映射为正逆谱，端到端最小化未来 GMV 波动训练（~7400 参数，与 n、ΔT 无关）；
   论文结果：5 日年化波动 11.17% vs 次优 14.08%（−20.7%），Sharpe 0.814 vs 0.580（+40%），
   26 年样本外（2000–2025，每 5 交易日调仓，含冲击/费用/公司行动模拟），MCS 0.1% 显著性仅保留 RIEnet。

### A股要点
- 数据源：tushare `suspend_d` + `daily` + `trade_cal`（任务指定的组合）；次新股上市不足窗口（如 <60/120 交易日）天然产生不等长。
- 建议回看窗 120–250 交易日、每 5/20 交易日重建面板；成分池含停牌股时 pairwise 重叠 T_ij 普遍 < 全窗长，
  GMV/风险预算之前**必须**过第 3–4 步。
- 与增补模块 A1 衔接：修复后的正定 Σ̂ 可直接充当 A1 的 Q；若想把停牌股当"数据缺失"而非"风险 0"，避免把
  停牌日收益率填 0（会造成伪低波动），一律走掩码路线。
```

---

## 与现有系统衔接
- 可作 L2/L3 权重分配模块：把选出的股票池用 EVaR 优化赋权，替代等权
- 风险度量可与 `nonparametric-var` 交叉验证（EVaR 是参数化上界，非参 VaR 是数据驱动）
- 与 `multi-factor-stock-picking` 衔接：选股 Top10 → 本 skill 赋权