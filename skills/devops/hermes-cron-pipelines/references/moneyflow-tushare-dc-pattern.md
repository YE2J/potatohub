# Tushare moneyflow_dc 增量管线参考

## 场景

从 Tushare `moneyflow_dc` 接口（东方财富数据源）增量拉取 A 股资金流向数据，写入 `moneyflow_daily` 表。替代同花顺问财/东财 API 作为每日增量来源。

## 数据源对比

| 维度 | Tushare moneyflow_dc | 东财 push2his (旧) | 问财 OpenAPI (旧) |
|------|---------------------|-------------------|-------------------|
| 数据起始 | 2023-09-11 | ~2020 | 取决于 Key 权限 |
| 覆盖股票 | A 股全量 (~5,970只) | 全量 | 全量 |
| 更新窗口 | 盘后 ~17:00-18:00 | 盘后 | 盘后 |
| 返回字段 | **净额** 金额+比例+涨跌幅(无成交量、无买卖分离) | 净额(无成交量) | 量+额(全) |
| 调用方式 | 全市场 1 次 API 调用 | 按股票分批 | 分批查询 |
| 单位 | **万元** (需 ×10000 转元) | 万元(需 ×10000) | 万元(需 ×10000) |
| 积分门槛 | 5000分（500元/年） | — | — |

## Tushare moneyflow_dc 接口说明

### 返回字段

```
trade_date        — 交易日期 (YYYYMMDD)
ts_code           — 股票代码 (如 000001.SZ)
name              — 股票名称
pct_change        — 涨跌幅 (%)
close             — 收盘价
net_amount        — 主力净流入额 (万元)   ← 净额！正=净流入，负=净流出
net_amount_rate   — 主力净流入率 (%)
buy_elg_amount    — 超大单净流入额 (万元)  ← 净额！不是买入额！
buy_elg_amount_rate — 超大单净流入占比 (%)
buy_lg_amount     — 大单净流入额 (万元)   ← 净额！
buy_lg_amount_rate  — 大单净流入占比 (%)
buy_md_amount     — 中单净流入额 (万元)   ← 净额！
buy_md_amount_rate  — 中单净流入占比 (%)
buy_sm_amount     — 小单净流入额 (万元)   ← 净额！
buy_sm_amount_rate  — 小单净流入占比 (%)
```

### ⚠️ 关键陷阱：字段名含义与直觉相反

**`buy_elg_amount` 虽然叫 `buy_`，但它是净额不是买入额！**

- ✅ 正数 = 净流入（买入 > 卖出）
- ✅ 负数 = 净流出（卖出 > 买入）

因为 `net_amount = buy_elg_amount + buy_lg_amount`（主力 = 超大单 + 大单），所以这些 `buy_*` 字段实质上是**各档位的净额**。

**错误的映射（会导致计算完全错误）：**
```
buy_elg_amount → elg_buy_amt    ❌ 下游会把净额当买入额算
buy_lg_amount  → lg_buy_amt     ❌
```

**正确的字段映射（映射到 `*_net_amt` 列，不是 `*_buy_amt`）：**

| SQLite 列 | moneyflow_dc 字段 | 单位转换 | 说明 |
|-----------|-----------------|---------|------|
| `stock_code` | `ts_code` | 去掉 .SH/.SZ 后缀 | |
| `date` | `trade_date` | 转 ISO 格式 YYYY-MM-DD | |
| `main_net_amt` | `net_amount` | ×10000 (万元→元) | 主力净额 |
| `net_mf_amt` | `net_amount` | ×10000 | 总净流入（= 主力净额） |
| `elg_net_amt` | `buy_elg_amount` | ×10000 | 超大单净额 |
| `lg_net_amt` | `buy_lg_amount` | ×10000 | 大单净额 |
| `md_net_amt` | `buy_md_amount` | ×10000 | 中单净额 |
| `sm_net_amt` | `buy_sm_amount` | ×10000 | 小单净额 |
| `data_source` | `'tushare_dc'` | 硬编码 | |

**所有 `*_buy_amt` / `*_sell_amt` / `*_vol` 列留 NULL**——这个数据源只提供净额，没有买卖分离量和成交量。

### 同花顺 ths 数据与 Tushare DC 的口径差异

同一只股票同一日，不同数据商的结果可能差异巨大：

| 数据源 | 华工科技 2026-06-30 主力净额 |
|--------|------------------------|
| 同花顺 ths_snapshot | +11.5亿（净流入） |
| Tushare moneyflow_dc (东方财富) | -3.7亿（净流出） |

**这不是 bug，是正常差异。** 不同数据商的大单/小单划分阈值不同。下游查询应隔离 data_source，不要跨源聚合。

### 数据缺失

moneyflow_dc 的定位是**资金流向快照**而非完整成交明细。缺失：
- ❌ 各档位买入/卖出量的分离值（只有净额）
- ❌ 各档位的成交量（手）
- ❌ 买卖方向拆解

## 架构：Hermes cron no_agent + 单次全量拉取

### 关键差异：MCP vs Python SDK

| 方式 | 调用 | 适用场景 |
|------|------|---------|
| MCP tool (`mcp_tushareMcp_moneyflow_dc`) | Hermes 对话中直接调用 | 即席查询、对话快查 |
| Python SDK (`pro.moneyflow_dc()`) | Cron 脚本中调用 | **每日增量（推荐）** |

**实测：全市场 5,970 只股票一次 API 调用即可返回**（5 秒内完成），不需要逐股分批拉取。

### 调度模式

```bash
# Hermes cron 创建（no_agent 模式，脚本本身就是 job）
hermes cron create "45 18 * * 1-5" \
  --name "资金流向-Tushare-DC增量" \
  --script daily_moneyflow_tushare_dc.sh \
  --no-agent \
  --deliver local
```

- `no_agent: true` → 直接运行脚本，不启动 LLM（省 token、速度快）
- `deliver: local` → 数据管道类作业只存本地，不推送
- 工作日 18:45 运行（Tushare 数据 ~17:00 更新完毕，留 1h45min 缓冲）
- 脚本内部前先检查数据库当天是否已有数据，避免重跑

### 脚本逻辑

```
[预检] 检查 TUSHARE_TOKEN 环境变量
[交易日] 调用 pro.trade_cal() 获取最新交易日
[防重]   SQLite 查询：当天 tushare_dc 行数 ≥ 100 则 exit 0
[拉取]   1 次 API 调用 pro.moneyflow_dc(trade_date=YYYYMMDD) → 全市场 5,970 只
[映射]   buy_*_amount → *_net_amt（注意：净额不是买入额！）×10000 转元
[写入]   INSERT OR REPLACE 到 moneyflow_daily (data_source='tushare_dc')
[验证]   查询写入行数确认完整
```

### Token 配置

Token 存储在 `~/.hermes/.env.tushare`（**不在** `~/.hermes/.env` 中，避免被 Tirith 凭证扫描器擦除）：

```bash
# ~/.hermes/.env.tushare
TUSHARE_TOKEN="your_token"
chmod 600 ~/.hermes/.env.tushare

# ~/.zshrc 添加
export TUSHARE_TOKEN="your_token"
```

Python 脚本加载顺序：环境变量 → `.env.tushare` 文件 → 报错退出。

### 推荐 Python 环境

```
~/.pyenv/versions/3.11.11/bin/python3
pip install tushare
```

## 多数据源过渡策略

### PK 约束：需停旧再启新

`moneyflow_daily` 表 `PRIMARY KEY (stock_code, date)` — **不包含 `data_source`**。

因此执行 `INSERT OR REPLACE` 时，不同 `data_source` 的行会**互相覆盖**同一 (stock_code, date) 的记录。

**正确的过渡步骤：**

```
Step 1: 注释掉旧来源的 crontab 条目 (如 iwencai 的 18:30)
Step 2: 等待一个交易日确认旧来源无新数据写入
Step 3: 创建新来源的 Hermes cron job
Step 4: 验证新数据写入成功（data_source='tushare_dc'）
Step 5: 旧脚本保留不动（仅禁用 crontab），留作回退
```

⚠️ **不要双轨并行** — 因为 PK 不含 data_source，双轨必然导致数据覆盖。

### 降级顺序

```
优先级 1: tushare_dc (日增量，东方财富口径，5,970只/天)
优先级 2: ths_snapshot (日快照净额，同花顺口径，5,185只/天)
优先级 3: ths (历史全量明细，14M行，有买卖分离，仅到2026-06-26)
优先级 4: iwencai (crontab 注释但脚本保留，已因IP限流失效)
```

## 相关文件

- `daily_moneyflow_tushare_dc.py` — 增量脚本 (data_source='tushare_dc')
- `daily_moneyflow_tushare_dc.sh` — cron wrapper
