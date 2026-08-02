# 衍生信号快速测试法

基于 2026-07-02 的 ic_analyzer.py 开发经验。

## 为什么要做衍生信号测试

在修改 daily_factors 表或 backtest_v4.py 的策略逻辑之前，先快速评估新信号的 IC 表现。如果 IC 为负或接近零，说明这个信号方向不对，不值得花时间集成。

## 实现方式

在 `ic_analyzer.py` 中定义 `DERIVED_FACTORS` 列表：

```python
DERIVED_FACTORS = [
    # (列名, 显示名, 计算函数)
    ("zhuli_above_zero",      "主力线>0",           lambda df: df["radar_zhuli"] > 0),
    ("zhuli_below_zero",      "主力线<0",           lambda df: df["radar_zhuli"] < 0),
    ("zhuli_peak_dd15_5d",    "峰回落15%(5日)",     lambda df: _peak_drawdown(df["radar_zhuli"], 5, 0.15)),
    ("zhuli_peak_dd20_5d",    "峰回落20%(5日)",     lambda df: _peak_drawdown(df["radar_zhuli"], 5, 0.20)),
    ("zhuli_peak_dd30_5d",    "峰回落30%(5日)",     lambda df: _peak_drawdown(df["radar_zhuli"], 5, 0.30)),
    ("zhuli_peak_dd30_10d",   "峰回落30%(10日)",    lambda df: _peak_drawdown(df["radar_zhuli"], 10, 0.30)),
    ("zhuli_rise_gt_0",       "主力线上涨",         lambda df: df["radar_zhuli"].diff() > 0),
    ("zhuli_fall_gt_0",       "主力线下跌",         lambda df: df["radar_zhuli"].diff() < 0),
]
```

核心函数 `_peak_drawdown()`：

```python
def _peak_drawdown(series: pd.Series, window: int = 5, threshold: float = 0.30) -> pd.Series:
    """检测序列是否从滚动窗口高点回落超过 threshold（相对幅度）。"""
    rolling_high = series.rolling(window=window, min_periods=1).max()
    drawdown = (rolling_high - series) / rolling_high.abs().clip(lower=1)
    return drawdown >= threshold
```

`run_evaluation()` 会自动：
1. 计算所有衍生信号列（在加载数据之后，IC计算之前）
2. 纳入 `compute_all_ic()` 的 IC/ICIR 评估
3. 纳入分层回测和衰减分析
4. 在 HTML 报告中用 "type: 衍生信号" 区分

## 注意事项

1. **只改 ic_analyzer.py**，不动 daily_factors。衍生信号是 on-the-fly 计算，不写入数据库。
2. **lambda 中的 df 是已加载的完整 DataFrame**（含所有原始因子列），可以引用任何已有列做组合。
3. **返回值转为 float**：`df[col] = fn(df).astype(float)`，布尔值变为 0.0/1.0。
4. **依赖检查**：在 `run_evaluation` 中先检查 `"radar_zhuli" in df.columns`，避免 KeyError。
5. **阈值对比**：定义多个同类型不同阈值（15%/20%/30%）的信号，一次跑完对比 IC 排名。

## 典型用例

### 主力线峰回落卖出信号

2024-06 全市场 20 天的实测对比：

| 信号 | IC | 含义 |
|------|:---:|------|
| 主力线<0 | +0.029 | 主力线转负后下跌 |
| 5日峰回落15% | **+0.024** | 最灵敏有效 |
| 5日峰回落20% | +0.024 | 同上 |
| 10日峰回落30% | +0.023 | 稳健 |
| 5日峰回落30% | +0.022 | 稳健 |
| 日跌幅>0 | +0.015 | 太敏感 |

越灵敏的阈值 IC 越高，5日 vs 10日窗口差别不大。

### 主力线买入信号

| 信号 | IC | 含义 |
|------|:---:|------|
| 主力线>0 | **-0.04** | 负向！主力线>0时反而下跌 |
| 上穿零轴 | **-0.02** | 同样负向 |

在 2024 年市场，买入信号 IC 为负，不建议单独作为买入依据。

## 可扩展的信号方向

- **量价背离**：价格涨但主力线下降 → 卖出
- **多因子交叉**：radar_zhuli > 0 AND dark_pool_1d > 0 → 强买入
- **动量加速**：主力线一阶导上升速度加快 → 强趋势
- **均值回复**：radar_zhuli 从 5日低点回升 N% → 买入
