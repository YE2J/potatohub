# 因子计算与评估方法论（2026-08-21 实战）

> 来源：P2 全流程（P1.5 权重推导 + P2 合成回测 + v2 重构）。与 a-share-quant-backtest 的失败诊断分工：
> 本文件=因子**计算/评估**方法；backtest 技能=回测**失败诊断**工作流。

## 一、负向因子 IC 计算（三因子退化为两因子的坑）

负向因子（如 turn_20、mom_60_20，A 股偏好低换手/反转）计算 IC 时**必须先取反再算**：

```python
if f in NEG_FACTORS:
    ic = gg[f].rank(ascending=False).corr(gg['fwd_ret'].rank())  # ✅ 先取反
else:
    ic = gg[f].rank().corr(gg['fwd_ret'].rank())
```

**原因**：ICIR 加权时用 `MIN_ICIR=0.15` 阈值过滤负 ICIR 因子。若直接对原始值算 IC（负值），负 ICIR 被过滤 → 因子零权重 → 静默消失（三因子变两因子）。
**注意**：取反后再展示的 IC 是"取向后方向"的 IC，不要再二次取反（显示 bug 会误导）。

## 二、ICIR 加权悖论（权重≠预测力）

ICIR 加权按 `ICIR = mean/std`，衡量的是**稳定性**而非**幅度**：
- 一个稳定弱因子（高 ICIR）可能拿到最大权重（P2 中 turn_20 ICIR 0.457 → 权重 0.388，最大）
- 一个波动强因子（低 ICIR）权重被压低
- 后果：组合合成后 alpha 薄，扣成本后无剩余。
**经验**：ICIR 加权适合"多因子等权打底"，但大权重因子必须在测试窗单独验证其真实贡献；权重分配后要检查"最大权重因子是否也是 IC 最强的"。

## 三、十分位单调性先验（选 TopN 前必做）

合成 composite 后，在**训练窗**内切十分位看 fwd 收益单调性：

```python
gg['decile'] = pd.qcut(gg['composite'], 10, labels=False, duplicates='drop') + 1
# 逐日 qcut → 按 decile 分组算平均 fwd_5d
# 单调性 = 分位序号 vs 平均收益的 Spearman
# shape 判定:
#   mono > 0.7  → strong_monotonic → Top10 可用
#   Q10 < Q9    → non_monotonic_tail → 避免纯 Top10，选 Top20/30（覆盖 Q8-9）
#   mono < 0.4  → non_monotonic → Top10 危险，需宽池
```

**关键洞察**：单调性修复成功（秩相关 0.03→0.87）**不代表策略可用**——若绝对价差太小（Q1→Q10 仅 ~0.76pp/5d），成本吞噬后无剩余。必须同时看**绝对价差**和**单调性**。

## 四、双子窗 maximin 选规则（防过拟合单段行情）

训练窗切两段（例 2020-21 / 2022-23），每个候选规则（TopN）在两子窗分别评估 → 取两子窗较差者 → 选较差者最大者：

```python
best = max(results, key=lambda r: r['worse_excess'])  # worse = min(sub1, sub2)
```

**诊断价值**：若子窗 1 全负、子窗 2 全正 → 策略是风格 Beta 依赖（小盘/价值周期），非稳定 Alpha。此时**停止调参**（再调=data snooping），交用户决策换赛道。

## 五、NF_5D 分母口径锁定（数据源切换铁律）

当 `daily_kline.amount` 在某历史段不可用（本项目 2020-2023 无个股 K 线金额）时，换用代理分母：

```python
amount_proxy = circ_mv(万元) × turnover_rate(%) / 100   # 源: daily_basic
```

**切换铁律**：
1. 生产脚本与回填脚本**同时**锁口径（注释写明口径与日期范围）
2. 切换后必须**全窗重算**（不能只补缺段，否则新旧口径混用）
3. 用秩相关验证代理分母可用性（P2 实测秩相关 median=1.0 → 可用；比值 10× 是单位差，以秩相关为准，比值仅提示）
4. 绝对阈值因子不可用代理分母（量纲污染 → 阈值无意义）；改用**每日截面排名分位**
5. 回填前建备份表（`factor_cross_section_bak_<date>`），全窗 7.8M 行可安全回滚
