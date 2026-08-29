---
name: paper-intake
description: Use when 用户要评估论文是否值得 skill 化。引用 TRIAGE 评分卡，A/B 级走 PoC 后沉淀。
author: Hermes Agent
version: "1.0.0"
license: MIT
metadata:
  hermes:
    tags: [arxiv, q-fin, paper, triage, meta-skill, ingestion]
    related_skills: [distribution-builder-sell, risk-portfolio-optimizer, nonparametric-var, a-share-strategy-research-flow]
---

# paper-intake — arXiv q-fin 论文深度处理 meta-skill

> 本 skill 用于对已通过 L1 轻量分拣（cron）标记的论文做深度处理与 skill 化。
> **评分卡唯一来源**：`~/paper_library/q-fin/TRIAGE.md` 第一节。本 skill 与 cron prompt 均引用该文档，禁止复制定义（防双源漂移）。
> **MOA 按需**：日常走快路径（单模型，省 token）；A 级论文且有时间时，由用户拍板触发深路径（MOA 评审）。

## When to Use
- 用户要评估某篇 arXiv q-fin 论文是否值得 skill 化 / 沉淀
- 用户要深度处理 cron 分拣出的 A/B 级论文（精读→PoC→建 skill）
- 用户想复盘论文处理经验（读 EXPERIENCE.md）
- 用户要查论文决策台账（读 TRIAGE.md）

## 相关文件
| 文件 | 用途 |
|---|---|
| `~/paper_library/q-fin/TRIAGE.md` | 决策台账 + 评分卡唯一定义（cron 与 skill 共用） |
| `~/paper_library/q-fin/EXPERIENCE.md` | 经验文档：问题/角度/方法/优化四块 |
| `~/paper_library/q-fin/INDEX.md` | 论文索引（脚本维护） |
| `~/paper_library/q-fin/<id>/paper.md` | 论文全文 md |
| `~/paper_library/q-fin/<id>/meta.json` | 元数据（arxiv_id/title/summary/categories/local 等） |

## 双路径分支

### 快路径（默认，单模型，无 MOA）
适合：日常处理、token 敏感。直接按下方「深度处理流程」单模型走完。

### 深路径（用户拍板后，A 级且有时间时）
适合：用户确认「有时间 MOA 评审」。在快路径基础上，对 A 级论文先触发 MOA 多模型评审（5 参考 + 聚合器），带回结论后再继续 PoC/建 skill。MOA 触发方式：对话内 /moa 指令块（见 moa-multi-model-review skill）。

## 深度处理流程（五步，快/深路径共用）

### Step 1 精读定位
- 读 `meta.json`（标题/摘要/分类/作者）
- 读 `paper.md` 开头 150 行（摘要+引言）+ 结尾 100 行（结论），定位核心贡献
- 关键公式对照 PDF 核验（md 转换会损失排版：分式/积分/上下标）

### Step 2 算法提取
识别并记录：
- 核心数学公式（截取关键行）
- 算法输入输出
- 数据要求（股价/因子/频率）
- 实现复杂度（低/中/高）

### Step 3 查台账 + 查 skill 库存
- `grep <arxiv_id> ~/paper_library/q-fin/TRIAGE.md` 确认未分析过
- skills_list 对照现有 skill（或 TRIAGE.md 第三节库存快照），判断重叠度

### Step 4 评分定级
按 TRIAGE.md 第一节五维评分卡综合判定 A/B/C/D：
- A：可提取独立算法 + 有 A 股数据可验证 → 新建 skill
- B：可增强现有 skill → 明确优化点
- C：方法论参考价值 → 概念卡片入知识库
- D：无关/纯理论 → 仅存档

### Step 5 PoC 验证（A/B 级必做）
- 用 `~/my_quant_system/stock_data.db` 真实数据写最小 PoC（`~/my_quant_system/.venv/bin/python` 运行）
- 成功标准：核心结论在真实数据上可复现
- 通过后：A → 新建 skill；B → patch 现有 skill；写回 TRIAGE.md 决策行 + 更新 EXPERIENCE.md

## 案例库（2026-08-16~20 批次，真实处置）

| arXiv ID | 评级 | 处置 | 关联 Skill | PoC 关键结论 |
|---|---|---|---|---|
| 2608.18783 | A | 新建 skill | distribution-builder-sell | 沪深300 A=−1.73 超可达区；合成参数验证有趣区 0<A<1 |
| 2608.18022 | A | 新建 skill | risk-portfolio-optimizer | EVaR≥CVaR≥VaR ✓；样本 MGF 替代参数化 MGF |
| 2608.17481 | A | 新建 skill | nonparametric-var | 真实 4 标的违约率 1.92%；高维 N=100 违约率 1.00% |
| 2608.20179 | B | 并入进阶模块 | risk-portfolio-optimizer | 与 18022 高度重叠，动态多期作进阶 |
| 2608.20304 | B | 嵌入随机基线检查 | a-share-strategy-research-flow | 校准放大随机噪声；permutation test 检查 |
| 2608.15841 | C | 知识库概念卡片 | — | 自监督 RL，暂不沉淀 |
| 2608.18195 | C | 知识库概念卡片 | — | 多层做市 RL，暂不沉淀 |
| 2608.19389 | C | 知识库概念卡片 | — | 集中流动性 RL，暂不沉淀 |

## Pitfalls（实测踩坑）

1. **MD 公式排版损失**：分式/积分在 md 中可能变形，关键公式必须对照 PDF 核验。
2. **个股数据不足**：daily_kline 普通个股仅 ~165 行（近半年），完整历史仅指数有（沪深300 5,255 行 2005-2026）。个股 μ/σ 估计不稳时用沪深300 替代。
3. **barrier 有趣区**：A∈(0,1) 才适用 barrier 精确公式；沪深300 实测 A=−1.73（超可达区）。真实个股若处有趣区需实测。
4. **Lévy 参数估计**：18022 原方法极复杂，PoC 用样本 MGF `M_X(−u)≈(1/T)Σexp(−u·r_t)` 替代，效果等价。
5. **滚动波动率 NaN**：滚动窗口前 14 行无效，j_start=15 起算。
6. **高维模拟溢出**：因子载荷 std ≤0.2，日波动约 2%。
7. **arXiv 未同行评审**：skill 正文标注「论文为预印本，公式需对照原 PDF 核实」。
8. **列名差异**：daily_kline 用 `date` 列，index_daily 用 `trade_date` 列（两表相反）。
9. **skill description ≤60 字符**：`Use when` 触发句在前、句号结尾；超长直接被拒（踩过 133/68 两次）。
10. **meta.json 规范**：html_url=`https://arxiv.org/html/{id}`；local 用绝对路径；indent=2；与 arxiv_qfin_daily.py 产出完全一致。
