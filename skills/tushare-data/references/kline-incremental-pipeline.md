# Tushare 日线（前复权）增量数据管道参考

## 接口特征

| 维度 | 值 |
|------|-----|
| **接口名** | `pro.daily()` |
| **最低积分** | 120（基座权限） |
| **数据范围** | 全 A 股全历史（90 年代~至今） |
| **每日更新** | 交易日 17:00~18:00 完成入库 |
| **单次调用覆盖** | **全市场 5500+ 只股票** ← 关键特征 |
| **分钟限频** | 500 次/分钟（5000 积分） |
| **前复权参数** | `adj='qfq'` |
| **补权因子** | `pro.adj_factor()` 返回逐日复权因子 |

## 核心模式：按交易日拉全市场

与"按股票代码分片"的常规思路不同，`pro.daily()` **按 `trade_date` 一次返回全市场**：

```python
pro = ts.pro_api()
# 单次调用 = 全市场某一天所有股票
df = pro.daily(trade_date='20260626')
# → 5513 行，列：ts_code, trade_date, open, high, low, close,
#   pre_close, change, pct_chg, vol, amount
```

这意味着增量更新只需**1 次 API 调用/交易日**，远低于 500 次/分钟的限频。

## 字段映射（→ daily_kline 表）

| 目标 DB 字段 | Tushare 字段 | 转换 | 单位 |
|------------|-------------|------|------|
| `stock_code` | `ts_code` | 去掉 `.SZ/.SH` 后缀 | — |
| `date` | `trade_date` | `YYYYMMDD` → `YYYY-MM-DD` | — |
| `open` / `high` / `low` / `close` | 同名 | 直接映射 | 元（前复权） |
| `volume` | `vol` | 直接映射 | **手**（×100 股） |
| `amount` | `amount` | 直接映射 | **元** |
| `change` | `change` | 直接映射 | 元 |
| `pct_change` | `pct_chg` | 直接映射（字段名不同） | % |
| `amplitude` | **无** | 计算：`(high-low)/pre_close*100` | % |
| `turnover` | **不在 daily 中** | 需另调 `daily_basic(trade_date=xxx)` 的 `turnover_rate` | % |

### ⚠️ 关键陷阱

1. **`amplitude`（振幅）Tushare 不提供**，必须计算。需要 `pre_close` 字段。
2. **`turnover`（换手率）不在 `pro.daily()` 返回中**，需单独调用 `pro.daily_basic(trade_date=xxx)` — 这也是一次全市场调用，约额外 1 次 API。
3. **`pct_chg` 是 Tushare 字段名**，不是 `pct_change`。映射时注意。
4. **`vol` 单位是手（1手=100股）**，不是股。如果要存股，需 `vol * 100`。
5. **`amount` 单位是元**，不是万元。直接存。
6. **`adj='qfq'` 是前复权**。Tushare 的不复权版本使用原始价格，复权后价格会因分红送股调整。增量脚本前复权和原始数据口径必须一致。

## 振幅计算公式确认

```python
amplitude = (high - low) / pre_close * 100
```

实测验证（000001.SZ 2026-06-26）：
- high=10.47, low=10.19, pre_close=10.42
- amplitude = (10.47-10.19)/10.42 × 100 ≈ **2.69%** ✅ 与同花顺/东财一致

多只股票交叉验证通过。

## API 重试策略（应对瞬时故障）

分批拉取时，单次 API 失败不应跳过整批。推荐 3 次重试 + 指数退避：

```python
max_retries = 3
for attempt in range(1, max_retries + 1):
    try:
        df = pro.daily(ts_code=ts_codes, start_date=trade_date, end_date=trade_date, adj='qfq')
        time.sleep(API_SLEEP)
        return df
    except Exception as e:
        delay = {1: API_SLEEP, 2: 3.0, 3: 9.0}.get(attempt, 9.0)
        if attempt < max_retries:
            log(f"API调用失败(第{attempt}次)，{delay}s后重试: {e}", "WARN")
            time.sleep(delay)
        else:
            log_error(f"API调用失败(3次重试均失败，已跳过该批): {e}")
            time.sleep(API_SLEEP)
            return None  # 跳过该批，不中断全流程
```

- 第1次：常规 `API_SLEEP`（1.2s）
- 第2次：3s
- 第3次：9s
- 3次全失败 → 跳过该批并打 ERROR 日志，**不中断**后续批次

此模式适用于 `daily()`、`daily_basic()` 等所有按批调用的 Tushare 接口。

## stock_code 过滤规则

`pro.daily(adj='qfq')` 可能返回非标准代码（指数、债转等）。写入 `daily_kline` 前应过滤只保留标准 A 股：

```python
STOCK_CODE_PATTERN = re.compile(r'^[03684]\d{5}$')
```

匹配的代码范围（与前述「快速判断代码类型」表一致）：

| 前缀 | 含义 | 
|------|------|
| `0xxxxx` | 深市主板/中小板 |
| `3xxxxx` | 深市创业板 |
| `6xxxxx` | 沪市主板/科创板 |
| `8xxxxx` | 北交所 |
| `4xxxxx` | 三板 |

同时作为 `has_data_for_date()` 的检查条件，确保计数时只计入标准 A 股。

## 换手率获取优化

`turnover`（换手率）不在 `pro.daily()` 返回中，需另调 `pro.daily_basic(trade_date=xxx)`。

**重要优化：`daily_basic` 也支持全市场单次调用**，不要按 50 只一批循环调用它。应在数据主循环外调用一次：

```python
# ✅ 正确：一次调用获取全市场换手率
turnover_map = {}
df_basic = pro.daily_basic(trade_date=trade_date)
for _, row in df_basic.iterrows():
    bare = row['ts_code'].split('.')[0]
    turnover_map[bare] = row.get('turnover_rate')

# 然后在每批处理中直接按股票代码查询
turn = turnover_map.get(bare_code)
```

这样做相当于：
- 按批次循环 50 只/批 × 100 批 = 100 次 `daily_basic` API 调用 → **降为 1 次**
- 每次 `daily_basic(trade_date=xxx)` 返回全市场 ~5500 只股票的换手率
- 分钟限频 500 次，省下的额度给更关键的 `daily()` 调用

## 停牌处理

**Tushare 自动过滤停牌股。** 某天无交易的股票不会出现在 `pro.daily(trade_date=xxx)` 的返回中。DB 中原有的旧数据保持不动。**不需要特殊处理。**

## 日期归一化（重要）

Coze 系统导出的日线经常出现**日期格式混用**：

| 格式 | 示例 | 长度 |
|------|------|------|
| `YYYY-MM-DD`（ISO） | `2026-06-30` | 10 |
| `YYYYMMDD`（紧凑） | `20260626` | 8 |

写入 DB 前必须统一。建议统一为 `YYYY-MM-DD`，与 SQLite 日期函数兼容性好。

```python
def normalize_date(d: str) -> str:
    d = d.strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d
```

## 股票代码映射问题

### 场景：数据库使用 bare code（如 `000001`），Tushare 返回 ts_code（如 `000001.SZ`）

建立一次性映射表：

```python
df = pro.stock_basic(list_status='L', fields='ts_code,symbol')
# symbol='000001' → ts_code='000001.SZ'
mapping = dict(zip(df['symbol'], df['ts_code']))
reverse_map = dict(zip(df['ts_code'], df['symbol']))

# 写入时：去掉后缀
stock_code = ts_code.split('.')[0]  # '000001.SZ' → '000001'
```

### 场景：数据库使用 InnerCode（Coze 内部编码，如 `10000`、`101150`）

约 59% 的 Coze 旧数据使用非标准内部码。这些代码**无法直接对应 Tushare 股票**。方案：

1. **短期**：新增量脚本只维护标准 A 股代码（`000xxx`、`300xxx`、`600xxx`、`688xxx`、`8xxxxx`）
2. **中期**：找到 InnerCode→symbol 映射表后，做全量重跑
3. **长期**：Tushare 全量初始化一次 `pro.daily(adj='qfq')` 重新建表

### 快速判断代码类型

| 前缀 | 含义 | 能否用 Tushare 增量 |
|------|------|-------------------|
| `000`、`001`、`002` | 深市主板/中小板 | ✅ |
| `300`、`301` | 深市创业板 | ✅ |
| `600`、`601`、`603`、`605` | 沪市主板 | ✅ |
| `688`、`689` | 沪市科创板 | ✅ |
| `8xxxxx` | 北交所 | ✅ |
| `4xxxxx` | 三板 | ❌ Tushare 不覆盖 |
| `10xxxx`、`1xxxx`、`1xxx` | Coze InnerCode | ❌ 需映射表 |
| `1Axxxx`、`1Bxxxx`、`1Cxxxx` | 指数代码 | ❌ 另用 `index_daily` |

## 增量更新完整流程

### 伪代码

```python
def incremental_kline_update():
    pro = ts.pro_api()
    
    # 1. 确定最新交易日
    today = datetime.now().strftime('%Y%m%d')
    cal = pro.trade_cal(exchange='SSE', 
                        start_date='yesterday-30d', 
                        end_date=today)
    last_trade = cal[cal['is_open']==1].iloc[-1]['cal_date']
    
    # 2. 跳过已覆盖（把 DB 中的两种日期格式都检查）
    exist_cnt = check_db_has_date(last_trade)  # 检查 YYYYMMDD 和 YYYY-MM-DD
    if exist_cnt > SOME_THRESHOLD:  # 比如 > 500 表示已有
        log('数据已存在，跳过')
        return
    
    # 3. 拉取
    df = pro.daily(trade_date=last_trade, adj='qfq')
    # df 约 5500 行
    
    # 4. 转换
    rows = []
    for _, row in df.iterrows():
        stock_code = row['ts_code'].split('.')[0]
        date = normalize_date(row['trade_date'])
        amplitude = (row['high'] - row['low']) / row['pre_close'] * 100
        
        rows.append((
            stock_code, date,
            row['open'], row['high'], row['low'], row['close'],
            row['vol'], row['amount'],
            amplitude, row['pct_chg'], row['change'], None  # turnover None
        ))
    
    # 5. 批量写入
    INSERT OR REPLACE INTO daily_kline
    (stock_code, date, open, high, low, close, volume, amount,
     amplitude, pct_change, change, turnover)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    
    # 6. 验证
    check_count = count_by_date(last_trade)
    log(f'导入完成：{check_count} 行')
```

### Hermes Cron 配置

```bash
# Tushare 日线通常在 17:00~18:00 更新完毕
# 避免与资金流向 cron 同时跑（18:45），错开 30 分钟
hermes cron create \
  --name "日线-Tushare-前复权增量" \
  --schedule "30 18 * * 1-5" \
  --script qfq_tushare_incremental.py \
  --no-agent \
  --deliver local
```

## 完整性验证

每日执行后应检查：

```sql
-- 行数是否在合理范围（全市场 ~5500）
SELECT COUNT(*) FROM daily_kline WHERE date = '2026-07-01';

-- 无异常 NULL
SELECT COUNT(*) FROM daily_kline 
WHERE date = '2026-07-01' AND (open IS NULL OR close IS NULL);

-- 抽样对比 Tushare 原始值
SELECT stock_code, close, volume 
FROM daily_kline 
WHERE date = '2026-07-01' AND stock_code = '000001';
```

## 与 Coze 旧管道的替换

旧系统（Coze→信号文件→CSV.GZ→导入）可安全替换：

1. `crontab -e` 禁用旧 cron（注释或删除 `qfq_import.sh` 行）
2. 旧脚本和旧数据不动，仅停调度
3. 新 cron 从 Tushare 直拉

**旧数据中的 NULL 字段补齐**：可在 Tushare 全量重跑时统一补齐，无需逐日修复。
