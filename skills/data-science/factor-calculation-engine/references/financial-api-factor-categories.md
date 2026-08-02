# Financial-API 5类因子扩充方案

> 基于同花顺Financial-API（涨停/连板/龙虎榜/热榜/异动）和Tushare打板专题数据的因子构造指南
> 2026-07-05

## 背景

原有15个因子（GS信号/主力雷达/AI活跃度/暗盘资金/主力持仓）全部基于OHLCV+资金流数据。Financial-API提供**Tushare完全没有**的差异化数据（涨停、连板、龙虎榜、热榜、异动），可构造全新的因子维度。

## 5类因子总览

| 类别 | 数据源表 | 因子数 | 与现有体系关系 |
|------|---------|:------:|---------------|
| 涨停因子 | `limit_up_pool` | 5+ | 与GS信号互补（时间+强度维度） |
| 龙虎榜因子 | `dragon_tiger_daily` | 4+ | 与暗盘资金互补（资金身份识别） |
| 热度因子 | `hot_stock_daily` | 3+ | 全新独立维度 |
| 异动因子 | `daily_anomaly` | 4+ | 全新短线维度 |
| 板块因子 | sw_daily/ths_daily等 | 4+ | **完全正交**，增量价值最大 |

## 构造公式

### 1. 涨停因子

```python
# 首次涨停时间分段
zt_first_time_bin = 0  # 非涨停
if is_limit_up:
    hour = int(first_time.split(':')[0])
    if hour < 10:       zt_first_time_bin = 3  # 早盘封板
    elif hour < 11:     zt_first_time_bin = 2  # 上午封板
    else:               zt_first_time_bin = 1  # 午后封板

# 开板次数（越小越好）
zt_open_times = open_times if is_limit_up else 0

# 封单/成交额比
zt_fd_ratio = fd_amount / max(amount, 1) if is_limit_up else 0

# 连板数
zt_consecutive = board_count

# 涨停质量综合分
zt_quality = z_score(zt_first_time_bin, -zt_open_times, zt_fd_ratio, zt_consecutive)
```

### 2. 龙虎榜因子

```python
# 龙虎榜净额
lh_net_amount = net_amount

# 机构参与信号
lh_inst_flag = 1 if inst_buy > 0 else 0

# 游资+机构合力分
lh_cooperation = hot_money_count + (1 if lh_inst_flag else 0)

# 净额率
lh_net_rate = net_amount / max(total_amount, 1)
```

### 3. 热度因子

```python
# 热度排名归一化（排名越靠前越大）
hot_rank_score = 1 - (rank / 5000) if rank else 0

# 热度飙升信号
hot_surge = 1 if rank_type == '飙升榜' else 0
```

### 4. 异动因子

```python
# 异动次数
yd_count = len(anomaly_list)

# 拉升异动信号
yd_lift_flag = 1 if '拉升' in anomaly_tags else 0

# 异动类型编码
yd_type_code = encode_yd_type(anomaly_tags)
```

### 5. 板块因子

```python
# 所属板块当日涨跌幅
stock_sector_perf = sector_pct_change

# 板块共振系数（正=有个股α）
sector_resonance = stock_pct_chg - sector_pct_change

# 强势板块信号
sector_strong = 1 if (sector_zt_ratio > 0.3 and sector_fund_flow > 0) else 0
```

## 接入现有因子管线

### daily_factors 表扩展

用 `ALTER TABLE` 追加新列（不破坏现有数据）：

```sql
ALTER TABLE daily_factors ADD COLUMN zt_quality REAL;
ALTER TABLE daily_factors ADD COLUMN zt_consecutive REAL;
ALTER TABLE daily_factors ADD COLUMN lh_net_amount REAL;
ALTER TABLE daily_factors ADD COLUMN lh_inst_flag REAL;
ALTER TABLE daily_factors ADD COLUMN lh_cooperation REAL;
ALTER TABLE daily_factors ADD COLUMN hot_rank_score REAL;
ALTER TABLE daily_factors ADD COLUMN hot_surge REAL;
ALTER TABLE daily_factors ADD COLUMN yd_count REAL;
ALTER TABLE daily_factors ADD COLUMN sector_resonance REAL;
ALTER TABLE daily_factors ADD COLUMN sector_strong REAL;
```

### ic_analyzer.py 适配

在 `FACTOR_COLS` 和 `DERIVED_FACTORS` 列表中追加新列名即可，无需改计算逻辑。

### 实现文件

- `~/my_quant_system/financial_api/factors.py` — 5类因子计算函数（~20KB）
- 每个函数接收 `date` 参数，从新建的Financial-API表查询数据，返回 `DataFrame(stock_code, factor1, factor2, ...)`

## 相关性预判

|                     | gs_point | radar_zhuli | dark_pool | ai_score |
|---------------------|:--------:|:-----------:|:---------:|:--------:|
| zt_first_time       | ★★★      | ★★          | ★         | ★        |
| zt_consecutive_days | ★★★      | ★★          | ★★        | ★★       |
| lh_net_amount       | ★        | ★★          | ★★★       | ★        |
| hot_rank            | ★        | ★★          | ★★        | ★★★      |
| sector_perf         | ★★       | ★★          | ★         | ★        |
| yd_count            | ★        | ★★          | ★         | ★★       |

图例: ★★★高相关 / ★★中等 / ★低

关键发现：
- **板块因子**几乎完全独立于现有体系，增量价值最大
- **涨停因子**与GS信号高相关，但提供了时间（几点封板）和强度（封单比）的新维度
- **龙虎榜因子**与暗盘资金互补，解决"无法区分资金身份"的根本缺陷
