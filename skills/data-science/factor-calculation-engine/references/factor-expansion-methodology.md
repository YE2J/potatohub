# Financial-API 因子扩充方法论

> 基于同花顺 Financial-API (fuyao.aicubes.cn) 的5大类新因子构造方法
> 适用于 `daily_factors` 表的 ALTER TABLE 扩充

---

## 因子分类全景

| 类别 | 数据来源 | 因子数 | 与现有体系关系 | 优先级 |
|------|---------|:------:|---------------|:------:|
| 涨停因子 | `limit-up-pool` / Tushare `limit_list_d` | 5 | 与GS信号互补（时间+强度维度） | 🔴 高 |
| 龙虎榜因子 | `dragon-tiger-list` / Tushare `top_list` | 4 | 与暗盘资金互补（资金身份识别） | 🔴 高 |
| 热度因子 | `hot-stock-list` / Tushare `ths_hot` | 2 | 新增独立维度 | 🟡 中 |
| 异动因子 | `anomaly-analysis-list/stock` | 3 | 新增短线维度 | 🟡 中 |
| 板块因子 | Tushare `sw_daily` / `ths_daily` | 3 | **完全正交**，增量价值最大 | 🔴 高 |

---

## 1. 涨停因子

### 数据来源
- Financial-API: `limit-up-pool`（每日涨停池）
- Tushare备源: `limit_list_d` / `limit_list_ths`

### 因子设计

```python
# 核心因子
zt_first_time_bin:  # 首次封板时间分段 (0=非涨停, 1=午后, 2=上午, 3=早盘<10:00)
    0 if not 涨停
    1 if first_time > "11:30"  # 午后
    2 if first_time > "10:00"  # 上午
    3 if first_time <= "10:00" # 早盘

zt_open_times:      # 开板次数（非涨停=0），开板少=封板坚决

zt_fd_ratio:        # 封单/成交额比 = fd_amount / amount，封单大=次日溢价高

zt_consecutive:     # 连板数（来自 limit-up-ladder 或限价判断）

zt_quality:         # 综合质量分 = z_score(zt_first_time_bin, -zt_open_times, zt_fd_ratio, zt_consecutive)
```

### 与现有GS信号的关系
- GS信号本身就是价格形态突破，涨停是高强度的突破形态
- 涨停因子提供了**时间维度**（几点封板、开板几次）和**强度维度**（封单比），GS信号没有这些
- 协同使用：GS信号触发 + 涨停因子确认 = 更高置信度

---

## 2. 龙虎榜因子

### 数据来源
- Financial-API: `dragon-tiger-list --board-type all`
- Tushare备源: `top_list` / `top_inst` / `hm_detail`

### 因子设计

```python
lh_net_amount:      # 龙虎榜净额 = buy_top_amount - sell_top_amount（元）
lh_net_rate:        # 龙虎榜净额率 = lh_net_amount / total_amount
lh_inst_flag:       # 是否有机构买入 (0/1) — 从 top_inst 的 inst_buy > 0 判断
lh_cooperation:     # 游资+机构合力分 (0~N) = 机构参与 + 知名游资数量
```

### 与暗盘资金的关系
- 暗盘资金反映全市场大单资金流，但无法区分资金身份
- 龙虎榜因子可以区分：机构买入 vs 游资接力 vs 散户接盘
- 协同：暗盘流入 + 龙虎榜机构净买 = 聪明钱一致性确认

---

## 3. 热度因子

### 数据来源
- Financial-API: `hot-stock-list --period day` / `skyrocket-list`

### 因子设计

```python
hot_rank_score:     # 热度排名归一化 = 1 - rank/5000（排名越靠前越大）
hot_surge_flag:     # 是否进入飙升榜 (0/1)
```

### 使用场景
- 买入验证：GS+主力信号触发时，要求股票不在冷门区（rank > 500）
- 趋势增强：连续3日排名上升 → 关注度递增，加强买入信心
- 卖出预警：股价上涨但排名下降 → 跟风盘不足

---

## 4. 异动因子

### 数据来源
- Financial-API: `anomaly-analysis-list` / `anomaly-analysis-stock`
- Tushare备源: `cls_stock_shock`

### 因子设计

```python
yd_count:           # 当日异动次数（近5日活跃度指标）
yd_lift_flag:       # 是否有拉升异动 (0/1)
yd_breakout_flag:   # 是否有突破异动 (0/1)
```

---

## 5. 板块因子

### 数据来源
- Tushare: `sw_daily`（申万行业日线）/ `ths_daily`（同花顺概念行情）/ `cls_index`

### 因子设计

```python
sector_pct_chg:     # 所属申万行业当日涨跌幅（%）
sector_zt_ratio:    # 所属概念板块涨停率 = 涨停数 / 成分股总数
sector_resonance:   # 板块共振系数 = 个股涨跌幅 - 板块涨跌幅
                    # 正 = 跑赢板块（有个股α），负 = 跑输板块（补涨潜力）
```

### 为什么板块因子优先级最高
- **完全正交**：现有GS/主力雷达/暗盘资金全是个股维度，板块因子是截面维度
- **A股板块效应极强**：同板块联动远强于美股等成熟市场
- **实现最简单**：直接用Tushare已有接口，无需新数据源

---

## IC 验证流程

```python
# Step 1: 将新因子写入 daily_factors 表
ALTER TABLE daily_factors ADD COLUMN zt_first_time_bin REAL;
ALTER TABLE daily_factors ADD COLUMN zt_open_times REAL;
-- ... 依次添加所有新因子列

# Step 2: 在 ic_analyzer.py 的 FACTOR_COLS 列表追加新列名
# ic_analyzer 自动发现新列并参与IC计算

# Step 3: 运行IC评估
python -m strategy_library.evaluation.ic_analyzer \
  --start 2026-06-01 --end 2026-06-30 --forward 1

# Step 4: 检查IC结果
# 理想：|IC| > 0.02, ICIR > 0.5, 分层单调
```

---

## 综合评分信号（Signal Enhancer）

基于新因子改造现有买卖逻辑：

### 买入评分制

```
base_score (max=10): GS信号3 + 主力线上穿3 + 主力持仓2 + 暗盘流入2
market_verify (max=10): 涨停封板3 + 龙虎榜净买3 + 热榜排名2 + 板块共振2
总分 ≥ 10 买入，≥ 15 满仓
```

### 卖出三级检查

| 级别 | 条件 | 动作 |
|:----:|------|:----:|
| 🔴 强制 | -8%止损 / 主力3连降 / 连板断板 / 龙虎榜净卖>买入50% | 立即卖出 |
| 🟡 建议 | 峰值回调5% / 热榜3日降 / 打压异动 / 主力线缩小 | 累计2项卖出 |
| 🟢 减半 | GS转空 / 暗盘转流出 / 游资对倒 | 减半仓 |

### 动态仓位

```
连板情绪 = (连板数2板以上股票数) / (总涨停数)
if 连板情绪 > 30% : 满仓3只
if 连板情绪 < 10% : 最多1只
```

---

## 实施步骤

```
Day 1:   创建5张新表 + import_financial_api.py 采集脚本 + 注册cron
Day 2:   跑一次全量回填（拉历史数据入新表）
Day 3:   修改 daily_factors 表结构（ALTER TABLE 追加新列）
Day 4:   实现5类因子计算 + IC验证
Day 5:   实现 signal_enhancer.py 综合评分
Day 6:   回测验证增强效果（对比新旧信号）
```
