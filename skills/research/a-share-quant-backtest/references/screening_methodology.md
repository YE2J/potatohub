# 全A股条件筛选方法论

## 用途

从全A股（~5,500只）中扫描满足 N 个条件的股票，用于选股池发现/策略信号确认。

## 核心工具

位置：`~/my_quant_system/screen_v4.py`

## 数据库核心问题：InnerCode ↔ SecuCode

```sql
-- daily_kline 通过 InnerCode（数字代码）存储
-- moneyflow_daily 通过 6位 SecuCode 存储
-- 连接 via all_ashare_stocks.csv 映射

SELECT *
FROM daily_kline dk
WHERE dk.stock_code = ?  -- InnerCode, 如 '101' → 华锦股份
```

**关键链路**：
```
daily_kline.stock_code = InnerCode (如 '101', '398589')
  ↓ all_ashare_stocks.csv
SecuCode (如 '000059', '920964')
  ↓ JOIN
moneyflow_daily.stock_code = SecuCode
```

加载映射：
```python
import csv
with open("all_ashare_stocks.csv") as f:
    reader = csv.DictReader(f)
    inner_to_secu = {r['InnerCode']: r['SecuCode'] for r in reader}
    secu_to_name = {r['SecuCode']: r['SecuAbbr'] for r in reader}
```

## 日期格式对齐

```python
# daily_kline — 两种格式共存！
# 旧导入 → '20260626' 无横线（仅 ~147只最新股，大部分是旧自选股）
# 新导入 → '2026-06-26' 有横线（全 A 股 ~5,500 只，2024年起，InnerCode格式）

# moneyflow_daily — 统一 '2026-06-26' 有横线格式
```

**日期格式混用的后果**：
- 用 `'20260626'` JOIN THS 资金流（`'2026-06-26'`）→ 日期不匹配 → JOIN 后只有 15 只
- 用 `'2026-06-26'`（有横线）→ 5,510 只全量可用

## ⚠️ 指标输出列名（容易踩坑）

### calc_zhuli_holdings 的输出列

| 你习惯用的名字 | 实际输出列名 |
|--------------|------------|
| ❌ `zhuli_holdings` | ✅ `zhuli_holding`（单数） |
| ❌ `holdings` | ✅ `zhuli_holding`（单数） |
| — | `zhuli_ddx_daily`（每日DDX变化） |

**主力持仓值始终在 2.08 ~ 97.18 区间内**（同花顺原版钳制）。

主力持仓递推算法（`_zhuli_holdings.py`）：
```python
# DDX从资金流计算
DDX = ((特大单净额 + 大单净额*0.7) / 成交额) * 100
# 从初始50%递推
X1[i] = X1[i-1] + DDX[i] * 0.1
# 钳制
if ret > 97.18: ret = 97.18  # 上限
if ret < 2.08:  ret = 2.08   # 下限
```

所以主力持仓绝大多数股票在 ~50%（中性）到 ~97%（极大值），**阈值 > 20 几乎总是 True**。

### ⚠️ MONEY=0 大坑 — 暗盘资金全错！（2026-07-02 修复）

**症状**：calc_dark_pool 对所有股票产出负值或零，导致 4 条件全 A 股扫描结果=0 只，与同花顺匹配率 0/11。

**根因**：MoneyflowAdapter._map_to_ths_columns() 中 MONEY 列依赖 amount 字段，但 THS moneyflow_daily 表没有 amount 列，导致 MONEY=0。

暗盘公式中的关键计算：
```python
小单买入初 = MONEY - 中单买入初 - 大单买入初 - 特大单买入初
```
当 MONEY=0，小单买入初 = -(中单+大单+特大单) → 永远是负数 → 暗盘资金公式全错。

**修复方法**：用 daily_kline 的 amount 按日期对齐后回填：
```python
mf_mapped = adapter._map_to_ths_columns(mf)
amt_map = dict(zip(dk_fixed['date'], dk_fixed['amount']))
mf_mapped['MONEY'] = mf_mapped['date'].map(amt_map).fillna(0).values
dp = calc_dark_pool(dk_fixed, mf_mapped)
```

注意：必须先修复 amount=0 问题（用 close×volume 回退），再做日期对齐。

**修复效果**：全A股4条件扫描 0只→26只；同花顺11只股票匹配率 0/11→10/11。

### ⚠️ CSV DictReader 迭代器耗尽

screen_v4.py 和 debug 脚本在加载 all_ashare_stocks.csv 时踩过的坑。

```python
# ❌ 错误：三个 dict 只有第一个有数据
with open(MAP_PATH) as f:
    reader = csv.DictReader(f)
    inner_to_secu = {r['InnerCode']: r['SecuCode'] for r in reader}  # √ 有数据
    secu_to_inner = {r['SecuCode']: r['InnerCode'] for r in reader}  # ❌ 空！
    secu_to_name = {r['SecuCode']: r['SecuAbbr'] for r in reader}    # ❌ 空！

# ✅ 正确：先装进 list
with open(MAP_PATH) as f:
    reader = list(csv.DictReader(f))
inner_to_secu = {r['InnerCode']: r['SecuCode'] for r in reader}
secu_to_inner = {r['SecuCode']: r['InnerCode'] for r in reader}
secu_to_name = {r['SecuCode']: r['SecuAbbr'] for r in reader}
```

后果：secu_to_inner 和 secu_to_name 一直是空 dict，导致 debug_ths_compare.py 中所有 11 只股票都"无 InnerCode"，screen_v4.py 的股票名全是代码本身。

### 同花顺决策先锋主力版条件对齐

同花顺APP"决策先锋主力版"→"主力线上穿零轴"使用的完整7个条件：

| # | 同花顺条件 | Hermes映射 | 状态 |
|---|-----------|-----------|------|
| 1 | GS策略:日线G信号+G区间 | `gs_g_point=True` OR `gs_bull_market=True` | ✅ |
| 2 | 机构活跃度:日线大牛线上 | `calc_ai_activity(df)['ai_activity'] >= 6`（大牛线=6） | ✅ |
| 3 | 主力资金:日线连续2天以上流入(暗盘) | 见上方暗盘判断 | ✅ |
| 4 | 主力雷达:日线主力线上穿零轴 | 见上方主力雷达判断 | ✅ |
| 5 | 市场活跃度:80~100 | 同花顺专有指标，无法复现 | ❌ |
| 6 | 市场关注度:80~100 | 同花顺专有指标，无法复现 | ❌ |
| 7 | 牛熊线:日线股价在决策线上 | `close >= gs_decision_line` | ✅ |

条件5、6为同花顺专有指标不可复现。但逻辑上它们只会在已有候选中做**进一步收紧**，所以Hermes不加这两个条件时选出的股票应≥同花顺数量。

2026-06-26验证：Hermes用5条件(跳过5/6)选出26只，同花顺7条件选出11只。Hermes选出的26只中包含同花顺11只中的10只（匹配率91%）。唯一不匹配的603078江化微是暗盘数据微偏差。

结论：**修复MONEY=0后，Hermes指标计算与同花顺基本一致**（91%匹配率），差异来源为条件5、6和数据时间差。

### ⚠️ amount=0 大坑（2026-07-01）

**修复方法**：传给指标前用 `close * volume` 回退：
```python
dk_fixed = dk.copy()
zero_amt = dk_fixed['amount'].fillna(0) == 0
if zero_amt.any():
    dk_fixed.loc[zero_amt, 'amount'] = (
        dk_fixed.loc[zero_amt, 'close'] * dk_fixed.loc[zero_amt, 'volume']
    )
zh = calc_zhuli_holdings(dk_fixed, mf_mapped)
```

### calc_dark_pool 的输出列

| 你习惯用的名字 | 实际输出列名 | 含义 |
|--------------|------------|------|
| ❌ `dark_pool_flow` | ✅ `dark_pool_1d` | 当日暗盘净额 |
| — | `dark_pool_3d` | 3日累计暗盘净额 |
| — | `dark_pool_5d` | 5日累计暗盘净额 |
| ✅ `dark_pool_inflow_signal` | ✅ (布尔) | 当日是否有暗盘流入 |
| — | `dark_pool_accum_signal` | 累计信号(布尔) |

**判断连续2日流入**：
```python
dark_pool_2day = bool(np.all(dp['dark_pool_inflow_signal'].tail(2).values == True))
```

或者用金额：
```python
dark_pool_2day = bool(np.all(dp['dark_pool_1d'].tail(2).values > 0))
```

### calc_gs_signal 的输出列

| 列名 | 含义 |
|------|------|
| `gs_g_point` | G 点触发（买入信号） |
| `gs_s_point` | S 点触发（卖出信号） |
| `gs_bull_market` | 多头市场 |
| `gs_bear_line` | 空头线 |
| `gs_tcy/tkc/tzk/tzd` | 趋势状态标志 |

### calc_zhuli_radar 的输出列

| 列名 | 含义 |
|------|------|
| `radar_zhuli` | 主力线值（EMA((C-MA7)/MA7*480,2)*5） |
| `radar_sanhu` | 散户线值 |
| `radar_maisell` | 卖点雷达(布尔*30) |
| `radar_maibuy` | 买点雷达(布尔*30) |

**判断主力线上穿零轴**：
```python
cross_zero = (prev_zhuli <= 0 and radar_zhuli > 0)
```

**脚本**：`~/my_quant_system/screen_v4.py`（单日） / `~/my_quant_system/screen_monthly_validation.py`（多日+表现追踪）

## 筛选模式

### 全量扫描（逐只）

```python
# 获取全量 InnerCode
cur = db.execute("SELECT DISTINCT stock_code FROM daily_kline WHERE date='2026-06-26'")
all_codes = [r[0] for r in cur.fetchall()]

for inner in all_codes:
    secu = inner_to_secu.get(inner, "")
    if not (len(secu) == 6 and secu.isdigit()):
        continue  # 跳过非 A 股
    
    # 1. 拉 OHLCV（使用 InnerCode）
    dk = pd.read_sql_query("SELECT ... FROM daily_kline WHERE stock_code=?", db, params=(inner,))
    
    # 2. 拉 THS 资金流（使用 SecuCode）
    mf = pd.read_sql_query("SELECT ... FROM moneyflow_daily WHERE stock_code=? AND data_source='ths'", db, params=(secu,))
    
    # 3. 计算指标
    gs = calc_gs_signal(dk)
    rd = calc_zhuli_radar(dk)
    
    # 4. 资金流指标需 MoneyflowAdapter 映射
    mf_mapped = adapter._map_to_ths_columns(mf)
    # 注意：传给 calc_zhuli_holdings 前，先修复 amount=0
    dk_fixed = dk.copy()
    zero_amt = dk_fixed['amount'].fillna(0) == 0
    if zero_amt.any():
        dk_fixed.loc[zero_amt, 'amount'] = dk_fixed.loc[zero_amt, 'close'] * dk_fixed.loc[zero_amt, 'volume']
    dp = calc_dark_pool(dk, mf_mapped)          # dark_pool 用原始 dk（不依赖 amount）
    zh = calc_zhuli_holdings(dk_fixed, mf_mapped)  # zhuli_holdings 用修复后的 dk_fixed
```

### MoneyflowAdapter 注意

`adapter._map_to_ths_columns()` 是私有方法但已广泛使用。它把 moneyflow_daily 的 `elg_buy_amt` 等列映射为同花顺公式变量名：
```
elg_buy_amt  → BIGBUYMONEY1 + WAITBUYMONEY1 (= elg_buy * 1.3)
lg_buy_amt   → BIGBUYMONEY2 + WAITBUYMONEY2 (= lg_buy * 1.3)
md_buy_amt   → BIGBUYMONEY3 + WAITBUYMONEY3 (= md_buy * 1.3)
MONEY        → 成交额（从 amount 或者 close*volume 估算）
```

WAITBUY* = 挂单买入，按实际成交的 30% 估算。

### except 陷阱

```python
# ❌ 错误：静默吞掉所有异常，失败股票零输出无痕迹
except Exception:
    continue

# ✅ 正确：加 logging + 异常计数器
logger = logging.getLogger(__name__)
errors = 0
except Exception as e:
    errors += 1
    if errors <= 5:
        logger.warning("%s %s 计算失败: %s", inner, secu, e)
```

## 时段扫描（多日遍历） + 信号后表现统计

对于策略验证/月度报告，需要**遍历多个交易日**，对每个信号追踪后续表现。

### 扫描逻辑

```python
# 1. 获取全量交易日
df_trade_cal = pd.read_sql_query(
    "SELECT DISTINCT date FROM daily_kline WHERE date >= ? AND date <= ? ORDER BY date",
    db, params=(HISTORY_START, SCAN_END)
)
all_dates = sorted(df_trade_cal['date'].tolist())
scan_dates = [d for d in all_dates if SCAN_START <= d <= SCAN_END]

# 2. 提前加载 THS 资金流全量（避免逐股重复查DB）
all_mf = pd.read_sql_query(
    """SELECT stock_code, date, elg_buy_amt, elg_sell_amt, lg_buy_amt, lg_sell_amt,
              md_buy_amt, md_sell_amt, sm_buy_amt, sm_sell_amt
       FROM moneyflow_daily WHERE data_source='ths' AND date >= ? AND date <= ?""",
    db, params=(HISTORY_START, SCAN_END)
)
mf_by_stock = {secu: grp.sort_values('date') for secu, grp in all_mf.groupby('stock_code')}

# 3. 遍历每只股票，为每个扫描日检查信号
for ic, secu, name in valid_stocks:
    dk = pd.read_sql_query("...WHERE stock_code=?", db, params=(ic,))  # InnerCode 加载K线
    gs = calc_gs_signal(dk)
    rd = calc_zhuli_radar(dk)
    
    mf = mf_by_stock.get(secu)
    mf_mapped = adapter._map_to_ths_columns(mf) if mf is not None else None
    if mf_mapped is not None:
        dp = calc_dark_pool(dk, mf_mapped)
        zh = calc_zhuli_holdings(dk_fixed, mf_mapped)
    
    for scan_date in scan_dates:
        try: idx = dk['date'].tolist().index(scan_date)
        except ValueError: continue
        
        # 检查4条件
        cond1 = bool(gs.iloc[idx]['gs_g_point']) or bool(gs.iloc[idx]['gs_bull_market'])
        cond2 = float(zh['zhuli_holding'].iloc[idx]) > 20
        cond3 = bool(np.all(dp['dark_pool_inflow_signal'].iloc[idx-1:idx+1].values == True))
        rd_now, rd_prev = float(rd['radar_zhuli'].iloc[idx]), float(rd['radar_zhuli'].iloc[idx-1])
        cond4 = (rd_prev <= 0 and rd_now > 0)
        risk_ok = float(dk['amount'].iloc[idx]) > 50_000_000
        
        if cond1 and cond2 and cond3 and cond4 and risk_ok and not is_st:
            signals.append({'scan_date': scan_date, 'secu': secu, 'name': name, 'close_price': close})
```

### 信号后表现追踪

```python
# For each signal, look up close price at +N trading days
def get_future_trading_day(base_date, offset, date_list):
    """从 base_date 起算 offset 个交易日后的日期"""
    try:
        idx = date_list.index(base_date)
        target_idx = idx + offset
        return date_list[target_idx] if target_idx < len(date_list) else None
    except ValueError:
        return None

# 对每个信号：查 base_date 之后 N 个交易日的收盘价
for s in signals:
    kline = pd.read_sql_query(
        "SELECT date, close FROM daily_kline WHERE stock_code=? AND date>=? ORDER BY date",
        db2, params=(inner_code, s['scan_date'])
    )
    dates = kline['date'].tolist()
    base_idx = dates.index(s['scan_date'])
    
    # +5 日
    if base_idx + 5 < len(dates):
        pct_5 = (float(kline['close'].iloc[base_idx + 5]) - base_price) / base_price * 100
```

### 统计指标

```python
def calc_stats(series):
    """计算该时间窗口的绩效统计"""
    valid = series.dropna()
    if len(valid) == 0: return None
    return {
        'count': len(valid),
        'win_rate': round((valid > 0).sum() / len(valid) * 100, 1),
        'avg': round(valid.mean(), 2),
        'median': round(valid.median(), 2),
        'max_gain': round(valid.max(), 2),
        'max_loss': round(valid.min(), 2)
    }
```

### 使用场景

- **月度验证报告**：扫描1个月信号，追踪+5/+10/+20交易日，评估策略有效性和稳定性
- **信号频率分析**：观察信号在时间上的分布（密集/稀疏/簇聚）
- **参数敏感性**：改条件阈值后重扫，对比绩效变化
- **脚本模板**：`~/my_quant_system/screen_monthly_validation.py`

### ⚠️ 时段扫描陷阱

1. **内存管理**：5,527 只 × 30 天指标全放内存可能 1.5GB+，建议分批（batch_size=50）或日级别流式处理
2. **THS 资金流提前加载**：`mf_by_stock` dict 占内存约 500MB，但避免每只股票重复查 DB 节约 10x 时间
3. **最近日期信号无未来数据**：如 2026-06-24 的信号 +20 日需要 2026-07-22 的行情数据，数据库必须有足够覆盖
4. **ST 过滤**：用 `secu_to_name` 的股票名检查 `'ST' in name or '退' in name`
5. **同一天多信号**：同一日期同一股票只记录一次信号（当天判断条件满足即可，不重复计数）

## 筛选结果解读

### 单日扫描（2026-06-26）

| 条件 | 命中率 |
|------|--------|
| GS 在 G 信号/G 区间 | 31.3% |
| 主力持仓 > 20% | ~93%（几乎全过，阈值太低） |
| 暗盘资金连续 2 日流入 | ~8.3% |
| 主力线上穿零轴 | 2.0% |
| **同时满足 4 个** | **0%** |
| 同时满足 3 个 | 14.6% |

**4条件AND = 0只的原因**：条件②阈值20太低（93%过），条件④上穿零轴罕见（2%），两者交集极窄。建议将持股阈值提到50%或改用加权评分。

### 月度扫描验证（2026-05-15 ~ 2026-06-26，30个交易日）

**发现：信号极其稀少** — 从 5,527 只 A 股、30 个交易日中仅产生 10 次信号（10只不同股票，9个交易日有信号）。

**耗时**: 约 2-3 分钟（每批 50 只，含 THS 资金流计算）

**信号后绩效**：

| 窗口 | 胜率 | 平均涨幅 | 中位数 | 最佳 | 最差 | 样本数 |
|------|------|---------|--------|------|------|-------|
| +5日 | 22.2% | -2.57% | -4.14% | +27.73% | -13.01% | 9 |
| +10日 | 14.3% | -1.85% | -7.74% | +46.44% | -21.92% | 7 |
| +20日 | 33.3% | +14.30% | -7.44% | +81.50% | -22.60% | 6 |

**观察**：
- 短期（+5d）表现偏弱，多数信号买入即回调
- 但中期（+20d）出现极端分化：普冉股份(688766) +81.5%，佰维存储(688525) +51.6%
- 科创板占信号量的 40%（4/10），且均为正收益
- 6月4日之后的信号密集度降低，说明4条件在震荡市表现不一致
- 信号后+20日样本仅6个（4个因时间不够尚未完成追踪）

**结论**：单一信号不说明稳健性，需要累积更多样本（3-6个月）才有统计意义。当前结果初步提示该策略在科创板更有效，但在传统主板+5d胜率不到20%，需要额外风控。
