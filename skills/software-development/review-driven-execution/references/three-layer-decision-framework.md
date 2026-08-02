# 三层决策框架 — 系统概览

## 架构

```
L1: 大盘温度评估（择时）
  ├─ 指数趋势 35% (5指数×MA排列/位置/MACD)
  ├─ 资金面 35% (主力+北向+两融) 
  └─ 情绪 30% (涨跌比+涨停数+连板+量能)
  → 输出: 仓位比例 0~1

L2: 板块轮动（选赛道）
  ├─ 资金连续流入天数 30%
  ├─ 资金趋势斜率 15%
  ├─ 板块涨幅 15%
  ├─ 均线多头占比 25%
  └─ 龙头强度 15%
  → 输出: Top20热门板块 + 龙头股

L3: 估值门控 + 决策融合（选个股+执行）
  ├─ PE-Band通道位置 (0~100刻度！！不是0~1)
  ├─ safety_margin (百分比 -87 = -87%)
  └─ 行业差异化估值
  → 输出: 买入/卖出/观察信号 → decision_log
```

## 数据管道时间线

```
18:00  前复权日线 + 指数日线
18:30  大盘资金流 + 北向资金 (daily_market_moneyflow.py)
18:45  板块资金流 (daily_sector_moneyflow.py)
19:00  大盘温度 L1     (engines/market_temperature.py)
20:00  板块轮动 L2     (engines/sector_rotation.py)
20:30  决策融合 L3     (engines/decision_fusion.py)
```

## 引擎文件

| 层 | 引擎 | 关键方法 | 实测性能 |
|:--|:-----|:---------|:--------:|
| L1 | `engines/market_temperature.py` | `calc_index_trend()`, `calc_capital_flow()`, `calc_sentiment()`, `run()` | ~16ms/run |
| L2 | `engines/sector_rotation.py` | `calc_sector_heat()`, `identify_leaders()`, `run()` | ~0.91s/run, 81天回填=74s |
| L3 | `engines/decision_fusion.py` | `check_valuation()`, `run()` | ~18.5ms/run |
| 数据 | `scripts/daily_market_moneyflow.py` | 大盘资金流+北向资金采集 | cron 18:30 |

## 估值门控阈值

**关键量纲注意：** `valuation_results.channel_position` 是 **0~100** 刻度，不是0~1！

| 信号 | 条件 | 置信度 |
|:-----|------|:------:|
| buy | pos ≤ 35 AND margin ≥ -20% | 80 |
| buy (第二层) | pos ≤ 52.5 AND margin ≥ -20% | 50 |
| sell | pos ≥ 85 OR margin < -50 | 80 |
| sell (预警) | pos ≥ 68 | 50 |
| hold | 其他 | 50 |
| unknown | 无估值数据 | 0 (→watch) |

## 仓位映射

```
仓位% = position_ratio × 100
最大标的数 = max(1, int(仓位% / 10))
仓位 ≤ 5% → 空仓，不生成买入信号
温度 < 25  → 冰点行情，不生成买入信号
```

## 已知数据陷阱

| 陷阱 | 症状 | 修复 |
|:-----|:-----|:-----|
| `channel_position` 是0~100 | 买入门控按0~1检查→永远不触发 | 阈值设为35/85 |
| `hsgt_moneyflow` 日期格式混存 | 新数据`20260710`(YYYYMMDD) vs 旧数据`2026-07-10`(YYYY-MM-DD) | 引擎查数据时同时试两种格式 |
| `limit_up_pool` 只有涨停股 | 跌停统计永远为0 | 从`daily_kline`按`pct_change < -9.0`估算 |
| `market_moneyflow.trade_date` | 格式为YYYYMMDD无横线 | 查询时用`date_stripped`变量 |
| `daily_kline.date` 列名 | 不是`trade_date` | 查询时用`date`列 |
| `limit_up_ladder.board_nums` 列名 | 不是`board_count` | 查询时用`board_nums`列 |
| `valuation_results` 89%数据缺失 | channel_position为None | 保守按hold处理，不买入不卖出 |
| `north_total` 单位万元 | 北向评分按亿元阈值→永远评错 | 评分时`/10000`转换为亿元 |

## 支持工具

- `scripts/kanban_await.py` — Kanban 卡自动轮询推送（`hermes kanban show --json` 结构化API）
- `scripts/db_utils.py` — PRAGMA 统一连接管理 + stock_code 标准化
