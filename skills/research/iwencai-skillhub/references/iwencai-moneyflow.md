# 问财资金流向 API 字段与调用策略

## 字段映射

问财 `hithink-market-query` 返回字段带 `[YYYYMMDD]` 日期后缀，需正则 `(.+)\[(\d{8})\]$` 解析。

### 成交量（股）
| 问财字段 | DB 列 | 说明 |
|----------|-------|------|
| `特大单买入量[YYYYMMDD]` | `elg_buy_vol` | 超大单买入量 |
| `特大单卖出量[YYYYMMDD]` | `elg_sell_vol` | 超大单卖出量 |
| `大单买入量[YYYYMMDD]` | `lg_buy_vol` | 大单买入量 |
| `大单卖出量[YYYYMMDD]` | `lg_sell_vol` | 大单卖出量 |
| `中单买入量[YYYYMMDD]` | `md_buy_vol` | 中单买入量 |
| `中单卖出量[YYYYMMDD]` | `md_sell_vol` | 中单卖出量 |
| `小单买入量[YYYYMMDD]` | `sm_buy_vol` | 小单买入量 |
| `小单卖出量[YYYYMMDD]` | `sm_sell_vol` | 小单卖出量 |

### 成交额（元）
| 问财字段 | DB 列 | 说明 |
|----------|-------|------|
| `特大单买入额[YYYYMMDD]` | `elg_buy_amt` | 超大单买入额 |
| `特大单卖出额[YYYYMMDD]` | `elg_sell_amt` | 超大单卖出额 |
| `大单买入额[YYYYMMDD]` | `lg_buy_amt` | 大单买入额 |
| `大单卖出额[YYYYMMDD]` | `lg_sell_amt` | 大单卖出额 |
| `中单买入额[YYYYMMDD]` | `md_buy_amt` | 中单买入额 |
| `中单卖出额[YYYYMMDD]` | `md_sell_amt` | 中单卖出额 |
| `小单买入额[YYYYMMDD]` | `sm_buy_amt` | 小单买入额 |
| `小单卖出额[YYYYMMDD]` | `sm_sell_amt` | 小单卖出额 |
| `主力资金流向[YYYYMMDD]` | `main_net_amt` | 主力净流入额 |

### 派生字段
- `elg_net_amt = elg_buy_amt - elg_sell_amt`（超大单净额）
- `lg_net_amt = lg_buy_amt - lg_sell_amt`（大单净额）
- `md_net_amt = md_buy_amt - md_sell_amt`（中单净额）
- `sm_net_amt = sm_buy_amt - sm_sell_amt`（小单净额）
- `net_mf_amt = Σ all_net_amt`（总净流入额）
- `net_mf_vol = Σ all_net_vol`（总净流入量）

## 查询模板

```python
MONEYFLOW_QUERY = (
    "{codes} 特大单买入量[{d}] 特大单卖出量[{d}] "
    "大单买入量[{d}] 大单卖出量[{d}] "
    "中单买入量[{d}] 中单卖出量[{d}] "
    "小单买入量[{d}] 小单卖出量[{d}] "
    "特大单买入额[{d}] 特大单卖出额[{d}] "
    "大单买入额[{d}] 大单卖出额[{d}] "
    "中单买入额[{d}] 中单卖出额[{d}] "
    "小单买入额[{d}] 小单卖出额[{d}] "
    "主力资金流向[{d}]"
)
```

## 频率策略

### 单 Key
| 参数 | 值 | 说明 |
|------|-----|------|
| batch_size | 12 | 每批最多 12 只股票 |
| sleep | 0.3s | 批间间隔 |
| 日请求量 | ~13 次 | 148 只/12=13 批 |

### 双 Key 交替
```python
keys = [key_a, key_b]
key_idx = 0
for batch in batches:
    key = keys[key_idx % 2]  # 交替使用
    key_idx += 1
```

双 Key 每 Key 日请求量减半（~6.5 次），14 天完成 ~19,500 次总请求的历史回补。

### 回补策略
- 每次运行 100 个交易日（`BACKFILL_DAYS_PER_RUN`）
- 凌晨 04:00 cron 触发
- 断点续跑：查询 `MAX(date) FROM moneyflow_daily WHERE data_source='iwencai'` 确定起点
- 失败日期写入 `~/.logs/moneyflow_failed_dates.txt` 标记

### 增量策略
- 工作日 18:30 cron 触发
- 前查 7 天覆盖长假（`INCREMENTAL_LOOKBACK=7`）
- 跳过已有 ≥90% 覆盖的日期

## Init 代码块（技能头）

```yaml
  - skill: hithink-market-query
    headers:
      X-Claw-Skill-Id: hithink-market-query
      X-Claw-Skill-Version: "1.0.0"
    endpoint: https://openapi.iwencai.com/v1/query2data
```
