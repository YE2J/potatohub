---
name: a-share-factor-ic-evaluation
description: A股因子IC评估全流程——从数据库读取、IC/ICIR/分层回测/衰减分析计算、HTML报告生成，到用同花顺App数据校准算法参数
---

# A股因子IC评估工作流

## 适用场景

- 已有 daily_factors（因子表）+ daily_kline（日线）数据，想评估各因子的预测力
- 想测试衍生信号（组合信号、阈值调整）的 IC 表现
- 需要对比系统计算结果与同花顺App的差异，校准算法参数
- 不想引入 Qlib/RD-Agent 等重型框架，纯 pandas/numpy 自实现

## Pipeline 架构

```
daily_factors           daily_kline
    │                       │
    ▼                       │
  load_data() ◄─────────────┘  (JOIN on stock_code + trade_date)
    │
    ├── compute_ic()           → (IC, ICIR)
    ├── compute_all_ic()      → DataFrame[factor, ic, icir]
    ├── compute_quantile_returns() → 分层回测累计收益
    ├── compute_decay()       → 滚动IC衰减曲线
    ├── compute_factor_correlation() → 相关性矩阵
    └── generate_html_report() → 离线HTML（Chart.js内嵌）
```

## 关键坑点与修复

### 1. kline 表日期格式混用
- daily_kline.date 同时存在 `YYYYMMDD`（SecuCode）和 `YYYY-MM-DD`（InnerCode）
- SQL 字符串比较 `>=` 对不同格式排序错乱（`-` ASCII 45 < 数字 48）
- **修复**: 去掉 SQL 中的日期 where，全量加载后在 pandas 中统一 `pd.to_datetime(..., format='mixed')` 过滤

### 2. kline stock_code 编码双体系
- YYYY-MM-DD 的行用 InnerCode（如 `398589`）
- YYYYMMDD 的行用 6位 SecuCode（如 `000988`）
- daily_factors 只用 6位 SecuCode
- **修复**: 加载 `all_ashare_stocks.csv` 的 InnerCode↔SecuCode 映射，在导入时转换

### 3. compute_ic 的统计方法

#### 大样本（N≥100只股票）——标准截面IC
- 不要用全样本混合相关（pooled correlation）——会被时间序列趋势污染
- **标准做法**: 按日算截面 Spearman IC → 取均值作为全样本IC → mean/std 得 ICIR
- 最少需要 2 个有效日截面（实际至少20天才有统计意义）
- 日截面最少 10 只股票有非空数据

#### 小样本（N<50只股票）——时间序列IC
当股票池很小（如N=20时，日截面IC噪声极大），改用**时间序列IC**：
- 每只股票独立计算`corr(因子值, 未来N日收益)`的全历史Spearman相关系数
- 跨股票聚合：`mean(各股时序IC)`作为因子总IC
- ICIR = `mean(各股时序IC) / std(各股时序IC)`——这里衡量的是**跨股票一致性**而非时间稳定性
- **注意**：这样算出的ICIR **不能**与标准ICIR（|ICIR|>2为显著）对比；它回答的是"这个因子在不同股票间行为是否一致"而非"预测力是否随时间稳定"
- 信号名称要明确标注计算方法（如"时间序列IC"而非"IC"）避免误导

**小样本IC评估局限**：
- 重叠收益窗口（`pct_change(forward_days)`相邻行共享收益数据）导致p值偏乐观
- 建议使用`forward_days=1`避免重叠，或使用HAC标准误修正
- 信号提前性分析（因子触发日距实际买卖日天数）在小样本下可能比IC值更有实际价值

### 4. 分层回测的 groupby 陷阱
- pandas `groupby.apply` 在部分版本会丢失非分组列（如 trade_date）
- **修复**: 改用显式 `for dt, grp in result.groupby('trade_date'):` 循环

### 5. json.dumps 处理 NaN
- Chart.js 数据中的 NaN 会使 json.dumps 报错
- **修复**: 序列化前用 `_safe_json()` 将 NaN 替换为 None

### 6. RSI 连续上涨时返回 NaN
- `_rsi()` 函数中 `loss.replace(0, np.nan)` 会导致连续上涨（loss=0）时RSI=NaN
- 修正：用 `np.where(loss == 0, np.inf, gain / loss)`，此时RSI应为100
- 验证：连续6天阳线 → RSI(6)=100.0 ✅，旧代码→NaN ❌

### 7. 数据完整性验证模式
在数据填充前/后，始终做三字段检查：
```python
cur.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM daily_kline WHERE stock_code=?", (code,))
min_dt, max_dt, cnt = cur.fetchone()
```
- 每个股票应覆盖从买入日（最早2025-01-02）到卖出日（最晚2026-07-03）
- 不应出现断档（COUNT少于预期天数时可疑）
- 用前复权close验证复权正确性：`pre_close * adj_factor ≈ close（复权版本）`

### 8. Tushare历史数据回填流程
当 `daily_kline` 缺少早期数据时：
1. 从Tushare MCP配置提取token（位于 `~/.hermes/mcp.json` 或 `~/.hermes/config.yaml` 的 `tushareMcp.url` 参数中）
2. 用 `ts.pro_api().daily(ts_code, start_date, end_date)` 批量获取
3. 用 `INSERT OR IGNORE` 写入DB，避免重复
4. 每次请求间 `time.sleep(0.35)` 避免限流
5. 写入后重新检查 MIN(date)/MAX(date)/COUNT(*)

## 同花顺数据校准方法

### 校准流程
1. 在同花顺App翻到特定日期，截取指标值（主力雷达、主力持仓、暗盘资金）
2. 从数据库查询同一日期的数据做对比
3. 如果偏差超过预期，调整算法参数

### 主力持仓校准方法论

#### 同花顺真实公式结构（2026-07 验证）

用户提供的同花顺源码（通达信语法）：

```
// 核心：LV_D_SUPER_HLD_RATIO 是L2独有字段，未知则无锚点
IF(ISNULL(LV_D_SUPER_HLD_RATIO[-1]) != 0) {
    b1 := BIGBUYCOUNT1[-1] + WAITBUYCOUNT1[-1];  // 注：用昨日[-1]数据
    s1 := BIGSELLCOUNT1[-1] + WAITSELLCOUNT1[-1];
    b2 := BIGBUYCOUNT2[-1] + WAITBUYCOUNT2[-1];
    s2 := BIGSELLCOUNT2[-1] + WAITSELLCOUNT2[-1];
    DDX := ((b1 - s1) + (b2 - s2) * 0.7) / TV_D_PUBLIC_SHARES * 100;
    x1 := LV_D_SUPER_HLD_RATIO * 100;   // ★ 真实持仓锚点
    ret := x1 + DDX;                     // = 前日真实值 + 昨日DDX调整
    // 三段衰减（极端水位减弱DDX影响）
    IF(DDX > 0) {
        IF(x1 > 95) ret := x1 + DDX * 0.1;
        ELSE IF(x1 > 90) ret := x1 + DDX * 0.5;
        ELSE IF(x1 > 85) ret := x1 + DDX * 0.8;
    }
    IF(DDX < 0) {
        IF(x1 < 5) ret := x1 + DDX * 0.1;
        ELSE IF(x1 < 10) ret := x1 + DDX * 0.5;
        ELSE IF(x1 < 15) ret := x1 + DDX * 0.8;
    }
    ret := clamp(ret, 2.08, 97.18);
}
```

#### 我们实现 vs 真实公式的关键差异

| 项 | 真实公式 | 我们的实现 | 影响 |
|:---|:---------|:-----------|:-----|
| **锚点** | `LV_D_SUPER_HLD_RATIO`（L2独有，每日真实值） | `INIT_HOLD`（凭空猜的15%） | 🔴 根本差异：无锚点则递推必然漂移 |
| **时间偏移** | `[-1]` 用**前一日**数据 | 用**当日**数据 | 影响DDX时序对齐 |
| **DDX分子** | `COUNT` **订单笔数**（如BIGBUYCOUNT1） | `MONEY` **金额**（elg_buy_amt） | 量纲不同，计数值≠资金额 |
| **DDX分母** | `TV_D_PUBLIC_SHARES` **流通股本(股)** | `amount` **成交额(元)** | 需估算流通股本 |
| **数据源** | 同花顺L2行情 | Tushare/东方财富资金流 | 采集口径不同 |

**核心结论：没有 LV_D_SUPER_HLD_RATIO，不可能精确复现同花顺主力持仓。** 纯DDX递推在个股间偏差可达10-30pp（见校准数据）。

#### 无LV2数据的替代方案（趋势方向版）

```
DDX_day = ((elg_buy_amt - elg_sell_amt) + (lg_buy_amt - lg_sell_amt) * 0.7) / amount * 100
DDX_shifted[t] = DDX[t-1]  // [-1]偏移：用昨日DDX调整今日holding
holding[t] = clip(holding[t-1] + DDX_shifted[t] * SCALE, 2.08, 97.18)
```
可选三段衰减：同真实公式，极端水位减弱DDX影响。

参数：INIT_HOLD（默认15.0）、SCALE（默认0.5）、三段衰减（默认启用）

#### ⚠️ SCALE 参数个股相关（已验证）

| 股票 | 代码 | 同花顺 | 系统(SCALE=0.5) | 说明 |
|:----|:----:|:------:|:--------------:|------|
| 蜀道装备 | 002173 | 11~15% | ~13% ✅ | 拟合过SCALE |
| 天华新能 | 300390 | 10.70% | 19.87% ❌ | 需要SCALE<<0.5 |
| 东方锆业 | 002167 | 19.52% | 53.81% ❌ | 需要SCALE≈0.05 |

SCALE在不同个股间可差10倍。建议统一参数作为趋势方向指标，不做绝对数值依赖。

#### 最小二乘法参数拟合
```
对所有候选SCALE/INIT组合做网格搜索
→ 计算各组合下递推序列 holding[t]  
→ RMSE = sqrt(mean((holding[i] - y[i])²))
→ 选RMSE最小的组合
```
**至少需要同一股票 5-6 个交易日的同花顺真实值做拟合**，覆盖持仓上升/下降场景。

#### 校准数据需求
- 最少：同一股票 5-6 个交易日（覆盖涨跌方向）
- 最佳：10+ 个离散交易日，跨度 2-4 周
- 获取：同花顺App截图 + DB查询系统值对比
- 注意：节假日休市会导致数据断档，拟合时需跳过
- 工具：用 `scripts/verify_zhuli.py`（在系统内）快速对比同花顺 vs 系统值

### 暗盘资金校准（已验证）
- 偏差较小（~250万），主要因数据源不同（Tushare vs 同花顺L2）
- 可接受，不影响信号判断

### 主力雷达校准（已验证）
- 同花顺App值 vs 系统值：完全一致 ✅
- 说明 calc_zhuli_radar 的算法复刻准确

## 衍生信号测试

可以在 `DERIVED_FACTORS` 列表中添加组合信号，自动参与IC计算：

```python
DERIVED_FACTORS = [
    # (列名, 显示名, 计算函数)
    ("zhuli_above_zero", "主力线>0(买入)",  lambda df: df["radar_zhuli"] > 0),
    ("combo_dd10_or_below", "峰回落10%或<0", lambda df: _peak_drawdown(df["radar_zhuli"], 5, 0.10) | (df["radar_zhuli"] < 0)),
]
```

## 增量验证流水线（ic_runner.py）

除了全量跑IC评估，还支持**增量验证**——自动判断最新交易日是否需要计算新因子，计算后跑IC评估。

### IC报告解读模板

当IC报告生成后，按以下结构解读：

**判断标准：**
- IC > 0.05: 有预测力
- ICIR > 0.5: 预测稳定（可入策略）
- 分层回测5组单调递增/递减：因子质量高
- 新因子IC > 原有因子：值得替换或补充

**新因子 vs 原有因子交叉验证模板：**

新因子（如涨停因子）必须与原有因子（GS/主力雷达）做IC对比：

| 因子 | IC | ICIR | 评价 |
|------|:--:|:----:|------|
| zt_first_time_bin（新） | +0.104 | 0.739 | 最强短期预测 |
| gs_bull_market（原有） | +0.072 | 0.322 | 中强度但更弱 |
| dark_pool_1d（原有） | +0.032 | 0.194 | 弱但正相关 |

**分层回测验证单调性：** 因子值从低到高5组，收益必须单调递增（正因子）或递减（负因子）。否则即使IC高也可能是过拟合。同时检查Group 5（最高组）是否显著跑赢Group 1（最低组）。

**决策：** 当新因子IC ≈ 原有因子IC × 1.5 以上时，应优先将新因子接入策略。当新因子ICIR > 0.5 时，可作为独立信号使用。

### 因子增量条件均值独立检验（MBCMI）——线性 IC 盲区扫描

**背景（论文 2608.20727，Rudkin & Rudkin 2026）**：上面的 IC/ICIR/五档单调性全部只度量**线性/秩**关系（E[Y|X]≈a+bX）。当新因子对收益的增量预测力是**局部、非线性**的（如只在 X 高分位区域有收益、U 型、环状/薄带/孤岛型结构），线性 IC≈0 是**盲区**。MBCMI（Multiscale Ball Conditional Mean Independence）检验

> H0：E[Y | X] = E[Y]（条件均值独立，即 X 对 Y 无条件均值预测力为零）

用"以每个观测为球心、半径相同的球"做**支持加权局部均值对比**，并对半径做**多尺度聚合**后取最大值；p 值由**递归 Rademacher 符号 bootstrap** 给出。论文应用对齐序列 null 实验 16,000 次复制**拒绝率 4.25%**（单元格 2.6%~5.8%）——即名义 5% 下校准良好。

**定位**：在 compute_ic 的"新因子 vs 原有因子交叉验证"之后作为**第二道门**，专答："**控制住市值/行业/已有因子之后，新因子是否还有（可能非线性的）增量条件均值预测力**"。输入仅需**月/周收益 + 因子面板**（截面），不依赖 L2/分钟数据。

#### 可复现步骤（设计 1：逐期截面 + 元聚合，A 股推荐）

① 构造逐期截面：对每个决策月 t（或非重叠周），取 `Y_i = 未来一个月收益`，`X_i = 新因子当期值`，`Z_i = 控制集`（ln市值、行业哑变量、已有因子当期值）。

② **交叉拟合残差化 Y（论文 I.3 的做法，必做）**：把 Z 对 Y 做 5 折**时间序连续**交叉拟合 OLS，取样本外残差 ε_i。论文最大教训在此：10 个全样本 MBCMI 拒绝在剔除交叉拟合的当期线性成分后**全部消失**——只报 raw MBCMI 不报 residual 版本，只能证明"当期线性联动"，不能证明非线性/预测力。⚠️ 若 X 与控制高度共线，可把 X 也残差化（更保守的增量口径，需在报告注明）。

③ 单期检验（n 为该月股票数，A 股全市场月截面 n≈3000+ 足够；论文规范设计 n=500）：
   - X 先做边际标准化（减均值除以 SD，论文记 Z = D⁻¹(X−a)）；
   - 半径 = 成对欧氏距离的 q 分位数，**q ∈ {0.05,…,0.75}，步长 0.01（71 个半径）**；半径合格条件 γ=0.20（至少 20% 的球心满足最小邻域 N_min=10）；
   - 固定半径统计量 T_n(e) = Σ_{i∈ℐ_n(e)} N_i(e)·{Ȳ_i(e) − Ȳ}²，N_i(e) 为球内邻居数，Ȳ_i(e) 为球内 Y 均值（**按邻域规模加权**，大球权重高，与总体判据对齐）；T_n^max = 跨半径最大值；
   - 缩放准则：bootstrap 必须**整体重搜半径最大**（raw null 尺度随半径/密度/重叠变化，不能与固定临界值比——论文 §2.2）。

④ p 值（iid 截面版）：**Rademacher wild multiplier**——每折 b 给残差乘独立 ±1：ε*_i = ξ_i·ε_i（保留 |ε_i|，异方差稳健），重算 71 半径最大值；B=999；p = (1 + #{T*_b ≥ T_obs}) / (B+1)。实现捷径：球心集合只依赖 X 不依赖 ε，半径分位数与球邻域掩码**可预计算一次**，bootstrap 内只重算球内均值与统计量。

⑤ **元聚合（关键，别拿单月当结论）**：对最近 24~60 个决策月各测一次，报 **5% 水平拒绝月占比**，与论文校准基线比：序列应用对齐 null ≈4.25%、iid 规范 null ≈5.2% → 拒绝占比显著高于 ~5%（如 >10%，或用二项检验）才判"有结构"；单月拒绝≈噪声。

⑥ 成对报告线性残差 IC：同月算 `corr(rank ε, rank X)`。判读：
   | 线性残差 IC | MBCMI 拒绝月占比 | 判读 |
   |:--|:--|:--|
   | ≈0 | 显著高 | **非线性增量候选**（线性 IC 盲区命中） |
   | 显著非 0 | 显著高 | 线性已存在，MBCMI 补充确认局部结构 |
   | ≈0 | ≈5% | 无增量证据（走下方 null 报告规范再下结论） |

核心代码骨架（pandas/numpy，其余沿用 ic_analyzer.py 的数据加载）：

```python
from scipy.spatial.distance import cdist
def _mbcm_tmax(y, X, qs, gamma=0.20, nmin=10):
    """y: (n,) 交叉拟合残差(已去均值); X: (n,d) 标准化新因子"""
    D = cdist(X, X)
    upper = D[np.triu_indices_from(D, 1)]
    masks, ns = [], []
    for q in qs:                       # q∈0.05..0.75 步长0.01
        e = np.quantile(upper, q)
        M = (D <= e);  N = M.sum(1)
        if (N >= nmin).sum() < gamma * len(y):   # 半径不合格→跳过
            masks.append(None); continue
        masks.append(M); ns.append(N)
    best = -np.inf
    for M, N in zip(masks, ns):
        if M is None: continue
        ybar_i = (M @ y) / np.maximum(N, 1)
        ok = N >= nmin
        T = float(np.sum(N[ok] * ybar_i[ok] ** 2))   # y 已中心化
        best = max(best, T)
    return best
# p 值（iid 截面版）：
# obs = _mbcm_tmax(yresid, Xstd, qs)
# cnt = sum(_mbcm_tmax(yresid*rng.choice([-1,1],n), Xstd, qs) >= obs for _ in range(999))
# p = (1+cnt)/1000
```

**⚠️ 设计 2（合并面板 + 串行 bootstrap）慎用**：若把股票-月合并成单一序列做检验，需用论文 D 节**预白化递归 Rademacher bootstrap**（对去中心 Y 拟合 AR(p)，p∈0..6、稳定性检查、可比样本 BIC 选阶；每折对一步创新 η̂_t 乘独立符号后按 AR 递归重生成 Y*，重算半径最大）。但该 bootstrap 的形式有效性**只对"稳定有限阶 AR + 条件符号对称创新"证明**，跨股票合并面板只是近似——严格做法优先设计 1；若序列有重叠 fwd 窗，先改非重叠月/周收益。

#### 与既有检验的对比参照（论文规范 MC，几何特定功效，勿当总排名）

| 方法 | 估计目标 | 结构 | 相对表现（论文结果） | 用法 |
|:--|:--|:--|:--|:--|
| **MBCMI（本文）** | 条件均值恒定 | 球邻域多尺度聚合 | local island / local linear island / ring / thin band / 低 SNR 领先 | 主检 |
| **MDD/MDC** | 条件均值恒定 | 全局距离泛函 | 论文中公开作者代码**未过预指定有限样本校准**（池化 6.6%、单族 7.6%、最差格 10.5%），未入功效排名 | 全局型备选；p 值只当近似 |
| **NCMD K=5/10** | 条件均值恒定 | kNN 图统计量 | interaction / checkerboard 设计最强（K 无数据驱动选择） | 交互结构互补检查 |
| **dCor / HSIC / KSG / MGC** | **完全独立** | 距离/核/MI/多尺度图 | 会对均值以外（方差、偏度、尾部）的依赖也响应 | 只当几何基准：拒绝 ≠ 有可预测均值结构 |
| kNN 局部均值 | 条件均值恒定 | 固定邻域数 | 与 MBCMI 几何最近，全 DGP 均值 AUC 接近 | 稳健性交叉验证 |

#### Pitfalls（论文明示 + 应用注意）

- **必须报 residual 版本**：全样本 raw 拒绝在去掉交叉拟合线性成分后普遍消失 → 只报 raw 即自欺（论文 10/10 全消失实证）。
- 非 omnibus：仅当**至少一个被索引半径**承载非零球平滑均值偏离时才有一致性；球内符号交替（正负相抵）的局域结构会失功效 → 与 NCMD/dCor 对照后再下"无结构"结论。
- X 维数高 → 球稀疏（维度灾难）；建议 X 用 1~3 维新因子或先做主成分（论文实证 d∈{5,6}）。
- 局部小区域拒绝 → 支撑样本少 → **下一道门仍是五档单调性 + 换手/容量检查**再谈上线（局部信号最易过拟合）。

---

### 文件位置

```
financial_api/
├── factors.py            # 5大类因子计算（涨停/龙虎榜/热度/异动/板块）
├── ic_runner.py          # ✨ 增量验证 runner（连接 factors.py + ic_analyzer.py）
└── ...

strategy_library/evaluation/
├── ic_analyzer.py        # IC/ICIR/分层回测/衰减/报告
├── reports/              # ✨ HTML 报告输出目录
│   └── ic_incremental_*.html
└── vendor/
    └── chart.umd.min.js  # Chart.js v4.4.0 离线版
```

### 增量验证工作流

`ic_runner.py` 自动执行以下步骤：

```
① 检查数据库状态
   └─ daily_factors 最新日期、各源表(limit_up_pool/dragon_tiger_daily/hot_stock_daily)最新日期
② 判断是否需要计算新因子
   └─ daily_factors 中有该日期行，但 zt_first_time_bin 全为 NULL/0 → 需要计算
③ 调用 factors.run_all(date) 计算5大类因子并写入
   └─ 涨停104只 / 龙虎榜 / 热度30只 / 异动 / 板块5193只
④ 确定 IC 评估日期范围
   └─ 需与 daily_kline 有交集（fwd_1d 需要 T+1 收盘价）
   └─ 默认取最近20个交易日
⑤ 运行 IC 评估（fwd_1d + fwd_5d 各一次）
   └─ 输出 HTML 报告到 reports/ 目录
```

### CLI 用法

```bash
cd ~/my_quant_system

# 完整流程：计算最新交易日因子 + 跑 IC 评估
~/my_quant_system/.pyenv/versions/3.11.11/bin/python financial_api/ic_runner.py

# 指定日期计算因子 + 跑 IC
python3 financial_api/ic_runner.py --date 2026-07-03

# 跳过因子计算，只跑 IC 评估
python3 financial_api/ic_runner.py --skip-factors --start 2026-06-01 --end 2026-06-26

# 跳过 IC 评估，只计算因子
python3 financial_api/ic_runner.py --skip-ic --date 2026-07-03
```

### 关键坑点

| 坑 | 说明 | 处理 |
|:---|:-----|:-----|
| **kline 日期滞后** | `daily_kline` 最新日期可能晚于因子源表（limit_up_pool 到 07-03 但 kline 只到 06-26） | IC评估自动取 `min(factors_max, kline_max - 1d)` |
| **龙虎榜/异动数据稀疏** | 并非每天都有数据，lh_* 和 yd_* 因子可能全为 NULL | IC评估时这些因子 IC=NaN，属于正常现象 |
| **日期格式不统一** | daily_kline 用 `YYYYMMDD`，daily_factors 用 `YYYY-MM-DD` | pandas `format='mixed'` 自动识别 |
| **new factor 列存在但为 NULL** | 旧日期的 daily_factors 有新因子列（ALTER TABLE 加的），但值都是 NULL | runner 检查 `zt_first_time_bin != 0` 判断是否已计算 |

### Python API

```python
from financial_api.ic_runner import run_pipeline

# 全自动增量验证
run_pipeline()

# 指定日期，跳过IC
run_pipeline(target_date="2026-07-03", skip_ic=True)

# 仅IC评估（因子已算好）
run_pipeline(
    skip_factors=True,
    ic_start="2026-06-01",
    ic_end="2026-06-26",
)
```

## 文件结构（ic_analyzer.py）

```
strategy_library/evaluation/
├── __init__.py           # 模块导出
├── ic_analyzer.py        # 主模块（~670行）
└── vendor/
    └── chart.umd.min.js  # Chart.js v4.4.0 离线版
```

## CLI 用法

```bash
cd ~/my_quant_system
python3 -m strategy_library.evaluation.ic_analyzer \
  --start 2024-06-01 --end 2024-06-30 \
  --watchlist              # 仅自选股
  --stocks 000988 300748   # 指定股票
  --forward 1              # fwd_1d / fwd_5d / fwd_10d
```

## 风险提示

- IC 衡量的是历史预测能力，不保证未来
- 数据不足 20 个交易日时结果统计意义低
- 二值信号（0/1）的 IC 绝对值通常比连续因子低

### null 声明报告规范（IC≈0 结论：bounded vs vacuous）

**背景（论文 2608.30490，David Tan 2026）**：报表里写"因子 IC≈0 / 无预测力"是一种 **null claim**。"统计不显著"≠"效应为零"——它只说明零**与一串其他效应量一起未被拒绝**。这一串里是否包含**经济上可交易的效应量**，决定了这句 null 是真是假。Fitzgerald (2025) 审计 135 篇顶刊经济学论文的 null 声明：约 1/3~2/3 **无法排除经济意义效应**——空话当成了证据。

**核心二分**（标准回归表看不出差别，必须看 CI）：
- **bounded null（有界空）**：CI **排除了经济意义效应量** → "无论效应是什么，都小到不可交易" = **真无效应证据**（≈"precisely estimated zero"）。这是 genuine finding。
- **vacuous null（空洞空）**：CI 太宽，**经济意义效应与零都未被拒绝** → 什么都没证明（缺样本或识别力）。
- **split verdict（分叉判决）**：双边 "no effect" 声明可一边 bounded、另一边 vacuous——比如"多头侧可排除可交易 alpha、空头侧无法区分"。

**三问协议**（判断任何 null 声明，只需效应量 + 标准误）：① 相关边缘（声明侧）的最大效应量是多少？② 它是否达到经济意义阈值 δ？③ 未达到→该侧 bounded；达到→该侧 vacuous。

**落地到 IC 评估（本 skill 的"无预测力"结论）**：

1. **先声明 δ（最小可交易效应量），在结果前固定**。默认锚定本 skill 既有门槛：`δ_IC = 0.05`（IC>0.05 有预测力）——但必须写明单位与来源（"每截面秩相关的月 IC"；依据内部基准/文献/成本模型）。论文要求 δ 用**决策单位的原始量纲**表述、按**具名增量**（此处：因子值一个截面分位/一个标准差对应的月 IC）。δ 需先声明——未声明的 δ 是"恰好在区间边缘落下的任意隐含阈值"，不可辩驳。
2. **每个 IC≈0 的因子补 CI，不满足只报 p/IC**：对逐日 IC 时序求均值 ± t·SE。⚠️ fwd_5d/20d 重叠窗使 IC 时序自相关，**必须用 HAC（Newey-West，lag≈持有期）标准误**，否则 CI 过窄 → 假 bounded。
3. **最小报告格式**（决策日/因子行新增两列）：`IC [95% CI]` + `null 判定`：
   - CI ⊂ (−δ, +δ) → **bounded**：可写"可排除 |IC|>0.05 的可交易 alpha"，报告："We can rule out effects larger than δ"。
   - CI 宽度 > 2δ → **vacuous**：只能写"样本不足以区分零与可交易效应"，严禁写"无预测力"。
   - 一侧窄一侧宽 → **split**：逐侧标注。
4. **量纲无自然单位时的 δ**：若指标无量纲（rank IC 本身是相关，介于 −1~1），按论文建议相对变异设定——如 δ = 0.5 个"逐日 IC 的标准差"或沿用内部 ICIR 门槛换算。
5. **与 MBCMI 联动**：bounded null 只覆盖**线性**可预测性；"IC≈0 且 bounded"**不授权**"无非线性结构"声明——非线性盲区由 MBCMI 步骤负责。反之 MBCMI 的"无结构"结论也需本节规范（给出拒绝占比的 CI 再定性）。

**示例**（fwd_1d 日截面 IC）：因子 A 均值 IC=0.012，HAC 95% CI [−0.010, +0.034]，δ=0.05 → CI 未排除 0.05 → **vacuous**，报告写"无法区分零与可交易 alpha"，不写"无预测力"。因子 B 均值 IC=0.008，CI [−0.020, +0.036]……同宽但若样本更长 CI=[−0.012,+0.028] 仍含 0.05 → 仍 vacuous；只有 CI 上界 <0.05 才算 bounded。注意方向性声明（"多头无 alpha"）只看对应单侧边缘。

**判定表**（进 IC 报告模板）：

| 因子 | IC | HAC 95% CI | δ（先声明） | null 判定 | 结论写法 |
|:--|:--|:--|:--|:--|:--|
| zt_first_time_bin | +0.104 | [0.06, 0.15] | 0.05 | 非 null（显著） | 线性预测力存在 |
| 某弱因子 | +0.008 | [−0.012, +0.028] | 0.05 | vacuous | 无法区分零与可交易 alpha |
| 某长窗因子 fwd_20d | −0.01 | [−0.09, +0.07] | 0.05 | vacuous（典型：长端样本少） | 数据不足以支持"无预测力" |

---

## 参考案例

实际应用示例见 `references/ai-case-analysis-20260706.md`（20只AI大牛股的跨案例因子分析），包含：
- 完整买卖点信号统计
- 小样本IC评估方法
- 3-Agent审核发现的问题清单（P0/P1/P2分类）
- 全部输出文件路径
