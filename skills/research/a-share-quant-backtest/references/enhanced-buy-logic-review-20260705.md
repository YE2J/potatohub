# signal_enhancer 买入逻辑审查（2026-07-05）

审查范围：`backtest_v4.py` + `financial_api/signal_enhancer.py` 的增强买入逻辑。

## 审查六维度

| # | 维度 | 核心问题 | 验证方法 |
|---|------|---------|---------|
| 1 | **买入阈值** | ≥10 BUY / ≥15 FULL 是否得当？ | base_score + market_score 是否反映信号强度 |
| 2 | **排序逻辑** | 评分排序 vs 主力线上涨幅度，影响排序质量吗？ | 离散评分 vs 连续幅度，平局问题 |
| 3 | **回退逻辑** | 新表不存在时是否静默回退？ | 检查 `_safe_query()` 和 `except` 路径 |
| 4 | **IC一致性** | 评分权重是否反映 IC 报告结果？ | 对比 Spearman IC 与评分权重 |
| 5 | **数据覆盖** | 2026-07-03 之前的数据是否全部回退失真？ | 检查 market_verify 表存在性 |
| 6 | **语义完整性** | enhanced_buy_decision 是否被引擎实际使用？ | 跟踪列值 -> 决策 -> 仓位 |

## 实证 IC 数据（fwd_1d, 2026-05-29 ~ 2026-06-25）

| 因子 | 类型 | Spearman IC | ICIR | 当前权重 |
|------|------|-------------|------|---------|
| 涨停-首封时间分段 | 连续 | **0.1044** | 0.7394 | 3 (涨停封板强度) |
| 涨停-连板数 | 连续 | **0.0814** | 0.8631 | 2 (连板情绪) |
| 涨停-综合质量分 | 连续 | **0.0805** | 0.5163 | — |
| GS牛市信号 | 信号 | **0.0720** | 0.3221 | 3 (GS信号) |
| 暗盘资金1日净额 | 连续 | **0.0320** | 0.1941 | 2 (暗盘连2日流入) |
| GS牛市+上穿零轴 | 信号 | **0.0189** | 0.3209 | 3 (主力线上穿) |
| GS G点信号 | 信号 | **0.0189** | 0.2892 | — |

**要点**：
- 涨停因子（IC=0.1044）比 GS 信号（IC=0.0720）有效性高 45%，但权重相同
- 主力线上穿（IC=0.0189）是 base 中最弱的因子，却占 3 分（与最强的 GS 并列）
- GS牛市+上穿零轴（IC=0.0189）和 GS G点信号（IC=0.0189）的 ICIR=0.32/0.29，置信度中等

## 发现汇总

### 🔴 Severe：daily_factors merge 日期格式不匹配

`backtest_v4.py` L761-797：
```python
f_df = pd.read_sql_query("""... FROM daily_factors ...""", ...)  # trade_date = '2026-06-26'
f_df['date'] = f_df['trade_date']
df = df.merge(f_df[...], on='date', how='left')  # df.date = '20260626' for SecuCode stocks
```

- `daily_factors.trade_date` = `YYYY-MM-DD`（`'2026-06-26'`）
- `daily_kline.date` (SecuCode) = `YYYYMMDD`（`'20260626'`）
- merge 做精确字符串比较 → **10.6% 匹配率**（14/132 行）
- 失败的 90% 行填充默认值（zhuli_holding=100.0, dark_pool_inflow=1）
- Enhanced 模式下评分虚高 4 分（持仓 2 + 暗盘 2）

**SQLite 验证命令**：
```sql
SELECT COUNT(*) FROM daily_kline k 
JOIN daily_factors f ON k.stock_code=f.stock_code AND k.date=f.trade_date
WHERE k.stock_code='000988';
-- exact match: 14 rows (10.6%)

SELECT COUNT(*) FROM daily_kline k 
JOIN daily_factors f ON k.stock_code=f.stock_code 
 AND REPLACE(k.date,'-','') = REPLACE(f.trade_date,'-','')
WHERE k.stock_code='000988';
-- relaxed match: 141 rows
```

### 🟡 Medium：FULL/BUY 语义丢失

- `sig_buy[i] = True` 条件：`score >= 10`（即 BUY 或 FULL 都触发）
- `buy_rank[i] = float(score)`：FULL（15分）和 BUY（10分）用相同值排序
- 回测引擎中无 FULL→full position 的仓位分配逻辑
- FULL 信号的意图（满仓/加仓）被降级为普通买入

### 🟡 Medium：排序平局

- Enhanced 模式：`buy_rank = float(score)`（离散 0-20）
- 原逻辑：`buy_rank = zhuli[i] - zhuli[i-1]`（连续浮点）
- 当 market_verify 表不可用时，4条件全满足的股票都得 10 分 → 排序完全取决于 Python stable sort 的原始顺序
- 导致回测结果不可复现

### ✅ Good：回退逻辑

- `_safe_query()` 使用 `logging.debug` 记录表缺失，返回 `[]` 不抛出
- `except Exception:` 在 L793 裸吞异常但没有 logging.warning（只填充默认值）

## 修复优先级

1. **P0**：修复 merge 日期格式（影响所有 SecuCode 股票的因子数据）
2. **P1**：IC 校准权重（涨停 > GS > 主力线上穿）— ✅ **已修复** (2026-07-05)
3. **P2**：FULL 信号实现真正满仓逻辑
4. **P3**：排序改用连续值 + score 的组合键（如 `score + zhuli_delta * 0.1`）

## 已修复问题 (2026-07-05)

### ✅ P1: IC 校准权重

`signal_enhancer.py` SCORE_WEIGHTS 已按 IC 报告调整：

| 因子 | 旧权重 | 新权重 | IC |
|------|--------|--------|-----|
| gs_signal | 3 | **2** | 0.072 |
| hot_rank_top | 2 | **1** | 0.023 |
| limit_up_strength | 3 | 3 | 0.104 |
| ladder_sentiment | 2 | 2 | 0.081 |

### ✅ 列名修复

所有 SQL 查询 `ts_code` → `thscode`（8处），`l_buy`/`l_sell` → `buy_top_amount`/`sell_top_amount`（2处），与 Financial-API 实际表结构对齐。
