# L2b P2 分层回测 · 技术沉淀（2026-08-22 实跑）

> 本文件沉淀 P1a 估值回填 + P1b 资金代理 + P2 分层回测实跑中修掉的 bug、协议与结构发现。
> 项目内结果文档：`docs/L2b_P2_layer_diagnosis.md`。

---

## 1. 回测预注册协议（防第三次 data snooping 红线）

**规则**：所有回测参数必须在脚本头部注释块**首跑前冻结**；看到结果后**零调参**。
任何参数改动（TOP_N/阈值/权重/窗口）= 新实验，须整体重做：预注册 → 训练/测试切分 → 测试窗只验一次。

```python
# PRE-REGISTERED PARAMETERS — DO NOT MODIFY AFTER FIRST RUN
# 行业池: 申万一级31 - 综合(510000) = 30; 房地产保留并标注
# 调仓频率: 月频 | 信号日: 月末T收盘(只用<=T分位,无前视) | 建仓: T+1收盘
# 组合: bottom-5 等权 | 成本: 0.25%/边, 首月只买一边, 换手(k/5)×0.5%双边
# 基准: 801003.SI | 窗口: 训练2020-01~2023-12 / 测试2024-01~2026-08 (walk-forward)
# 门控: D6 六门控(全部为诊断对照)
```

## 2. 实跑中修掉的 6 个真 bug

### 2a. numpy 布尔歧义（gate 函数必踩）
`if excess3m:`（numpy array）→ `ValueError: truth value of an array is ambiguous`。
修正：`if len(excess3m) > 0:`；`if pos and neg:` → `if len(pos) > 0 and len(neg) > 0:`。

### 2b. pandas 列对齐（EXCLUDE 后 KeyError）
scores pivot 含被排除行业（如 510000），closes pivot 不含 → `closes.loc[T, c]` 抛 KeyError。
修正：两 pivot 加载后显式对齐 `scores = scores[[c for c in scores.columns if c in closes.columns]]`。

### 2c. 成本公式双算
❌ `replaced = len(prev-pick) + len(pick-prev); cost = (replaced/TOP_N) × 0.5%`（每笔换手算了两次）
✅ 首月 `cost = 0.25%`（只买一边）；后续 `k = len(set(prev)-set(pick)); cost = (k/TOP_N) × 0.5%`。

### 2d. ICIR 符号（低分位=买入方向）
"低分位=买"类策略截面 Spearman IC 系统性为负，直接 `icir >= 0.3` 恒 FAIL（方向性假失败）。
修正：`abs(icir) >= 0.3`（符号无意义）。相关概念见 `a-share-factor-ic-evaluation` 技能。

### 2e. circ_mv 单位陷阱（致命，错 4 个数量级）
Tushare `daily_basic.circ_mv` 单位是**万元**，非元。
❌ `turnover_rate/100 × circ_mv / 1e8` → ✅ `/ 1e4` 得亿元。
验算：平安银行 2024-06-14 circ_mv=19,754,846 万元 ≈ 1,975 亿元（股价~10 元×流通股本，合理）。

### 2f. 5y 窗短数据全 NaN
数据仅 2020 起，5 年滚动窗（1260 交易日）→ 训练窗（2020-2023）全 NaN。
修正：**双轨** = 2 年滚动（504 日, min_periods=120）+ expanding 全历史（min_periods=120）。
2y 捕捉近期 regime，expanding 保证训练窗有值。逻辑同理适用于任何"窗口>数据历史"场景。

## 3. 无前视分位实现（严格只用 ≤T 历史）

```python
import bisect
import numpy as np

def rolling_rank(arr, window, min_periods):
    out = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        v = arr[i]
        if not np.isfinite(v):
            continue
        lo = max(0, i - window + 1)
        valid = arr[lo:i+1][np.isfinite(arr[lo:i+1])]
        if len(valid) >= min_periods:
            out[i] = float((valid <= v).sum()) / len(valid)
    return out

def expanding_rank(arr, min_periods):
    out = np.full(len(arr), np.nan)
    sorted_vals = []
    for i in range(len(arr)):
        v = arr[i]
        if np.isfinite(v):
            if len(sorted_vals) >= min_periods - 1:
                idx = bisect.bisect_right(sorted_vals, v)
                out[i] = (idx + 1) / (len(sorted_vals) + 1)
            bisect.insort(sorted_vals, v)
    return out
```

注意：跨脚本复制时 `expanding_rank` 易漏（P1b 首版引用未定义 → NameError），复制后 grep 确认。

## 4. Tushare SDK token 加载范式（生产 cron 脚本同款）

```python
def load_token():
    with open(os.path.expanduser('~/.hermes/.env.tushare')) as f:
        for line in f:
            if line.startswith('TUSHARE_TOKEN='):
                return line.split('=', 1)[1].strip().strip('\r').strip('"').strip("'")
    raise RuntimeError('TUSHARE_TOKEN 未找到')

ts.set_token(load_token()); pro = ts.pro_api()   # 用 set_token, 不要 ts.pro_api(token)
```
关键：`.strip('\r')` 处理 Windows 换行、`.strip('"').strip("'")` 处理引号包裹；调用间隔 ≥1.5s（限频红线）。

## 5. 结构发现：单维"低分位买入" OOS 不成立

P2 分层回测（bottom-5 月频，30 行业）：
- 层1 估值(pe_5y, 银行 pb_5y) / 层2 资金(turnover_2y 冰点) 测试窗 2024-26 **均 0/6 门控**，毛超额负（-3.25% / -2.37%），IC 负。
- 训练窗 2/6 与 3/6（3M 超额为正但月度年化转负）→ 仅存微弱均值回归 alpha，被月频换仓+成本吃光。
- 测试窗选股构成：层1 食品饮料 30/30 月（持续下修=接飞刀）；层2 煤炭 67% + 价值陷阱簇(地产/银行/煤炭/钢铁/建筑) 23%。
- **根因**：单维低分位买入缺"盈利维一票否决"（40% 权重，因扣子数据库未恢复、E0 前向积累中）——失败模式恰是该维度设计的防御场景。
- **纪律结论**：不调参（训练窗接近不得作为调参理由）、不强行合成（分层验证红线）、P3 集成阻塞。
- 待扣子恢复 → ≥6 个月快照 → 按**原预注册规则**重验盈利维与合成。

## 6. 数据地基事实（防重复探测）

- `industry_valuation_history`：87,668 行 / 31 行业 / 2015-01-05~2026-08-21，含 pe/pb/close + 双窗分位 4 列。
- `industry_capital_proxy_daily`：49,848 行 / 31 行业 / 2020-01-02 起，含 avg_turnover/total_amount/amount_share_pct + 2y/expanding 双轨分位。
- `index_daily` 已含 801003.SI（2,828 行）基准。
- `ths_member` 静态快照（无 trade_date）→ P1b 早期成分 survivorship bias，无法修复，仅文档化。
- `daily_kline` 2020-2023 仅指数行（如 1A0002），**前向收益须用 sw_daily 行业级 close**（industry_valuation_history.close），不能用个股行情表。
- sw_daily MCP/SDK 历史最早 2015-01-05（5y 分位底层足够）；申万 2021 版 31 一级行业名称↔恒生聚源码映射 31/31 已建。
