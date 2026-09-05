---
name: a-share-liquidity-tail-risk
description: Use when 用户要算流动性枯竭尾部风险(IlliQaR)/流动性压力预警。分钟价量造 realized Amihud，MEM-J 跳模型预测日流动性尾部分位，Berkowitz 覆盖率回测。
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [liquidity, illiquidity, amihud, realized-volatility, jumps, mem, tail-risk, a-share, illiqar]
metadata:
  hermes:
    tags: [liquidity, illiquidity, amihud, jumps, mem, tail-risk, a-share, illiqar, coverage-test]
    category: a-share
    related_skills: [nonparametric-var, a-share-strategy-research-flow, risk-portfolio-optimizer, ths-hd1-data-pipeline, quant-classics-reference, a-share-backtesting]
---

# A股流动性尾风险（IlliQaR）— realized Amihud × 跳模型

Illiquidity-at-Risk（IlliQaR）：回答"**给定概率 p，未来一天流动性枯竭到什么程度**"（流动性版的 VaR，右尾度量）。核心方法论来自论文 **"Illiquidity at Risk"（arXiv:2609.00943, q-fin.RM, Lacava & Santucci de Magistris, 2026-09）**：用分钟价量构造高精度 realized Amihud，用带跳的乘性误差模型（MEM-J）估计其条件密度，取 α=1−p 条件分位数即 IlliQaR；用 Berkowitz 检验做覆盖率回测。

⚠️ **诚实声明**：本 skill 中所有公式与数字均提取自论文 HTML 转换版（`/Users/yellow/paper_library/q-fin/2609.00943/paper.md`，正文从约第 50 行起）。该转换在个别公式处有符号破坏（已逐处标注 ⚠️）；「A股适配」部分是本 skill 的实现建议，**论文未涉及 A 股**。凡论文未明确给出的实现细节（截断上界、滤波初值、参数范围等）一律标注"论文未给"。

## When to Use

- 用户要度量个股/指数/板块的**流动性枯竭尾部风险**（不是价格跌幅，是"卖不掉/冲击成本飙升"）
- 用户要预警压力期流动性危机（2015 股灾、2016 熔断、2024 微盘/雪球敲入等）
- 用户有分钟价量数据（本地 hd1 分钟管线 / tushare 分钟接口），要造日频高精度 illiquidity 序列
- 用户要检验某个流动性预测模型在**极端尾部的覆盖率**是否达标
- 与 `nonparametric-var`（价格收益尾部）组合成"价格风险 + 流动性风险"双维度风控

## 论文依据

| 项 | 内容 |
|---|---|
| 标题 | Illiquidity at Risk（IlliQaR） |
| 作者 | Demetrio Lacava（Messina）、Paolo Santucci de Magistris（Luiss） |
| arXiv | 2609.00943，q-fin.RM + econ.EM，2026-09-01 |
| 数据 | S&P 500 日度 realized Amihud（2005-01-03→2021-10-15，4216 观测）；25 只道指成分股（2012-01-03→2024-01-10） |
| 来源 | 本地 `/Users/yellow/paper_library/q-fin/2609.00943/`（paper.md / meta.json） |

**一句话结论**：流动性是高度持久 + 正偏 + 肥尾 + **带跳**的过程；连续模型（HAR/MEM 无跳版）在压力期**系统性低估流动性枯竭**（覆盖率回测全拒，p=0.000）；显式加跳成分（MEM-J）并用跳稳健度量（BPV 版 realized Amihud）后，IlliQaR 的尾部覆盖率才达标。个股流动性枯竭与指数流动性压力**聚类出现，指数是领先指标**。

## 与 nonparametric-var 的互补定位（读本 skill 前先厘清）

| 维度 | `nonparametric-var`（已有） | 本 skill（IlliQaR） |
|---|---|---|
| 风险对象 | **价格收益**尾部（VaR/CVaR：跌多少） | **流动性/价格冲击**尾部（IlliQaR：枯竭到什么程度、要多大冲击才能交易） |
| 度量 | 组合收益（多标的高维） | 单标的日频 illiquidity 序列（可横向铺 25+ 标的） |
| 方法 | 历史 bootstrap 蒙特卡洛，无分布假设 | 参数化条件密度（Gamma / Gamma+Kappa 混合），MLE + 条件分位数 |
| 时间结构 | 忽略序列相关（滚动窗自适应） | 显式建模持久性（HAR 多尺度 + MEM 递归）与跳 |
| 用途 | 组合 VaR 预警、压力测试 | 交易成本/可交易性预警：压力期"卖得动吗、滑点多大" |

**组合用法**（A股适配建议，非论文内容）：① 组合层用 nonparametric-var 看价格尾部；② 对重点持仓个股/板块指数用本 skill 算日 IlliQaR；③ 论文 5.3 发现个股 IlliQaR 违约（violation）聚集于指数流动性压力期、指数有领先性——A股可把**市场/指数 IlliQaR 状态**作为个股流动性风险的先行条件变量（与 2015/2016/2024 三次全市场流动性危机一致）。

## 一、指标：realized Amihud（先于建模的第一步，论文强调"测量精度是前提"）

经典 Amihud（2002）= 日绝对收益/日成交量，噪声大、**掩盖真实尾部行为**（论文 Table 5：用它建模 IlliQaR，连跳模型也被 Berkowitz 全拒，p=0.000）。论文改用 **realized Amihud**（Ranaldo & Santucci de Magistris 2022；Lacava et al. 2026）：

将一日切成 M 个子区间（论文用 **5 分钟**），

$$\text{Illiq}_t=\frac{\text{RPV}_t}{\nu_t},\qquad \text{RPV}_t=\sum_{i=1}^{M}|r_{t,i}|,\qquad \nu_t=\sum_{i=1}^{M}\nu_{t,i}$$（论文式 2）

- r_{t,i} = 第 i 个 5 分钟对数收益；ν_{t,i} = 该子区间成交量。
- **实际使用中可用 RV 替换 RPV**：RV = √(Σ r_i²)（论文 3.1 用 Oxford-Man 的 5 分钟 realized variance 开方 ÷ 日成交量），论文注明 RPV 与 RV 相关 R²>99%，互换影响可忽略。
- M=1 即退化为日频 Amihud（论文式 2 说明）——正是要避免的噪声版本。
- 论文实证数值（S&P 500，realized Amihud ×1e9 缩放）：均值 0.0020、中位 0.0018、标准差 0.0011、**偏度 2.49、峰度 18.18**（Table 1）→ 强正偏 + 肥尾，是"枯竭尖峰"的来源，也是为什么需要尾部分位数而非均值。

**测量精度为何是前提**（论文核心论点之一）：低频代理（日频 Amihud）噪声会把真实尾部分布"糊掉"，使任何模型都分不清"暂时性波动"与"真流动性冲击"→ 覆盖率全拒；高频 realized Amihud 才让跳识别成为可能。

## 二、IlliQaR 定义（论文式 1）

$$\Pr(\text{Illiq}_t > \text{IlliQaR}_t(p)\mid \mathcal{F}_{t-1}) = p$$

即 IlliQaR_t(p) 是条件分布 **1−p 分位（上尾）**：p=5% 对应"明天流动性以 5% 概率超过的水平"≈ 95 分位。论文回测取 **p ∈ {1%, 5%, 10%}**。

三根支柱：① 高精度测量（§一）；② 条件动态模型（§三）；③ 灵活误差分布刻画正偏肥尾（Gamma / Gamma+Kappa 混合）。

## 三、模型族（论文式 3–9）

论文比较了 13 个规格：连续类（HAR、AHAR、MEM、AMEM、MEM-HAR、AMEM-HAR、G-AMEM-HAR）与跳类（MEM-J、AMEM-J、AMEM(2,1)-J、G-AMEM-HAR-J、MEM-HAR-J、AMEM-HAR-J，即各 μ 动态的 -J 后缀）。

### 3.1 连续基准：HAR（Corsi 2009，高斯线性，OLS）

$$\text{Illiq}_t=\omega+\alpha_1\text{Illiq}_{t-1}+\alpha_2\text{Illiq}_{t-1:t-5}+\alpha_3\text{Illiq}_{t-1:t-21}+u_t,\quad u_t\sim N(0,\sigma_u^2)$$（式 3）

周/月项 = 过去 5/21 日均值（捕获伪长记忆）。对应 IlliQaR 为解析式：

$$\text{IlliQaR}_t^{\text{HAR}}(p)=\hat\mu_t+\Phi^{-1}(1-p)\,\hat\sigma_u$$（式 3 后）

⚠️ AHAR（非对称 HAR）在正文中**没有给出公式**，只有名字与估计结果（附录 C 有参数表）；如需复刻请查附录或视作 HAR+负收益哑元。

### 3.2 MEM 族（Engle 2002 / Engle-Gallo 2006，Gamma 误差，MLE）

$$\text{Illiq}_t=\mu_t\epsilon_t,\qquad \epsilon_t\mid\mathcal{F}_{t-1}\sim\Gamma(\vartheta,\,1/\vartheta)\ \ (\text{E}[\epsilon]=1,\ \text{Var}[\epsilon]=1/\vartheta)$$（式 4）

μ_t 动态（"G" = 带 GARCH(1,1) 型 β 滞后项；"HAR" = 带 5/21 日项；AMEM = 带不对称项）：

$$\mu_t=\omega+\alpha_1\text{Illiq}_{t-1}+\alpha_2\text{Illiq}_{t-1:t-5}+\alpha_3\text{Illiq}_{t-1:t-21}+\beta\mu_{t-1}+\gamma D_{t-1}\text{Illiq}_{t-1}$$（式 5，G-AMEM-HAR）

- D_{t-1}=1 当标的当日收益为负（流动性"杠杆效应"：下跌后流动性更易恶化）。嵌套关系：α2=α3=0 且去 HAR 项→AMEM（GARCH 型）；β=0→AMEM-HAR。
- 约束：ω,α,β,γ>0；平稳性论文原文印为 "α1+β1+γ/2>0" ⚠️ **疑为 HTML 转换丢符号，合理应为 α1+β1+γ/2<1**（请对照 PDF 原文确认后使用）。
- E(Illiq|F)=μ_t，Var=μ_t²/ϑ；条件密度闭式 → MLE 一致有效（QML 性质，Engle 2002）。ϑ 为 Gamma 形状（论文实证个股 ϑ∈[13,25] 附近）。
- MEM 族 IlliQaR（闭式，式 6）：

$$\text{IlliQaR}_t^{\text{MEM}}(p)=\frac{\mu_t}{\vartheta}\,\gamma^{-1}\!\big(\vartheta,\ \Gamma(\vartheta)(1-p)\big)$$（γ⁻¹=下不完全 Gamma 逆）

**Python（scipy）映射**：`x* = scipy.special.gammaincinv(ϑ, 1-p)`（单位尺度 Gamma(ϑ,1) 的 1−p 分位）→ `IlliQaR = μ_t/ϑ * x*`（与式 6 等价：γ(ϑ,x*)/Γ(ϑ)=1−p）。⚠️ 注意 gammaincinv 的第二个参数是正则化 CDF 值（0~1），别传 Γ(ϑ)(1−p) 这种未正则化量。

### 3.3 MEM-J（论文核心贡献；Caporin et al. 2017 的跳 MEM 思路）

$$\text{Illiq}_t=\mu_t Z_t\epsilon_t$$（式 7）

- Z_t = 跳成分，与 ε_t 独立；N_t ~ Poisson(κ_t) 时变强度；N_t=0 时 Z_t=d_{κ_t}，N_t>0 时 Z_t=Σ_{j=1}^{N_t}Y_j，Y_j|F ~ Γ（均值 d_{κ_t}、形状 ζ 的 mean-shape 表示，即 scale=d_{κ_t}/ζ），**d_{κ_t}=(e^{−κ_t}+κ_t)^{−1}** 保证 E[Z_t]=1（含 N=0 时 d_κ<1 的补偿）。
- 跳强度动态（Chan-Maheu 2002 型）：κ_t=φ1+φ2κ_{t-1}+φ3ξ_{t-1}；约束 φ1>0、1>φ2>φ3>0。ξ_t 为跳创新（滤波更新）：

$$\xi_t=E(N_t|\mathcal{F}_t)-E(N_t|\mathcal{F}_{t-1})=\sum_{j=0}^{\infty}j\,\Pr(N_t=j|\mathcal{F}_t)-\kappa_t$$

- 条件密度 = **Gamma（无跳日）与 Kappa（跳日，含第二类修正贝塞尔函数 𝕂）的 Poisson 加权无穷混合**，闭式可得 → 可 MLE：

$$f_{\text{MEM-J}}(\text{Illiq}_t|\mathcal{F}_{t-1})=e^{-\kappa_t}f_G(\cdot|N_t{=}0)+\sum_{j=1}^{\infty}\frac{e^{-\kappa_t}\kappa_t^{j}}{j!}f_K(\cdot|N_t{=}j)$$（式 8 分母、附录 A 式 14）

- 滤波概率（贝叶斯，式 8）：Pr(N_t=j|F_t) ∝ f(Illiq_t|N_t=j,F_{t-1})·Pr(N_t=j|F_{t-1})，用于算 ξ_t。
- **Proposition 1（式 9）**：IlliQaR = 求根 x 使 p = 1 − F_MEM-J(x|F_{t-1})；CDF 同为 Gamma CDF + Kappa CDF 的 Poisson 加权混合（Kappa CDF 参数：μ=μ_t·j·d_κ、形状 ϑ1=jζ、ϑ2=ϑ，附录 A 式 15）。

**实现要点（论文未给的数值细节，全部标 ⚠️）**：
- 无穷混合截断：论文未给 J 上界；建议取使 Pr(N>J)=1−Σ_{j≤J}e^{-κ}κ^j/j! < 1e-8 的 J（论文报道指数级跳强度 ~22%/日 → λ≈0.22 时 J≈12 即足够，个股 1–5% 更小；数值上在**对数域**做 log-sum-exp 防下溢）。
- ξ/κ 滤波需要逐期递推（μ_t 与 κ_t 交替更新），初值（κ_0、μ_0、ξ_0）论文未给 → 用样本均值/无条件值启动 + burn-in。
- 每步密度含 𝕂_{jζ−ϑ}(2√(x/μ·ϑζ/d_κ))（scipy.special.kv），j 大时易溢出，注意缩放。
- 个股附录（Appendix C）用**常数跳强度 κ_t=κ** 的 AMEM-HAR-J；指数主文用时变 κ。轻量落地可先做常数 κ 版。

### 3.4 论文原版 vs 轻量替代（含明确分级）

| 方案 | 内容 | 状态 |
|---|---|---|
| **A. 论文原版** | MEM-J 族（AMEM-HAR-J / G-AMEM-HAR-J），MLE，CDF 求根取分位 | 论文验证过的路径（但实现重：混合密度 + 贝叶斯滤波 + Bessel 函数 + 数值求根） |
| **B. 轻量 v0（本 skill 建议，⚠️ 论文未测试）** | HAR 结构 + 跳回归：以 BPV/RV 跳贡献 J_t=max(RV−BPV,0) 或跳日哑元为外生回归量（类似 HAR-RV-J 惯例）造条件均值，误差用 Gamma 近似或滚动经验分位数取 IlliQaR | 只能当**快速原型**；论文明确显示"连续+回归"类若不显式建模跳分布，尾部覆盖率很可能仍不合格——**必须过 Berkowitz/违约率检验才能升级** |
| **C. 度量层净化（论文 4.1 强烈建议）** | 分子用 BPV（bipower variation，Barndorff-Nielsen & Shephard 2004）代替 RV：Illiq^C_t = BPV_t/ν_t，滤掉价格跳对 illiquidity 的机械污染 | 论文实证：跳模型覆盖率在 Illiq^C 上进一步改善（如 MEM-J 在 1% 分位 p 值 0.183→0.447） |

**为什么加跳是必要的（论文核心发现）**：突发公共信息（央行公告/财报/宏观冲击）使所有交易者保留价同向移动——产生大价格波动但**几乎无成交**（量来自分歧而非共识），RV 把连续扩散与离散价格跳一起聚合 → realized Amihud 假性尖峰；反之真实流动性枯竭（做市资本约束、高频"幽灵流动性"撤单、不利选择冲击，Brunnermeier-Pedersen 2009 / Kirilenko 2017 / Glosten-Milgrom 1985）也是跳。连续模型把这两类跳都当噪声平滑掉 → 压力期系统性低估尾部。

## 四、论文实证结论（A股落地的"应有表现"验收锚点）

1. **持续性/聚簇**：illiquidity 长记忆强聚簇；α_d+α_w+α_m 之和接近 1（个股）；µ 用跳模型后 Ljung-Box 残差改善；跳模型 LogLik 更高（S&P：HAR 24753 → G-AMEM-HAR-J 26053，Table 2）。
2. **短期必须加跳，长期可回归简约**：S&P 1 步前 MCS（QLIKE，10% 显著性）唯一胜者为 **G-AMEM-HAR-J**；5 步前 AMEM-HAR；22 步前线性 HAR（Table 3）。个股同构：1 步跳模型（G-AMEM-HAR-J / AMEM(2,1)-J 常进 MCS），5/22 步 HAR 胜（Fig 4）。
3. **覆盖率（核心验收项，Table 4/6）**：无跳模型在 1/5/10% 三个分位**全样本与 OOS 全部被拒（Berkowitz p=0.000）**；跳模型全样本在 1%/10% 通过（5% 边缘）；OOS 用 realized Amihud 时跳模型也常被拒，**换 BPV 版 Illiq^C 后 OOS 基本通过**（唯一例外 MEM-J@5% p=0.0055）。→ 结论：**度量精度（BPV 净化）+ 跳模型 缺一不可**。
4. **噪声代理不可用**：日频 Amihud 版（Table 5）所有模型全拒——低精度测量毁掉尾部识别。
5. **个体股差异**（Fig 3）：个股跳强度 ~1–5% vs 指数 ~22%（指数跳更频繁=系统性压力持续）；个股跳尺寸形状 ζ∈[4,9] 明显低于指数（个股跳更猛但短暂、偏特质性）；ϑ∈[13,25]；杠杆效应 γ>0 但弱于指数。
6. **违约驱动（logit，式 12–13）**：负收益哑元显著（边际效应 ~0.016 滞后 / ~0.05 同期）；OOS 期 VIX、EPU、TED 显著；VIX 分解后**风险规避（Risk Aversion = VIX² − Uncertainty）正向显著、Uncertainty 负向大**——监控"风险规避/情绪"比 VIX 总量更能预判 IlliQaR 违约。TED 系数为负。
7. **系统性**：个股 IlliQaR violation 聚类于指数流动性压力期 → **指数是领先指标**（用于 A股：市场级 IlliQaR 预警 → 排查个股）。

## 五、完整算法步骤（A股落地主流程）

> 【A股适配】论文样本与窗口是美股设定；下述步骤将其映射到 A股数据与三次压力期。凡"建议值"均为本 skill 给出，论文未给处已标 ⚠️。

**S0 范围设定**：选定标的下沉层——市场指数（上证指数/沪深300）、板块指数（中证2000/微盘代理等）、个股（自选/持仓池，建议 20~50 只铺横截面）；定 p∈{1%,5%,10%} 与预测步长 h=1（短期看跳，长步长可退 HAR）。

**S1 分钟价量准备**：
- 本地：`minute_kline`（1 分钟）/`minute5_kline`（5 分钟），字段 (stock_code, seq, open/high/low/close, volume, amount, trades)，库 `~/my_quant_system/stock_data.db`（见 `ths-hd1-data-pipeline` skill；⚠️ 该表主键只有 seq，**须自行确认日期维度的归档方式**，逐日文件→CSV 导入时带上 trade_date）。
- tushare：历史 5 分钟用 `stk_mins`（需权限；`rt_min` 只给当日/近期）；指数分钟 `idx_mins`/`rt_idx_min`；日线成交额用 `daily_kline`/tushare `daily`。
- **复权**：r_i 必须用前复权价计算（本地 .min 多为不复权，除权日会有假跳；成交额是现金口径不受送转影响，可直接用）。**涨跌停/停牌标记**：用 `daily_kline` 的 pct_change/振幅或 tushare `limit_list_d` 识别一字板与停牌日（见 Pitfalls 1）。
- 重采样：1 分钟→5 分钟（取每 5 分钟收盘价 + 聚合 volume/amount）；剔除集合竞价/非连续竞价时段（A股连续竞价 9:30–11:30、13:00–15:00；建议从 9:35 首根算起 ⚠️ 论文用美股 6.5h 全天，未涉及 A股时段规则，本规则为适配建议）。

**S2 造日频 illiquidity 序列**（每标的每日一行）：
```
r_i  = ln(P_5min,i / P_5min,i-1)
RV_t   = sqrt( Σ r_i² )        # 或 RPV_t = Σ|r_i|（论文：二者可互换）
ν_t    = Σ 当日全部分钟成交额（元）   # 或成交量；口径须全样本一致
Illiq_t = RV_t / ν_t           # 建议 ×1e9 缩放（对齐论文数值量级）
# 可选对照：Illiq^C_t = BPV_t / ν_t,  BPV = 双幂变差（BNS 2004）
#   ⚠️ 论文只引用"BPV"未列公式；标准估计量 BPV = μ1⁻²Σ|r_i||r_{i-1}|（μ1=√(2/π)），实现前请以 BNS 2004 原文为准
```
输出 {Illiq_t} 日频序列 + 可选 {Illiq^C_t}。

**S3 数据切分**（防未来信息，见 `a-share-strategy-research-flow`）：
- 论文做法：固定 IS 窗一次估计（S&P IS 2005-01→2015-10，OOS 2015-10→2021-10 约 6 年；个股 IS→2020-02-04，OOS 2020-02-05 起）。
- 【A股适配】IS 至少 ≥8~10 年日频；**OOS 必须覆盖压力期**：2015-06→2016-01（股灾+熔断）、2024-01→2024-02（微盘/雪球敲入/DMA 踩踏）【建议还含 2018 与 2020-02 视数据】。

**S4 估计**：
- HAR：OLS（statsmodels），存 (ω̂, α̂, σ̂u)。
- MEM/AMEM-HAR/G-AMEM-HAR：Gamma 拟似然 MLE（scipy.optimize 或 statsmodels 自写），参数约束 ω,α,β,γ>0；ϑ 由误差矩估或并入 MLE。
- MEM-J：按 §3.3 实现要点做 MLE（对数域截断混合 + 贝叶斯滤波递推 + kv Bessel）；**建议先用常数 κ 版（个股附录做法）跑通，再上时变 κ**。
- 模型对照集至少含：HAR、AMEM-HAR、AMEM-HAR-J（或 G-AMEM-HAR-J）+ 各自在 Illiq 与 Illiq^C 上的版本（度量层对照）。

**S5 预测 + IlliQaR**（h=1）：
- HAR：IlliQaR = μ̂_t + Φ⁻¹(1−p)σ̂_u。
- MEM：IlliQaR = (μ_t/ϑ)·gammaincinv(ϑ, 1−p)。
- MEM-J：对 x 求根 p = 1−F_MEM-J(x|F_{t-1})（F 为截断混合 CDF，单调递增，用 brentq/二分，初值可取 MEM 版结果 ×1.2）。
- 输出日频 IlliQaR_t(p) 序列（每个 p、每个模型、每个标的）。

**S6 覆盖率回测**（Berkowitz，论文 2.4）：对每个模型/分位 p：
1. 概率积分变换 y_t = F(Illiq_t | F_{t-1})（用**样本外/递推**参数算；H0 正确时 y_t~U(0,1)）。
2. s_t = Φ⁻¹(y_t)；右尾截断 s*_t = max(s_t, c)，c=Φ⁻¹(1−p)。⚠️ 论文 md 式(11)把截断点印成 illiquidity 量纲的 IlliQaR_t(p)，与 s_t 量纲矛盾，**系转换损坏；以标准 Berkowitz (2001) 右尾截断（c 为标准正态 1−p 分位）为准**。
3. 对截断序列估截断正态 μ̂、σ̂（极大似然），LR = 2(ll_unrestricted − ll_restricted) ~ χ²(2)（H0：μ=0, σ=1）。
4. 判定：p 值 > 0.10 → 覆盖率合格（论文门槛）。并报**经验违约率** v = #{Illiq_t > IlliQaR_t}/T，对照 p ± 2√(p(1−p)/T)。

**S7 压力期解剖**（A股回看）：把 OOS 违约日期与 2015 股灾/2016 熔断/2024 微盘危机对照：
- 连续模型应在压力窗口出现**违约簇**（v 明显 > p、Berkowitz 拒）；
- 跳模型应显著缓解；若仍不行 → 检查度量层（换 BPV 版 Illiq^C，论文 4.1 的修复路径）。
- 报告三窗口各自的违约率、最大 Illiq 相对 IlliQaR 倍数（枯竭深度）。

**S8 （可选）违约驱动 logit**：I_t=1{Illiq_t>IlliQaR_t(p)} 对滞后/同期解释变量回归（式 12–13 的 A股映射，均【适配建议】）：负收益哑元（=非参数 Var 的收益状态）、市场/板块 IlliQaR 状态（领先指标检验）、波动率状态（如 300ETF 期权隐含波动率替代 VIX）、融资余额变化/资金面替代 TED、政策不确定性代理。预期：下跌日 + 风险规避上行 → 违约概率升。

## 六、验证方法（自查清单）

- [ ] 造出的 Illiq 序列统计形状对齐论文 Table 1 特征：正偏（偏度>2）+ 肥尾（峰度>>3）+ 长记忆（自相关缓慢衰减）；用 `a-share-data` 或日线复核 RPV vs RV 相关 >99%
- [ ] 除权日/停牌日/一字板已被标记剔除（见 Pitfalls 1）
- [ ] 违约率置信带：v ∈ p±2√(p(1−p)/T)（如 T=1200、p=5%：4.0%~6.0%）
- [ ] Berkowitz p 值分层应复现论文表 4/6 层级：无跳模型 ≪ 跳模型；realized Amihud 版 < BPV(Illiq^C) 版；日频 Amihud 版全拒（噪声检查）
- [ ] 压力窗（2015/2016/2024）违约簇定位：连续模型在此处击穿最严重
- [ ] 数值卫生：MEM-J CDF 单调且 F(+∞)=1（截断余量 <1e-8）；模拟对拍——从估计参数抽样，经验分位 vs CDF 求根结果一致
- [ ] 模型对照：MCS/QLIKE（可选）+ 三档损失（论文用 QLIKE，Patton 2011）
- [ ] 若用轻量 HAR+跳方案：Berkowitz/违约率必须达标才可替代 MEM-J（论文 3.3/4 证明连续近似大概率不达标）

## 七、A股数据源映射速查

| 环节 | 数据 | 来源 | 备注 |
|---|---|---|---|
| 5 分钟价量 | `minute5_kline` / `minute_kline` | 本地 hd1 管线（`~/Documents/同花顺指标/`，见 `ths-hd1-data-pipeline`） | ⚠️ 历史深度有限（表内 ~5 日/标的），长历史需批量导 .mn5 或 tushare |
| 历史分钟 | `stk_mins`（个股）/`idx_mins`（指数） | tushare | 需积分；2015/2016 深挖历史的首选 |
| 实时/近期分钟 | `rt_min` | tushare | 仅当日附近，适合上线监控不适合回测 |
| 日线（成交额/复权因子/涨跌停） | `daily_kline` | 本地（Coze 前复权增量） | 除权日检测、停牌/涨跌停标记 |
| 板块/指数流动性 | 上证指数/沪深300/中证2000 分钟 | tushare `rt_idx_min` 等；同花顺板块指数分钟 ⚠️ 需确认有无成交额字段 | 板块指数用 `ths_member` 成分自行合成亦可（见 `a-share-data`） |
| 市场状态变量（S8） | 300ETF 期权隐波、融资余额、北向 | tushare（`opt_daily`/`margin`/`hsgt` 系） | A股替代 VIX/TED/EPU 的适配变量 |

## Pitfalls

1. **Amihud 类度量的"死区"误读**：一字涨停/跌停与停牌日 RV≈0 且 ν≈0 → Illiq≈0 或 NaN，会被机器当成"高度流动/无风险日"，实则是最不可交易的时刻。必须用涨跌停+停牌标记剔除或单列，否则 IlliQaR 低估 + 违约率失真最严重处恰好是压力期。
2. **除权除息假跳**：分钟价不复权时除权日产生巨大假 |r| → 假 Illiq 尖峰进训练集，污染跳参数与 κ 滤波；必须前复权价算 r + 当日成交额口径不动（见 S1）。
3. **单位/缩放口径漂移**：成交量在送转/拆股后机械跳变（分母突变→Illiq 假跌）；成交额（元）口径更稳；全样本同一天切换口径（如部分时段用手、部分用股）会产生结构性断点。建议固定用**成交金额（元）**，缩放系数 ×1e9 全样本一致。
4. **PDF/HTML 转换公式损坏**（本 skill 多处 ⚠️）：平稳性约束疑为 "<1"、Berkowitz 截断点量纲矛盾、AHAR/AMEM(2,1)-J 无公式、个股 ω 数值区间可疑（0.07 vs 0.015）——**引用公式前对照 arXiv PDF 原文**（本地 `paper.pdf`）。
5. **"跳"识别依赖测量精度**：噪声分钟数据（错价/断档/不连续时段混入）会产生假跳，而论文结论是"跳模型的增益以度量精度为前提"——脏数据下跳模型会过拟合假跳、覆盖反而更差。
6. **轻量替代不是论文结论**："HAR+跳回归取分位数"是快速原型，论文验证的是 MEM-J 类 + BPV 度量；用它出报告前必须过 §六 覆盖率检查。
7. **无穷混合截断/滤波初值论文未给**：J 太小 → 尾部概率被低估（正是本 skill 要抓的风险）；用对数域求和 + Pr(N>J)<1e-8 规则 + 模拟对拍（见 §五 S4/§六）。
8. **长步长误用跳模型**：h≥5 时跳贡献衰减、HAR 更优是论文实证——监控/回测若看周频流动性，别强上 MEM-J。
9. **覆盖率 ≠ 只数违约数**：Berkowitz 检的是"条件密度整条尾部"（含分位位置是否偏），违约率达标但位置系统性偏移（连续低估）也会被 Berkowitz 拒绝——两个指标都报。

## 来源

- Lacava, D. & Santucci de Magistris, P. (2026). "Illiquidity at Risk". arXiv:2609.00943 (q-fin.RM).
- 本地：`/Users/yellow/paper_library/q-fin/2609.00943/paper.md`（正文从约第 50 行起，正文 §2–6 对应行 115–1342；式号与论文编号一致：式 1 IlliQaR 定义、式 2 realized Amihud、式 3 HAR、式 4–5 MEM/AMEM、式 6 MEM-IlliQaR、式 7–9 MEM-J/滤波/Prop.1、式 10–11 Berkowitz、式 12–13 违约 logit、附录 A 式 14–15 Kappa CDF 参数化）。
- 上游文献：Ranaldo & Santucci de Magistris (2022) realized Amihud；Lacava et al. (2026) 测度理论；Corsi (2009) HAR；Engle (2002)/Engle-Gallo (2006) MEM；Caporin et al. (2017) MEM-J；Barndorff-Nielsen & Shephard (2004) BPV；Berkowitz (2001) 覆盖率检验；Hansen et al. (2011) MCS；Patton (2011) QLIKE。
- 本 skill 于 2026-09 精读论文后撰写；A股适配部分为技能建议，未经论文验证处均已标注。
